# Enforcement

Mechanical layers that prevent Golden Principle violations.

## Current Status

Notes-only vault — no git pre-commit / CI layer. Only Claude Code PostToolUse hooks are applicable.

| Golden Principle | Enforcement method | Status |
|-----------------|-------------------|--------|
| #1 Existing notes immutable | AGENTS.md rule + Hard Stop + 대량편집 dry-run 규율 | Doc-enforced (의도적) |
| #2 Follow templates | `check-template.py` PostToolUse hook (mechanical) | Shell-enforced (committed) |
| #3 Normalize tags (form) | `validate-tags.sh` PostToolUse hook (mechanical) | Shell-enforced (committed) |
| #3 Normalize tags (semantic) | `hookify.tag-validator.local.md` delegation reminder | Hookify-enforced (enabled) |
| #4 Folder rules | `check-folder-rules.py` PostToolUse hook (mechanical) | Shell-enforced (committed) |
| #2 Task date fields | `check-todo-due-date.py` PostToolUse hook (mechanical) | Shell-enforced |
| #5 Inbox (01_Inbox) via skill | AGENTS.md delegation rule | Doc-enforced |

### GP#1을 훅으로 막지 않는 이유 (의도적 결정, 2026-06)

기존 노트 편집을 PreToolUse로 차단하면 정상 워크플로(status-sync·tag-validator·note-evaluator·inbox-process 모두 기존 노트를 수정)가 깨진다. "사용자가 요청한 편집"과 "사고성 편집"을 구분할 기계 신호가 없다. PostToolUse는 쓰기 *후* 발화라 애초에 차단 불가. 실제 위험은 단일 Edit이 아니라 **Bash `sed -i`/스크립트 대량 변경**이며, 이건 Write|Edit 훅을 우회한다. 따라서 블런트 훅은 득보다 실(거짓양성·워크플로 파손)이 크다.

대신 규율로 막는다: **노트 대량 편집(frontmatter 백필·status 정규화·링크 치환) 전 항상 (1) 정확한 타깃만 anchored 매칭, (2) CRLF/LF sandbox 테스트(`open(newline="")` raw IO — `read_text()`는 CRLF를 LF로 무음 손상), (3) dry-run 매니페스트 확인 후 적용.** 노트는 gitignore라 되돌리기 없음(과거 정상 링크 358개 소실 사고).

## Todo Date Fields Validation Hook

### Active: `check-todo-due-date.py` (mechanical)

`.claude/hooks/check-todo-due-date.py`, registered in `settings.json` as `PostToolUse` on `Write|Edit`. Invoked via `$CLAUDE_PROJECT_DIR`-anchored path so CWD at hook fire time is irrelevant. Checks:

- Target: 모든 `.md` 파일 (templates/docs/harness/archive 제외)
- `- [ ]` 체크박스: `➕ YYYY-MM-DD` (추가일) + `📅 YYYY-MM-DD` (마감일) 필요
- `- [x]` 완료 체크박스: 위 두 필드 + `✅ YYYY-MM-DD` (완료일) 필요
- Warning-only (does not block). Zero token cost.

`validate-due-date.sh` (bash, `settings.local.json`)는 2026-05-27 retired — PS hook으로 통합 후 `check-todo-due-date.ps1` → `.py` 재작성 (2026-06, 인코딩 안정성).

## Tag Validation Hooks

### Active: `validate-tags.sh` (mechanical)

`.claude/hooks/validate-tags.sh`, registered in **`settings.json`** (committed) as `PostToolUse` on `Write|Edit`. Regex-based checks:

- Forbidden `#업무/` prefixes (e.g., `#업무/인트라넷/`, `#업무/학사/`)
- Parentheses in `#업무/` tags
- Unknown areas (outside allowed list)
- `#부서/` tags appearing in frontmatter

Skips: `.claude/`, `99_Template/`, `docs/` (harness docs contain tag examples that would false-positive).

Output: `hookSpecificOutput.additionalContext` JSON — same format as `check-todo-due-date.py`, so warnings appear in Claude's tool-result context. Warning-only (does not block). Zero token cost (this hook; hookify semantic layer has advisory token cost when triggered — see below).

### Active: `qmd-update.sh` (mechanical — machine-local)

`.claude/hooks/qmd-update.sh`, registered in `settings.local.json` as `PostToolUse` on `Write|Edit`. Refreshes the QMD semantic index after every note write:

- Runs `qmd update` then `qmd embed` (requires `qmd` binary — present on dev machine only)
- Silent on success; errors are non-blocking
- Machine-local only: `qmd` CLI is not portable, so this hook stays in `settings.local.json`

### Active: `hookify.tag-validator.local.md` (agent delegation)

`enabled: true`. On every `.md` write containing `#업무/` or `#부서/`, injects a delegation reminder to run `tag-validator` in `validate` mode. Prompt-based, advisory — the agent need not run every time. Complements `validate-tags.sh` (catches semantic area-assignment errors the regex hook cannot detect). Token cost: agent delegation is advisory, not forced.

## Template Check Hook

### Active: `check-template.py` (mechanical)

`.claude/hooks/check-template.py`, registered in `settings.json` as `PostToolUse` on `Write|Edit`. Checks:

