# Workflows

Recurring task patterns. Each workflow runs independently.

---

## `inbox` — Process 01_Inbox (unified)

Convert 공문·요청 into 업무사안 notes, and reference materials into `_Sources`/`_Wiki`. The skill routes between two branches.

1. Run `inbox-process` skill.
2. Skill scans three areas: `01_Inbox/` root, `action/`, `reference/`.
3. Root files → skill reads headers and proposes action/reference classification → moves to the appropriate subfolder after user confirmation.
4. **Action branch** (`01_Inbox/action/`): creates 업무사안 note using `99_Template/_업무사안.md`. Delegate tag authoring to `tag-validator`.
   - **No attachments** → single `10_Areas/{area}/YYYYMM_{summary}.md`
   - **With attachments** → `10_Areas/{area}/YYYYMM_{slug}/YYYYMM_{summary}.md` + attachments in same folder (slug ≤ 20 chars)
5. **Reference branch** (`01_Inbox/reference/`): creates/updates `19_Reference/_Sources/` source note and relevant `_Wiki/` pages; updates `_Wiki/index.md` and `_Wiki/log.md`.
6. Skill deletes processed originals after user confirmation.

---

## `incident` — Handle Incident

When a 통합학사시스템 error occurs.

1. Delegate error log to `incident-analyst` agent — provide: PARAMETER_INFO, ERR_INFO, stack trace.
2. After diagnosis, use `obsidian-operator` agent to create incident note.
   - Template: `99_Template/_인시던트.md` · Path: `14_Changes/incident/{year}/`
3. Delegate tag authoring to `tag-validator` agent.
4. After resolution, update note `status: done` (on user request).

---

## `improve` — Improvement Plan

Feature additions, query fixes, UI changes.

1. Delegate to `improvement-planner` agent.
2. Review generated note.
   - Path: `14_Changes/improvement/{year}/` · Template: `99_Template/_개선.md`
3. For past-case research, use `vault-navigator` agent.

---

## `training` — Training Note

After attending education/training.

1. Delegate to `training-note-manager` agent.
2. Agent applies template (`99_Template/_교육.md`) and evaluates quality.
3. Path: `20_Training/`

---

## `search` — Past Cases

Find similar incidents, past improvements, related notes.

1. Delegate to `vault-navigator` agent — provide: keywords, work domain.
2. Agent returns matches via Glob/Grep/QMD semantic search.

---

## `moc` — Create/Update Operational MOC

Create or update a domain MOC when: (a) a domain has 20+ notes, or (b) the same incident type has recurred 3+ times.

1. Delegate to `vault-navigator` — provide domain name and scope (`10_Areas/{domain}/`, `14_Changes/` filtered by `#업무/{domain}`). Request: note inventory (title·tag·status·1-line summary) + pattern analysis (monthly volume, recurring incident types, open items, related departments).
2. Review inventory. Identify: seasonal calendar, top-3 recurring incident patterns, open items, key entities.
3. Delegate to `obsidian-operator` — pass inventory + MOC spec from `_Wiki/contracts.md` → Operational MOC section. Save path: `_Wiki/topics/{도메인}-운영-MOC.md`.
4. After creation: add entry to `_Wiki/index.md` Topics section and append to `_Wiki/log.md`.
5. Trigger conditions for **updating** an existing MOC:
   - New incident of a known type → add wikilink to pattern section.
   - Seasonal period changes → update calendar section.
   - Static snapshot → refresh quarterly.

---

## `sweep` — Vault Health Check

Run periodically (between feature completions, or monthly).

1. `vault-cleanup` skill: check 90_Archive and 10_Areas.
2. Review unresolved manual items in `plan.md`.
3. Audit AGENTS.md rules for continued validity.

---

## Context Anxiety

For long multi-step tasks:
- Write `handoff-{task}.md` **at the start** (don't wait until context is full).
- Prefer **reset** over compaction when context overflows.
- Include in handoff: goal, completed steps, next steps, open decisions.
- Delete handoff file when task is complete.
