#!/usr/bin/env python3
import json, sys, re, pathlib

try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

fp = (d.get("tool_input") or {}).get("file_path", "")
if not fp or not fp.endswith(".md"):
    sys.exit(0)

skip = ["99_Template", "\\docs\\", ".claude\\", "90_Archive", "backlog.md", "tasks.md"]
if any(s in fp for s in skip):
    sys.exit(0)

p = pathlib.Path(fp)
if not p.exists():
    sys.exit(0)

warnings = []
for line in p.read_text(encoding="utf-8").splitlines():
    is_open = bool(re.search(r"- \[ \]", line))
    is_done = bool(re.search(r"- \[[xX]\]", line))
    if not (is_open or is_done):
        continue

    missing = []
    if "➕" not in line:
        missing.append("➕ YYYY-MM-DD (추가일)")
    if "📅" not in line:
        missing.append("📅 YYYY-MM-DD (마감일)")
    if is_done and "✅" not in line:
        missing.append("✅ YYYY-MM-DD (완료일)")

    if missing:
        warnings.append(f"  {line.strip()}\n    → 필요: {', '.join(missing)}")

if warnings:
    msg = "[WARNING] 할일 날짜 누락:\n" + "\n".join(warnings)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