- `![[...]]` embed anywhere in file → warn (GP#2: embeds forbidden unless explicitly requested)
- Empty wikilink placeholder `[[ ]]` anywhere in file (fenced code blocks excluded) → warn (GP#2: `## 관련 문서` 등 content-conditional 섹션은 근거 없으면 섹션째 생략 — 템플릿 섹션을 기계적으로 다 채우지 말 것; 2026-07)
- Missing `type:` frontmatter in note-bearing folders (`10_Areas`, `12_Projects`, `11_Routines`, `14_Changes`, `20_Training`) → warn (GP#2: use template from `99_Template/`)
- Missing `status:` OR non-enum value in note-bearing folders → warn. Allowed: `open|in-progress|hold|closed|active` (`_메타데이터 규칙.md` 5개 고정). Catches the `done`/`resolved`/`pending-action` drift that left status-sync blind (2026-06).

Skips: `99_Template`, `docs`, `.claude`, `90_Archive`, `_Wiki`, `_Sources`, `01_Inbox`, `_work`, `backlog.md`, `tasks.md`, `AGENTS.md`, `CLAUDE.md`. Warning-only, exit 0.

## Folder Rules Hook

### Active: `check-folder-rules.py` (mechanical)

`.claude/hooks/check-folder-rules.py`, registered in `settings.json` as `PostToolUse` on `Write`. Four path-only checks:

1. **`12_Projects/`** — loose `.md` at root (no sub-folder) → warn
2. **`90_Archive/`** — any write → warn (no file creation allowed)
3. **`10_Areas/`** — depth > 2 levels, attachment-folder slug > 20 chars, summary > 60 chars, 무첨부 래퍼 폴더(첨부 없는데 폴더로 감쌈) → warn
4. **`14_Changes/incident/`** — filename must match `통합학사시스템 오류 처리 {YYYY-MM-DD}_{순번}.md` (NFC-normalized) → warn. Blocks legacy drift patterns (`Error_*`, `오류 처리 *`, `_통합학사…`). Fires on `Write` only, so editing the ~96 pre-existing legacy notes is not nagged; new incident notes must use `incident-analyze` 스킬의 `new_incident_path.py`.

Warning-only, exit 0.

## Reinforcement Order

All three layers are now active. Promotion log:

1. ✅ GP #3 **semantic** tag errors → `hookify.tag-validator.local.md` enabled (2026-06)
2. ✅ GP #2 template non-use → `check-template.py` PostToolUse `Write` hook (2026-06)
3. ✅ GP #4 folder rule violations → `check-folder-rules.py` PostToolUse `Write` hook (2026-06)
4. ✅ Incident filename drift (`Error_*`/`오류 처리 *` vs canonical) → `check-folder-rules.py` Rule 4 (2026-06)
5. ✅ `validate-tags.sh` false positives on fenced/inline code → strips ` ``` ` blocks + `` `code` `` before tag extraction, so MOC Dataview/Tasks query tags and doc-example tags (`#업무/{도메인}`) no longer warn (2026-06)
6. ✅ Incident frontmatter completeness → `check-template.py` Check 3: `14_Changes/incident/` notes require `change_type: incident` + `status:` (2026-06)
7. ✅ status 어휘 드리프트 (`done`/`resolved`/`pending-action` vs status-sync의 `closed`) → `check-template.py` Check 2b: 모든 note-bearing 폴더에서 `status:` 필수 + enum 검증 (2026-06). 동시에 `conventions.md`·`_메타데이터 규칙.md`·`workflows.md` 종결 상태를 `closed`로 통일.
8. ✅ 무첨부 래퍼 폴더 (첨부 없는데 `{YYYYMM}_{slug}/` 폴더로 감쌈) → `check-folder-rules.py` Rule 3 확장 + `new_work_path.py --flat` 옵션 + `inbox-process` action-branch 문서화 (2026-06). conventions.md "No attachments → single .md" 규칙을 생성·검증 양쪽에서 기계화.
9. ✅ `## 관련 문서` 등 content-conditional 섹션을 근거 없이도 템플릿대로 채우다 빈 `[[ ]]` 플레이스홀더가 남는 문제 (2건 발견) → `check-template.py`에 빈 wikilink 감지 추가 + `action-branch.md`·`incident-analyze/SKILL.md`·`improvement-plan/SKILL.md`·`eval-criteria.md`·`conventions.md`에 "근거 없으면 섹션째 생략" 명시 (2026-07)

## Generator Config (not version-controlled)

`.obsidian/` is **gitignored** — these fixes live only on the local machine (Syncthing-synced), not in git:

- **Obsidian Linter timestamp format** (`.obsidian/plugins/obsidian-linter/data.json` → `yaml-timestamp.format`): was `YYYY-MM-DD HH:MM:SS` (moment.js `MM`=month, `SS`=fractional-second → minute slot showed month, seconds >59). Fixed to `YYYY-MM-DD HH:mm:ss` (2026-06). This was the root cause of ~485 impossible-timestamp frontmatter values vault-wide (since batch-corrected). `update-on-file-contents-updated: never` limits re-stamping. If `.obsidian` is reset/reinstalled, re-apply this format.
