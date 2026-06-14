#!/usr/bin/env python3
# PostToolUse hook: GP#4 folder-path validation
# Write 후 네 가지 폴더 규칙 검사 (path-only, 파일 읽기 불필요):
#   1. 12_Projects/ 직접 하위 .md 금지 (폴더만 허용)
#   2. 90_Archive/ 파일 생성 금지
#   3. 10_Areas/ 깊이·slug·summary 길이 제한
#   4. 14_Changes/incident/ 파일명 단일 명명규칙 강제
import json, sys, re, pathlib, unicodedata

try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

fp = (d.get("tool_input") or {}).get("file_path", "")
if not fp or not fp.endswith(".md"):
    sys.exit(0)

# Normalize separators for consistent segment splitting
fp_norm = fp.replace("\\", "/")

violations = []

# Rule 1: 12_Projects/ — loose .md directly under root (no sub-folder)
if "/12_Projects/" in fp_norm:
    after = fp_norm.split("/12_Projects/", 1)[1]
    if "/" not in after:
        violations.append("12_Projects/ 직접 하위에 .md 금지 — 프로젝트 폴더 안에 넣을 것 (GP#4)")

# Rule 2: 90_Archive/ — any write is a violation (no skip!)
if "/90_Archive/" in fp_norm:
    violations.append("90_Archive/ 에 직접 파일 생성 금지 — vault-cleanup 스킬로만 이동 (GP#4)")

# Rule 3: 10_Areas/ — depth, slug length, summary length
if "/10_Areas/" in fp_norm:
    after = fp_norm.split("/10_Areas/", 1)[1]
    parts = after.split("/")
    # Valid shapes:
    #   [area, filename]          → depth 1 (no attachment folder) ✓
    #   [area, YYYYMM_slug, file] → depth 2 (attachment folder) ✓
    #   [area, ?, ?, ...]         → depth 3+ ✗

    if len(parts) > 3:
        violations.append("10_Areas/ 깊이 최대 2 레벨 초과 (GP#4)")
    elif len(parts) == 3:
        slug_folder = parts[1]
        summary_file = parts[2]
        # slug length: YYYYMM_{slug} → extract slug after first underscore (after 6 digits)
        m = re.match(r'^\d{6}_(.+)$', slug_folder)
        if m:
            slug = m.group(1)
            if len(slug) > 20:
                violations.append(
                    f"10_Areas/ 폴더 slug 20자 초과: '{slug}' ({len(slug)}자) (GP#4)")
        # summary length: strip .md, check char count
        summary = re.sub(r'\.md$', '', summary_file)
        if len(summary) > 60:
            violations.append(
                f"10_Areas/ 파일명(summary) 60자 초과: {len(summary)}자 (GP#4)")

# Rule 4: 14_Changes/incident/ — single canonical filename pattern
#   '통합학사시스템 오류 처리 {YYYY-MM-DD}_{순번}.md'
#   과거 드리프트(Error_*, '오류 처리 *', '_통합학사…') 재발 차단.
#   경로/순번은 incident-analyze 스킬의 scripts/new_incident_path.py가 생성한다.
if "/14_Changes/incident/" in fp_norm:
    name = unicodedata.normalize("NFC", pathlib.Path(fp).name)
    if not re.match(r'^통합학사시스템 오류 처리 \d{4}-\d{2}-\d{2}_\d+\.md$', name):
        violations.append(
            "14_Changes/incident/ 파일명 규칙 위반 — "
            "'통합학사시스템 오류 처리 {YYYY-MM-DD}_{순번}.md' 형식 필수. "
            "new_incident_path.py로 경로를 생성할 것 (명명규칙 단일화)")

if violations:
    fname = pathlib.Path(fp).name
    msg = ("[GP#4 폴더 규칙 경고] " + fname + "\n"
           + "\n".join("  - " + v for v in violations))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
