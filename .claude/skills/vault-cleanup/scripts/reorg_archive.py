#!/usr/bin/env python3
"""Deterministic helpers for vault-cleanup (reorganize + archive modes).

Subcommands:
  scan-structure <area_root>
      List every `YYYYMM_*` folder in `<area_root>` and report the target
      `{area}/YYYY/YYYYMM_*` location. Highlights orphans (not already under
      a YYYY parent) vs. already-correct entries. Also detects duplicates
      (same basename existing both flat and under the YYYY subfolder).

  find-stale <10_areas_root> [--months 12] [--ref YYYY-MM]
      List `YYYYMM_*` folders older than `ref - months` (default: today - 12).
      Output shows current + proposed archive path under `90_Archive/`.

  apply-reorg <area_root>   (requires --apply, otherwise dry-run)
      Move flat `{area}/YYYYMM_*` folders into `{area}/YYYY/YYYYMM_*`.
      Refuses to overwrite an existing target. Does NOT add tags — frontmatter
      tag changes stay a separate step so the LLM/Linter can review them.

  apply-archive <src_folder> <dst_archive_root>   (requires --apply)
      Move a single stale folder from 10_Areas into 90_Archive/{area}/{YYYY}/.
      For batch use, loop in the caller.

All modes emit JSON on `--json` for machine parsing; otherwise a human table.
Comparison uses NFC (macOS HFS+ stores filenames in NFD).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

YYYYMM_RE = re.compile(r"^(\d{4})(\d{2})_.+")
YYYY_RE = re.compile(r"^\d{4}$")


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


@dataclass
class Entry:
    current: str
    target: str
    kind: str  # "orphan" | "ok" | "duplicate"
    year: str
    month: str


def _iter_dated_folders(root: Path):
    """Yield (folder_path, yyyy, mm) for every YYYYMM_* folder anywhere
    inside `root` (recursive)."""
    if not root.exists():
        return
    for p in root.rglob("*"):
        if not p.is_dir():
            continue
        m = YYYYMM_RE.match(p.name)
        if m:
            yield p, m.group(1), m.group(2)


def scan_structure(area_root: Path) -> list[Entry]:
    entries: list[Entry] = []
    existing_targets: dict[str, Path] = {}

    for folder, yyyy, _mm in _iter_dated_folders(area_root):
        # classify by whether its immediate parent is a YYYY dir directly
        # under the area_root.
        rel = folder.relative_to(area_root)
        parts = rel.parts
        target_dir = area_root / yyyy / folder.name

        already_correct = (
            len(parts) == 2 and YYYY_RE.match(parts[0]) and parts[0] == yyyy
        )
        kind = "ok" if already_correct else "orphan"

        # duplicate detection: same basename seen twice (one flat, one under
        # {area}/{YYYY}/).
        key = _nfc(folder.name)
        if key in existing_targets:
            kind = "duplicate"
        existing_targets[key] = folder

        entries.append(Entry(
            current=str(folder),
            target=str(target_dir),
            kind=kind,
            year=yyyy,
            month=_mm,
        ))
    return entries


def find_stale(areas_root: Path, ref: date, months: int,
               archive_root: Path) -> list[dict]:
    # cutoff = first day of (ref month - months)
    total_months = ref.year * 12 + (ref.month - 1) - months
    cutoff_year, cutoff_m0 = divmod(total_months, 12)
    cutoff = date(cutoff_year, cutoff_m0 + 1, 1)

    out: list[dict] = []
    if not areas_root.exists():
        return out
    for area_dir in sorted(p for p in areas_root.iterdir() if p.is_dir()):
        for folder, yyyy, mm in _iter_dated_folders(area_dir):
            folder_date = date(int(yyyy), int(mm), 1)
            if folder_date < cutoff:
                dst = archive_root / area_dir.name / yyyy / folder.name
                out.append({
                    "current": str(folder),
                    "archive_target": str(dst),
                    "yyyymm": f"{yyyy}{mm}",
                    "area": area_dir.name,
                })
    return out


def apply_reorg(area_root: Path, apply: bool) -> list[dict]:
    """Move orphan `YYYYMM_*` folders into `{area}/YYYY/YYYYMM_*`."""
    actions: list[dict] = []
    # snapshot entries first so iteration isn't affected by the moves we make
    for entry in scan_structure(area_root):
        if entry.kind != "orphan":
            continue
        src = Path(entry.current)
        dst = Path(entry.target)
        record: dict = {"src": str(src), "dst": str(dst), "status": "planned"}
        if apply:
            if dst.exists():
                record["status"] = "skipped: target exists"
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                record["status"] = "moved"
        actions.append(record)
    return actions


def apply_archive(src: Path, archive_root: Path, apply: bool) -> dict:
    m = YYYYMM_RE.match(src.name)
    if not m:
        return {"status": "error: src name does not match YYYYMM_*",
                "src": str(src)}
    yyyy = m.group(1)
    # area name = the path component directly under `10_Areas/`; callers must
    # pass src as `.../10_Areas/{area}/.../YYYYMM_*`.
    parts = src.parts
    try:
        i = parts.index("10_Areas")
        area = parts[i + 1]
    except (ValueError, IndexError):
        return {"status": "error: src must be under 10_Areas/{area}/",
                "src": str(src)}

    dst = archive_root / area / yyyy / src.name
    record = {"src": str(src), "dst": str(dst), "status": "planned"}
    if apply:
        if dst.exists():
            record["status"] = "skipped: target exists"
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            record["status"] = "moved"
    return record


def _emit(rows: list, as_json: bool) -> None:
    if as_json:
        print(json.dumps(
            [asdict(r) if hasattr(r, "__dataclass_fields__") else r
             for r in rows],
            ensure_ascii=False, indent=2))
        return
    if not rows:
        print("(no entries)")
        return
    for r in rows:
        d = asdict(r) if hasattr(r, "__dataclass_fields__") else r
        print(" | ".join(f"{k}={v}" for k, v in d.items()))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s_scan = sub.add_parser("scan-structure")
    s_scan.add_argument("area_root", type=Path)
    s_scan.add_argument("--json", action="store_true")

    s_stale = sub.add_parser("find-stale")
    s_stale.add_argument("areas_root", type=Path,
                         help="path to 10_Areas/")
    s_stale.add_argument("--months", type=int, default=12)
    s_stale.add_argument("--ref", default=None,
                         help="reference date YYYY-MM (default: today)")
    s_stale.add_argument("--archive-root", type=Path, required=True,
                         help="path to 90_Archive/")
    s_stale.add_argument("--json", action="store_true")

    s_reorg = sub.add_parser("apply-reorg")
    s_reorg.add_argument("area_root", type=Path)
    s_reorg.add_argument("--apply", action="store_true",
                         help="actually move folders (default: dry-run)")
    s_reorg.add_argument("--json", action="store_true")

    s_arch = sub.add_parser("apply-archive")
    s_arch.add_argument("src", type=Path)
    s_arch.add_argument("archive_root", type=Path)
    s_arch.add_argument("--apply", action="store_true")
    s_arch.add_argument("--json", action="store_true")

    args = p.parse_args()

    if args.cmd == "scan-structure":
        _emit(scan_structure(args.area_root.resolve()), args.json)
    elif args.cmd == "find-stale":
        if args.ref:
            y, m = map(int, args.ref.split("-"))
            ref = date(y, m, 1)
        else:
            ref = date.today()
        rows = find_stale(args.areas_root.resolve(), ref, args.months,
                          args.archive_root.resolve())
        _emit(rows, args.json)
    elif args.cmd == "apply-reorg":
        rows = apply_reorg(args.area_root.resolve(), args.apply)
        _emit(rows, args.json)
    elif args.cmd == "apply-archive":
        row = apply_archive(args.src.resolve(), args.archive_root.resolve(),
                            args.apply)
        _emit([row], args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
