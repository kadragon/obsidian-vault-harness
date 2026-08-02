# Delegation

The orchestrator plans, routes, and verifies. Heavy work goes to sub-agents.

## Routing Table

### Mandatory Gates (blocking)

If any trigger applies, delegate first — do not proceed without it.

| Trigger | Delegate to | Context to pass |
|---------|------------|----------------|
| Error log present (PARAMETER_INFO, ERR_INFO, stack trace) | `incident-analyst` | Full error log, menu path, date/time |
| Improvement/change plan requested | `improvement-planner` | Change description, related menu/procedure |
| File to process in `01_Inbox/` (action or reference) | `inbox-process` skill | File path or subfolder (`action/`/`reference/`) |
| Tag 검증 | **1차 `.claude/lib/validate_tag.py --json`** (결정론적). 스크립트가 못 푸는 문맥 의존 건만 `tag-validator` | Note content, mode: `suggest` or `validate` |
| Obsidian note create(템플릿)/open/프로퍼티 | `obsidian-operator` | Template name, save path, initial content |
| 기존 노트 소규모 수정 (수 줄·1~2파일) | **직접 Edit — 위임 금지** (AGENTS.md 위임 비용 규칙 #3) | — |
| Training note cleanup requested | `training-note-manager` | Training info, note path |

### Background Gates (non-blocking)

| Trigger | Delegate to | Context to pass |
|---------|------------|----------------|
| Past cases / similar notes needed | `vault-navigator` | Keywords, work domain |
| Periodic vault cleanup | `vault-cleanup` skill | — |
| Weekly system change report needed | `change-log` skill | Date range (default: past week) |
| Status open→closed sync needed | `status-sync` skill | — |
| Syncthing conflict files present | `syncthing-conflict-cleanup` skill | — |
| `.hwpx` 문서 작업 | `productivity:hwpx` skill | File path, operation type |
| 개선 완료/결과 안내 공문 초안 작성 | `draft-gongmun` skill | 개선 노트 경로 |
| Note created by agent (모든 생성 경로) | **메인 스레드가** 게이트 실행: 1차는 기계 검사(`check-template.py`·`validate-tags.sh`·`moc_gate.py`) + 훅이 못 잡는 잔여분 직접 확인(`#부서/` 부재·area 적합성·MOC 순방향 등록·**`10_Areas` 업무사안 외 노트 종류의 섹션 구조**), `note-evaluator`는 **조건 해당 시에만** 호출 (조건 목록 → `inbox-process/SKILL.md` 5단계-3-b). 생성자는 자기 노트를 평가하지 않는다 (AGENTS.md 위임 비용 규칙 #5) | note path, 워커가 반환한 추출본 경로 |

### Escalation

| Trigger | Action |
|---------|--------|
| Same error repeats 2+ times | Report to user and stop |
| Existing note modification appears necessary | Confirm with user (Golden Principle #1) |
| Unknown tag needed | Request user approval for new tag |

## Agent Context Manifests

### incident-analyst
- Required: PARAMETER_INFO block, ERR_INFO block, stack trace (if present)
- Optional: menu path (`#업무/`), department (`#부서/`), occurrence date/time
- Reference: `docs/architecture.md`, `docs/eval-criteria.md`

### improvement-planner
- Required: improvement description (free-form)
- Optional: related SQL, procedure name, UI menu path
- Reference: `docs/architecture.md`, `docs/conventions.md`, `docs/eval-criteria.md`

### vault-navigator
- Required: search intent (what are you looking for)
- Optional: work domain, date range, folder scope
- Specify thoroughness: `quick` | `medium` | `very thorough`
- Reference: `docs/eval-criteria.md`

### tag-validator
- Required: note content or path
- Required: mode — `suggest` (create tags) or `validate` (check existing tags)
- Reference: `tag-normalize` skill, `docs/eval-criteria.md`

### obsidian-operator
- Required: operation type (`create` | `open` | `append` | `prepend` | `set-property`)
- Required: save path or note name
- Optional: template name, initial frontmatter
- Reference: `docs/eval-criteria.md`

### training-note-manager
- Required: training name, date (or note path)
- Optional: content summary, quality evaluation requested
- Reference: `99_Template/_교육.md`, `docs/eval-criteria.md`

## Multi-step Chains

Single-step routing handles most requests. For compound requests, chain agents sequentially — pass previous output as context to the next.

| Request shape | Chain |
|---------------|-------|
| 에러 분석 + "개선 방안도 정리해줘" | `incident-analyst` → `improvement-planner` (pass incident note path) |
| "비슷한 에러 찾고 인시던트 노트 만들어줘" | `vault-navigator` → `incident-analyst` (pass search results) |
| "과거 사례 참고해서 개선안 작성해줘" | `vault-navigator` → `improvement-planner` (pass search results) |
| "정리해서 MOC에 반영해줘" / "synthesis 만들어줘" | `vault-navigator` → `obsidian-operator` (pass note paths) |

Pattern: collect prior agent's output (note path, summary) → inject into next agent's prompt explicitly.

## Delegation Principles

- Pass context as **file paths**, not inline content.
- Sub-agents have no conversation history — include all necessary background in the prompt.
- Structural changes returned by agents (folders, links) → apply in current cycle.
- Behavioral change suggestions returned by agents → confirm with user before applying.
