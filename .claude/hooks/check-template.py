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
        "/_Wiki/", "/_Sources/", "/01_Inbox/", "/_work",
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

# Check 1b: empty wikilink placeholder — template's `- [[ ]]` left unfilled
# instead of omitting the (content-conditional) section. Strip fenced code
# blocks first so documented `[[ ]]` examples don't false-positive.
text_no_code = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
if re.search(r'\[\[\s*\]\]', text_no_code):
    violations.append(
        "빈 wikilink 플레이스홀더 [[ ]] 발견 — 관련 문서 등 content-conditional 섹션은 "
        "근거 없으면 섹션째 생략 (docs/conventions.md, docs/eval-criteria.md)")

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
        status_val = sm.group(1).strip('"\'') if sm else None
        if not sm:
            violations.append("frontmatter에 status: 없음 — open|in-progress|hold|closed|active 중 하나 필요")
        elif status_val not in valid_status:
            violations.append(
                f"비표준 status: '{status_val}' — open|in-progress|hold|closed|active만 허용 "
                "('done'/'resolved'/'pending-action' → 'closed'로 통일)")
        # Check 2c: doc_date/recv_date 형식 — 공문 유래 노트의 선택 필드 (2026-07-30 신설)
        #   제목 날짜 프리픽스 규칙을 대체한 필드. 공문 표기 '2026. 7. 20.'를 그대로 넣으면
        #   정렬·Dataview 쿼리가 깨지므로 YYYY-MM-DD로 고정한다.
        for fld in ("doc_date", "recv_date"):
            dm = re.search(rf'^{fld}:\s*(\S+)', fm, re.MULTILINE)
            if dm:
                val = dm.group(1).strip('"\'')
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', val):
                    violations.append(
                        f"{fld} 형식 위반: '{val}' — YYYY-MM-DD 고정 "
                        "(공문 표기 '2026.07.20.' 그대로 넣지 말 것, 99_Template/_메타데이터 규칙.md)")

        # Check 3: incident notes require change_type (_인시던트 템플릿)
        if "/14_Changes/incident/" in fp_norm:
            if not re.search(r'^change_type:\s*incident', fm, re.MULTILINE):
                violations.append("incident frontmatter에 'change_type: incident' 없음 (_인시던트 템플릿 사용)")
    else:
        violations.append("frontmatter 없음 — 99_Template/ 해당 템플릿 사용 필요 (GP#2)")

# Check 4: 필수 섹션 앵커 (10_Areas 업무사안)
#   측정 근거(2026-07-30, 10_Areas 202건): `## 🙋‍♂️ 관련` 116건·`## 🛠 해결 방안` 115건으로
#   이모지 별칭이 다수 관행이고, 템플릿 5섹션 외 자유 섹션 보유 노트가 136건이다.
#   따라서 "템플릿 문자열 일치"·"모든 섹션 존재"는 오탐이 되므로 검사하지 않는다.
#   필수 앵커 2개의 존재만 본다 (별칭 허용, 자유 섹션 추가 허용).
#   기준 동기화 대상: docs/eval-criteria.md → Template Adherence
if "/10_Areas/" in fp_norm:
    # 선행 기호(이모지·ZWJ·variation selector·번호 기호)를 떼고 한글 본문으로 비교
    heads = {re.sub(r'^[\W_]+', '', h).strip()
             for h in re.findall(r'^##[ \t]+(.+?)[ \t]*$', text_no_code, re.MULTILINE)}
    anchors = (("관련", {"관련"}, "## 🙋‍♂️ 관련"),
               ("할 일", {"할 일", "해결 방안"}, "## 🛠 해결 방안"))
    for label, accepted, alias_example in anchors:
        if not (heads & accepted):
            violations.append(
                f"필수 섹션 '## {label}' 없음 (이모지 별칭 허용: '{alias_example}') "
                "— 자유 섹션 추가는 위반 아님 (docs/eval-criteria.md → Template Adherence)")

if violations:
    msg = ("[GP#2 템플릿 경고] " + p.name + "\n"
           + "\n".join("  - " + v for v in violations))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
