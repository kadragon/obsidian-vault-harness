#!/usr/bin/env python3
"""지적 문장이 '근거 - 당위 - 실제 - 요청' 4요소를 갖추었는지 기계 검사.

사용:
    python3 lint_findings.py <파일...>          # .md / .html
    python3 lint_findings.py --json <파일>      # 기계 판독용 (종료코드 동일)

종료코드
    0  검사한 지적이 모두 4요소 충족
    1  미비 지적 있음
    3  **검사 대상을 찾지 못함** — 통과가 아니다. 표제·형식을 고치고 다시 돌린다

지적 블록 인식 (실측 관행 기준)
    .md   `지적사항`·`보완 요청`·`정정 요청`·`검토 필요 사항` 표제(H2 이하) 아래의
          `### N. 제목` 또는 `1. **제목** — 본문` / `- **제목** — 본문`.
          표제가 없으면 검사하지 않는다 — 사실 카드를 지적으로 오인하지 않기 위함.
    .html `<div class="item">` (전달본 A 항목)만 본다.
          B 표는 표기 정정이라 4요소 대상이 아니다.

4요소
    근거  L1 조문 / L2 기준 문서 + 위치 / L3 문서 간 대조. **인용부호만으로는 근거가 아니다**
          (제출 문서 제목을 「」로 감싼 것을 근거로 오인하지 않기 위함)
    당위  "~하여야 / ~해야 / ~되어야 / 원칙임 / 할 수 없음"
    실제  "~되어 있음 / 없음 / 누락 / 상이 / 미기재 / 미첨부"
    요청  "요청 —"(전달본) / "**요구** —"(노트) / "~ 바람" / "~ 제출"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --- 근거 등급 ------------------------------------------------------------
# L1: 조문. 고시번호·별표·별지 포함
L1 = re.compile(
    r"(법률?\s*제\d+조|제\d+조(제\d+항)?|시행령\s*제\d+조|고시\s*제\d{4}-\d+호"
    r"|별표\s*\d+|별지\s*제\d+호|§\s*\d+)"
)
# L2: 기준 문서를 이름과 위치로 특정한 경우. 「」만으로는 성립하지 않는다
L2 = re.compile(
    r"([「『][^」』]*?(가이드|지침|기준|예규|규정|고시)[^」』]*?[」』]"
    r"|대가산정\s*가이드|과업심의\s*가이드|세부기준|계약예규|용역계약일반조건"
    r"|가이드\s*(Part|파트|부록)|별표\s*\d|운영\s*지침)"
)
# L3: 문서 간 대조 — 근거가 불일치 자체인 경우
L3 = re.compile(r"(vs\b|↔|불일치|상이|서로 다르|문서마다 다|어긋|양립하지|3자 대조)")

DUTY = re.compile(
    r"(하여야|해야 함|해야 하|되어야|이어야|여야 함|원칙임|원칙이|의무임|필수임"
    r"|불가함|금지됨|할 수 없음|하도록 규정)"
)
FACT = re.compile(
    r"(되어 있음|기재되어|적혀 있음|없음|부재함|누락|미기재|미첨부|미제출|미명시"
    r"|상이함|불일치|초과함|미달함|공란|확인되지 않음|제시되지 않|vs\b)"
)
# `바람직` 은 요청이 아니다
REQ = re.compile(
    r"(요청\s*\*{0,2}\s*[—\-–:]|요구\s*\*{0,2}\s*[—\-–:]"
    r"|바람(?!직)|요망|제출 바람|제출할 것|재작성 바람|확정하고 근거)"
)

SKIP_TITLE = re.compile(r"(지적 아님|확인된 사항|참고 사항|추가 제출 불필요|해소 확인)")
# 태그·위키링크·순수 링크 줄은 지적이 아니다
NOISE = re.compile(r"^\s*[-*•]\s*(#[\w가-힣/]+|\[\[[^\]]+\]\]|https?://\S+)\s*$")

# --- 블록 경계 ------------------------------------------------------------
START = re.compile(
    r"^\s{0,3}(?:#{2,6}\s*)?(?:\d+[.)]|[-*•])\s+\*{0,2}(?P<title>[^*\n]{2,80}?)\*{0,2}\s*(?P<rest>—.*)?$"
)
SCOPE = re.compile(r"(지적사항|지적 목록|보완\s*요청|정정\s*요청|검토\s*필요\s*사항)")

TAG = re.compile(r"<[^>]+>")
DIV_ITEM = re.compile(r'<div[^>]*class="[^"]*\bitem\b[^"]*"[^>]*>(?P<body>.*?)</div>', re.S | re.I)
P_TITLE = re.compile(r'<p[^>]*class="[^"]*\bt\b[^"]*"[^>]*>(?P<t>.*?)</p>', re.S | re.I)


def level(line: str) -> int:
    """헤딩 레벨. 헤딩이 아니면 0."""
    m = re.match(r"^\s{0,3}(#{1,6})\s", line)
    return len(m.group(1)) if m else 0


def strip_html(text: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    return re.sub(r"\s+", " ", TAG.sub(" ", text)).strip()


def scoped(text: str) -> str:
    """'지적사항'류 표제 아래만 남긴다.

    표제는 **H2 이하**만 인정한다 — 노트 H1(`# … 위원 검토의견`)을 표제로 잡으면
    문서 전체가 범위가 되어 `## 관련`의 태그·링크까지 지적으로 오인한다.
    구간은 같은 레벨 이상의 다음 헤딩까지다(지적 1건이 `### N.` 하위 헤딩인 관행 보존).
    """
    lines = text.splitlines()
    starts = [
        i
        for i, ln in enumerate(lines)
        if SCOPE.search(ln) and (2 <= level(ln) <= 6 or ln.strip().startswith("**"))
    ]
    if not starts:
        return ""
    keep: list[str] = [""] * len(lines)
    for st in starts:
        lv = level(lines[st]) or 6  # 굵은 글씨 표제는 다음 헤딩에서 끊는다
        for i in range(st, len(lines)):
            if i > st and 0 < level(lines[i]) <= lv:
                break
            keep[i] = lines[i]
    return chr(10).join(keep)


def _body_end(lines: list[str], start: int) -> int:
    """리스트형 지적의 본문 끝.

    빈 줄 뒤에 들여쓰기·리스트·표·인용이 아닌 줄이 오면 거기서 끊는다.
    (다음 지적의 산문이 흘러들어와 요소를 대신 충족시키는 것을 막는다)
    """
    i = start
    blank = False
    while i < len(lines):
        ln = lines[i]
        if START.match(ln) or level(ln):
            return i
        if not ln.strip():
            blank = True
            i += 1
            continue
        if blank and not re.match(r"^(\s{2,}|[-*•>|]|\|)", ln) and not ln.startswith("**요"):
            return i
        blank = False
        i += 1
    return i


def blocks_from_markdown(text: str) -> list[tuple[int, str, str]]:
    """(줄번호, 제목, 본문) 목록."""
    out: list[tuple[int, str, str]] = []
    lines = scoped(text).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = START.match(line)
        if not m or NOISE.match(line):
            i += 1
            continue
        title = m.group("title").strip()
        end = _body_end(lines, i + 1)
        body = (m.group("rest") or "") + chr(10) + chr(10).join(lines[i + 1 : end])
        out.append((i + 1, title, body))
        i = max(end, i + 1)
    return out


def blocks_from_html(text: str) -> list[tuple[int, str, str]]:
    """전달본은 `div.item`(A 항목)만 본다.

    B 표(표기 정정)는 4요소 대상이 아니다.
    """
    out: list[tuple[int, str, str]] = []
    for m in DIV_ITEM.finditer(text):
        raw = m.group("body")
        tm = P_TITLE.search(raw)
        title = strip_html(tm.group("t")) if tm else strip_html(raw)[:40]
        out.append((text[: m.start()].count(chr(10)) + 1, title, strip_html(raw)))
    return out


def grade(body: str) -> str:
    if L1.search(body):
        return "L1"
    if L2.search(body):
        return "L2"
    if L3.search(body):
        return "L3"
    return "L4"


def check(body: str) -> dict:
    return {
        "근거": bool(L1.search(body) or L2.search(body) or L3.search(body)),
        "당위": bool(DUTY.search(body)),
        "실제": bool(FACT.search(body)),
        "요청": bool(REQ.search(body)),
    }


def lint(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    is_html = path.suffix.lower() in {".html", ".htm"}
    blocks = blocks_from_html(text) if is_html else blocks_from_markdown(text)
    results = []
    for lineno, title, body in blocks:
        if SKIP_TITLE.search(title):
            continue  # 지적이 아니라고 스스로 밝힌 블록
        full = f"{title}{chr(10)}{body}"
        el = check(full)
        if "{{" in full:  # 자리표시자가 남은 채로 통과시키지 않는다
            el = {k: False for k in el}
        results.append(
            {
                "file": str(path),
                "line": lineno,
                "title": title,
                "elements": el,
                "missing": [k for k, v in el.items() if not v],
                "grade": grade(full),
            }
        )
    return results


NOTHING = (
    "검사 대상 없음 — 통과가 아니다.\n"
    "  .md   `지적사항`·`보완 요청`·`정정 요청`·`검토 필요 사항` 표제(## 이하)와\n"
    "        그 아래 `### N. 제목` 또는 `1. **제목** — 본문` 블록이 있어야 한다.\n"
    "  .html 전달본 A 항목은 `<div class=\"item\">`으로 감싼다 (assets/report.html 참조)."
)


def main() -> int:
    ap = argparse.ArgumentParser(description="지적 문장 4요소(근거·당위·실제·요청) 검사")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    all_results: list[dict] = []
    for p in args.paths:
        path = Path(p)
        if not path.exists():
            print(f"[ERROR] 파일 없음: {p}", file=sys.stderr)
            return 2
        all_results.extend(lint(path))

    bad = sum(1 for r in all_results if r["missing"])

    if args.json:
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
    elif not all_results:
        print(NOTHING)
    else:
        for r in all_results:
            mark = "OK  " if not r["missing"] else "FAIL"
            print(f"{mark} [{r['grade']}] {r['file']}:{r['line']}  {r['title'][:40]}")
            if r["missing"]:
                print(f"       누락 요소: {', '.join(r['missing'])}")
            if r["grade"] == "L4":
                print("       근거 등급 L4 — 조문·기준 인용 없음. 전달본에서 빼고 노트에만 남길 것")
        print(f"\n지적 {len(all_results)}건 중 {bad}건 미비")

    if not all_results:
        return 3
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
