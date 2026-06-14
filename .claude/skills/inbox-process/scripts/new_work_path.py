#!/usr/bin/env python3
"""Compute folder + note paths for a new 10_Areas work-matter note.

Rules (from inbox-process SKILL.md):
  - Folder:  `10_Areas/{area}/{YYYYMM}_{sanitized_title}/`
  - Note:    `{folder}/_{YYYYMM}_{sanitized_title}.md`  (underscore prefix)
  - Sanitize: strip `/ \\ : * ? " < > |` from the title; keep spaces + emoji
  - Dup:     if folder already exists, append `_2`, `_3`, ... to the
             `{YYYYMM}_{title}` slug (both folder and note name)

Uses NFC normalization for filename comparisons (macOS HFS+ stores NFD).

Usage:
    python new_work_path.py <area> "<title>" [--yyyymm YYYYMM] \\
        [--vault /path/to/vault] [--doc-number "총무과-7453"] [--json]

Output (default, two lines):
    <folder_path>
    <note_path>

With --doc-number and --json, also includes `duplicate_candidates` list.
If duplicates found, the caller must NOT create the note and should surface
them to the user as an open question before proceeding.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

FORBIDDEN_CHARS = re.compile(r'[/\\:\*\?"<>\|]')


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def sanitize_title(title: str) -> str:
    return FORBIDDEN_CHARS.sub("", title).strip()


def find_duplicates(vault: Path, doc_number: str) -> list[str]:
    """Search 10_Areas/**/*.md for doc_number. Returns matching relative paths.

    Note: performs a full rglob on every call — acceptable for current vault size
    (~hundreds of notes) but will degrade at 10k+ notes. If inbox runs slow,
    consider a pre-built doc-number index.
    """
    areas_dir = vault / "10_Areas"
    if not areas_dir.exists():
        return []
    matches = []
    for md in areas_dir.rglob("*.md"):
        try:
            if doc_number in md.read_text(encoding="utf-8", errors="ignore"):
                matches.append(str(md.relative_to(vault)))
        except OSError:
            pass
    return matches


def compute_paths(vault: Path, area: str, title: str, yyyymm: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"\d{6}", yyyymm):
        raise ValueError(f"yyyymm must be 6 digits, got {yyyymm!r}")
    clean_title = sanitize_title(title)
    if not clean_title:
        raise ValueError("title is empty after sanitize")
    if not area or "/" in area:
        raise ValueError(f"invalid area: {area!r}")

    area_dir = vault / "10_Areas" / area
    base_slug = f"{yyyymm}_{clean_title}"

    # NFC set of existing folder names at this area level.
    existing: set[str] = (
        {_nfc(p.name) for p in area_dir.iterdir() if p.is_dir()}
        if area_dir.exists() else set()
    )

    slug = base_slug
    n = 1
    while _nfc(slug) in existing:
        n += 1
        slug = f"{base_slug}_{n}"

    folder = area_dir / slug
    note = folder / f"_{slug}.md"
    return folder, note


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("area", help="Top-level area folder, e.g. '수업성적'")
    p.add_argument("title", help="Work-matter title (will be sanitized)")
    p.add_argument("--yyyymm", default=None,
                   help="6-digit year-month (default: today)")
    p.add_argument("--vault", default=".", help="vault root (default: cwd)")
    p.add_argument("--doc-number", default=None,
                   help="공문 번호 (e.g. '총무과-7453'). If provided, searches "
                        "10_Areas/**/*.md for duplicates and reports them in JSON.")
    p.add_argument("--json", action="store_true",
                   help="emit {folder, note, slug, sanitized_title, "
                        "duplicate_candidates} as JSON")
    args = p.parse_args()

    yyyymm = args.yyyymm or date.today().strftime("%Y%m")
    vault = Path(args.vault).resolve()

    try:
        folder, note = compute_paths(vault, args.area, args.title, yyyymm)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    duplicates: list[str] = []
    if args.doc_number:
        duplicates = find_duplicates(vault, args.doc_number)

    if args.json:
        print(json.dumps({
            "folder": str(folder),
            "note": str(note),
            "slug": folder.name,
            "sanitized_title": sanitize_title(args.title),
            "duplicate_candidates": duplicates,
        }, ensure_ascii=False, indent=2))
    else:
        print(folder)
        print(note)
        if duplicates:
            print("duplicate_candidates:", file=sys.stderr)
            for d in duplicates:
                print(f"  {d}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
