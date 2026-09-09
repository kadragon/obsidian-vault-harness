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
import os
import sys
import tempfile
from pathlib import Path


def _tmp_dir() -> Path:
    """Private 0700 scratch dir for extracted PDFs.

    The output name is a content hash, so it is predictable by design (callers
    cache on it). A predictable name in a shared directory is pre-emptable: a
    symlink planted at that path would redirect our write. Keep the names and
    put them inside a directory only this user can enter.
    """
    d = Path(tempfile.gettempdir()) / "vault-pdf"
    if d.is_symlink():
        raise RuntimeError(f"refusing to use symlinked scratch dir: {d}")
    d.mkdir(mode=0o700, exist_ok=True)
    return d


def write_private(path: Path, data: bytes) -> None:
    """Write 0600, never following a symlink at `path`.

    O_NOFOLLOW/O_BINARY are absent on some platforms; `getattr` keeps the call
    portable (Windows %TEMP% is already per-user).
    """
    flags = (os.O_WRONLY | os.O_CREAT | os.O_TRUNC
             | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def out_path_for(data: bytes) -> Path:
    """Deterministic, absolute temp path for a source file's extracted PDF.

    Hashes the WHOLE source, not a 1 KiB prefix: Handysoft wrapper headers are
    template-generated, so a prefix hash collides across unrelated documents
    (measured on 897 vault PDFs: 786 distinct 8-hex prefixes, one prefix
    covering 20 files of 14 different sizes). classify_pdf.py writes and
    returns this path per file, so a collision would hand the caller document
    B's text under document A's name, with no error.

    Built from `tempfile.gettempdir()` so the result is drive-qualified on
    Windows — a bare `/tmp/...` resolves to `\\tmp\\...`, which is correct only
    while the process CWD happens to sit on the same drive. See `_tmp_dir()`
    for why the predictable name is safe to keep.
    """
    file_hash = hashlib.md5(data).hexdigest()[:8]
    return _tmp_dir() / f"extracted_{file_hash}.pdf"


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
    write_private(out_path, pdf_data)

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
