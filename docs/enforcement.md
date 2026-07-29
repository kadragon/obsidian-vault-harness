# Enforcement

Mechanical layers that prevent Golden Principle violations.

## Current Status

Notes-only vault — no git pre-commit / CI layer. Only Claude Code PostToolUse hooks are applicable.

| Golden Principle | Enforcement method | Status |
|-----------------|-------------------|--------|
| #1 Existing notes immutable | AGENTS.md rule + Hard Stop + 대량편집 dry-run 규율 | Doc-enforced (의도적) |
| #2 Follow templates | `check-template.py` PostToolUse hook (mechanical) | Shell-enforced (committed) |
| #3 Normalize tags (form) | `validate-tags.sh` PostToolUse hook (mechanical) | Shell-enforced (committed) |
| #3 Normalize tags (semantic) | 생성 워크플로가 `validate_tag.py --json` 호출 (script-first) → 문맥 의존 건만 `tag-validator` | Workflow-enforced (2026-07-24) — 훅 아님, 아래 사각지대 참조 |
| 위임 비용 규칙 #1 (중첩 위임 금지) | `check-nested-delegation.py` PostToolUse hook (mechanical) | Shell-enforced (committed) |
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

### Retired: `hookify.tag-validator.local.md` (agent delegation) — 2026-07-24

`enabled: false`. 은퇴 사유:

- **본문이 advisory가 아니었다.** 룰 본문은 "직접 검증하지 말 것 — 반드시 에이전트에 위임할 것"으로 강제였고, 이 문서의 과거 서술("advisory, not forced")과 어긋났다.
- **중복.** `validate-tags.sh`가 금지 접두어·괄호·미등록 area·`#부서` frontmatter 오배치를 이미 결정론적으로 검사하고, **위반이 있을 때만** "tag-validator 에이전트를 실행하세요" 경고를 낸다 → 필요할 때만 에이전트가 뜨는 구조가 이미 완성.
- **비용.** 위반이 없어도 태그 포함 쓰기마다 풀에이전트 기동(실측 ~39k 토큰 / 43초).

의미 수준 검증이 필요하면 `tag-normalize/scripts/validate_tag.py --json`으로 먼저 판정하고(직급 매핑·금지 접두어 제거까지 처리), 스크립트가 못 푸는 문맥 의존 건만 `tag-validator`로 에스컬레이션한다.

**알려진 사각지대 (2026-07-24):** `validate_tag.py`를 **자동으로 부르는 훅은 없다.** 호출 지점은 생성 워크플로(`inbox-process` 오케스트레이터 5단계, `incident-analyst`·`improvement-planner`·`training-note-manager` §태그 작성)뿐이다. 그 경로 밖에서 태그가 달린 노트를 직접 쓰면 남는 자동 검사는 `validate-tags.sh`(형식 수준: 금지 접두어·괄호·미등록 area·`#부서` frontmatter 오배치)뿐이라, **직급 매핑 같은 의미 수준 오류는 통과한다**. 근본 해결은 `validate-tags.sh`가 태그를 추출해 `validate_tag.py`에 파이프하는 것 → `tasks.md`.

## Nested Delegation Guard

### Active: `check-nested-delegation.py` (mechanical)

`.claude/hooks/check-nested-delegation.py`, `settings.json`의 `PostToolUse` `Write|Edit`에 등록.

**배경 (2026-07-24 실측):** 서브에이전트의 도구 목록에 `Agent`·`Task`가 **없다**(`Skill`·`Read`·`Write`·`Edit`·`Bash`·`Grep`·`Glob`는 있음). 그런데 `improvement-planner`·`incident-analyst`·`training-note-manager` 3개 정의가 `Agent(subagent_type: "tag-validator")`를 호출하도록 지시하고 있었다 → 런타임 **무음 실패**로 태그 작성이 조용히 누락됐다.

**검사 대상** (서브에이전트가 읽는 파일만): `.claude/agents/*.md` · `description`에 `Do NOT invoke directly`가 있는 **스킬 디렉터리 전체**(`SKILL.md` + `references/` 이하 모든 `.md`) · `inbox-process/references/{action,reference}-branch.md`.

**에이전트명 목록**은 `.claude/agents/*.md`에서 **런타임에 유도**한다. 하드코딩하면 에이전트 추가 시 갱신을 잊어 산문 탐지가 조용히 꺼진다 — 훅이 막으려는 바로 그 무음 실패다.

**검출:** `subagent_type` / `Agent(` / `Task(` / "{에이전트명} … 위임·호출·맡기·기동" + **어미** 패턴. 어미는 `한다`·`하라`·`할 것`·`할 수 있`·`해야`·`하도록`·`하고`·`하거나`·`하여`·`해서`·`한 뒤`와 **줄끝**·**여는 괄호 앞**까지 포함한다(명사형 `…에 위임`으로 끝나는 줄, `…에 위임 (`, `…에 위임하거나`가 실제 누락됐다). "위임 금지/불가", "호출할 수 없다" 같은 **부정문은 제외**(규칙을 문서화한 줄은 위반이 아님).

> **어미 그룹을 선택(`?`)으로 풀지 말 것.** 에이전트명 근처의 모든 `위임`·`호출`이 걸려, 규칙이 **권장하는** 표현("보고에 적어 메인 스레드가 호출하게 한다", "오케스트레이터가 수행한다", "incident-analyst 추가 호출 필요?로 반환")까지 오탐한다 — 실측 8건. `하게`·`하지`·` 불가`·` 필요`는 의도적으로 어미 목록에서 뺐다.

검증: 위반 6종(`Agent(subagent_type:…)`, `…에 위임한다`, `…를 위임할 수 있다`, 명사형 줄끝 `…에 위임`, `…에 위임하거나`, `…에 위임 (`) 탐지 + 부정문·"메인 스레드가 호출하게 한다" 무시 확인, 현행 하네스 전체 파일 스윕 **오탐 0**.

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
3. **`10_Areas/`** — depth > 2 levels, 무첨부 래퍼 폴더(첨부 없는데 폴더로 감쌈) → warn. 길이 제한(slug 20자·summary 60자)은 2026-07-24에 제거 — `conventions.md`가 "전체 제목, 길이 캡 없음"으로 확정됐다.
   - **알려진 사각지대 (2026-07-24 실측):** 래퍼 폴더 생성 후 `GRACE_SECONDS`(60초) 이내 Write는 검사를 통째로 건너뛴다. 첨부가 노트보다 늦게 저장되는 경우의 오탐을 막으려는 유예인데, 폴더·노트를 한 번에 만드는 **최초 생성 경로에서는 항상 유예에 걸려** 무첨부 래퍼가 잡히지 않는다(재현 확인: 신규 폴더 + 노트 Write → 무경고). 이후 같은 노트를 편집하면 검사된다. 1차 방어는 생성 측 `new_work_path.py --flat`. 잔존분 일괄 검출은 sweep 스크립트 필요 → `tasks.md`.
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
