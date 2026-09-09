# Backlog

## Review Backlog

### PR #22 — [HARNESS] add gwaeop-simui skill and PDF classifier front-end (2026-08-18)

- [ ] [debt] `extract_bundle.py` 의 `SKIP` 집합이 `.xlsx`·`.xls` 를 버려 산출내역서가 스프레드시트로 제출되면 금액·수량·VAT 근거가 번들 추출물에 남지 않는다 — 스프레드시트 추출 경로를 추가하거나 대체 리더를 명시 (source: codex) — `.claude/skills/gwaeop-simui/scripts/extract_bundle.py:23`
- [ ] [harness] Read 도구가 PDF를 못 읽는 근본 원인은 poppler(`pdftoppm`) 미설치다. 문서로 우회(PyMuPDF 경유)했을 뿐이므로 poppler 설치로 근본 해소할지 결정 (source: code-review) — 볼트 전역

## 2-evaluator-contract — 평가자 기본 모드 계약 재작성

- [ ] [REFACTOR] `note-evaluator.md`를 기본 모드(원본 대조 사실검증) 우선으로 재작성한다. 출력은 `필드 | 원본 값 | 노트 값 | 결과(PASS·FAIL·UNVERIFIED)` 표, 값 불일치는 FAIL, 원본 부재는 UNVERIFIED이며 UNVERIFIED 잔존 시 원본 삭제 보류. 훅 실행 절차를 평가자에서 제거하고 메인이 1회 실행한 결과를 넘긴다(3-a). 5축 채점은 `full-quality` 명시 요청으로 한정. 소비 형식을 명시하는 호출자 `SKILL.md` 3-b를 같은 커밋에서 수정하고, `note-evaluator.md:35`의 교육 노트 `#업무/` finding 지시(=`eval-criteria.md:43`과 정면 충돌)를 제거한다 (source: 같은 spec Solution §평가자 계약 재작성) — `.claude/agents/note-evaluator.md` · `.claude/skills/inbox-process/SKILL.md` 3-b

## 3-policy-ssot — 임베드·기존 본문 갱신 정책 SSOT 정리

- [ ] [FIX] 충돌 정책 2건에 소유 문서를 하나씩 정하고 나머지는 참조만 남긴다. (a) `eval-criteria.md:74-81` Wikilink Style binary 채점 대상을 **노트 임베드로 한정**해 `AGENTS.md` GP#2가 허용하는 첨부 `![[...]]`를 감점에서 제외(가중치·임계 불변). (b) `reference-branch.md:97`(기존 페이지 갱신 요구) ↔ `inbox-reference-worker.md:54`(얇은 링크 추가만) 모순을 GP#1 문장 참조로 일원화 (source: 같은 spec Solution §정책 SSOT 정리) — `docs/eval-criteria.md:74-81` · `.claude/skills/inbox-process/references/reference-branch.md:97` · `.claude/agents/inbox-reference-worker.md:54`

## 4-hwpx-shared — HWPX 추출 경로 공용화

- [ ] [REFACTOR] `gwaeop-simui/scripts/extract_bundle.py`의 `find_hwpx_text_py()` 경로 해석(marketplaces 우선·cache 폴백)을 두 진입점이 공유하는 위치로 올리고, reference 갈래의 `.hwpx`를 "파싱 불가"에서 추출 시도 대상으로 재분류한다. 도구 부재·실제 추출 실패일 때만 맥락 기반 보류(`UNVERIFIED`)로 내려가며 `.hwp`(레거시 바이너리)는 변환 필요 판정 유지. `AGENTS.md` 위임표의 없는 이름 `productivity:hwpx` → `prod:hwpx` 정정 포함. `gwaeop-simui` 동작은 회귀 테스트로 고정한 뒤 이동 (source: 같은 spec Solution §HWPX 추출 경로 공유) — `.claude/skills/gwaeop-simui/scripts/extract_bundle.py:30-44` · `.claude/skills/inbox-process/references/reference-branch.md:125` · `.claude/agents/inbox-reference-worker.md:58` · `AGENTS.md`

## PR #23 — [FIX] gate Inbox reference cleanup on a proven durable copy (2026-09-09)

- [ ] [risk] action 갈래는 삭제 게이트에서 전면 면제됐으나, 링크 형식이 안 맞을 뿐 `copy_verified.py verify`(존재 + SHA-256 일치)는 적용 가능하다. 첨부 복사가 조용히 실패하면 아무 검증 없이 공문 원본이 삭제된다 — 링크 실재 검사만 면제하고 사본 동일성 검사는 요구할지 결정 (source: code-review) — `.claude/skills/inbox-process/SKILL.md` 5단계-4 · `.claude/skills/inbox-process/references/action-branch.md`
