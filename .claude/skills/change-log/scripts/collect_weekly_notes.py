#!/usr/bin/env python3
"""Collect notes from a target week for the weekly change-log report.

Scans:
  - 10_Areas/{INCLUDED_AREAS}/   — work notes (area notes)
  - 14_Changes/improvement/       — technical improvements
  - 14_Changes/incident/          — incidents

Criteria: notes whose `date created` frontmatter falls in the target week.

Output (stdout): JSON with week range and list of note metadata.

Usage:
    python collect_weekly_notes.py [--week YYYY-MM-DD] [--vault PATH]

    --week   Any date inside the desired week (Mon-Sun).
             Defaults to the previous full week relative to today.
    --vault  Vault root path. Defaults to cwd.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

# Windows Bash shells default to cp949; force UTF-8 for JSON output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
elif hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Folders inside 10_Areas/ to include (all others are excluded)
INCLUDED_AREAS = [
    "AI플랫폼",
    "강사료퇴직금",
    "개발공통",
    "교수업적",
    "교직",
    "등록",
    "수강신청",
    "수업성적",
    "시설물이용",
    "전임교원공채",
    "졸업",
]

# How area names map to the top-level output category
CATEGORY_MAP: dict[str, str] = {
    "수업성적": "학사",
    "수강신청": "학사",
    "졸업": "학사",
    "교직": "학사",
    "등록": "학사",
    "학적": "학사",
    "교수업적": "행정",
    "시설물이용": "행정",
    "전임교원공채": "행정",
    "강사료퇴직금": "행정",
    "교육연구학생지도": "행정",
    "AI플랫폼": "공통",
    "개발공통": "공통",
}

# Non-standard tag prefixes found in some 14_Changes notes → canonical area
TAG_ALIAS: dict[str, str | None] = {
    "교무": "수업성적",
    "수업": "수업성적",
    "성적": "수업성적",
    "수강": "수강신청",
    "교직이수": "교직",
    "시설": "시설물이용",
    "행정": None,  # Need second level — handled separately
}


def prev_week_range(ref: date | None = None) -> tuple[date, date]:
    """Return (monday, sunday) of the full week before the reference date's week."""
    if ref is None:
        ref = date.today()
    days_back = ref.weekday() + 7
    mon = ref - timedelta(days=days_back)
    return mon, mon + timedelta(days=6)


def parse_date_value(val: str) -> date | None:
    try:
        return date.fromisoformat(val.strip()[:10])
    except ValueError:
        return None


def read_frontmatter_date(text: str, key: str) -> date | None:
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return parse_date_value(m.group(1)) if m else None


def extract_title(text: str, fallback: Path) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return fallback.stem.lstrip("_")


def first_tag(text: str) -> str | None:
    m = re.search(r"#업무/[^\s#]+", text, re.MULTILINE)
    return m.group(0) if m else None


def infer_area_from_tag(text: str) -> str | None:
    """Extract the canonical area from the first #업무/ tag found in the note."""
    m = re.search(r"#업무/([^\s#/]+)(?:/([^\s#/]+))?", text)
    if not m:
        return None
    first = m.group(1)
    second = m.group(2)

    # Direct match to known areas
    if first in CATEGORY_MAP:
        return first

    # Alias map
    alias = TAG_ALIAS.get(first)
    if alias is not None:
        return alias

    # Special case: #업무/행정/{area}/... — use second segment
    if first == "행정" and second:
        # Normalize second segment (e.g., 교수업적평가 → 교수업적)
        for area in CATEGORY_MAP:
            if second.startswith(area):
                return area
        return second  # Return as-is even if not in map

    return first  # Fall through with raw value


def collect_10areas(vault: Path, start: date, end: date) -> list[dict]:
    results = []
    areas_root = vault / "10_Areas"
    for area in INCLUDED_AREAS:
        area_path = areas_root / area
        if not area_path.exists():
            continue
        for md in area_path.rglob("*.md"):
            text = md.read_text(encoding="utf-8", errors="ignore")
            if "date created:" not in text:
                continue  # Skip attachment files with no frontmatter
            dc = read_frontmatter_date(text, "date created")
            if dc and start <= dc <= end:
                results.append(
                    {
                        "path": str(md),
                        "area": area,
                        "category": CATEGORY_MAP.get(area, "기타"),
                        "source": "10_Areas",
                        "title": extract_title(text, md),
                        "date_created": dc.isoformat(),
                        "tag": first_tag(text),
                    }
                )
    return results


def collect_14changes(vault: Path, start: date, end: date) -> list[dict]:
    results = []
    changes_root = vault / "14_Changes"
    for sub in ("improvement", "incident"):
        sub_path = changes_root / sub
        if not sub_path.exists():
            continue
        for md in sub_path.rglob("*.md"):
            text = md.read_text(encoding="utf-8", errors="ignore")
            if "date created:" not in text:
                continue
            dc = read_frontmatter_date(text, "date created")
            if dc and start <= dc <= end:
                area = infer_area_from_tag(text)
                results.append(
                    {
                        "path": str(md),
                        "area": area or sub,
                        "category": CATEGORY_MAP.get(area or "", "기타"),
                        "source": f"14_Changes/{sub}",
                        "title": extract_title(text, md),
                        "date_created": dc.isoformat(),
                        "tag": first_tag(text),
                    }
                )
    return results


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--week",
        default=None,
        help="Any date in the target week (YYYY-MM-DD). Default: previous full week.",
    )
    p.add_argument("--vault", default=".", help="Vault root (default: cwd)")
    args = p.parse_args()

    ref = date.fromisoformat(args.week) if args.week else None
    start, end = prev_week_range(ref)
    vault = Path(args.vault).resolve()

    notes = collect_10areas(vault, start, end) + collect_14changes(vault, start, end)
    notes.sort(key=lambda n: (n["category"], n["area"], n["date_created"]))

    print(
        json.dumps(
            {
                "week_start": start.isoformat(),
                "week_end": end.isoformat(),
                "count": len(notes),
                "notes": notes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
