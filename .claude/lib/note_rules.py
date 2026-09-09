#!/usr/bin/env python3
"""노트 템플릿·frontmatter 규칙의 단일 진실 원천 (GP#2).

`check-template.py` 훅(쓰기 시점 단건)과 `vault_lint.py`(전수 스캔)가 **같은 함수**를
호출하도록 규칙을 여기 모은다. 훅이 정규식으로 규칙을 재구현하면 두 사본이 드리프트한다
(`validate_tag.py` ← `validate-tags.sh` 와 같은 구조).

제외 경로는 호출자가 `skip=`으로 넘긴다 — 쓰기 시점 기준(`HOOK_SKIP`)을 함수에
하드코딩하면 lint가 `_Wiki/`·`_Sources/`를 영원히 못 본다.
"""
import re
import pathlib
import unicodedata

# 훅(쓰기 시점) 제외 경로: 하네스·메타·비노트 경로
HOOK_SKIP = ("/99_Template/", "/docs/", "/.claude/", "/90_Archive/",
             "/_Wiki/", "/_Sources/", "/01_Inbox/", "/_work",
             "backlog.md", "tasks.md", "AGENTS.md", "CLAUDE.md")

NOTE_FOLDERS = ("10_Areas", "12_Projects", "11_Routines", "14_Changes", "20_Training")

# embed 예외로 인정하는 첨부 확장자 (Check 1 참조)
ATTACHMENT_EXT = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp",
    "pdf", "hwp", "hwpx", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "csv", "txt", "zip", "mp4", "mov", "mp3", "wav", "excalidraw",
}
VALID_STATUS = {"open", "in-progress", "hold", "closed", "active"}

# `10_Areas/과업심의/`의 **심의 서식** 판별 (2026-08-02 사용자 결정).
#   회차마다 재생산되는 `심의의견_*`·`*_사업목록`·`위원별_검토의견_수집`·`과업심의_프로세스`는
#   `사업 개요`/`과업내용 적정성` 구조의 서식이지 업무사안이 아니다. 앵커(Check 4)뿐 아니라
#   `status:`(Check 2b)·`#업무/`(Check 5)도 의미가 없어 회차마다 같은 경고가 재발했다
#   (실측 2026-08-02: 서식 10건이 status·#업무/ 양쪽 경고, 두 집합이 동일).
#   **폴더째 제외하지 않는 이유**: 같은 폴더 18건 중 3건은 앵커·status·태그를 갖춘 진짜
#   업무사안(`202602_..._과업심의위원회.md` 등)이고 회차마다 새로 생긴다 — 폴더를 통째로
#   빼면 그 갈래가 영구히 무게이트가 된다. 그래서 **파일명 어휘**로 서식만 골라낸다.
#   기준 동기화 대상: docs/eval-criteria.md → 기계 검사 커버리지
SIMUI_FORM = ("심의의견", "사업목록", "검토의견", "과업심의_프로세스")


def normalize_path(file_path):
    """macOS는 한글 파일명을 NFD로 저장한다 — 한글 경로 리터럴(`/과업심의/`)과 비교하려면
    NFC로 정규화해야 한다. ASCII 경로 비교에는 영향이 없다."""
    return unicodedata.normalize("NFC", str(file_path).replace("\\", "/"))


def is_area_body(fp_norm):
    """`10_Areas/` 업무사안 **본체**인가 (폴더 규칙 → docs/conventions.md).

    본체는 두 형태뿐이다:
      - 영역 루트 단일 노트: `10_Areas/{영역}/{제목}.md`
      - 첨부 래퍼 폴더의 내부 노트: `10_Areas/{영역}/{제목}/_{제목}.md`
    그 외 래퍼 폴더 안의 파일은 자식 문서(메모·원문·계획서)다.
    """
    if "/10_Areas/" not in fp_norm:
        return False
    parts = fp_norm.split("/10_Areas/", 1)[1].split("/")
    if len(parts) == 2:                       # {영역}/{제목}.md
        return True
    name = parts[-1]
    return name.startswith("_") and name[1:-3] == parts[-2]


def is_skipped(fp_norm, skip=HOOK_SKIP):
    return any(s in fp_norm for s in skip)


