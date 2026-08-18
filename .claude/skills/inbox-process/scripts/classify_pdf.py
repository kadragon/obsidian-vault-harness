#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pdf-inspector"]
# ///
"""Classify a PDF as text-based or scanned, so the caller picks the right reader.

Why this exists: the reading branch used to be a judgement call ("if Read
pulls almost no text, OCR it"). Measured on all 545 vault PDFs, this
classifier separates the two cases exactly — the 146 `scanned` files yield
0 chars/page under PyMuPDF, and no `text_based` file yields under 50. So the
branch is mechanical, and a scanned file no longer costs a wasted Read first.

Handysoft wrappers are unwrapped in memory before classification. When the
source is a wrapper, the embedded PDF is also written to the system temp dir
(same path convention as extract_handysoft_pdf.py) and reported as `read_path`
— an absolute, drive-qualified path — so one call covers both the unwrap and
the classify step.

Usage:
    uv run .claude/skills/inbox-process/scripts/classify_pdf.py <file.pdf> [more.pdf ...]

    `uv run` resolves pdf-inspector from the header above — nothing to install.
    Plain `python3` also works if the package is already present.

Output (JSON array on stdout, one object per input):
    path       source path as given
    handysoft  true when the source was a Handysoft wrapper
    read_path  path to read text from (extracted temp copy, or the source)
    type       text_based | scanned | mixed | image_based
    pages      page count
    ocr_pages  1-based page numbers needing OCR
    ocr_ranges ocr_pages compressed into ocr_pdf.py --pages arguments,
               one call per entry (e.g. ["3-5", "9"])
    action     read | ocr | read+ocr — the branch to take (see below)
    error      present instead of the above when the file could not be read

Follow `action`, not `type` — a `mixed` file may list no OCR pages at all,
so `type` alone does not determine the branch:
    read       PyMuPDF on read_path (the Read tool needs poppler, absent here)
    ocr        ocr_pdf.py read_path
    read+ocr   read normally, then ocr_pdf.py --pages once per ocr_ranges entry

Exit: 0 classified at least one file · 1 every input failed · 2 usage error.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_handysoft_pdf import out_path_for, unwrap  # noqa: E402


def to_ranges(pages: list) -> list:
    """Compress 1-based page numbers into ocr_pdf.py `--pages` arguments.

    OCR pages are often scattered (e.g. [1, 15, 25, 73]), and ocr_pdf.py takes
    only a single page or one contiguous range per call — so hand the caller
    ready-made arguments instead of leaving it to do the arithmetic.
    [3, 4, 5, 9] -> ["3-5", "9"]
    """
    out = []
    for page in pages:
        if out and page == out[-1][1] + 1:
            out[-1][1] = page
        else:
            out.append([page, page])
    return [str(a) if a == b else f"{a}-{b}" for a, b in out]


def classify(src: str) -> dict:
    import pdf_inspector

    rec: dict = {"path": src}
    raw = Path(src).read_bytes()
    rec["handysoft"] = not raw.startswith(b"%PDF-")

    data, _ = unwrap(raw)
    if rec["handysoft"]:
        out = out_path_for(raw)
        out.write_bytes(data)
        rec["read_path"] = str(out)
    else:
        rec["read_path"] = src

    result = pdf_inspector.classify_pdf_bytes(data)
    rec["type"] = str(result.pdf_type)
    rec["pages"] = result.page_count
    # pdf-inspector reports 0-indexed pages; ocr_pdf.py --pages is 1-based.
    ocr_pages = sorted(p + 1 for p in (result.pages_needing_ocr or []))
    rec["ocr_pages"] = ocr_pages
    rec["ocr_ranges"] = to_ranges(ocr_pages)

    # Decide the branch here rather than leaving the caller to re-derive it —
    # `type` alone is not enough, since a `mixed` file may list no OCR pages.
    if ocr_pages and len(ocr_pages) >= (result.page_count or 0):
        rec["action"] = "ocr"
    elif ocr_pages:
        rec["action"] = "read+ocr"
    else:
        rec["action"] = "read"
    return rec


def main() -> int:
    sources = sys.argv[1:]
    if not sources:
        print("Usage: classify_pdf.py <file.pdf> [more.pdf ...]", file=sys.stderr)
        return 2

    records = []
    for src in sources:
        try:
            records.append(classify(src))
        except Exception as e:  # noqa: BLE001 - report per file, never abort the batch
            records.append({"path": src, "error": f"{type(e).__name__}: {e}"})

    json.dump(records, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 1 if all("error" in r for r in records) else 0


if __name__ == "__main__":
    sys.exit(main())
