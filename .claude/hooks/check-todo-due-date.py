#!/usr/bin/env python3
import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from hook_io import run_standalone

DATE_MARKERS = {
    "➕": "추가일",
    "📅": "마감일",
    "✅": "완료일",
}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
SKIP = ["99_Template", "/docs/", "/.claude/", "90_Archive", "20_Training", "backlog.md", "tasks.md"]


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


def check(fp, tool_name=None):
    if not fp or not fp.endswith(".md"):
        return None

    fp_norm = fp.replace("\\", "/")
    if any(s in fp_norm for s in SKIP):
        return None

    p = pathlib.Path(fp)
    if not p.exists():
        return None

    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return None

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
        return "[WARNING] 할일 날짜 점검:\n" + "\n".join(warnings)
    return None


if __name__ == "__main__":
    sys.exit(run_standalone(check))
