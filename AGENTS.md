# AGENTS — Obsidian Vault

Work log vault for 통합학사시스템 administrator. Notes only — no source code.
XML, Java, SQL, and procedure content comes from user-provided materials or existing notes.

## Docs Index

| File | When to read |
|------|-------------|
| `docs/architecture.md` | Deciding which folder a note belongs in |
| `docs/conventions.md` | Writing filenames, tags, frontmatter, **or MOC creation rules** |
| `docs/workflows.md` | Processing Inbox, creating incident/improvement notes, **or updating domain MOCs** |
| `docs/delegation.md` | Deciding which agent/skill to use |
| `docs/eval-criteria.md` | Evaluating note quality after creation — all agent context manifests reference this as the evaluation rubric |
| `docs/enforcement.md` | Enforcement layer status and how to strengthen it |
| `docs/runbook.md` | Diagnosing hook failures, checking skill trigger phrases, or looking up agent capabilities |
| `_Wiki/README.md` | Understanding the wiki layer structure (index·log·MOC·entities·topics·syntheses) |
| `_Wiki/workflow.md` | Cross-skill process flow **and search priority** (qmd → rg → index.md) — read before vault search or multi-skill chains |
| `_Wiki/contracts.md` | Source note / wiki page / synthesis / **operational MOC** document contracts |
| `_Wiki/index.md` | Vault topic map — starting point for exploring existing wiki pages |
| `_Wiki/log.md` | Append-only ingest/event log — write here after note creation or closure |
| `docs/migration-flat-areas.md` | One-time migration guide for flat `10_Areas/` notes (reference only) |

## Golden Principles

1. **Existing notes are immutable** — do not modify existing notes unless the user explicitly requests it.
2. **Follow templates** — new notes must use the matching template from `99_Template/`. Internal links use plain `[[노트명]]`; never `![[...]]` embeds unless explicitly requested.
3. **Normalize tags** — `#업무/` and `#부서/` tags follow `tag-normalize` skill rules. When uncertain, delegate to `tag-validator`. Mechanically enforced via `validate-tags.sh` PostToolUse hook.
4. **Follow folder rules** — no loose `.md` files in `12_Projects/` (folders only); no file creation in `90_Archive/`; `10_Areas/` depth max 2 levels (attachments → `YYYYMM_{slug}/` folder, slug ≤ 20 chars, inner file `YYYYMM_{summary}.md`, summary ≤ 60 chars). See `docs/conventions.md` → `10_Areas/ Depth Rules`.
5. **Inbox via skill** — all `01_Inbox/` processing (action + reference) must use the `inbox-process` skill.

## Workflow Gates

Workflow gate (not a Golden Principle — threshold-based): when a domain reaches 20+ notes or 3+ recurring incident types, create or update `_Wiki/topics/{도메인}-운영-MOC.md` (structure: `_Wiki/contracts.md`); register in `_Wiki/index.md` and `_Wiki/log.md`. Details: `docs/workflows.md` → `moc` workflow.

## Delegation — Quick Reference

Never perform these directly without the designated agent/skill:

| Task | Delegate to (skill → Skill tool · agent → Agent tool) |
|------|------------|
| Error log / incident analysis | `incident-analyst` agent |
| Improvement plan authoring | `improvement-planner` agent |
| Vault search / past cases | `vault-navigator` agent |
| Tag suggestion / validation | `tag-validator` agent |
| 노트 품질 평가 (생성 직후 게이트, `docs/eval-criteria.md` 루브릭) | `note-evaluator` agent |
| `01_Inbox/` document processing (공문·참고자료 모두) | `inbox-process` skill |
| Training note cleanup | `training-note-manager` agent |
| Obsidian note create/edit/open | `obsidian-operator` agent |
| Vault cleanup (Archive) | `vault-cleanup` skill |
| Status open→closed sync | `status-sync` skill |
| Syncthing conflict files | `syncthing-conflict-cleanup` skill |
| `.hwpx` 문서 생성/읽기/편집 | `productivity:hwpx` skill |
| 개선 완료/결과 안내 공문 초안 작성 | `draft-gongmun` skill |
| 주간업무회의 자료 생성 | `weekly-report` skill |
| 시스템 변경 이력 주간 보고서 생성 | `change-log` skill |
| Domain MOC 사전 조사 | `vault-navigator` agent |
| Domain MOC 노트 생성·등록 | `obsidian-operator` agent |

Full context manifest → `docs/delegation.md`

## Search Priority

Vault search order: `qmd` (semantic) → `rg`/grep (keyword) → `_Wiki/index.md` (topic map). Delegate to `vault-navigator` when scope is unclear or requires semantic matching. `qmd` index auto-refreshes via PostToolUse hook after every write.

## Branching

Direct-to-main: allowed — notes-only vault; no feature branches required.

<!-- commit-guard: allow-main -->

## Context Management

- Write `handoff-{feature}.md` at the **start** of long tasks, not when context is already full.
- When context overflows, prefer **reset** over compaction.
- Use this file as the entry point; load `docs/` files only on demand.

## Hard Stops — Always ask the user

- Task has 2+ valid interpretations.
- Same error repeats 2+ times.
- Modifying an existing note appears necessary (Golden Principle #1).

## Maintenance

Update this file **only** when ALL of the following are true:

1. The information is not directly discoverable from code / config / manifests / docs
2. It is operationally significant — affects build, test, deploy, or runtime safety
3. It would likely cause mistakes if left undocumented
4. It is stable and not task-specific

**Never add:** architecture summaries, directory overviews, style conventions enforced by tooling, anything visible in the repo, temporary or task-specific instructions.
