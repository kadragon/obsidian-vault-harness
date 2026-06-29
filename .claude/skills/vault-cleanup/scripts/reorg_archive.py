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
from datetime import date, datetime
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
        # flat single-file notes at the area root (no wrapper folder, from
        # new_work_path.py --flat). _iter_dated_folders yields folders only,
        # so these would otherwise never be archived.
        for md in sorted(area_dir.glob("*.md")):
            fm = YYYYMM_RE.match(md.stem.lstrip("_"))
            if not fm:
                continue
            f_yyyy, f_mm = fm.group(1), fm.group(2)
            if date(int(f_yyyy), int(f_mm), 1) < cutoff:
                out.append({
                    "current": str(md),
                    "archive_target": str(
                        archive_root / area_dir.name / f_yyyy / md.name),
                    "yyyymm": f"{f_yyyy}{f_mm}",
                    "area": area_dir.name,
                })
    return out


CLOSED_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) #closed \[\[([^\]]+)\]\]")


def _flat_name_candidates(dated: str, note_part: str) -> list[str]:
    names: list[str] = []
    for raw in (note_part, dated):
        name = raw if raw.endswith(".md") else raw + ".md"
        variants = [name]
        if name.startswith("_"):
            variants.append(name.lstrip("_"))
        else:
            variants.append("_" + name)
        for variant in variants:
            norm = _nfc(variant)
            if norm not in names:
                names.append(norm)
    return names


def _find_flat(area_dir: Path, dated: str, note_part: str):
    """The matching flat note at an area root, or None.

    Used to resolve a folder-form log entry whose wrapper folder was later
    flattened (new_work_path.py --flat). It only accepts exact matches for the
    original note filename or folder stem. Matching by YYYYMM alone can archive
    an unrelated note from the same month.
    """
    if not area_dir.is_dir():
        return None
    candidates = set(_flat_name_candidates(dated, note_part))
    hits: list[Path] = []
    for md in area_dir.glob("*.md"):
        if _nfc(md.name) in candidates:
            hits.append(md)
    return hits[0] if len(hits) == 1 else None


def _archive_unit(vault: Path, wikipath: str):
    """Map a log.md wikilink path to the archivable unit under 10_Areas/.

    Returns (unit_path, area, yyyymm) or None if not an archivable 10_Areas
    work note. Folder-form (note inside `{YYYYMM}_slug/`) → the dated folder;
    flat-form (single `{YYYYMM}_X.md` at area root) → the file itself.
    """
    # tolerate Obsidian alias (`path|alias`) and Windows separators
    wp = _nfc(wikipath.replace("\\", "/").split("|")[0].strip().lstrip("/"))
    if not wp.startswith("10_Areas/"):
        return None
    rest = wp[len("10_Areas/"):]
    parts = rest.split("/")
    if len(parts) < 2:
        return None
    area, dated = parts[0], parts[1]
    # strip a legacy leading `_` (note-file prefix) before the date match;
    # keep `dated` itself for path reconstruction.
    stem = (dated[:-3] if dated.endswith(".md") else dated).lstrip("_")
    m = YYYYMM_RE.match(stem)
    if not m:
        return None
    yyyymm = m.group(1) + m.group(2)
    if len(parts) == 2:  # flat single-file note at area root
        name = dated if dated.endswith(".md") else dated + ".md"
        return vault / "10_Areas" / area / name, area, yyyymm
    # folder-form: archive the whole dated folder. If the wrapper folder no
    # longer exists, the note may have been flattened to a single file at the
    # area root after the log entry was written — resolve to that flat file so
    # it stays an archive candidate (and is not double-counted as unlogged).
    folder = vault / "10_Areas" / area / dated
    if not folder.exists():
        flat = _find_flat(vault / "10_Areas" / area, dated, parts[-1])
        if flat is not None:
            return flat, area, yyyymm
    return folder, area, yyyymm


def find_closed(vault: Path, log_path: Path, ref: date, days: int,
                archive_root: Path) -> dict:
    """Closed-work → archive candidates, from _Wiki/log.md #closed events.

    A note closed >= `days` ago (per its log close-date) and still living in
    10_Areas/ is an archive candidate. Also reports notes whose frontmatter is
    `status: closed` but have NO log entry (unlogged — close-date unknown).
    """
    # latest close-date per archive unit (a note may be re-closed)
    closed: dict[str, tuple[date, str, str]] = {}  # unit_str -> (date, area, yyyymm)
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            mm = CLOSED_RE.match(line)
            if not mm:
                continue
            d = date(*map(int, mm.group(1).split("-")))
            u = _archive_unit(vault, mm.group(2))
            if not u:
                print(f"warn: #closed entry not an archivable 10_Areas note, "
                      f"skipped: {mm.group(2)!r}", file=sys.stderr)
                continue
            unit, area, yyyymm = u
            key = str(unit)
            if key not in closed or d > closed[key][0]:
                closed[key] = (d, area, yyyymm)

    candidates: list[dict] = []
    logged_units = set(closed.keys())
    for key, (d, area, yyyymm) in sorted(closed.items()):
        unit = Path(key)
        if not unit.exists():
            continue  # already archived / moved
        age = (ref - d).days
        if age >= days:
            yyyy = yyyymm[:4]
            candidates.append({
                "current": key,
                "archive_target": str(archive_root / area / yyyy / unit.name),
                "area": area,
                "closed_date": d.isoformat(),
                "age_days": age,
            })

    # unlogged: frontmatter status: closed but no #closed log entry
    unlogged: list[str] = []
    areas_dir = vault / "10_Areas"
    if areas_dir.exists():
        for md in areas_dir.rglob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = re.match(r'^---\s*\r?\n(.*?)\r?\n---', text, re.DOTALL)
            if not fm or not re.search(r'^status:\s*closed', fm.group(1), re.MULTILINE):
                continue
            u = _archive_unit(vault, str(md.relative_to(vault)))
            if u and str(u[0]) not in logged_units:
                unlogged.append(str(md.relative_to(vault)))

    return {"candidates": candidates, "unlogged_closed": sorted(unlogged)}


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
    # tolerate a legacy leading `_` (flat note-file prefix) when reading the
    # date; `src.name` is kept intact for the archive target. Without the
    # lstrip, `_YYYYMM_*.md` notes emitted by find_stale fail to match here.
    m = YYYYMM_RE.match(src.name.lstrip("_"))
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


