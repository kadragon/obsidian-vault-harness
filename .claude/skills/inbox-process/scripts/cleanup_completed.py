#!/usr/bin/env python3
"""Verify and delete completed Inbox files from an explicit JSON manifest.

Default is dry-run. --apply unlinks verified files (not a trash move), never
recursively deletes a directory, and preserves every unlisted or blocked file.
Exit 0: all scoped files verified/deleted; 1: some preserved; 2: invalid input.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import copy_verified as copies


class CleanupError(ValueError):
    """The manifest or one deletion precondition cannot be proved."""


def path_in_vault(vault: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CleanupError(f"{label} must be a nonempty vault path")
    raw = Path(value).expanduser()
    raw = raw if raw.is_absolute() else vault / raw
    if ".." in raw.parts:
        raise CleanupError(f"parent traversal forbidden: {label}")
    return copies._vault_path(vault, raw, label)


def inventory(vault: Path, scope: object) -> tuple[set[Path], set[Path]]:
    if not isinstance(scope, list) or not scope:
        raise CleanupError("scope must be a nonempty list of selected Inbox paths")
    files, folders = set(), set()
    inbox = vault / "01_Inbox"
    for value in scope:
        selected = path_in_vault(vault, value, "scope")
        if not selected.is_relative_to(inbox):
            raise CleanupError("scope must be inside 01_Inbox")
        if not selected.exists():
            raise CleanupError(f"scope missing: {value}")
        if selected.is_file():
            files.add(selected)
            continue
        if not selected.is_dir():
            raise CleanupError(f"scope is not a file/directory: {value}")
        # Never follow symlink directories; retain and report them as blocked files.
        def onerror(error):
            raise CleanupError(f"cannot enumerate scope: {error}")
        for root, dirs, names in os.walk(selected, followlinks=False, onerror=onerror):
            current = Path(root)
            folders.add(current)
            for name in list(dirs):
                p = current / name
                if p.is_symlink():
                    files.add(p)
                    dirs.remove(name)
            files.update(current / name for name in names)
    return files, folders


def fingerprint(path: Path) -> tuple[int, int, int, int, int]:
    st = path.stat()
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def verify(entry: dict, vault: Path) -> Path:
    if entry.get("completed") is not True or entry.get("quality") != "PASS" or entry.get("hold") is not False:
        raise CleanupError("requires completed=true, quality=PASS, hold=false")
    branch = entry.get("branch")
    if not isinstance(branch, str) or branch not in {"action", "reference"}:
        raise CleanupError("branch must be action or reference")
    source = path_in_vault(vault, entry.get("source"), "source")
    note = path_in_vault(vault, entry.get("note"), "note")
    if not source.is_relative_to(vault / "01_Inbox"):
        raise CleanupError("source must be inside 01_Inbox")
    note_root = "10_Areas" if branch == "action" else "_Sources"
    if not note.is_relative_to(vault / note_root) or note.suffix.lower() != ".md":
        raise CleanupError(f"{branch} note must be an .md under {note_root}")
    if note.is_relative_to(vault / "_Sources" / "_Assets"):
        raise CleanupError("an attachment is not a source note")
    paths = [source, note]
    text_absorbed = entry.get("durable") == "text-absorbed"
    if not text_absorbed:
        durable = path_in_vault(vault, entry.get("durable"), "durable")
        copies._durable_destination(vault, durable)
        paths.append(durable)
    for p in paths:
        copies._regular(p, "cleanup input")
    for i, p in enumerate(paths):
        if any(os.path.samefile(p, other) for other in paths[:i]):
            raise CleanupError("source, note and durable must be distinct files")
    before = [fingerprint(p) for p in paths]
    for key, p in (("source_sha256", source), ("note_sha256", note)):
        expected = entry.get(key)
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise CleanupError(f"{key} must record the completed input's SHA-256")
        if copies._sha256(p)[0] != expected:
            raise CleanupError(f"{key} changed after completion/quality review")
    if text_absorbed:
        if branch != "action" or source.suffix.lower() not in {".txt", ".md"}:
            raise CleanupError("text-absorbed requires an action .txt/.md source")
        original = source.read_bytes().decode("utf-8")
        body = note.read_bytes().decode("utf-8")
        body = re.sub(r"\A---\r?\n.*?\r?\n---(?:\r?\n|$)", "", body, count=1, flags=re.S)
        if not original.strip() or original not in body:
            raise CleanupError("complete source text is not exactly present in note body")
    elif branch == "reference":
        copies.verify_link(source, note, durable, vault)
    else:
        copies.verify_copy(source, durable, vault)
    # Reinspect lexical paths too: a concurrent symlink replacement must not pass.
    for key in ("source", "note") + (() if text_absorbed else ("durable",)):
        path_in_vault(vault, entry[key], key)
    if before != [fingerprint(p) for p in paths]:
        raise CleanupError("input changed while verifying; source preserved")
    return source


def cleanup(manifest: dict, vault: Path, apply: bool = False) -> dict:
    vault = copies._vault_root(vault)
    if (not isinstance(manifest, dict) or type(manifest.get("version")) is not int
            or manifest.get("version") != 1 or not isinstance(manifest.get("files"), list)):
        raise CleanupError("manifest requires version=1 and a files list")
    actual, folders = inventory(vault, manifest.get("scope"))
    entries, invalid = {}, []
    for entry in manifest["files"]:
        try:
            if not isinstance(entry, dict):
                raise CleanupError("file entry must be an object")
            source = path_in_vault(vault, entry.get("source"), "source")
            if source not in actual:
                raise CleanupError("source is missing or outside selected scope")
            entries.setdefault(source, []).append(entry)
        except (CleanupError, copies.CopyError, OSError) as exc:
            invalid.append({"source": entry.get("source") if isinstance(entry, dict) else None,
                            "reason": str(exc)})
    results = []
    for source in sorted(actual):
        result = {"source": source.relative_to(vault).as_posix()}
        try:
            candidates = entries.get(source, [])
            if len(candidates) != 1:
                raise CleanupError("unlisted file" if not candidates else "duplicate manifest source")
            entry = candidates[0]
            verify(entry, vault)
            if apply:
                # Do not reuse the dry-run or earlier batch verification at deletion time.
                verified_source = verify(entry, vault)
                verified_source.unlink()
            result["status"] = "deleted" if apply else "ready"
        except (CleanupError, copies.CopyError, OSError, UnicodeError) as exc:
            result.update(status="preserved", reason=str(exc))
        results.append(result)
    removed = []
    if apply:
        # Files created during the batch are never covered by an earlier inventory.
        # Keep and report them, including new subfolders under the selected roots.
        remaining = set()
        for value in manifest["scope"]:
            try:
                selected = path_in_vault(vault, value, "scope")
                if selected.is_dir():
                    current, _ = inventory(vault, [value])
                    remaining.update(current)
            except (CleanupError, copies.CopyError, OSError) as exc:
                results.append({"source": value, "status": "preserved", "reason": str(exc)})
        for new_file in sorted(remaining - actual):
            results.append({"source": new_file.relative_to(vault).as_posix(),
                            "status": "preserved", "reason": "unlisted file appeared during cleanup"})
        protected = {vault / "01_Inbox", *(vault / "01_Inbox" / name for name in ("action", "reference", "scraps"))}
        for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
            if folder in protected:
                continue
            try:
                path_in_vault(vault, str(folder), "empty folder")
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
                    removed.append(folder.relative_to(vault).as_posix())
            except (copies.CopyError, CleanupError, OSError) as exc:
                results.append({"source": folder.relative_to(vault).as_posix(),
                                "status": "preserved", "reason": f"folder cleanup: {exc}"})
    preserved = sum(r["status"] == "preserved" for r in results)
    return {"mode": "apply" if apply else "dry-run", "results": results,
            "manifest_errors": invalid,
            "deleted": sum(r["status"] == "deleted" for r in results),
            "ready": sum(r["status"] == "ready" for r in results),
            "preserved": preserved, "removed_empty_folders": removed,
            "ok": not preserved and not invalid}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--vault", type=Path, default=Path("."))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = cleanup(manifest, args.vault, args.apply)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except (CleanupError, copies.CopyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
