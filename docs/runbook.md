# Runbook

Vault operational cheat sheet. No build/deploy — vault is notes-only.

## Vault Location

Syncthing으로 다중 기기 동기화. OS별 경로:
- **macOS**: `/Users/kadragon/ObsidianVault`
- **Windows**: `C:\dev\ObsidianVault`

## Environment

### Image-PDF OCR (scanned reference PDFs)

이미지(스캔) PDF는 Read/`pdftotext`로 텍스트가 안 나온다. OCR로 추출한다.

- **도구**: PyMuPDF(`fitz`) + Tesseract 5.x. `pdftoppm` 불필요.
- **스크립트**: `python .claude/skills/inbox-process/scripts/ocr_pdf.py "<pdf>" --pages 1-5` (페이지당 수 초; 대용량은 범위 샘플)
- **언어 데이터**: `kor`+`eng` → `%TESSDATA_PREFIX%` (`~/tessdata/`). 사용자 env에 영구 등록됨.
- **재구축** (새 머신): `winget install UB-Mannheim.TesseractOCR` → `kor.traineddata`(tessdata_best)를 쓰기 가능 디렉터리에 두고 `TESSDATA_PREFIX` 지정 + Tesseract를 PATH에. Program Files tessdata는 쓰기 권한 없음 — 홈에 둘 것.

## Common Operations

### Process Inbox

