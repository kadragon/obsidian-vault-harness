#!/usr/bin/env python3
"""OCR an image-based PDF to plain text using PyMuPDF + Tesseract.

For PDFs whose pages are scanned images (little or no embedded text layer),
`Read` / `pdftotext` return almost nothing. This script renders each page and
runs Tesseract OCR (kor+eng) via PyMuPDF's get_textpage_ocr.

Requirements (already provisioned on this machine):
    - PyMuPDF (import fitz)
    - Tesseract installed; kor+eng traineddata under TESSDATA_PREFIX
      (default fallback: ~/tessdata, and Tesseract on PATH)

Usage:
    python3 ocr_pdf.py <source.pdf> [--pages 1-5] [--lang kor+eng] [--dpi 200]

Output:
    Prints OCR'd text to stdout. Page breaks marked with form-feed.
    Exits non-zero with an error message on failure.

Note: OCR is slow (seconds per page). Use --pages to sample large files first.
"""
import argparse
import os
import sys
from pathlib import Path


def _ensure_tess_env() -> None:
    """Point Tesseract at a writable tessdata dir and ensure it's on PATH."""
    if not os.environ.get("TESSDATA_PREFIX"):
        fallback = Path.home() / "tessdata"
        if fallback.is_dir():
            os.environ["TESSDATA_PREFIX"] = str(fallback)
    tess_dir = r"C:\Program Files\Tesseract-OCR"
    if os.path.isdir(tess_dir) and tess_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + tess_dir


def _parse_pages(spec: str, count: int) -> range:
    if not spec:
        return range(count)
    try:
        if "-" in spec:
            a, b = spec.split("-", 1)
            start = int(a) - 1 if a.strip() else 0
            end = int(b) if b.strip() else count
        else:
            start = int(spec) - 1
            end = start + 1
    except ValueError:
        raise ValueError(
            f"invalid page range {spec!r}: expected forms like '3', '1-5', '2-', '-4'"
        )
    start = max(0, start)
    end = min(count, end)
    if start >= end:
        raise ValueError(
            f"page range {spec!r} is empty or out of bounds for a {count}-page document"
        )
    return range(start, end)


def ocr(src: str, pages: str, lang: str, dpi: int) -> str:
    import fitz  # PyMuPDF

    _ensure_tess_env()
    with fitz.open(src) as doc:
        out = []
        for i in _parse_pages(pages, doc.page_count):
            page = doc[i]
            tp = page.get_textpage_ocr(language=lang, dpi=dpi, full=True)
            out.append(page.get_text(textpage=tp))
    return "\f".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="OCR an image-based PDF to text.")
    ap.add_argument("source", help="path to the PDF")
    ap.add_argument("--pages", default="", help="page range, e.g. 1-5 or 3 (1-based)")
    ap.add_argument("--lang", default="kor+eng", help="Tesseract languages")
    ap.add_argument("--dpi", type=int, default=300, help="render DPI for OCR")
    args = ap.parse_args()

    if not Path(args.source).is_file():
        print(f"ERROR: file not found: {args.source}", file=sys.stderr)
        return 1
    try:
        text = ocr(args.source, args.pages, args.lang, args.dpi)
    except ValueError as e:  # usage error (bad --pages), not an OCR failure
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 - surface any failure to caller
        print(f"ERROR: OCR failed: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
