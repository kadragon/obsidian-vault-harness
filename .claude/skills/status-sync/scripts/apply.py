#!/usr/bin/env python3
"""Mutate status-sync targets without making the orchestrator Read note bodies.

Subcommands:
  close <path>... [--report FILE]  Close notes; retain a JSONL recovery report.
  add-todo <path> <todo>     Insert `- [ ] <todo> ➕ YYYY-MM-DD` at the end of the
                             `## 할 일` section. Add `--due YYYY-MM-DD` only when a
                             deadline is explicitly known.

All paths are vault-relative. Exits non-zero if any target could not be updated.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

VAULT = Path(__file__).resolve().parents[4]
FM_RE = re.compile(r"\A(---\n)(.*?)(\n---\n)", re.DOTALL)
# Match either the 10_Areas heading (`## 할 일`) or the 14_Changes heading
# (`## 🏷 Todo`). Both point at the checkbox list where new TODOs append.
TODO_SECTION_RE = re.compile(
    r"(^##\s*(?:할\s*일|🏷\s*Todo)\s*$)(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _resolve(rel: str) -> Path | None:
    p = (VAULT / rel).resolve()
    try:
        p.relative_to(VAULT)
    except ValueError:
        print(f"SKIP outside vault: {rel}", file=sys.stderr)
        return None
    if not p.exists():
        print(f"SKIP missing: {rel}", file=sys.stderr)
        return None
    return p


def close_note(path: Path) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        return False, "no frontmatter"
    fm = m.group(2)
    if not re.search(r"^status:\s*open\s*$", fm, re.MULTILINE):
        return False, "status is not 'open'"
    fm_new = re.sub(r"^status:\s*open\s*$", "status: closed", fm, count=1, flags=re.MULTILINE)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fm_new = re.sub(
        r"^date modified:.*$",
        f"date modified: {now}",
        fm_new,
        count=1,
        flags=re.MULTILINE,
    )
    path.write_text(m.group(1) + fm_new + m.group(3) + text[m.end():], encoding="utf-8")
    return True, "ok"


def _valid_date(value: str) -> bool:
    """Accept only an ISO calendar date, including real month/day values."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def add_todo(path: Path, todo: str, due: str | None = None) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    m = TODO_SECTION_RE.search(text)
    if not m:
        return False, "no '## 할 일' section"
    if due is not None and not _valid_date(due):
        return False, f"invalid due date: {due}"
    today = datetime.now().strftime("%Y-%m-%d")
    body = m.group(2).rstrip("\n")
    # If the 할 일 section is a `> [!todo]` callout, keep the new item inside
    # it by quoting the line; otherwise append a bare checkbox. Match the
    # callout marker `> [!` specifically — a plain `>` blockquote mixed with
    # flat checkboxes must NOT push the new item into a quote.
    in_callout = any(ln.lstrip().startswith("> [!") for ln in body.splitlines())
    prefix = "> " if in_callout else ""
    line = f"{prefix}- [ ] {todo.strip()} ➕ {today}"
    if due is not None:
        line += f" 📅 {due}"
    # Preserve a single blank line between the new item and the next section.
    new_block = m.group(1) + body + "\n" + line + "\n\n"
    new_text = text[:m.start()] + new_block + text[m.end():]
    if new_text == text:
        return False, "no-op"
    path.write_text(new_text, encoding="utf-8")
    return True, "ok"


def cmd_close(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="apply.py close")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--report", type=Path, help="new JSONL file for Wiki-log recovery")
    options = parser.parse_args(args)
    report = None
    if options.report:
        try:
            options.report.parent.mkdir(parents=True, exist_ok=True)
            # Never overwrite an earlier recovery report or an existing note.
            report = options.report.open("x", encoding="utf-8")
            _record(report, {"event": "planned", "paths": options.paths})
        except OSError as exc:
            if report:
                report.close()
            print(f"ERR report {options.report}: {exc}; no notes changed", file=sys.stderr)
            return 1
    failures = 0
    try:
        for rel in options.paths:
            p = _resolve(rel)
            if p is None:
                ok, msg = False, "missing or outside vault"
            else:
                try:
                    ok, msg = close_note(p)
                except OSError as exc:
                    ok, msg = False, str(exc)
                print(f"{'OK ' if ok else 'ERR'} close {rel}  — {msg}")
            failures += 0 if ok else 1
            if report:
                try:
                    _record(report, {
                        "event": "closed" if ok else "failed",
                        "path": p.relative_to(VAULT).as_posix() if p else rel,
                        "message": msg,
                    })
                except OSError as exc:
                    print(f"ERR report write: {exc}; stop and reconcile planned paths with notes", file=sys.stderr)
                    return 1
    finally:
        if report:
            report.close()
            print(f"REPORT {options.report}")
    return 1 if failures else 0


def _record(report, entry: dict) -> None:
    """Persist each result before processing the next note."""
    entry["recorded_at"] = datetime.now().isoformat(timespec="seconds")
    report.write(json.dumps(entry, ensure_ascii=False) + "\n")
    report.flush()
    os.fsync(report.fileno())


def cmd_add_todo(args: list[str]) -> int:
    if len(args) not in {2, 4} or (len(args) == 4 and args[2] != "--due"):
        print("usage: apply.py add-todo <path> <todo-text> [--due YYYY-MM-DD]", file=sys.stderr)
        return 2
    rel, todo = args[:2]
    due = args[3] if len(args) == 4 else None
    p = _resolve(rel)
    if p is None:
        return 1
    ok, msg = add_todo(p, todo, due)
    print(f"{'OK ' if ok else 'ERR'} add-todo {rel}  — {msg}")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: apply.py {close|add-todo} ...", file=sys.stderr)
        return 2
    cmd, *args = argv[1:]
    if cmd == "close":
        return cmd_close(args)
    if cmd == "add-todo":
        return cmd_add_todo(args)
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
