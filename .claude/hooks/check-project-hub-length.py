#!/usr/bin/env python3
# PostToolUse hook (Write|Edit): project hub length advisory.
# A project hub is `12_Projects/.../{folder}/_{folder}.md`. When it grows past
# MAX_LINES, suggest the project-restructure skill (split into stage notes).
# Advisory only — never blocks.
import json, pathlib, sys, unicodedata

MAX_LINES = 120

try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

fp = (d.get("tool_input") or {}).get("file_path", "")
if not fp or not fp.endswith(".md"):
    sys.exit(0)

# leading "/" so a vault-relative `12_Projects/...` path also matches
fp_norm = "/" + unicodedata.normalize("NFC", fp.replace("\\", "/")).lstrip("/")
if "/12_Projects/" not in fp_norm:
    sys.exit(0)

path = pathlib.PurePosixPath(fp_norm)
if path.stem != "_" + path.parent.name:
    sys.exit(0)
# Project folder sits at 12_Projects/{folder} or 12_Projects/{YYYY}/{folder};
# deeper matches are stage-folder notes such as `3. 과업심의/_3. 과업심의.md`.
container = path.parent.parent
if not (container.name == "12_Projects"
        or (container.name.isdigit() and len(container.name) == 4
            and container.parent.name == "12_Projects")):
    sys.exit(0)

try:
    with open(fp, encoding="utf-8") as f:
        lines = sum(1 for _ in f)
except (OSError, UnicodeDecodeError):
    sys.exit(0)

if lines <= MAX_LINES:
    sys.exit(0)

msg = (f"[프로젝트 허브 길이] {path.name} — {lines}줄 (기준 {MAX_LINES}줄 초과). "
       "완료 단계의 진행 기록을 단계 노트로 나누려면 project-restructure 스킬을 제안할 것. "
       "사용자 승인 없이 분리하지 말 것.")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