def purge_to_trash(target: Path, vault: Path, apply: bool) -> dict:
    """Reversible delete: move target into <vault>/.trash/<timestamp>/<relpath>.

    Vault notes are git-ignored, so `rm -rf` is unrecoverable. This moves
    instead, preserving the relative path so the user can restore or empty
    .trash after verifying. Refuses anything outside the vault, the vault root
    itself, or paths already under .trash.
    """
    vault = vault.resolve()
    target = target.resolve()
    try:
        rel = target.relative_to(vault)
    except ValueError:
        return {"status": "error: target outside vault", "target": str(target)}
    if rel == Path(".") or rel.parts[:1] == (".trash",):
        return {"status": "error: refusing vault root or .trash", "target": str(target)}
    if not target.exists():
        return {"status": "error: target missing", "target": str(target)}
    dst = vault / ".trash" / datetime.now().strftime("%Y%m%d-%H%M%S") / rel
    record = {"target": str(target), "trash": str(dst), "status": "planned"}
    if apply:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(dst))
        record["status"] = "trashed"
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

    s_closed = sub.add_parser("find-closed")
    s_closed.add_argument("vault_root", type=Path, help="vault root")
    s_closed.add_argument("--log", type=Path, default=None,
                          help="path to _Wiki/log.md (default: <vault>/_Wiki/log.md)")
    s_closed.add_argument("--days", type=int, default=90,
                          help="archive a note closed at least this many days ago (default 90)")
    s_closed.add_argument("--ref", default=None,
                          help="reference date YYYY-MM-DD (default: today)")
    s_closed.add_argument("--archive-root", type=Path, required=True)
    s_closed.add_argument("--json", action="store_true")

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

    s_purge = sub.add_parser("purge",
                             help="reversible delete: move target into <vault>/.trash/")
    s_purge.add_argument("target", type=Path, help="file/folder to remove")
    s_purge.add_argument("vault_root", type=Path, help="vault root")
    s_purge.add_argument("--apply", action="store_true",
                         help="실제 이동 (기본: dry-run)")
    s_purge.add_argument("--json", action="store_true")

    args = p.parse_args()

    if args.cmd == "scan-structure":
        _emit(scan_structure(args.area_root.resolve()), args.json)
    elif args.cmd == "find-stale":
        if args.ref:
            try:
                y, m = map(int, args.ref.split("-"))
                ref = date(y, m, 1)
            except (ValueError, TypeError):
                print("error: --ref must be YYYY-MM", file=sys.stderr)
                return 2
        else:
            ref = date.today()
        rows = find_stale(args.areas_root.resolve(), ref, args.months,
                          args.archive_root.resolve())
        _emit(rows, args.json)
    elif args.cmd == "find-closed":
        vault = args.vault_root.resolve()
        log_path = (args.log.resolve() if args.log else vault / "_Wiki" / "log.md")
        if args.ref:
            try:
                ref = date(*map(int, args.ref.split("-")))
            except (ValueError, TypeError):
                print("error: --ref must be YYYY-MM-DD", file=sys.stderr)
                return 2
        else:
            ref = date.today()
        res = find_closed(vault, log_path, ref, args.days,
                          args.archive_root.resolve())
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"## 종결→아카이브 후보 ({args.days}일 이상 경과, {len(res['candidates'])}건)")
            for c in res["candidates"]:
                print(f"  {c['closed_date']} ({c['age_days']}d)  {c['current']}")
                print(f"    → {c['archive_target']}")
            print(f"\n## 미기록 종결 (status:closed 인데 log.md #closed 없음, {len(res['unlogged_closed'])}건)")
            for u in res["unlogged_closed"]:
                print(f"  {u}")
    elif args.cmd == "apply-reorg":
        rows = apply_reorg(args.area_root.resolve(), args.apply)
        _emit(rows, args.json)
    elif args.cmd == "apply-archive":
        row = apply_archive(args.src.resolve(), args.archive_root.resolve(),
                            args.apply)
        _emit([row], args.json)
    elif args.cmd == "purge":
        row = purge_to_trash(args.target.resolve(), args.vault_root.resolve(),
                             args.apply)
        _emit([row], args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
