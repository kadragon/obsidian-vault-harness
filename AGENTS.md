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
| `docs/enforcement.md` | Enforcement layer status and how to strengthen it |
| `_Wiki/README.md` | Understanding the wiki layer structure (index·log·MOC·entities·topics·syntheses) |
| `_Wiki/contracts.md` | Source note / wiki page / synthesis / **operational MOC** document contracts |
| `docs/migration-flat-areas.md` | One-time migration guide for flat `10_Areas/` notes (reference only) |

## Golden Principles

1. **Existing notes are immutable** — do not modify existing notes unless the user explicitly requests it.
2. **Follow templates** — new notes must use the matching template from `99_Template/`.
3. **Normalize tags** — `#업무/` and `#부서/` tags follow `tag-normalizer` skill rules. When uncertain, delegate to `tag-validator`.
4. **Follow folder rules** — no loose `.md` files in `12_Projects/` (folders only). No file creation in `90_Archive/`.
5. **Inbox via skill** — all `01_Inbox/` processing (action + reference) must use the `inbox-process` skill.
6. **Wikilink style** — always write plain `[[노트명]]`. Never `![[...]]` (embed) unless explicitly requested.
7. **Wiki MOC feedback loop** — operational notes must feed back into `_Wiki/`. When a domain has 20+ notes or 3+ recurring incident types, create or update `_Wiki/topics/{도메인}-운영-MOC.md` (structure: `_Wiki/contracts.md`); register in `_Wiki/index.md` and `_Wiki/log.md`.
8. **`10_Areas/` depth max 2 levels** — no attachments → single `.md` at area root; with attachments → `YYYYMM_{slug}/` folder (slug ≤ 20 chars) containing `YYYYMM_{summary}.md` + attachments. Folder name and inner note name are intentionally different. Summary ≤ 60 chars. See `docs/conventions.md` → `10_Areas/ Depth Rules`.

## Delegation — Quick Reference

Never perform these directly without the designated agent/skill:

| Task | Delegate to |
|------|------------|
| Error log / incident analysis | `incident-analyst` agent |
| Improvement plan authoring | `improvement-planner` agent |
| Vault search / past cases | `vault-navigator` agent |
| Tag suggestion / validation | `tag-validator` agent |
| `01_Inbox/` document processing (공문·참고자료 모두) | `inbox-process` skill |
| Training note cleanup | `training-note-manager` agent |
| Obsidian note create/edit/open | `obsidian-operator` agent |
| **Vault work (single entry point — unsure which skill to use, or multi-step)** | **`vault-orchestrate` skill** — routes to the right agent/skill automatically |
| Vault cleanup (Archive) | `vault-cleanup` skill |
| Status open→closed sync | `status-sync` skill |
| Syncthing conflict files | `syncthing-conflict-cleanup` skill |
| 주간업무회의 자료 생성 | `weekly-report` skill |
| Domain MOC 사전 조사 | `vault-navigator` agent |
| Domain MOC 노트 생성·등록 | `obsidian-operator` agent |

Full context manifest → `docs/delegation.md`

## Branching

Direct-to-main: allowed — notes-only vault; no feature branches required.

## Context Management

- Write `handoff-{feature}.md` at the **start** of long tasks, not when context is already full.
- When context overflows, prefer **reset** over compaction.
- Use this file as the entry point; load `docs/` files only on demand.

## Hard Stops — Always ask the user

- Task has 2+ valid interpretations.
- Same error repeats 2+ times.
- Modifying an existing note appears necessary (Golden Principle #1).
