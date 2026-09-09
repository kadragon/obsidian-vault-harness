# Backlog

## Review Backlog

### PR #22 — [HARNESS] add gwaeop-simui skill and PDF classifier front-end (2026-08-18)

- [ ] [debt] `extract_bundle.py` 의 `SKIP` 집합이 `.xlsx`·`.xls` 를 버려 산출내역서가 스프레드시트로 제출되면 금액·수량·VAT 근거가 번들 추출물에 남지 않는다 — 스프레드시트 추출 경로를 추가하거나 대체 리더를 명시 (source: codex) — `.claude/skills/gwaeop-simui/scripts/extract_bundle.py:23`
- [ ] [harness] Read 도구가 PDF를 못 읽는 근본 원인은 poppler(`pdftoppm`) 미설치다. 문서로 우회(PyMuPDF 경유)했을 뿐이므로 poppler 설치로 근본 해소할지 결정 (source: code-review) — 볼트 전역
