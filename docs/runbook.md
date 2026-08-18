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
- **스크립트**: `uv run .claude/skills/inbox-process/scripts/ocr_pdf.py "<pdf>" --pages 1-5` (페이지당 수 초; 대용량은 범위 샘플)
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
Run: incident-analyst agent  (reads .claude/agents/workflows/incident-analyze/WORKFLOW.md)
Input: PARAMETER_INFO, ERR_INFO, stack trace
Output: 14_Changes/incident/{year}/ note
```

### Create Improvement Plan

```
Run: improvement-planner agent  (reads .claude/agents/workflows/improvement-plan/WORKFLOW.md)
Input: change description, related SQL/procedure
Output: 14_Changes/improvement/{year}/ note
```

### Review a 과업심의 Request

```
Run: gwaeop-simui skill
Input: 심의자료 폴더 (01_Inbox/action/ 또는 10_Areas/과업심의/{회차}/{번호}/심의자료/)
Output: 지적사항 + 판정(안) → 10_Areas/과업심의/{회차}/..._심의의견.md (+ 요청 시 PDF)
Note: 회차 폴더 셋팅·서식 생성은 이 스킬이 아니라
      10_Areas/과업심의/과업심의_프로세스.md (Step 1~11)
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
| `gwaeop-simui` | 과업심의 검토, 심의위원이라면 | 심의자료 폴더 → 지적사항·판정(안) |
| `gongmun-draft` | 공문 작성, 결과 안내 공문 | 개선 노트 → 공문 본문 |
| `weekly-report` | 주간업무회의 자료 | Vault scan |
| `change-log` | 기능 개선 내역 | Vault scan (past week) |
| `status-sync` | status 동기화 | Vault scan |
| `syncthing-conflict-cleanup` | conflict 파일 정리 | Vault scan |
| `vault-cleanup` | 아카이브 정리 | Vault scan |

> 복합 볼트 작업(여러 스킬/에이전트 연계)은 `docs/delegation.md` § Multi-step Chains 참조.

## Agent Workflows — `.claude/agents/workflows/`

에이전트 한 곳만 읽는 절차서는 스킬이 아니다. 스킬로 등록하면 사용자용 스킬 목록에
"직접 호출하지 말 것" 항목이 상주하며 매 세션 description 토큰을 쓴다.

| 워크플로우 | 소유 에이전트 |
|-----------|-------------|
| `workflows/improvement-plan/WORKFLOW.md` | `improvement-planner` |
| `workflows/incident-analyze/WORKFLOW.md` | `incident-analyst` |
| `workflows/tag-normalize/WORKFLOW.md` | `tag-validator` |
| `workflows/training-manage/WORKFLOW.md` | `training-note-manager` |

각 폴더의 `references/`·`scripts/`는 해당 워크플로우 전용이다. 소비자가 둘 이상으로
늘어나면 스크립트는 `.claude/lib/`로 승격한다 (아래).

`check-nested-delegation.py`는 `/.claude/agents/` 경로 전체를 서브에이전트 대상 문서로
간주하므로, 이 폴더의 파일도 중첩 위임 린트를 그대로 받는다.

## Shared Scripts — `.claude/lib/`

소비자가 한 스킬을 넘어서는 결정론적 스크립트는 스킬 폴더가 아니라 `.claude/lib/`에 둔다.
스킬 안에 두면 그 스킬을 옮기거나 없앨 때 훅·에이전트·docs가 조용히 깨진다.

| 스크립트 | 호출처 |
|---------|-------|
| `.claude/lib/validate_tag.py` | `validate-tags.sh` 훅 · `incident-analyst`·`improvement-planner`·`training-note-manager` 에이전트 · `inbox-process` 스킬 · `improvement-plan` 워크플로우 |
| `.claude/lib/moc_gate.py` | `note-evaluator` 에이전트 · `inbox-process` 스킬 · `docs/workflows.md` sweep 헬스체크 |

소비자가 하나뿐인 스크립트는 그 자산의 `scripts/`에 남긴다 — 스킬이면 `{skill}/scripts/`
(`reorg_archive.py`, `ocr_pdf.py`), 워크플로우면 `workflows/{name}/scripts/`
(`new_improvement_path.py`, `new_incident_path.py`).

## Agent Reference

