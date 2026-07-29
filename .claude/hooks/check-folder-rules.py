#!/usr/bin/env python3
# PostToolUse hook: GP#4 folder-path validation
# Write 후 네 가지 폴더 규칙 검사 (path-only, 파일 읽기 불필요):
#   1. 12_Projects/ 직접 하위 .md 금지 (폴더만 허용)
#   2. 90_Archive/ 파일 생성 금지
#   3. 10_Areas/ 깊이 제한 및 무첨부 래퍼 폴더 검사
#   4. 14_Changes/incident/ 파일명 단일 명명규칙 강제
import json, sys, re, pathlib, time, unicodedata

# 래퍼 폴더가 방금 생성됐으면(첨부 저장 전 과도기) 무첨부 경고를 스킵하는 유예 시간(초)
GRACE_SECONDS = 60

try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

fp = (d.get("tool_input") or {}).get("file_path", "")
if not fp or not fp.endswith(".md"):
    sys.exit(0)

# Normalize separators for consistent segment splitting
fp_norm = fp.replace("\\", "/")

# Skip harness dirs (skills/agents/hooks/docs) and templates — these are not
# vault notes, so the GP#4 folder rules never apply. Keeps skill/agent edits
# from triggering the hook.
if any(s in fp_norm for s in ("/.claude/", "/99_Template/", "/docs/")):
    sys.exit(0)

violations = []

# Rule 1: 12_Projects/ — loose .md directly under root (no sub-folder)
if "/12_Projects/" in fp_norm:
    after = fp_norm.split("/12_Projects/", 1)[1]
    if "/" not in after:
        violations.append("12_Projects/ 직접 하위에 .md 금지 — 프로젝트 폴더 안에 넣을 것 (GP#4)")

# Rule 2: 90_Archive/ — any write is a violation (no skip!)
if "/90_Archive/" in fp_norm:
    violations.append("90_Archive/ 에 직접 파일 생성 금지 — vault-cleanup 스킬로만 이동 (GP#4)")

# Rule 3: 10_Areas/ — depth, no-attachment wrapper folder
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
        # no-attachment wrapper folder: 래퍼 폴더는 첨부 있을 때만.
        #   현재 폴더에 non-md 파일이 하나도 없으면 단일 파일이어야 함.
        #   (첨부가 노트보다 늦게 저장될 수 있으므로 차단 아닌 권고)
        #   grace period: 폴더가 GRACE_SECONDS 이내에 생성됐으면 첨부 저장 전
        #   과도기 상태일 뿐이므로 경고 자체를 스킵한다.
        # st_ctime(Windows: 생성 시각) 사용 — st_mtime은 이 훅을 트리거한 바로 그
        # Write가 폴더에 새 항목을 추가하며 매번 갱신되므로(디렉터리 mtime bump),
        # 노트 생성 순간엔 항상 age~0이 되어 유예 조건이 사실상 상시 True가 됨.
        # 폴더 생성 시각(ctime)은 이후 자식 파일 추가로 바뀌지 않아 실제 경과 시간을 반영.
        wrapper_dir = pathlib.Path(fp).parent
        try:
            folder_age = time.time() - wrapper_dir.stat().st_ctime
        except OSError:
            folder_age = GRACE_SECONDS + 1  # stat 실패 시 유예 없이 기존 동작 유지
        if folder_age > GRACE_SECONDS:
            try:
                # rglob, not iterdir: 첨부가 `{wrapper}/2026-012/결과물/x.pdf`처럼
                # 한 단계 아래 놓이는 경우가 많다. 직속 자식만 세면 첨부 147개를
                # 가진 폴더도 "무첨부"로 읽혀 헛경고가 난다 (2026-07-29 실측 5건).
                siblings = [p for p in wrapper_dir.rglob("*") if p.is_file()]
                has_attachment = any(
                    p.suffix.lower() != ".md" for p in siblings)
                # .lower() on both sides — a `.MD` note must not count as
                # neither attachment nor note.
                md_count = sum(1 for p in siblings if p.suffix.lower() == ".md")
                if not has_attachment and md_count <= 1:
                    violations.append(
                        f"10_Areas/ 무첨부 래퍼 폴더 — 첨부 없으면 '{slug_folder}/' 폴더 없이 "
                        "area 루트에 단일 .md로 둘 것. 첨부를 곧 추가할 거면 무시 (conventions.md)")
            except OSError:
                pass

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
