#!/usr/bin/env python3
# PostToolUse hook: GP#2 template check
# Write 후 (1) ![[...]] embed 감지, (2) note-bearing 폴더에서 type: frontmatter 누락 감지
import json, sys, re, pathlib

try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

fp = (d.get("tool_input") or {}).get("file_path", "")
if not fp or not fp.endswith(".md"):
    sys.exit(0)

# Skip harness/meta dirs and non-note paths
skip = ["99_Template", "\\docs\\", ".claude\\", "90_Archive",
        "_Wiki", "19_Reference\\", "01_Inbox\\", "\\_work",
        "backlog.md", "tasks.md"]
if any(s in fp for s in skip):
    sys.exit(0)

p = pathlib.Path(fp)
if not p.exists():
    sys.exit(0)

try:
    text = p.read_text(encoding="utf-8")
except Exception:
    sys.exit(0)

violations = []

# Check 1: ![[...]] embed — GP#2 forbids embeds unless explicitly requested
if re.search(r'!\[\[', text):
    violations.append("![[...]] embed 사용 — 명시적 요청 없으면 embed 금지 (GP#2)")

# Check 2: missing type: frontmatter — only for note-bearing folders
note_folders = ["10_Areas", "12_Projects", "13_Routines", "14_Changes", "20_Training"]
if any(f in fp for f in note_folders):
    fm_match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        if not re.search(r'^type:\s*\S', fm, re.MULTILINE):
            violations.append("frontmatter에 type: 없음 — 99_Template/ 해당 템플릿 사용 필요 (GP#2)")
    else:
        violations.append("frontmatter 없음 — 99_Template/ 해당 템플릿 사용 필요 (GP#2)")

if violations:
    msg = ("[GP#2 템플릿 경고] " + p.name + "\n"
           + "\n".join("  - " + v for v in violations))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
