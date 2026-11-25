"""Shared I/O for PostToolUse checks.

Every `.claude/hooks/check-*.py` exposes `check(fp, tool_name=None) -> str | None`
(the advisory text, or None when clean). `post-write.py` runs them all in one process;
`run_standalone` lets a single check still be run on its own (tests, manual runs).
"""
from __future__ import annotations

import json
import sys


def payload_fields(d) -> tuple[str, str | None]:
    """Return (file_path, tool_name) from a hook payload; ("", None) when absent."""
    if not isinstance(d, dict):
        return "", None
    inp = d.get("tool_input")
    if not isinstance(inp, dict):
        return "", d.get("tool_name")
    fp = inp.get("file_path") or inp.get("filePath") or ""
    return (fp if isinstance(fp, str) else ""), d.get("tool_name")


def emit(msg: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                             "additionalContext": msg}}))


def run_standalone(check) -> int:
    try:
        d = json.loads(sys.stdin.read())
    except Exception:
        return 0
    fp, tool = payload_fields(d)
    if not fp:
        return 0
    msg = check(fp, tool)
    if msg:
        emit(msg)
    return 0
