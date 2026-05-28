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
| Tag rule uncertain | `tag-validator` | Note content, mode: `suggest` or `validate` |
| Obsidian note create/open requested | `obsidian-operator` | Template name, save path, initial content |
| Training note cleanup requested | `training-note-manager` | Training info, note path |

### Background Gates (non-blocking)

| Trigger | Delegate to | Context to pass |
|---------|------------|----------------|
| Past cases / similar notes needed | `vault-navigator` | Keywords, work domain |
| Complex multi-step vault task | `vault-orchestrate` skill | Full task goal |
| Periodic vault cleanup | `vault-cleanup` skill | — |
| Weekly system change report needed | `change-log` skill | Date range (default: past week) |
| Status open→closed sync needed | `status-sync` skill | — |
| Syncthing conflict files present | `syncthing-conflict-cleanup` skill | — |
| `.hwpx` 문서 작업 | `toolkit:hwpx` skill | File path, operation type |

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
- Reference: `tag-normalizer` skill, `docs/eval-criteria.md`

### obsidian-operator
- Required: operation type (`create` | `open` | `append` | `prepend` | `set-property`)
- Required: save path or note name
- Optional: template name, initial frontmatter
- Reference: `docs/eval-criteria.md`

### training-note-manager
- Required: training name, date (or note path)
- Optional: content summary, quality evaluation requested
- Reference: `99_Template/_교육.md`, `docs/eval-criteria.md`

## Delegation Principles

- Pass context as **file paths**, not inline content.
- Sub-agents have no conversation history — include all necessary background in the prompt.
- Structural changes returned by agents (folders, links) → apply in current cycle.
- Behavioral change suggestions returned by agents → confirm with user before applying.
