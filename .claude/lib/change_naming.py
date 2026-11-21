#!/usr/bin/env python3
"""14_Changes/ 노트 이름 규칙의 단일 진실 원천.

파일명: "{YYYY-MM-DD} {system} {screen_id} {요약}.md" — screen_id는 있을 때만.
  예: "2026-11-19 PATIS hl_3020701_u 전자출석부 강의일자 기본값 개선.md"

이 모듈을 쓰는 곳 (규칙을 재구현하지 말 것):
  - 생성: incident-analyze·improvement-plan 워크플로우의 new_*_path.py
  - 쓰기 시점 경고: .claude/hooks/check-folder-rules.py Rule 4
  - frontmatter 일치 검사: note_rules.py Check 6 (훅·vault_lint 공용)
어휘·형식 문서: 99_Template/_메타데이터 규칙.md, docs/conventions.md (2026-11-21 개명).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

# 고정 어휘 — 레포 단위(patis·sugang·webservice·uniweb) + 대표 홈페이지 + 여러 시스템에 걸친 건.
SYSTEMS = ("PATIS", "sugang", "webservice", "uniweb", "홈페이지", "공통")
# Nexacro 화면 ID: 모듈 2글자 + 메뉴코드 7자리 + 유형(u·v·b·r…) + 선택 번호. 'hl09' 같은 약칭은 아니다.
SCREEN_ID_RE = re.compile(r"[a-z]{2}_\d{7}_[a-z]\d{0,2}")
SUMMARY_MAX = 45
# Windows 파일명 금지 문자 + Obsidian 링크를 깨는 문자 + 긴 대시(요약에 부연을 붙이는 관행 차단)
FORBIDDEN = set('\\/:*?"<>|#^[]') | {"—"}
KINDS = ("incident", "improvement")

_NAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) "
    r"(?P<system>" + "|".join(re.escape(s) for s in SYSTEMS) + r") "
    r"(?:(?P<screen_id>" + SCREEN_ID_RE.pattern + r") )?"
    r"(?P<summary>\S.*?)(?: \((?P<dup>\d+)\))?$"
)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def parse_name(stem: str) -> dict | None:
    """파일명(확장자 없음)을 분해한다. 첨부 폴더 노트의 '_' 접두는 떼고 본다. 규칙 밖이면 None."""
    m = _NAME_RE.match(nfc(stem).lstrip("_"))
    if not m:
        return None
    try:
        date.fromisoformat(m.group("date"))
    except ValueError:
        return None
    return {k: (m.group(k) or "") for k in ("date", "system", "screen_id", "summary", "dup")}


def summary_problems(summary: str) -> list[str]:
    out = []
    s = summary.strip()
    if not s:
        out.append("요약이 비어 있음")
    if len(s) > SUMMARY_MAX:
        out.append(f"요약 {len(s)}자 — {SUMMARY_MAX}자 이하 (긴 부연은 본문 요약 callout에)")
    bad = sorted({c for c in s if c in FORBIDDEN})
    if bad:
        out.append(f"요약에 금지 문자 {''.join(bad)}")
    return out


def build_name(on: str, system: str, screen_id: str, summary: str) -> str:
    """규칙에 맞는 파일명(확장자 없음)을 만든다. 규칙 위반이면 ValueError."""
    date.fromisoformat(on)
    if system not in SYSTEMS:
        raise ValueError(f"system '{system}' — {'·'.join(SYSTEMS)} 중 하나")
    screen_id = (screen_id or "").strip().lower().replace("-", "_")
    if screen_id and not SCREEN_ID_RE.fullmatch(screen_id):
        raise ValueError(f"screen_id '{screen_id}' — 형식 xx_NNNNNNN_x (예: hl_3020701_u)")
    probs = summary_problems(summary)
    if probs:
        raise ValueError("; ".join(probs))
    return nfc(" ".join(p for p in (on, system, screen_id, summary.strip()) if p))


def half_year(month: int) -> str:
    if not 1 <= month <= 12:
        raise ValueError(f"invalid month: {month}")
    return "상반기" if month <= 6 else "하반기"


def compute_path(vault: Path, kind: str, on: str, system: str, screen_id: str, summary: str) -> Path:
    """새 노트 경로. 폴더는 날짜 기준 '{YYYY}/{상반기|하반기}/'. 14_Changes 안에 같은 이름이
    있으면 ' (2)', ' (3)'…을 붙인다 — 위키링크는 파일명으로 풀리므로 유형·연도를 넘어 검사한다."""
    if kind not in KINDS:
        raise ValueError(f"kind '{kind}' — {KINDS}")
    stem = build_name(on, system, screen_id, summary)
    d = date.fromisoformat(on)
    root = vault / "14_Changes"
    existing = {nfc(p.stem).lstrip("_") for p in root.rglob("*.md")} if root.exists() else set()
    name, n = stem, 2
    while name in existing:
        name, n = f"{stem} ({n})", n + 1
    return root / kind / str(d.year) / half_year(d.month) / f"{name}.md"
