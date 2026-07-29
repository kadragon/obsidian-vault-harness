# Tasks

## Review Backlog

### PR #8 — [HARNESS] rename 13_Routines to 11_Routines, enable humanize-korean plugin (2026-06-16)

- [x] [debt] `agents/skills` 심볼릭 링크 — `.agents/skills`와 동일 대상 중복, Windows `core.symlinks` 미확인 (source: pr-review-toolkit:review-pr, code-review) — `core.symlinks=true` 확인, `agents/skills` 중복 제거
- [x] [debt] `settings.json` 커뮤니티 플러그인(`humanize-korean@im-not-ai`)과 공식 플러그인 혼재 — 의도적 (공식 플러그인 전부 비활성, 커뮤니티 플러그인만 활성화된 정상 상태)

### PR #16 — [HARNESS] delegation cost rules (2026-07-24)

- [ ] [debt] 무첨부 래퍼 폴더 sweep 스크립트 — `check-folder-rules.py`의 60초 유예 때문에 최초 생성 경로에서 무첨부 래퍼가 검출되지 않음(재현 확인). PostToolUse 훅만으로는 잔존분을 못 잡으니 `10_Areas/` 전체를 훑어 "첨부 0 + .md 1개"인 래퍼 폴더를 목록화하는 스크립트를 `vault-cleanup` 스킬에 추가 (source: codex-review P2) — 상세: `docs/enforcement.md` → Folder Rules Hook §알려진 사각지대
- [ ] [harness] `validate-tags.sh`가 태그를 추출해 `validate_tag.py --json`에 파이프하도록 확장 — 현재 의미 수준 태그 검증(직급 매핑 등)을 자동으로 부르는 훅이 없어, 생성 워크플로 밖에서 쓴 노트는 형식 검사만 통과한다 (source: codex-review P2) — 상세: `docs/enforcement.md` → Retired: hookify.tag-validator §알려진 사각지대
- [ ] [doc] bare `python` 잔여 정리 — `.claude/skills/tag-normalize/scripts/validate_tag.py:5-7` docstring, `docs/runbook.md:18`(`ocr_pdf.py`). 둘 다 이번 브랜치 이전부터 있던 것이고 macOS에선 `~/.zshrc` alias로 동작하지만, canonical 문서(`tag-normalize/SKILL.md`)와 `settings.local.json`의 `Bash(python3 *)` allowlist는 `python3` 기준이다 (source: codex-review P1 → 검증자가 P3로 강등)

