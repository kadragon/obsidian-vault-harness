# Tasks

## Review Backlog

### PR #8 — [HARNESS] rename 13_Routines to 11_Routines, enable humanize-korean plugin (2026-06-16)

- [x] [debt] `agents/skills` 심볼릭 링크 — `.agents/skills`와 동일 대상 중복, Windows `core.symlinks` 미확인 (source: pr-review-toolkit:review-pr, code-review) — `core.symlinks=true` 확인, `agents/skills` 중복 제거
- [x] [debt] `settings.json` 커뮤니티 플러그인(`humanize-korean@im-not-ai`)과 공식 플러그인 혼재 — 의도적 (공식 플러그인 전부 비활성, 커뮤니티 플러그인만 활성화된 정상 상태)

### PR #16 — [HARNESS] delegation cost rules (2026-07-24)

- [ ] [debt] 무첨부 래퍼 폴더 sweep 스크립트 — `check-folder-rules.py`의 60초 유예 때문에 최초 생성 경로에서 무첨부 래퍼가 검출되지 않음(재현 확인). PostToolUse 훅만으로는 잔존분을 못 잡으니 `10_Areas/` 전체를 훑어 "첨부 0 + .md 1개"인 래퍼 폴더를 목록화하는 스크립트를 `vault-cleanup` 스킬에 추가 (source: codex-review P2) — 상세: `docs/enforcement.md` → Folder Rules Hook §알려진 사각지대