def check(file_path, text, skip=HOOK_SKIP):
    """노트 1건의 GP#2 위반 목록을 반환한다. 제외 대상이면 빈 리스트."""
    fp_norm = normalize_path(file_path)
    # 경로 세그먼트 검사(`/14_Changes/incident/` 등)는 선행 슬래시를 전제한다. 훅은 절대
    # 경로를 넘겨 우연히 맞았지만 lint는 볼트 상대 경로(`14_Changes/...`)를 넘겨 전부
    # 빗나갔다 — change_type 누락 79건이 무음 통과했다(실측 2026-08-25). 여기서 한 번
    # 정규화해 호출자가 절대·상대 어느 쪽을 넘겨도 같은 판정을 받게 한다.
    fp_norm = "/" + fp_norm.lstrip("/")
    if not fp_norm.endswith(".md") or is_skipped(fp_norm, skip):
        return []

    is_simui_form = ("/10_Areas/과업심의/" in fp_norm
                     and any(k in fp_norm.rsplit("/", 1)[-1] for k in SIMUI_FORM))

    violations = []

    # 선행 BOM은 떼고 본다. `re.match(r'^---')`가 BOM에 막혀 frontmatter를 통째로 못 읽고
    # "frontmatter 없음"으로 오판했다 (실측 2026-08-25: 과업심의 서식 2건). 오판은
    # 경고 1건에 그치지 않는다 — type·status·change_type 검사 전체가 무음이 된다.
    text = text.lstrip("﻿")

    # 코드(펜스·인라인)는 규칙 판정에서 제외한다. `![[...]]`·`[[ ]]`를 **설명하는** 문서가
    # 스스로 위반으로 잡히기 때문 (실측: `_Wiki/log.md`가 과거 임베드 치환 기록 때문에 적발).
    text_no_code = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text_no_code = re.sub(r'`[^`\n]*`', '', text_no_code)

    # Check 1: ![[노트]] embed — GP#2 forbids embeds unless explicitly requested.
    #   **첨부 임베드는 예외**(2026-08-25 사용자 결정): 금지의 근거는 2026-06-13 정리에서
    #   드러난 정적 MOC의 노트-임베드 52건 — 문서가 서로를 통째로 빨아들여 같은 내용이
    #   중복 표시되고 노후화되는 문제였다. 이미지·문서 첨부는 그 문제와 무관하고 오히려
    #   본문 가독성을 만든다(스크린샷을 plain 링크로 바꾸면 본문에서 사라진다).
    #   확장자 **화이트리스트**로 판별한다 — "점이 있으면 첨부"로 하면 이름에 확장자꼴이
    #   든 노트(`...처리 불가(hg_3060404_b.xfdl)`)를 첨부로 오인한다.
    for raw_target in re.findall(r'!\[\[([^\]]+)\]\]', text_no_code):
        target = raw_target.split("|")[0].split("#")[0].strip()
        ext = target.rsplit(".", 1)[-1].lower() if "." in target else ""
        if ext in ATTACHMENT_EXT:
            continue
        violations.append(
            f"![[{target}]] 노트 embed 사용 — 명시적 요청 없으면 노트 embed 금지, "
            "plain [[...]] 링크 사용 (GP#2 · 첨부 파일 임베드는 예외)")
        break

    # Check 1b: empty wikilink placeholder — template's `- [[ ]]` left unfilled
    # instead of omitting the (content-conditional) section.
    if re.search(r'\[\[\s*\]\]', text_no_code):
        violations.append(
            "빈 wikilink 플레이스홀더 [[ ]] 발견 — 관련 문서 등 content-conditional 섹션은 "
            "근거 없으면 섹션째 생략 (docs/conventions.md, docs/eval-criteria.md)")

    # Check 2: missing type: frontmatter — only for note-bearing folders
    note_type = None   # Check 4 gates on this — set only when frontmatter declares it
    if any(f in fp_norm for f in NOTE_FOLDERS):
        fm_match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            tm = re.search(r'^type:[ \t]*(\S+)', fm, re.MULTILINE)
            note_type = tm.group(1).strip('"\'') if tm else None
            if not re.search(r'^type:\s*\S', fm, re.MULTILINE):
                violations.append("frontmatter에 type: 없음 — 99_Template/ 해당 템플릿 사용 필요 (GP#2)")
            # Check 2b: status required + enum-valid (모든 note-bearing 폴더)
            #   허용 어휘 5개 고정 — 99_Template/_메타데이터 규칙.md 와 동일
            #   심의 서식은 **부재만** 면제한다 — 진행 상태를 갖는 업무사안이 아니므로 없는 게 정상이지만
            #   (위 SIMUI_FORM 주석), 값이 있으면 어휘는 지켜야 한다. 통째로 끄면 서식 15건 중 status를
            #   가진 5건의 `done`/`resolved` 드리프트가 무검사가 된다 — 제외 근거는 "상태 개념이 없다"이지
            #   "아무 값이나 된다"가 아니다.
            sm = re.search(r'^status:\s*(\S+)', fm, re.MULTILINE)
            status_val = sm.group(1).strip('"\'') if sm else None
            if not sm and is_simui_form:
                pass
            elif not sm:
                violations.append("frontmatter에 status: 없음 — open|in-progress|hold|closed|active 중 하나 필요")
            elif status_val not in VALID_STATUS:
                violations.append(
                    f"비표준 status: '{status_val}' — open|in-progress|hold|closed|active만 허용 "
                    "('done'/'resolved'/'pending-action' → 'closed'로 통일)")
            # Check 2c: doc_date/recv_date 형식 — 공문 유래 노트의 선택 필드 (2026-07-30 신설)
            #   제목 날짜 프리픽스 규칙을 대체한 필드. 공문 표기 '2026. 7. 20.'를 그대로 넣으면
            #   정렬·Dataview 쿼리가 깨지므로 YYYY-MM-DD로 고정한다.
            #   `\s*`를 쓰면 개행까지 먹어 빈 값일 때 다음 키를 값으로 잡는다 — 한 줄로 고정한다.
            #   값 뒤 인라인 주석(`doc_date: 2026-07-20  # 공문 시행일`)은 값이 아니다 — 떼고 비교한다.
            for fld in ("doc_date", "recv_date"):
                dm = re.search(rf'^{fld}:[ \t]*(\S.*?)[ \t]*$', fm, re.MULTILINE)
                if dm:
                    val = dm.group(1).split('#')[0].strip().strip('"\'')
                    if not val:
                        continue
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', val):
                        violations.append(
                            f"{fld} 형식 위반: '{val}' — YYYY-MM-DD 고정 "
                            "(공문 표기 '2026.07.20.' 그대로 넣지 말 것, 99_Template/_메타데이터 규칙.md)")

            # Check 3: change 노트는 change_type 필수 (_인시던트·_개선 템플릿)
            #   eval-criteria.md 기준 1은 incident/improvement 양쪽을 요구한다 — 한쪽만 검사하면
            #   개선 노트의 change_type 누락이 기계 검사를 무음 통과한다.
            for seg, ct in (("/14_Changes/incident/", "incident"),
                            ("/14_Changes/improvement/", "improvement")):
                #   값 따옴표(`change_type: "improvement"`)는 YAML상 합법 — 다른 검사(type·status)가
                #   `.strip('"\'')`로 허용하는 것과 맞춘다.
                if seg in fp_norm and not re.search(rf'^change_type:[ \t]*["\']?{ct}\b', fm, re.MULTILINE):
                    violations.append(
                        f"{ct} frontmatter에 'change_type: {ct}' 없음 "
                        f"(99_Template/_{'인시던트' if ct == 'incident' else '개선'}.md 사용)")
        else:
            violations.append("frontmatter 없음 — 99_Template/ 해당 템플릿 사용 필요 (GP#2)")

    # Check 4: 필수 섹션 앵커 (10_Areas 업무사안 — `type: work`만)
    #   측정 근거(2026-07-30, 10_Areas 202건): `## 🙋‍♂️ 관련` 116건·`## 🛠 해결 방안` 115건으로
    #   이모지 별칭이 다수 관행이고, 템플릿 5섹션 외 자유 섹션 보유 노트가 136건이다.
    #   따라서 "템플릿 문자열 일치"·"모든 섹션 존재"는 오탐이 되므로 검사하지 않는다.
    #   필수 앵커 2개의 존재만 본다 (별칭 허용, 자유 섹션 추가 허용).
    #   `type: work`으로 한정한다 — 10_Areas 아래에도 `type: reference` 분석 노트가 있고
    #   (실측 2/2건 전수 오탐) 업무사안 템플릿을 쓰지 않는 것이 정상이다.
    #   `10_Areas/과업심의/`의 **심의 서식**은 제외한다 — 판별과 근거는 위 `SIMUI_FORM`.
    #   제외 전 미통과 20건 중 15건이 이 서식이었고 회차가 열릴 때마다 같은 경고가 재발했다.
    #   기준 동기화 대상: docs/eval-criteria.md → Template Adherence
    #   **업무사안 본체만** 대상이다 (2026-08-25). 래퍼 폴더 안의 자식 문서(분석 메모·수신
    #   메일 원문·개선계획서)는 "요청 → 처리" 구조가 아니라 첨부 성격이라 '할 일'이 없는 게
    #   정상이다. 실측: 본체 미보유 6/193(3%)로 규칙이 관행에 맞지만, 자식은 17/28(61%)로
    #   반대다 — 자식까지 요구하면 다수가 오탐이 된다.
    if ("/10_Areas/" in fp_norm and note_type == "work"
            and is_area_body(fp_norm) and not is_simui_form):
        # 앵커 비교는 두 단계다:
        #   (1) 선행 기호(이모지·ZWJ·variation selector·구두점)를 떼고 한글 본문으로 비교.
        #       `\W`는 숫자를 포함하지 않으므로 번호 프리픽스(`## 1. 관련`)는 떼이지 않는다 — 의도된 동작이다.
        #   (2) '할 일' 앵커는 동의어 '해결 방안'도 받는다 (관련 앵커엔 동의어 없음)
        heads = {re.sub(r'^[\W_]+', '', h).strip()
                 for h in re.findall(r'^##[ \t]+(.+?)[ \t]*$', text_no_code, re.MULTILINE)}
        anchors = (("관련", {"관련"}, "## 🙋‍♂️ 관련"),
                   ("할 일", {"할 일", "해결 방안"}, "## 🛠 해결 방안"))
        for label, accepted, alias_example in anchors:
            if not (heads & accepted):
                violations.append(
                    f"필수 섹션 '## {label}' 없음 (이모지 별칭 허용: '{alias_example}') "
                    "— 자유 섹션 추가는 위반 아님 (docs/eval-criteria.md → Template Adherence)")

    # Check 5: `#업무/` 태그 존재
    #   대상: 10_Areas(`type: work`) · 14_Changes/. 두 갈래 모두 미보유가 소수라(각 13/201·24/203)
    #   요구가 관행에 부합한다. 10_Areas만 검사하면 incident·improvement가 무게이트로 남는다 (PR #20 리뷰).
    #   `20_Training/`은 제외한다 (2026-08-02 사용자 결정): 실측 미보유 25/35(71%)로 **관행이
    #   아니다** — 기계화하면 다수가 오탐이 된다. 같은 결정으로 `_교육.md` 템플릿의 `- #업무/`도
    #   제거해 템플릿과 관행을 정렬했으므로, 교육 노트의 `#업무/` 부재는 더 이상 위반이 아니다.
    #   `10_Areas/과업심의/`의 심의 서식도 제외한다 — 근거는 위 `SIMUI_FORM`.
    #   validate-tags.sh는 **발견한 태그의 형식**만 보고, 게다가 중괄호 플레이스홀더(`grep -v '[{}]'`)와
    #   인라인 코드를 제거한 뒤 검사하므로 `#업무/{영역}/...`만 있는 노트는 양쪽 다 무음이었다 —
    #   그래서 여기서는 **중괄호도 인라인 코드도 아닌 구체 태그**를 요구한다.
    #   `#부서/`는 검사하지 않는다: 실측 미보유 56/201(28%)로 관행이 아니라 **선택 필드로 강등**됐다
    #   (2026-08-02 사용자 결정) — 부재는 위반도 감점도 아니다.
    #   `type: index` 노트(`14_Changes/_Changes.md` 등 폴더 설명·대시보드)는 제외한다
    #   (2026-08-25): 특정 업무 도메인에 속하지 않는 안내 문서라 `#업무/` 태그가 의미가 없고,
    #   본문의 Dataview 예시(`#업무/{도메인}`)만 갖고 있어 매번 오탐이었다.
    if ((("/10_Areas/" in fp_norm and note_type == "work")
         or "/14_Changes/" in fp_norm)
            and note_type != "index" and not is_simui_form):
        text_no_inline = re.sub(r'`[^`\n]*`', '', text_no_code)
        if not re.search(r'#업무/(?![{\s])', text_no_inline):
            violations.append(
                "#업무/ 구체 태그 없음 — `## 관련`에 `#업무/{영역}/{하위영역}/{메뉴명}` 형태로, "
                "중괄호를 실제 값으로 채워 작성 (docs/eval-criteria.md 기준 2: 태그 전무는 1점)")

    return violations


def check_file(path, skip=HOOK_SKIP):
    """경로만으로 검사한다 — 읽기 실패는 빈 리스트(쓰기를 막지 않는다)."""
    p = pathlib.Path(path)
    if not p.exists():
        return []
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return []
    return check(path, text, skip)
