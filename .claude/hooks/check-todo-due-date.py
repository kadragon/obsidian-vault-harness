#!/usr/bin/env python3
import datetime
import json
import pathlib
import re
import sys

DATE_MARKERS = {
    "➕": "추가일",
    "📅": "마감일",
    "✅": "완료일",
}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

fp = (d.get("tool_input") or {}).get("file_path", "")
if not fp or not fp.endswith(".md"):
    sys.exit(0)

fp_norm = fp.replace("\\", "/")
skip = ["99_Template", "/docs/", "/.claude/", "90_Archive", "20_Training", "backlog.md", "tasks.md"]
if any(s in fp_norm for s in skip):
    sys.exit(0)

p = pathlib.Path(fp)
if not p.exists():
    sys.exit(0)

def _date_token(line, marker):
    """Return marker presence and the token following it, if any."""
    m = re.search(re.escape(marker) + r"(?:[ \t]+(\S+))?", line)
    return (m is not None, None if not m else m.group(1))


def _date_issue(line, marker, required):
    """Return a warning fragment for a missing or invalid required date."""
    present, token = _date_token(line, marker)
    label = DATE_MARKERS[marker]
    if not present:
        if required:
            return f"{marker} YYYY-MM-DD ({label}) 누락"
        return None
    if token is None:
        return f"{marker} 값 누락 ({label})"
    if not DATE_RE.fullmatch(token):
        return f"{marker} 값 {token!r}은 YYYY-MM-DD 형식이 아님"
    try:
        datetime.date.fromisoformat(token)
    except ValueError:
        return f"{marker} 날짜 {token}은 유효하지 않음"
    return None

try:
    text = p.read_text(encoding="utf-8")
except Exception:
    sys.exit(0)

warnings = []
for line in text.splitlines():
    is_open = bool(re.search(r"- \[ \]", line))
    is_done = bool(re.search(r"- \[[xX]\]", line))
    if not (is_open or is_done):
        continue

    issues = []
    created_issue = _date_issue(line, "➕", required=True)
    if created_issue:
        issues.append(created_issue)
    # A deadline is optional when the source does not specify one. When the
    # marker is present, however, its value must be a real calendar date.
    due_issue = _date_issue(line, "📅", required=False)
    if due_issue:
        issues.append(due_issue)
    if is_done:
        completed_issue = _date_issue(line, "✅", required=True)
        if completed_issue:
            issues.append(completed_issue)

    if issues:
        warnings.append(f"  {line.strip()}\n    → 점검: {'; '.join(issues)}")

if warnings:
    msg = "[WARNING] 할일 날짜 점검:\n" + "\n".join(warnings)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
