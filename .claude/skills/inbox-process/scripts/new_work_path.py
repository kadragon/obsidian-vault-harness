#!/usr/bin/env python3
"""Compute folder + note paths for a new 10_Areas work-matter note.

Rules (from inbox-process SKILL.md / docs/conventions.md 10_Areas Depth Rules):
  - With attachments:    folder `10_Areas/{area}/{YYYYMM}_{title}/`,
                         note `{folder}/_{YYYYMM}_{title}.md` (underscore prefix)
  - Without attachments: single `10_Areas/{area}/{YYYYMM}_{title}.md` at area
                         root — NO wrapper folder, NO underscore prefix (--flat)
  - Sanitize: strip `/ \\ : * ? " < > |` from the title; keep spaces + emoji
  - Dup:     if the slug collides with an existing folder OR flat `.md` stem,
             append `_2`, `_3`, ... to the `{YYYYMM}_{title}` slug

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


def compute_paths(
    vault: Path, area: str, title: str, yyyymm: str, flat: bool = False
) -> tuple[Path | None, Path]:
    """Return (folder, note). When flat=True (no attachments), folder is None
    and the note is a single `.md` at the area root."""
    if not re.fullmatch(r"\d{6}", yyyymm):
        raise ValueError(f"yyyymm must be 6 digits, got {yyyymm!r}")
    clean_title = sanitize_title(title)
    if not clean_title:
        raise ValueError("title is empty after sanitize")
    if not area or "/" in area:
        raise ValueError(f"invalid area: {area!r}")

    area_dir = vault / "10_Areas" / area
    base_slug = f"{yyyymm}_{clean_title}"

    # NFC set of existing slugs at this area level: folder names AND flat .md
    # stems (with/without the legacy `_` prefix) — so a flat note and a wrapper
    # folder never collide on the same slug.
    existing: set[str] = set()
    if area_dir.exists():
        for p in area_dir.iterdir():
            if p.is_dir():
                existing.add(_nfc(p.name))
            elif p.suffix == ".md":
                existing.add(_nfc(p.stem))
                existing.add(_nfc(p.stem.lstrip("_")))

    slug = base_slug
    n = 1
    while _nfc(slug) in existing:
        n += 1
        slug = f"{base_slug}_{n}"

    if flat:
        return None, area_dir / f"{slug}.md"
    folder = area_dir / slug
    return folder, folder / f"_{slug}.md"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("area", help="Top-level area folder, e.g. '수업성적'")
    p.add_argument("title", help="Work-matter title (will be sanitized)")
    p.add_argument("--yyyymm", default=None,
                   help="6-digit year-month (default: today)")
    p.add_argument("--vault", default=".", help="vault root (default: cwd)")
    p.add_argument("--flat", action="store_true",
                   help="no attachments → single .md at area root (no wrapper "
                        "folder, no underscore prefix). 'folder' is null in JSON.")
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
        folder, note = compute_paths(vault, args.area, args.title, yyyymm, args.flat)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    duplicates: list[str] = []
    if args.doc_number:
        duplicates = find_duplicates(vault, args.doc_number)

    # slug = note stem minus the legacy '_' prefix (flat notes have no prefix)
    slug = note.stem.lstrip("_")
    if args.json:
        print(json.dumps({
            "folder": str(folder) if folder else None,
            "note": str(note),
            "slug": slug,
            "sanitized_title": sanitize_title(args.title),
            "duplicate_candidates": duplicates,
        }, ensure_ascii=False, indent=2))
    else:
        print(folder if folder else "")
        print(note)
        if duplicates:
            print("duplicate_candidates:", file=sys.stderr)
            for d in duplicates:
                print(f"  {d}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
