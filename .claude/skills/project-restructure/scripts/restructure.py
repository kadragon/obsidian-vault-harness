#!/usr/bin/env python3
"""Deterministic helpers for the project-restructure skill.

Subcommands (PROJECT = the project folder under 12_Projects/):
  scan   PROJECT                 hub size, checkboxes, root files, duplicate files
  move   PROJECT MANIFEST [--apply]  preflight + move per TSV manifest (from<TAB>to)
  refs   PROJECT MANIFEST        references that point at moved (old) paths
  verify PROJECT [--baseline F]  wikilink resolution, hub checkboxes, attachment set

All output is JSON on stdout. Paths in output are POSIX, NFC, relative to
the project (scan/move/verify) or to the vault root (refs file field).
Exit 1 when move preflight fails or verify reports failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}
TEXT_SUFFIXES = {".md", ".gs", ".js", ".py", ".txt", ".canvas"}
CHECKBOX = re.compile(r"^\s*- \[([ xX])\] ")
WIKILINK = re.compile(r"!?\[\[(.+?)\]\](?!\])")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def rel(path: Path, base: Path) -> str:
    return nfc(path.relative_to(base).as_posix())


def vault_root(project: Path) -> Path:
    for parent in project.resolve().parents:
        if parent.name == "12_Projects":
            return parent.parent
    raise SystemExit(f"not under 12_Projects/: {project}")


def hub_path(project: Path) -> Path:
    return project / f"_{project.name}.md"


def walk_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and not SKIP_DIRS & set(p.relative_to(root).parts):
            yield p


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def checkbox_counts(text: str) -> tuple[int, int]:
    open_, done = 0, 0
    for line in text.splitlines():
        m = CHECKBOX.match(line)
        if m:
            if m.group(1) == " ":
                open_ += 1
            else:
                done += 1
    return open_, done


# ---------------------------------------------------------------- scan

def scan(project: Path) -> dict:
    project = project.resolve()
    hub = hub_path(project)
    hub_info = None
    if hub.exists():
        text = hub.read_text(encoding="utf-8")
        o, d = checkbox_counts(text)
        hub_info = {"path": hub.name, "lines": len(text.splitlines()),
                    "checkboxes_open": o, "checkboxes_done": d}
    by_hash = defaultdict(list)
    folders = Counter()
    for p in walk_files(project):
        r = rel(p, project)
        if "/" in r:
            folders[r.split("/", 1)[0]] += 1
        if p.suffix.lower() != ".md":
            by_hash[md5(p)].append(r)
    root_files = sorted(nfc(p.name) for p in project.iterdir() if p.is_file())
    return {
        "project": nfc(project.name),
        "hub": hub_info,
        "root_files": root_files,
        "folders": dict(sorted(folders.items())),
        "duplicates": [sorted(v) for v in by_hash.values() if len(v) > 1],
    }


# ---------------------------------------------------------------- manifest / move

def read_manifest(path: Path) -> list[tuple[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        a, _, b = line.partition("\t")
        a, b = nfc(a.strip().replace("\\", "/")), nfc(b.strip().replace("\\", "/"))
        if (a, b) == ("from", "to"):
            continue
        rows.append((a, b))
    return rows


def move(project: Path, manifest: Path, apply: bool) -> dict:
    project = project.resolve()
    rows = read_manifest(manifest)
    errors = []
    targets = Counter(b for _, b in rows)
    under = lambda p, q: p == q or p.startswith(q + "/")  # noqa: E731
    # rows run in order: an earlier row can remove a later source or create a later target
    for i, (a, b) in enumerate(rows):
        if any(under(a, x) for x, _ in rows[:i]):
            errors.append(f"source moved by earlier row: {a}")
        if any(under(y, b) and y != b for _, y in rows[:i]):
            errors.append(f"target created by earlier row: {b}")
    for a, b in rows:
        if not a or not b:
            errors.append(f"empty path in row: {a!r} -> {b!r}")
            continue
        outside = [x for x in (a, b) if not (project / x).resolve().is_relative_to(project)
                   or (project / x).resolve() == project]
        if outside:
            errors.extend(f"outside project: {x}" for x in outside)
            continue
        if not (project / a).exists():
            errors.append(f"missing source: {a}")
        if (project / b).exists():
            errors.append(f"target exists: {b}")
        if targets[b] > 1:
            errors.append(f"duplicate target: {b}")
        if (b + "/").startswith(a + "/"):
            errors.append(f"target inside source: {a} -> {b}")
    out = {"moves": [{"from": a, "to": b} for a, b in rows], "errors": sorted(set(errors)),
           "applied": False, "undo_manifest": None, "removed_empty_dirs": []}
    if errors or not apply:
        return out

    undo = manifest.with_name(manifest.stem + ".undo.tsv")
    done = []
    for a, b in rows:
        dst = project / b
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(project / a), str(dst))
        done.append((b, a))
        undo.write_text("from\tto\n" + "".join(f"{x}\t{y}\n" for x, y in reversed(done)), encoding="utf-8")
    # prune source parents that became empty (deepest first, never the project root)
    candidates = {(project / a).parent for a, _ in rows}
    for d in sorted(candidates, key=lambda p: len(p.parts), reverse=True):
        while d != project and d.exists() and not any(d.iterdir()):
            d.rmdir()
            out["removed_empty_dirs"].append(rel(d, project))
            d = d.parent
    out.update(applied=True, undo_manifest=str(undo))
    return out


# ---------------------------------------------------------------- refs

def refs(project: Path, manifest: Path) -> list[dict]:
    """Find text that still points at moved paths.

    Inside the project: relative paths containing the old location
    (`과업심의/x.hwpx`, `[[참고문서/r.pdf]]`). A root-level file moved by name
    only is skipped there — basename wikilinks keep resolving.
    Vault-wide: full paths `12_Projects/.../{project}/{old}` (e.g. _Wiki/log.md).
    """
    project = project.resolve()
    vault = vault_root(project)
    proj_rel = rel(project, vault)
    # needle -> new paths that end with the needle (an updated reference such as
    # `3. 과업심의/` contains the old `과업심의/` and must not count as a hit)
    needles_local: dict[str, list[str]] = {}
    needles_full: dict[str, list[str]] = {}
    for a, b in read_manifest(manifest):
        # Decide dir/file from disk (source before apply, target after).
        # Never from Path.suffix: `99. 작년 예시` has suffix `. 작년 예시`.
        is_dir = (project / a).is_dir() or (project / b).is_dir()
        old, new = (a + "/", b + "/") if is_dir else (a, b)
        if "/" in old:
            needles_local[old] = [new] if new.endswith(old) else []
        strip = (lambda s: s[:-3] if s.endswith(".md") else s)
        full_old, full_new = f"{proj_rel}/{strip(a)}", f"{proj_rel}/{strip(b)}"
        needles_full[full_old] = [full_new] if full_new.endswith(full_old) else []
    hits = []
    for p in walk_files(vault):
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        in_project = project in p.resolve().parents
        needles = dict(needles_full, **(needles_local if in_project else {}))
        try:
            text = nfc(p.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
        if not any(n in text for n in needles):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for n, news in needles.items():
                for m in re.finditer(re.escape(n), line):
                    e = m.end()
                    if any(line[max(0, e - len(x)):e] == x for x in news):
                        continue
                    # valid relative to the note's own folder (stage note -> `수요조사/`),
                    # unless that path is the move source itself (pre-apply preview)
                    if n in needles_local:
                        local = (p.parent / n).resolve()
                        if local.exists() and local != (project / n).resolve():
                            continue
                    hits.append({"file": rel(p, vault), "line": i, "old": n, "text": line.strip()[:200]})
                    break
    return hits


# ---------------------------------------------------------------- verify

def build_index(vault: Path) -> tuple[set[str], dict[str, int]]:
    keys, names = set(), Counter()
    for p in walk_files(vault):
        k = rel(p, vault)
        if k.lower().endswith(".md"):
            k = k[:-3]
        keys.add(k)
        names[k.rsplit("/", 1)[-1]] += 1
    return keys, names


def resolves(target: str, keys: set[str], names: dict[str, int], scope: str = "") -> bool:
    """`scope` limits partial-path matches to one folder, so a link left behind
    after a move does not pass by matching another project's same-named path."""
    t = target.strip().lstrip("/")
    if t.lower().endswith(".md"):
        t = t[:-3]
    if "/" not in t:
        return names.get(t, 0) > 0
    return t in keys or any(k.endswith("/" + t) and k.startswith(scope) for k in keys)


