#!/usr/bin/env python3
"""Compute the target path for a new improvement note.

Rules (from improvement-plan WORKFLOW.md):
  - Directory: `14_Changes/improvement/{YYYY}/{상반기|하반기}/`
  - Half-year: month 1-6 → 상반기, 7-12 → 하반기
  - Filename:  `{제목}.md`, free-form Korean title
  - Dup rule:  if `{제목}.md` already exists (anywhere under the year dir),
               append `_2`, `_3`, ... until unique

Usage:
    python3 new_improvement_path.py "수강신청 로그 개선" \\
        [--date YYYY-MM-DD] [--vault /path/to/vault]

Output: absolute path of the new note on stdout. Does NOT create the file.
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from datetime import date
from pathlib import Path


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def half_year(month: int) -> str:
    if not 1 <= month <= 12:
        raise ValueError(f"invalid month: {month}")
    return "상반기" if month <= 6 else "하반기"


def compute_path(vault: Path, title: str, on: date) -> Path:
    year_dir = vault / "14_Changes" / "improvement" / str(on.year)
    folder = year_dir / half_year(on.month)

    # Dup check spans the whole year (cross-half-boundary safety).
    # macOS stores names in NFD — normalize both sides before comparing.
    existing: set[str] = (
        {_nfc(p.name) for p in year_dir.rglob("*.md")}
        if year_dir.exists() else set()
    )

    def first_free(base: str) -> str:
        candidate = _nfc(f"{base}.md")
        if candidate not in existing:
            return candidate
        n = 2
        while _nfc(f"{base}_{n}.md") in existing:
            n += 1
        return _nfc(f"{base}_{n}.md")

    return folder / first_free(title)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("title", help="improvement note title (no .md suffix)")
    p.add_argument("--date", default=None,
                   help="reference date for half-year (default: today)")
    p.add_argument("--vault", default=".",
                   help="vault root (default: cwd)")
    args = p.parse_args()

    on = date.fromisoformat(args.date) if args.date else date.today()
    vault = Path(args.vault).resolve()

    if not args.title.strip():
        print("error: title is empty", file=sys.stderr)
        return 2
    if "/" in args.title:
        print("error: title must not contain '/'", file=sys.stderr)
        return 2

    print(compute_path(vault, args.title.strip(), on))
    return 0


if __name__ == "__main__":
    sys.exit(main())
