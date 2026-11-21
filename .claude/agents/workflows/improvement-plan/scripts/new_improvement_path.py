#!/usr/bin/env python3
"""Compute the target path for a new improvement note (14_Changes/improvement/).

Naming rule lives in .claude/lib/change_naming.py:
  "{YYYY-MM-DD} {system} {screen_id} {summary}.md" — screen_id only when the note
  centers on one Nexacro screen; system in PATIS·sugang·webservice·uniweb·홈페이지·공통.
  Folder: {YYYY}/{상반기|하반기}/ by the date. Same name anywhere under 14_Changes -> " (2)", " (3)" ...
  Date = 작업 완료일. Summary says what changed.

Usage:
    python3 new_improvement_path.py --date YYYY-MM-DD --system PATIS \
        [--screen-id hl_3020701_u] --summary "요약 45자 이하" [--vault /path/to/vault]

Output: absolute path of the new note on stdout. Does NOT create the file.
Exit 2 on a rule violation (message on stderr).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
import change_naming  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", default=None, help="work completion date, YYYY-MM-DD (default: today)")
    p.add_argument("--system", required=True, help="·".join(change_naming.SYSTEMS))
    p.add_argument("--screen-id", default="", help="primary Nexacro screen, e.g. hl_3020701_u (optional)")
    p.add_argument("--summary", required=True, help="one-line Korean summary, <= 45 chars")
    p.add_argument("--vault", default=".", help="vault root (default: cwd)")
    a = p.parse_args()
    on = a.date or date.today().isoformat()
    try:
        print(change_naming.compute_path(Path(a.vault).resolve(), "improvement", on, a.system, a.screen_id, a.summary))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