def verify(project: Path, baseline: dict | None = None) -> dict:
    project = project.resolve()
    vault = vault_root(project)
    keys, names = build_index(vault)
    missing = []
    for p in walk_files(project):
        if p.suffix.lower() != ".md":
            continue
        for i, line in enumerate(nfc(p.read_text(encoding="utf-8")).splitlines(), 1):
            for m in WIKILINK.finditer(line):
                target = re.split(r"[|#]", m.group(1), maxsplit=1)[0]
                if target and not resolves(target, keys, names, rel(project, vault) + "/"):
                    missing.append({"note": rel(p, project), "line": i, "target": nfc(target.strip())})
    hub = hub_path(project)
    hub_open, hub_done = checkbox_counts(hub.read_text(encoding="utf-8")) if hub.exists() else (0, 0)
    attachments = sorted(md5(p) for p in walk_files(project) if p.suffix.lower() != ".md")
    md_count = sum(1 for p in walk_files(project) if p.suffix.lower() == ".md")
    out = {"missing_links": missing, "hub_checkboxes": hub_open + hub_done,
           "hub_checkboxes_open": hub_open, "md_count": md_count,
           "attachment_hashes": attachments, "failures": []}

    if baseline is None:
        new_missing = missing
    else:
        # count per target, not per (note, target): a moved note changes its path,
        # but one more break to an already-broken target must still count
        before = Counter(m["target"] for m in baseline.get("missing_links", []))
        now = Counter(m["target"] for m in missing)
        new_missing = [m for m in missing if now[m["target"]] > before[m["target"]]]
        if out["hub_checkboxes"] < baseline["hub_checkboxes"]:
            out["failures"].append(
                f"hub_checkboxes decreased {baseline['hub_checkboxes']} -> {out['hub_checkboxes']}")
        lost = Counter(baseline["attachment_hashes"]) - Counter(attachments)
        if lost:
            out["failures"].append(f"attachments lost: {sum(lost.values())}")
        if md_count < baseline["md_count"]:
            out["failures"].append(f"md_count decreased {baseline['md_count']} -> {md_count}")
    if new_missing:
        out["failures"].append(f"missing_links: {len(new_missing)} new")
    out["ok"] = not out["failures"]
    return out


# ---------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("project")
    m = sub.add_parser("move"); m.add_argument("project"); m.add_argument("manifest")
    m.add_argument("--apply", action="store_true")
    r = sub.add_parser("refs"); r.add_argument("project"); r.add_argument("manifest")
    v = sub.add_parser("verify"); v.add_argument("project"); v.add_argument("--baseline")
    for p in (s, m, r, v):
        p.add_argument("--out", help="also write the JSON to this file (UTF-8, no BOM)")
    a = ap.parse_args(argv)

    project = Path(a.project)
    if a.cmd == "scan":
        out, code = scan(project), 0
    elif a.cmd == "move":
        out = move(project, Path(a.manifest), a.apply)
        code = 1 if out["errors"] else 0
    elif a.cmd == "refs":
        out, code = refs(project, Path(a.manifest)), 0
    else:
        base = json.loads(Path(a.baseline).read_text(encoding="utf-8-sig")) if a.baseline else None
        out = verify(project, base)
        code = 0 if out["ok"] else 1
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return code


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.exit(main())