| Agent | Use when |
|-------|---------|
| `incident-analyst` | Error log diagnosis |
| `improvement-planner` | Improvement note authoring |
| `vault-navigator` | Past cases / vault search |
| `tag-validator` | 문맥 의존 태그 판정만 — 규칙 대조는 `validate_tag.py --json` 우선 (AGENTS.md 위임 비용 규칙 #2) |
| `obsidian-operator` | Create(템플릿)/open/프로퍼티/앱 내 JS — **기존 노트 소규모 수정은 직접 Edit** (규칙 #3) |
| `note-evaluator` | 생성 직후 품질 게이트 (`docs/eval-criteria.md`) |
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

### `pip install <pkg>` succeeds but `python -c "import <pkg>"` fails <!-- bare-python-ok: 맨 `python`의 Windows 해석 자체가 이 항목의 주제다 -->

> 이 항목의 `python`은 **Windows PowerShell 문맥**이다. 이 저장소의 훅·스크립트를 실행할 때는 `python3`를 쓴다.

**Symptom:** Bare `pip install X` reports success (or `python -m pip show X` even lists it installed), but `python -c "import X"` raises `ModuleNotFoundError`.
**Cause:** Bare `pip` resolves to a different Python than bare `python` — e.g. `pip` → `C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\pip.exe` (store-alias Python) while `python` → `C:\Users\<user>\AppData\Local\Programs\Python\Python313\python.exe`. Two separate site-packages trees.
**Fix:** Always install via the same interpreter you'll run: `python -m pip install X`, not bare `pip install X`. Verify with `(Get-Command python).Source` vs `(Get-Command pip).Source` if unsure they match.

### git status shows files as modified but git diff is empty

**Symptom:** `git status` lists many files as `modified`, but `git diff HEAD -- <file>` returns nothing for most of them (only a small subset actually has content changes).
**Cause:** `core.autocrlf=true` combined with `.gitattributes` forcing `eol=lf` on tracked files — a stat/mtime cache mismatch (racy git) flags files as possibly-modified without any real content difference. Confirm with `git update-index --refresh` (reports `needs update`) and `git ls-files --eol <file>` (shows `i/lf w/lf`, i.e. index and working tree already match).
**Fix:** Trust `git diff --stat HEAD` / `git diff HEAD --name-only` over the modified-file count in `git status` when scoping a commit — it reflects actual content changes. Do not assume every `git status` "modified" entry needs staging.

### `dev-tools:dev-review-cycle` PR step fails / reviews empty diff in this repo

**Symptom:** `dev-review-cycle --auto` preflight returns `feature_branch == base_branch == "main"`. Step 1's `--pr` create then fails or is meaningless (head branch == base branch), and Step 2 reviewers diffing `base_branch...HEAD` see an empty diff once the commit is already pushed to `main`.
**Cause:** This repo's `AGENTS.md` opts into direct-to-main (notes-only vault, no feature branches required — see global `CLAUDE.md` git-rule exception clause), so work often sits uncommitted on `main`. There is no CI (`.github/workflows/` absent). The skill's default flow assumes a feature branch distinct from base with a PR/CI loop.
**Fix:** **First run the open-PR check in the next entry** — it decides which of these two paths applies. If no PR carries this work: skip Step 0, commit on `main` and `git push origin main` directly (do not attempt `--pr`), and have Step 2 diff/review against the **parent commit** (`git rev-parse HEAD~1` before pushing, or the prior `git log` SHA) instead of `base_branch`, since `base_branch` now equals `HEAD`. Step 6 (CI wait) never applies — there is no CI; stop after Step 5. Note the vault *does* use PRs in practice (#12–#16) even though direct-to-main is permitted, so "no open PRs" must be verified, never assumed.

### review cycle on dirty `main` while an open PR already carries the same work

**Symptom:** `main` has a large uncommitted diff and looks like fresh work, but `gh pr list --state open` shows an open PR whose head branch does not exist locally. Committing to `main` here silently duplicates the PR and orphans it.
**Cause:** A previous session created the feature branch, pushed, opened the PR, then the local branch was deleted and `main` was left holding the same changes uncommitted. `git branch -a` shows only `main`, so nothing signals that the work is already published. Observed 2026-07-29 with PR #16 (`harness/delegation-cost-rules`, 2 commits) whose content was byte-identical to the uncommitted diff on `main`.
**Fix:** Before Step 0 of any review cycle started on a dirty base branch, run `gh pr list --state open --json number,headRefName,title`. If a PR exists, confirm it is the same work with a **content** diff, not history: `git fetch origin <headRef>` then `git diff origin/<headRef> --stat` from the dirty tree. Expect only known-benign deltas — untracked files (invisible to `git diff`), files committed to `main` after the branch forked (e.g. `.gitattributes`), and the `.agents/skills` mode artifact. If it matches, recreate the local branch **from `main` without touching the working tree** (`git checkout -b <headRef>`) and commit there, so the cycle updates the existing PR instead of forking a duplicate. Check `gh pr view <n> --json mergeable,mergeStateStatus` too — a `CONFLICTING` PR built on an older base is usually best replaced by the clean re-commit rather than merged as-is.

### `.agents/skills` shows git mode 100644 instead of 120000

**Symptom:** `git ls-files -s .agents/skills` reports mode `100644` (regular file) instead of `120000` (symlink); the file's content is the literal text `../.claude/skills` (17 bytes, no trailing newline).
**Cause:** This is a historical commit artifact, not a per-checkout side effect — confirmed empirically: a genuinely-committed symlink (mode `120000`) still reports `120000` via `git ls-files -s` even on a fresh `core.symlinks=false` clone (checkout capability does not downgrade the index mode). So the `100644` here means `.agents/skills` was `git add`ed from a working tree where it was *already* a plain text file (Windows, no symlink privilege, at commit time) — every clone (Windows or POSIX) inherits that same `100644` blob until someone with real symlink capability (Developer Mode) recreates the path and recommits it as a genuine `120000` object.
**Fix:** No action needed *for this repo's own code* — nothing here dereferences `.agents/skills` expecting real symlink semantics (`os.path.islink()` or similar); only `tasks.md`/`.gitignore` reference the path textually, and `symlink-guard.sh`'s Case 2 treats the current text-pointer form as valid, non-blocking state (exits 0). Caveat: this means `.agents/skills` does **not** function as a live directory symlink on *any* platform today, not just Windows — if Codex CLI or other external tooling ever needs to traverse `.agents/skills/` as a real directory (rather than just reading it as a static reference), this placeholder won't resolve anywhere, and the only real fix is recreating it as a genuine `120000` object on a machine with Developer Mode + real symlink support, then recommitting. Revisit if Codex reports actual skill-discovery failures (not just static mode-mismatch commentary) through this path.

### local branch diverged from `origin/main` after squash-merge PRs

**Symptom:** `git branch -vv` shows local `main` both ahead and behind `origin/main`; a local feature branch has commits with no matching hash upstream, even though the same work appears to already be merged.
**Cause:** This repo merges PRs via squash/rebase (see `dev-tools:dev-review-cycle` runbook entry above — actually direct-to-main here) or a parallel session re-did equivalent work under different commit hashes. Commit-level diffing (`git log branch..origin/main`) looks scary but is misleading — it compares history shape, not content.
**Fix:** Diagnose with **working-tree-vs-origin content diff**, not commit history: `git diff origin/main --stat` (run from the branch with all commits + uncommitted changes applied). If it shows near-zero diff, local work is already reflected upstream under different commits — safe to `git reset --hard origin/main` on `main` and drop the stale branch. Before deleting any branch (local or remote), confirm with `gh pr list --state all --json headRefName,state,mergedAt` that its PR is `MERGED`, not just that the diff looks small. Preserve any local-only files (e.g. gitignored-but-force-added files like `.gitattributes`) by `git show <old-branch>:<path>` before resetting.

### Agent tool spawn fails with `name` regex error on Korean folder/area names

**Symptom:** `Agent(name: "review-홈페이지")` (or similar Korean-labeled agent name) → `InputValidationError: name must start with a letter or digit and contain only letters, digits, underscores, or hyphens`.
**Cause:** Agent tool's `name` param is ASCII-only (`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`). This vault's areas/folders (`10_Areas/`, `90_Archive/areas/`) are Korean-named by convention, so any multi-agent fan-out keyed by area name hits this immediately.
**Fix:** Use a short ASCII slug for `name` (e.g. `review-homepage` for 홈페이지, `review-grades` for 수업성적) while keeping the Korean folder path in the `prompt`/`description`. Map slugs 1:1 to areas before spawning so results can be re-associated afterward.

### PostToolUse 훅 수동 테스트가 항상 "위반 없음"으로 나온다

**Symptom:** 위반이 명백한 샘플 파일을 만들어 훅에 먹였는데 출력이 비고 exit 0. 훅이 고장난 것처럼 보인다.
**Cause:** git-bash `$(pwd)`는 `/c/Dev/...` 형식을 준다. 훅은 Windows Python이라 `pathlib`이 이를 `C:\c\Dev\...`로 해석 → `path.is_file()` False → 조용히 exit 0. 실제 Claude Code는 `C:/...` 형식으로 넘기므로 런타임에는 정상.
**Fix:** 수동 테스트 시 `file_path`에 **Windows 경로**(`C:/Dev/ObsidianVault/...`)를 쓴다:

```bash
echo '{"tool_input":{"file_path":"C:/Dev/ObsidianVault/.claude/agents/incident-analyst.md"}}' \
  | python3 .claude/hooks/check-nested-delegation.py
```

무출력이 "위반 없음"인지 "경로 인식 실패"인지 구분하려면 위반 샘플로 true-positive를 먼저 확인할 것.

### 스킬 contract 테스트가 pytest로 수집되지 않는다

**Symptom:** `python3 -m pytest .claude/skills/status-sync/tests/test_contract.py` → `no tests ran`.
**Cause:** 테스트가 `.claude/`(dot-prefixed) 아래에 있고, pytest 형식(`test_*` 함수)이 아닌 **단독 실행 스크립트**다.
**Fix:** 직접 실행한다 — 성공 시 `OK — ...` 출력 + exit 0.

```bash
python3 .claude/skills/status-sync/tests/test_contract.py
```

### inbox-process skill cannot find template

**Symptom:** Skill fails with "template not found".  
**Cause:** `99_Template/` is missing the expected template file.  
**Fix:** Check `99_Template/` contents. Template name must match exactly what skill expects.

## Harness Asset Placement & Naming

새 하네스 자산(스킬·에이전트·워크플로우·스크립트)을 만들 때 적용한다. 기존 자산은
그대로 둔다 — 스킬 이름은 곧 호출 경로이고 문서 여러 곳이 참조하므로, 규약을 맞추려고
바꾸면 트리거 정확도만 잃는다.

**배치 — 소비자 수로 결정한다**

| 소비자 | 위치 |
|-------|-----|
| 사용자가 직접 호출 | `.claude/skills/{name}/SKILL.md` |
| 에이전트 1개만 읽는 절차서 | `.claude/agents/workflows/{name}/WORKFLOW.md` |
| 에이전트 여러 개가 읽는 절차서 | `.claude/agents/workflows/{name}.md` (예: `tag-writing.md`) |
| 스킬/에이전트 1개만 쓰는 스크립트 | 그 자산의 `scripts/` |
| 소비자가 둘 이상인 스크립트 | `.claude/lib/` |

"직접 호출하지 말 것"이라고 써야 하는 스킬은 스킬이 아니다 — 워크플로우로 만든다.

**이름 — `{도메인}-{동사}`, kebab-case, 영문**

`inbox-process` · `status-sync` · `incident-analyze` · `tag-normalize` · `training-manage`
· `improvement-plan` (여기서 `plan`은 동사).

동사 없이 산출물만 쓰지 않는다(`weekly-report`·`change-log`가 이 경우다 — 트리거 문구가
촘촘하고 서로 구분이 미묘해, 이름을 고쳐 얻는 일관성보다 트리거 정확도를 잃을 위험이 커
의도적으로 동결했다). 순서를 뒤집거나 로마자 한국어를 섞는 형태는 쓰지 않는다
(`draft-gongmun` → `gongmun-draft`로 정리 완료).

**`references/` 파일명**: 모드 분기는 `mode-{모드명}.md`. 모드가 아닌 분기는 예외이며
파일 상단에 이유를 적는다 (`inbox-process/references/{action,reference}-branch.md` —
action/reference는 실행 모드가 아니라 문서 분류 결과다).

에이전트 정의를 새로 만들 때는 `tools:` 화이트리스트 줄을 반드시 넣는다
(`docs/enforcement.md` § `tools:` 화이트리스트).

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
