# Tasks

## Review Backlog

### PR #8 — [HARNESS] rename 13_Routines to 11_Routines, enable humanize-korean plugin (2026-06-16)

- [x] [debt] `agents/skills` 심볼릭 링크 — `.agents/skills`와 동일 대상 중복, Windows `core.symlinks` 미확인 (source: pr-review-toolkit:review-pr, code-review) — `core.symlinks=true` 확인, `agents/skills` 중복 제거
- [x] [debt] `settings.json` 커뮤니티 플러그인(`humanize-korean@im-not-ai`)과 공식 플러그인 혼재 — 의도적 (공식 플러그인 전부 비활성, 커뮤니티 플러그인만 활성화된 정상 상태)

### PR #10 — [HARNESS] note-evaluator gate, status enum enforcement, MOC gate detector (2026-06-20)

- [ ] [debt] `check-folder-rules.py` 무첨부 래퍼 폴더 경고가 신규 노트 생성 직후(첨부 저장 전) 일시적 false-positive로 뜸 (source: agy) — `.claude/hooks/check-folder-rules.py:69`. 현재 경고문에 "첨부 곧 추가 시 무시" 안내가 있어 advisory로 완화돼 있으나, 에이전트 혼선 여지. 차단 아님이므로 보류 — 향후 noise 보고 시 grace 처리 검토.