```
Run: inbox-process skill
Input: 01_Inbox/ (action/ or reference/ subfolders)
Output: 10_Areas/{area}/ note or _Sources/ entry
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
| `incident-analyze` | 에러 분석, 오류 처리 | → `incident-analyst` agent |
| `improvement-plan` | 개선 계획, 쿼리 수정 | → `improvement-planner` agent |
| `draft-gongmun` | 공문 작성, 결과 안내 공문 | 개선 노트 → 공문 본문 |
| `weekly-report` | 주간업무회의 자료 | Vault scan |
| `change-log` | 기능 개선 내역 | Vault scan (past week) |
| `status-sync` | status 동기화 | Vault scan |
| `syncthing-conflict-cleanup` | conflict 파일 정리 | Vault scan |
| `vault-cleanup` | 아카이브 정리 | Vault scan |

> 복합 볼트 작업(여러 스킬/에이전트 연계)은 `docs/delegation.md` § Multi-step Chains 참조.

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

### vault-navigator returns path that does not exist

**Symptom:** `vault-navigator` result에 포함된 파일 경로로 `Read`하면 "File does not exist" 오류.  
**Cause:** QMD 인덱스가 경로를 정규화함 — 공백과 언더스코어를 하이픈으로 변환. 반환 경로는 QMD 내부 경로이며 실제 OS 경로와 다를 수 있음.  
**Fix:** `vault-navigator` 경로를 `Read`하기 전에 `Glob`으로 실제 경로를 먼저 확인. 예: 디렉터리 패턴 `10_Areas/강사료퇴직금/**/*.md`로 후보 확인 후 정확한 경로로 `Read`.

### Grep tool returns no results for files under Korean-named folders

**Symptom:** `Grep` (ripgrep-backed) returns "No files found" even when a file with matching content demonstrably exists (confirmed via `Read`/`Glob`) under a Korean-named nested path, e.g. `14_Changes/incident/2024/상반기/*.md`.
**Cause:** Suspected Unicode normalization mismatch (NFC/NFD) on Korean directory/file names in this Syncthing-synced vault — same root class of issue as the conflict-file NFC normalization handled by `syncthing-conflict-cleanup`.
**Fix:** Fall back to PowerShell: `Get-ChildItem -Path "<dir>" -Filter *.md -Recurse | Select-String -Pattern "<term>" -List | Select-Object -ExpandProperty Path`. Do NOT use a `**` glob string with `Select-String -Path` directly — PowerShell 5.1 does not expand `**`; use `Get-ChildItem -Recurse` instead. Prefer `qmd search`/`vsearch` as the first search layer (per `_Wiki/workflow.md`) since it is unaffected by this issue; reserve Grep/PowerShell fallback for exact-string confirmation.

### python invocation fails on Windows (hwpx skill scripts etc.)

**Symptom:** `python3`/`python` via Bash tool → `Permission denied` (resolves to WindowsApps stub). `py` launcher via PowerShell → garbled/failed on Korean (non-ASCII) filenames/args.
**Cause:** `C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python*.exe` are store-alias stubs, not a real interpreter. `py.exe` launcher mis-encodes non-ASCII argv in some environments.
**Fix:** Call the real interpreter directly via PowerShell (not Bash), e.g. `& "C:\Users\<user>\AppData\Local\Programs\Python\Python313\python.exe" script.py args...`. Locate installed versions with `py -0p`.

### git status shows files as modified but git diff is empty

**Symptom:** `git status` lists many files as `modified`, but `git diff HEAD -- <file>` returns nothing for most of them (only a small subset actually has content changes).
**Cause:** `core.autocrlf=true` combined with `.gitattributes` forcing `eol=lf` on tracked files — a stat/mtime cache mismatch (racy git) flags files as possibly-modified without any real content difference. Confirm with `git update-index --refresh` (reports `needs update`) and `git ls-files --eol <file>` (shows `i/lf w/lf`, i.e. index and working tree already match).
**Fix:** Trust `git diff --stat HEAD` / `git diff HEAD --name-only` over the modified-file count in `git status` when scoping a commit — it reflects actual content changes. Do not assume every `git status` "modified" entry needs staging.

### `.agents/skills` shows git mode 100644 instead of 120000

**Symptom:** `git ls-files -s .agents/skills` reports mode `100644` (regular file) instead of `120000` (symlink); the file's content is the literal text `../.claude/skills` (17 bytes, no trailing newline).
**Cause:** Windows checkout without symlink privilege (Developer Mode + `core.symlinks=true`) cannot materialize a real symlink, so the checkout falls back to a plain text file containing the link target. This is the harness's own documented **Case 2** fallback in `symlink-guard.sh` (find current copy via `find ~/.claude/plugins/cache/kadragon/dev-tools -name symlink-guard.sh`) — the script's comment explicitly names a regular file containing exactly `../.claude/skills` as "the correct representation" for a `core.symlinks=false` checkout, and treats it as a success case, not an error.
**Fix:** Do nothing — this is expected, not a bug. Running `symlink-guard.sh` against the repo exits 0 silently, confirming Case 2 is satisfied. Do not "fix" by adding `.agents/skills` to `.gitignore` or by setting `core.symlinks=true` alone: flipping the local config does not retroactively change the *already-committed blob's mode* — that would additionally require Developer Mode enabled and recreating the path as a real symlink (`rm .agents/skills && ln -s ../.claude/skills .agents/skills && git add .agents/skills`), which is unnecessary since Case 2 is already valid. Nothing in this repo reads `.agents/skills` expecting real symlink semantics (`os.path.islink()` or similar) — only `tasks.md`/`.gitignore` reference the path textually.

### inbox-process skill cannot find template

**Symptom:** Skill fails with "template not found".  
**Cause:** `99_Template/` is missing the expected template file.  
**Fix:** Check `99_Template/` contents. Template name must match exactly what skill expects.

## Harness Maintenance

Plugin: `kadragon/dev-tools` (versioned cache — locate current scripts per OS below).

**macOS (zsh/bash):**
```bash
SCRIPTS=$(find ~/.claude/plugins/cache/kadragon/dev-tools -name "validate-harness.sh" | sort -V | tail -1 | xargs dirname)
bash "$SCRIPTS/validate-harness.sh"
bash "$SCRIPTS/symlink-guard.sh"
python3 "$SCRIPTS/reconcile-harness.py"
```

**Windows (PowerShell):**
```powershell
$SCRIPTS = Get-ChildItem "$env:USERPROFILE\.claude\plugins\cache\kadragon\dev-tools" -Recurse -Filter "validate-harness.sh" | Sort-Object FullName | Select-Object -Last 1 | Split-Path
bash "$SCRIPTS/validate-harness.sh"
bash "$SCRIPTS/symlink-guard.sh"
python3 "$SCRIPTS/reconcile-harness.py"
```
