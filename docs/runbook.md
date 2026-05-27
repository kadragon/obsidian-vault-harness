# Runbook

Vault operational cheat sheet. No build/deploy — vault is notes-only.

## Vault Location

`C:\dev\ObsidianVault` — synced via Syncthing. Obsidian opens this directory.

## Common Operations

### Process Inbox

```
Run: inbox-process skill
Input: 01_Inbox/ (action/ or reference/ subfolders)
Output: 10_Areas/{area}/ note or 19_Reference/_Sources/ entry
```

### Handle Incident

```
Run: incident-analyze skill  (or delegate to incident-analyst agent directly)
Input: PARAMETER_INFO, ERR_INFO, stack trace
Output: 14_Changes/incident/{year}/ note
```

### Create Improvement Plan

```
Run: improvement-plan skill  (or delegate to improvement-planner agent directly)
Input: change description, related SQL/procedure
Output: 14_Changes/improvement/{year}/ note
```

### Weekly Report

```
Run: weekly-report skill
Output: 주간업무회의 자료 draft
```

### System Change Log

```
Run: change-log skill
Output: 주간 기능 개선 내역 보고서
```

### Sync Note Statuses

```
Run: status-sync skill
Scope: 10_Areas/ and 14_Changes/
Effect: open notes with all tasks done → status: closed
```

### Clean Syncthing Conflicts

```
Run: syncthing-conflict-cleanup skill
Scope: entire vault
Effect: identical conflict files purged; differing ones reviewed
```

### Archive Stale Notes

```
Run: vault-cleanup skill
Scope: 10_Areas/ → 90_Archive/
```

## Skills Reference

| Skill | Trigger phrase | Entry point |
|-------|---------------|-------------|
| `inbox-process` | inbox 처리, 공문 처리 | `01_Inbox/` scan |
| `incident-analyze` | 에러 분석, 오류 처리 | Error log paste |
| `improvement-plan` | 개선 계획, 쿼리 수정 | Change description |
| `weekly-report` | 주간업무회의 자료 | Vault scan |
| `change-log` | 기능 개선 내역 | Vault scan (past week) |
| `status-sync` | status 동기화 | Vault scan |
| `syncthing-conflict-cleanup` | conflict 파일 정리 | Vault scan |
| `vault-cleanup` | 아카이브 정리 | Vault scan |
| `vault-orchestrate` | 볼트 작업 (복합) | Routes to right skill |

## Agent Reference

| Agent | Use when |
|-------|---------|
| `incident-analyst` | Error log diagnosis |
| `improvement-planner` | Improvement note authoring |
| `vault-navigator` | Past cases / vault search |
| `tag-validator` | Tag suggest or validate |
| `obsidian-operator` | Create/open/edit note in Obsidian |
| `training-note-manager` | Training note cleanup |
| `inbox-action-worker` | Sub-agent of inbox-process (action branch) |
| `inbox-reference-worker` | Sub-agent of inbox-process (reference branch) |
| `status-judge` | Sub-agent of status-sync |

## Common Failures

### validate-tags.sh fires on every edit

**Symptom:** Hook warnings appear after every Write/Edit to `.md` files.  
**Cause:** Correct behavior — hook is warning-only, not blocking.  
**Fix:** Review warning. If false positive, note exception. Hook lives at `.claude/hooks/validate-tags.sh`.

### Syncthing conflict files appear

**Symptom:** Files named `*.sync-conflict-*.md` in vault.  
**Cause:** Edit collision during sync.  
**Fix:** Run `syncthing-conflict-cleanup` skill.

### Note lands in wrong folder

**Symptom:** Agent created note at wrong path.  
**Cause:** Area mismatch or depth rule violation.  
**Fix:** Do not modify existing note (Golden Principle #1). Create correct note via skill; ask user to archive misplaced one manually.

### inbox-process skill cannot find template

**Symptom:** Skill fails with "template not found".  
**Cause:** `99_Template/` is missing the expected template file.  
**Fix:** Check `99_Template/` contents. Template name must match exactly what skill expects.

## Harness Maintenance

```bash
# Validate harness structure
bash /c/Users/KNUE/.claude/plugins/cache/kadragon/toolkit/1.13.0/skills/harness-init/scripts/validate-harness.sh

# Repair .agents/skills symlink
bash /c/Users/KNUE/.claude/plugins/cache/kadragon/toolkit/1.13.0/skills/harness-init/scripts/symlink-guard.sh

# Reconcile backlog with completed tasks
python /c/Users/KNUE/.claude/plugins/cache/kadragon/toolkit/1.13.0/skills/harness-init/scripts/reconcile-harness.py
```
