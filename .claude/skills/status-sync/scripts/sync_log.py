#!/usr/bin/env python3
"""Replay confirmed close events into the Wiki log without duplicate entries.

Usage: sync_log.py REPORT.jsonl --vault VAULT [--apply]
Dry-run is the default. Unknown/interrupted outcomes never authorize an entry.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata


def key(day: str, path: str) -> tuple[str, str]:
    return day, unicodedata.normalize("NFC", path.replace("\\", "/").removesuffix(".md"))


def report_path(vault: Path, value: str) -> str:
    """apply.py writes planned paths as typed but results vault-relative; compare both alike."""
    text = value.replace("\\", "/")
    try:
        text = (vault / text).resolve().relative_to(vault).as_posix()
    except (OSError, ValueError):
        pass
    return unicodedata.normalize("NFC", text)


def safe_note(vault: Path, value: str) -> Path:
    if not isinstance(value, str) or any(c in value for c in "\r\n[]|#"):
        raise ValueError("invalid note path")
    raw = vault / value
    path = raw.resolve()
    relative = path.relative_to(vault)
    if not relative.parts or relative.parts[0] not in {"10_Areas", "14_Changes"} or path.suffix != ".md":
        raise ValueError(f"not a status-sync note: {value}")
    if any(p.is_symlink() for p in [raw, *raw.parents] if p != vault and vault in p.parents):
        raise ValueError(f"symlink note: {value}")
    return path


def replay(report: Path, vault: Path, apply: bool = False) -> dict:
    vault = vault.resolve(strict=True)
    rows = [json.loads(line) for line in report.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("report rows must be objects")
    log = vault / "_Wiki" / "log.md"
    if log.is_symlink() or log.parent.is_symlink():
        raise ValueError("symlink Wiki log")
    lock = log.with_name(".status-sync-log.lock")
    lock_fd = None
    temp = None
    try:
        if apply:
            lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        original = log.read_bytes()
        text = original.decode("utf-8-sig")
        existing = {key(m[1], m[2]) for m in re.finditer(
            r"^- (\d{4}-\d{2}-\d{2}) #closed \[\[([^\]|]+)(?:\|[^\]]*)?\]\]", text, re.M)}
        added, skipped, pending = [], [], []
        resolved = {report_path(vault, r["path"]) for r in rows
                    if r.get("event") in {"closed", "failed"} and isinstance(r.get("path"), str)}
        for row in rows:
            event = row.get("event")
            if event == "planned":
                paths = row.get("paths")
                if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
                    raise ValueError("invalid planned paths")
                pending.extend(p for p in paths if report_path(vault, p) not in resolved)
                continue
            if event == "failed":
                continue
            if event != "closed":
                raise ValueError(f"unknown report event: {event}")
            stamp = datetime.fromisoformat(row["recorded_at"])
            day = stamp.date().isoformat()
            path = safe_note(vault, row["path"])
            relative = path.relative_to(vault).as_posix()
            identity = key(day, relative)
            if identity in existing:
                skipped.append(relative)
                continue
            note = path.read_text(encoding="utf-8-sig")
            fm = re.match(r"\A---\n(.*?)\n---(?:\n|$)", note, re.S)
            if not fm or not re.search(r"^status:[ \t]*(['\"]?)closed\1[ \t]*(?:#.*)?$", fm[1], re.M):
                pending.append(relative)
                continue
            tag = re.search(r"#업무/([^/\s#`\[\]]+)(?:/([^/\s#`\[\]]+))?", note)
            domain = (tag[2] or tag[1]) if tag else "unknown"
            added.append(f"- {day} #closed [[{relative.removesuffix('.md')}]] — {domain} 종결")
            existing.add(identity)
        if apply and added:
            ending = b"\r\n" if b"\r\n" in original else b"\n"
            suffix = (b"" if not original or original.endswith(b"\n") else ending)
            suffix += ending.join(line.encode("utf-8") for line in added) + ending
            fd, name = tempfile.mkstemp(prefix=".status-sync-", dir=log.parent)
            temp = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(original + suffix)
                stream.flush()
                os.fsync(stream.fileno())
            temp.chmod(log.stat().st_mode)
            if log.read_bytes() != original:
                raise ValueError("Wiki log changed during replay; retry")
            os.replace(temp, log)
        return {"applied": apply, "entries": added, "already_logged": skipped,
                "pending": sorted(set(pending))}
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
        if lock_fd is not None:
            os.close(lock_fd)
            lock.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--vault", type=Path, default=Path("."))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = replay(args.report, args.vault, args.apply)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["pending"] else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
