# Backlog

## Review Backlog

### PR #25 — [REFACTOR] make note-evaluator default to source fact-check table (2026-10-03)

- [ ] [verify] 새 평가자 계약의 실제 호출 1회 관찰 검증(spec Testing Decisions) — 에이전트 정의가 세션 시작 시 로드돼 같은 세션에서는 관찰 불가. 다음 inbox 처리에서 3-b 호출 시 표·`VERDICT`·`HOLD_DELETE` 반환 여부 확인 (source: task-next) — `.claude/agents/note-evaluator.md` *(deferred: live inbox run needed — agent definitions load at session start)*

### Public history scrub — personal data in past commits (2026-10-19)

- [ ] [security] Follow-ups to the history scrub: GitHub Support purge request for `refs/pull/1..34/head` and cached commit views (submitted 2026-10-24 — await GitHub's reply; done when old PR head SHAs, e.g. #34 `2be1b43c05aa`, no longer resolve via `gh api repos/kadragon/obsidian-vault-harness/commits/<sha>`); reset the Syncthing peer clone to `origin/main`; delete the pre-scrub mirror backup (`vault-backup.git` in the 2026-10-23 session scratchpad) once confirmed.

## 레거시 메타데이터 참고 (2026-07-31 실측)

> 참고 — 이 PR과 무관한 선행 백로그가 더 크다. 볼트 477건 전수 스캔 시 `status:` 누락 **220건**(2026-07-31 재측정 — improvement 백필로 57건 해소), incident `change_type` 누락 79건. 태그 보완과는 별도 범위이며 이번 작업에서는 수정하지 않았다.
