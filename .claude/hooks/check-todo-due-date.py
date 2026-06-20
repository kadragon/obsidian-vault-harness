#!/usr/bin/env python3
import json, sys, re, pathlib, datetime

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

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

def has_dated(line, emoji):
    return bool(re.search(re.escape(emoji) + r"\s*\d{4}-\d{2}-\d{2}", line))

def due_date_is_weekend(line):
    m = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", line)
    if not m:
        return None
    try:
        d = datetime.date.fromisoformat(m.group(1))
        wd = d.weekday()
        if wd >= 5:
            return (m.group(1), WEEKDAY_KO[wd])
    except ValueError:
        pass
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

    missing = []
    if not has_dated(line, "➕"):
        missing.append("➕ YYYY-MM-DD (추가일)")
    if not has_dated(line, "📅"):
        missing.append("📅 YYYY-MM-DD (마감일)")
    if is_done and not has_dated(line, "✅"):
        missing.append("✅ YYYY-MM-DD (완료일)")

    if missing:
        warnings.append(f"  {line.strip()}\n    → 필요: {', '.join(missing)}")

    weekend = due_date_is_weekend(line)
    if weekend:
        date_str, day_ko = weekend
        warnings.append(f"  {line.strip()}\n    → 마감일 {date_str}({day_ko})은 휴일(주말). 평일로 변경 필요.")

if warnings:
    msg = "[WARNING] 할일 날짜 누락:\n" + "\n".join(warnings)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
