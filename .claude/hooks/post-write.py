#!/usr/bin/env python3
# PostToolUse hook (Write|Edit): runs every in-process vault check in ONE python process.
#
# Why: Claude Code spawns one process per registered hook. On this Windows machine each
# bash -> python3 hop costs ~0.4 s before any check runs, and 9 of them ran per edit.
# Reading the payload once and importing the checks drops that to a single hop.
#
# Each check lives in its own file and exposes `check(fp, tool_name=None) -> str | None`
# (advisory text, or None when clean) and can still be run alone: `python3 check-x.py < payload`.
# The messages are joined into one additionalContext; nothing here blocks a write.
#
# markdownlint is a Node process and stays a separate hook (check-markdownlint.py) so it
# runs in parallel with this one.
import importlib.util
import json
import pathlib
import sys
import traceback

HOOKS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HOOKS.parent / "lib"))
from hook_io import emit, payload_fields

CHECKS = (
    ("check-todo-due-date.py", False),
    ("check-tags.py", False),
    ("check-template.py", False),
    ("check-nested-delegation.py", False),
    ("check-skill-doc.py", False),
    ("check-bare-python.py", False),
    ("check-project-hub-length.py", False),
    ("check-folder-rules.py", True),
)


def load(filename: str):
    spec = importlib.util.spec_from_file_location(
        "hook_" + pathlib.Path(filename).stem.replace("-", "_"), HOOKS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(fp: str, tool_name) -> list[str]:
    messages = []
    for filename, write_only in CHECKS:
        if write_only and tool_name != "Write":
            continue
        try:
            msg = load(filename).check(fp, tool_name)
        except Exception as exc:  # noqa: BLE001 — surfaced below, never swallowed
            traceback.print_exc(file=sys.stderr)
            msg = f"[훅 오류] {filename}: {type(exc).__name__}: {exc} — 이 검사는 실행되지 않았다."
        if msg:
            messages.append(msg)
    return messages


def main() -> int:
    try:
        d = json.loads(sys.stdin.read())
    except Exception:
        return 0
    fp, tool_name = payload_fields(d)
    if not fp:
        return 0
    messages = run(fp, tool_name)
    if messages:
        emit("\n\n".join(messages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
