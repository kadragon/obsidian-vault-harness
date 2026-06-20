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

fp_norm = fp.replace("\\", "/")

# Skip harness/meta dirs and non-note paths
skip = ["/99_Template/", "/docs/", "/.claude/", "/90_Archive/",
        "/_Wiki/", "/19_Reference/", "/01_Inbox/", "/_work",
        "backlog.md", "tasks.md", "AGENTS.md", "CLAUDE.md"]
if any(s in fp_norm for s in skip):
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
note_folders = ["10_Areas", "12_Projects", "11_Routines", "14_Changes", "20_Training"]
if any(f in fp_norm for f in note_folders):
    fm_match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        if not re.search(r'^type:\s*\S', fm, re.MULTILINE):
            violations.append("frontmatter에 type: 없음 — 99_Template/ 해당 템플릿 사용 필요 (GP#2)")
        # Check 2b: status required + enum-valid (모든 note-bearing 폴더)
        #   허용 어휘 5개 고정 — 99_Template/_메타데이터 규칙.md 와 동일
        valid_status = {"open", "in-progress", "hold", "closed", "active"}
        sm = re.search(r'^status:\s*(\S+)', fm, re.MULTILINE)
        if not sm:
            violations.append("frontmatter에 status: 없음 — open|in-progress|hold|closed|active 중 하나 필요")
        elif sm.group(1) not in valid_status:
            violations.append(
                f"비표준 status: '{sm.group(1)}' — open|in-progress|hold|closed|active만 허용 "
                "('done'/'resolved'/'pending-action' → 'closed'로 통일)")
        # Check 3: incident notes require change_type (_인시던트 템플릿)
        if "/14_Changes/incident/" in fp_norm:
            if not re.search(r'^change_type:\s*incident', fm, re.MULTILINE):
                violations.append("incident frontmatter에 'change_type: incident' 없음 (_인시던트 템플릿 사용)")
    else:
        violations.append("frontmatter 없음 — 99_Template/ 해당 템플릿 사용 필요 (GP#2)")

if violations:
    msg = ("[GP#2 템플릿 경고] " + p.name + "\n"
           + "\n".join("  - " + v for v in violations))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
