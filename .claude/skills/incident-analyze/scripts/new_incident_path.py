#!/usr/bin/env python3
"""Compute the target path + filename for a new incident note.

Rules (from incident-analyze SKILL.md):
  - Directory: `14_Changes/incident/{YYYY}/{상반기|하반기}/`
  - Half-year: month 1-6 → 상반기, 7-12 → 하반기
  - Filename:  `통합학사시스템 오류 처리 {YYYY-MM-DD}_{seq}.md`
  - Seq: 1-based, incremented across existing files for the same date
         (scanned anywhere under `14_Changes/incident/{YYYY}/`)

Usage:
    python new_incident_path.py <YYYY-MM-DD> [--vault /path/to/vault]

Output: absolute path of the new note on stdout. Does NOT create the file.
"""
from __future__ import annotations

import argparse
import re
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


def next_seq(year_dir: Path, iso_date: str) -> int:
    """Find max existing sequence for `iso_date` under year_dir, return max+1.

    Uses a broad `*.md` glob and filters in Python — `pathlib.rglob` with
    non-ASCII literal prefixes has returned zero matches on macOS in practice.
    """
    if not year_dir.exists():
        return 1
    prefix = _nfc(f"통합학사시스템 오류 처리 {iso_date}_")
    seq_re = re.compile(r"_(\d+)\.md$")
    max_seq = 0
    for p in year_dir.rglob("*.md"):
        # macOS stores filenames in NFD; normalize before comparing.
        name = _nfc(p.name)
        if not name.startswith(prefix):
            continue
        m = seq_re.search(name)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def compute_path(vault: Path, occurred: date) -> Path:
    iso = occurred.isoformat()
    year_dir = vault / "14_Changes" / "incident" / str(occurred.year)
    half = half_year(occurred.month)
    folder = year_dir / half
    seq = next_seq(year_dir, iso)
    return folder / f"통합학사시스템 오류 처리 {iso}_{seq}.md"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("date", help="incident date, YYYY-MM-DD")
    p.add_argument("--vault", default=".",
                   help="vault root (default: cwd)")
    args = p.parse_args()

    try:
        occurred = date.fromisoformat(args.date)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    vault = Path(args.vault).resolve()
    print(compute_path(vault, occurred))
    return 0


if __name__ == "__main__":
    sys.exit(main())
