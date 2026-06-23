#!/usr/bin/env python3
"""Mutate status-sync targets without making the orchestrator Read note bodies.

Subcommands:
  close <path>...            Frontmatter `status: open` → `closed`, bump `date modified`.
  add-todo <path> <todo>     Insert `- [ ] <todo> ➕ YYYY-MM-DD 📅 YYYY-MM-DD` at the
                             end of the `## 할 일` section (before the next `## ` or EOF).

All paths are vault-relative. Exits non-zero if any target could not be updated.
"""
from __future__ import annotations
import re
import sys
from datetime import datetime
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


def add_todo(path: Path, todo: str) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    m = TODO_SECTION_RE.search(text)
    if not m:
        return False, "no '## 할 일' section"
    today = datetime.now().strftime("%Y-%m-%d")
    body = m.group(2).rstrip("\n")
    # If the 할 일 section is a `> [!todo]` callout, keep the new item inside
    # it by quoting the line; otherwise append a bare checkbox. Match the
    # callout marker `> [!` specifically — a plain `>` blockquote mixed with
    # flat checkboxes must NOT push the new item into a quote.
    in_callout = any(ln.lstrip().startswith("> [!") for ln in body.splitlines())
    prefix = "> " if in_callout else ""
    line = f"{prefix}- [ ] {todo.strip()} ➕ {today} 📅 {today}"
    # Preserve a single blank line between the new item and the next section.
    new_block = m.group(1) + body + "\n" + line + "\n\n"
    new_text = text[:m.start()] + new_block + text[m.end():]
    if new_text == text:
        return False, "no-op"
    path.write_text(new_text, encoding="utf-8")
    return True, "ok"


def cmd_close(args: list[str]) -> int:
    if not args:
        print("usage: apply.py close <path>...", file=sys.stderr)
        return 2
    failures = 0
    for rel in args:
        p = _resolve(rel)
        if p is None:
            failures += 1
            continue
        ok, msg = close_note(p)
        print(f"{'OK ' if ok else 'ERR'} close {rel}  — {msg}")
        failures += 0 if ok else 1
    return 1 if failures else 0


def cmd_add_todo(args: list[str]) -> int:
    if len(args) != 2:
        print("usage: apply.py add-todo <path> <todo-text>", file=sys.stderr)
        return 2
    rel, todo = args
    p = _resolve(rel)
    if p is None:
        return 1
    ok, msg = add_todo(p, todo)
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
