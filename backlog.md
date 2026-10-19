# Backlog

## Review Backlog

### PR #25 — [REFACTOR] make note-evaluator default to source fact-check table (2026-10-03)

- [ ] [verify] 새 평가자 계약의 실제 호출 1회 관찰 검증(spec Testing Decisions) — 에이전트 정의가 세션 시작 시 로드돼 같은 세션에서는 관찰 불가. 다음 inbox 처리에서 3-b 호출 시 표·`VERDICT`·`HOLD_DELETE` 반환 여부 확인 (source: task-next) — `.claude/agents/note-evaluator.md` *(deferred: live inbox run needed — agent definitions load at session start)*

### PR #33 — [HARNESS] rename vault skills to verb-suffixed names and add homepage-collect (2026-10-19)

- [ ] [debt] Generated round documents keep the source form's stale `Preview/PrvText.txt` (old project name, `[√] 승인`); regenerate or drop preview entries (source: codex) — `.claude/skills/gwaeop-simui-review/scripts/round_setup.py:274` (introduced here)
- [ ] [debt] `verify` compares on-disk Korean filenames without NFC normalization — macOS NFD names report as EXTRA (source: codex) — `.claude/skills/gwaeop-simui-review/scripts/round_setup.py:407` (introduced here)
- [ ] [debt] Manual links outside managed markers are resolved only against the collector output folder, so a valid hub link fails verification (source: codex) — `.claude/skills/homepage-collect/scripts/verify_notes.py:29` (introduced here)
- [ ] [debt] `find_hwpx_scripts` duplicates `hwpx_text.find_text_py` and lacks the Codex cache tier (source: code-review conf 45, agy P3) — `.claude/skills/gwaeop-simui-review/scripts/round_setup.py:43` (introduced here)
- [ ] [debt] Baseline read with `utf-8`, so a PowerShell 5.1 `>` redirect (BOM/UTF-16) is rejected as invalid; use `utf-8-sig` or an `--output` flag (source: code-review conf 40) — `.claude/lib/vault_lint.py:242` (introduced here)
- [ ] [debt] Generated homepage snapshot notes are stamped `type: project / status: active`; only the weekly collector's duplicated marker filters them out (source: code-review conf 45) — `.claude/skills/homepage-collect/scripts/render_notes.py:101` (introduced here)

## 레거시 메타데이터 참고 (2026-07-31 실측)

> 참고 — 이 PR과 무관한 선행 백로그가 더 크다. 볼트 477건 전수 스캔 시 `status:` 누락 **220건**(2026-07-31 재측정 — improvement 백필로 57건 해소), incident `change_type` 누락 79건. 태그 보완과는 별도 범위이며 이번 작업에서는 수정하지 않았다.
