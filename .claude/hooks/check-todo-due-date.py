#!/usr/bin/env python3
import json, sys, re, pathlib

try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

fp = (d.get("tool_input") or {}).get("file_path", "")
if not fp or not fp.endswith(".md"):
    sys.exit(0)

skip = ["99_Template", "\\docs\\", ".claude\\", "90_Archive"]
if any(s in fp for s in skip):
    sys.exit(0)

p = pathlib.Path(fp)
if not p.exists():
    sys.exit(0)

bad = [l for l in p.read_text(encoding="utf-8").splitlines()
       if re.search(r"- \[ \]", l) and "📅" not in l]

if bad:
    lines = "\n".join(f"  {l}" for l in bad)
    msg = f"[WARNING] due date 없는 할일 발견:\n{lines}\n-> 📅 YYYY-MM-DD 추가 필요"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
