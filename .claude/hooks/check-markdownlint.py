#!/usr/bin/env python3
# PostToolUse hook (Write|Edit): markdownlint advisory for the file just written.
# Rules and ignores live in `.markdownlint-cli2.jsonc` at the vault root
# (Obsidian-aware whitelist). Advisory only — never blocks, never fixes.
# Silently skips when npx is missing, the file is outside the vault, or the
# linter times out, so a broken Node setup never interrupts note writing.
import json, os, pathlib, re, shutil, subprocess, sys

PKG = "markdownlint-cli2@0.17.2"
TIMEOUT = 20
MAX_SHOWN = 10
HIT_RE = re.compile(r"^(?P<file>.+?\.md):(?P<line>\d+)(?::\d+)? (?P<rule>MD\d{3})/\S+ (?P<msg>.*)$")

try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

fp = (d.get("tool_input") or {}).get("file_path", "")
if not fp or not fp.endswith(".md"):
    sys.exit(0)

root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parents[2]).resolve()
if not (root / ".markdownlint-cli2.jsonc").is_file():
    sys.exit(0)
try:
    rel = pathlib.Path(fp).resolve().relative_to(root)
except ValueError:
    sys.exit(0)

npx = shutil.which("npx")
if not npx:
    sys.exit(0)

try:
    r = subprocess.run([npx, "--yes", PKG, rel.as_posix()], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
except (OSError, subprocess.TimeoutExpired):
    sys.exit(0)

hits = [m for m in (HIT_RE.match(l) for l in (r.stdout + r.stderr).splitlines()) if m]
if not hits:
    sys.exit(0)

lines = [f"  L{m['line']} {m['rule']} {m['msg']}" for m in hits[:MAX_SHOWN]]
if len(hits) > MAX_SHOWN:
    lines.append(f"  … 외 {len(hits) - MAX_SHOWN}건")
msg = (f"[markdownlint] {rel.name} — {len(hits)}건 (경고, 차단 아님)\n" + "\n".join(lines) +
       "\n방금 작성한 부분이면 고칠 것. 기존 본문은 사용자 승인 범위 밖이면 손대지 말 것(GP#1).")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
