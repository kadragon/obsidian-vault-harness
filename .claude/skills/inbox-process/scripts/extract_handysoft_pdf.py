#!/usr/bin/env python3
"""Extract embedded PDF from Handysoft e-approval .pdf files.

Handysoft files use a proprietary wrapper format with `.pdf` extension.
A real PDF is embedded between `%PDF-` and `%%EOF` markers.

Usage:
    python3 extract_handysoft_pdf.py <source.pdf>

Output:
    Prints the extracted PDF path to stdout on success.
    Exits with non-zero status and error message on failure.
"""
import hashlib
import sys
from pathlib import Path


def out_path_for(data: bytes) -> Path:
    """Deterministic /tmp path for a source file's extracted PDF.

    Hashing the source bytes (not the slice) keeps concurrent workers from
    colliding while letting a repeat call reuse the same file.
    """
    file_hash = hashlib.md5(data[:1024]).hexdigest()[:8]
    return Path(f"/tmp/extracted_{file_hash}.pdf")


def unwrap(data: bytes) -> tuple[bytes, bool]:
    """Slice the embedded PDF out of a Handysoft wrapper.

    Returns (pdf_bytes, had_eof_marker). A plain PDF passes through unchanged
    (its `%PDF-` sits at offset 0), so callers need not pre-check the header.
    Raises ValueError when no `%PDF-` marker exists at all.
    """
    start = data.find(b"%PDF-")
    if start < 0:
        raise ValueError("No embedded PDF found (missing %PDF- marker)")

    end = data.rfind(b"%%EOF")
    return (data[start : end + 5] if end >= 0 else data[start:]), end >= 0


def extract(src: str) -> str:
    data = Path(src).read_bytes()
    out_path = out_path_for(data)
    pdf_data, had_eof = unwrap(data)
    out_path.write_bytes(pdf_data)

    suffix = "" if had_eof else " (no EOF marker)"
    print(f"{out_path} ({len(pdf_data)} bytes){suffix}")
    return str(out_path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: extract_handysoft_pdf.py <source.pdf>", file=sys.stderr)
        sys.exit(2)
    try:
        extract(sys.argv[1])
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
