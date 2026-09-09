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
| `docs/harness-log.md` | Harness edits with falsifiable predictions — read before re-auditing or removing a harness asset |
| `docs/design/*.md` | 다중 세션 작업의 승인된 설계 문서를 확인하거나 후속 티켓의 근거를 찾을 때 |
| `docs/runbook.md` | Diagnosing hook failures, checking skill trigger phrases, looking up agent capabilities, **or placing/naming a new harness asset (skill·agent·workflow·script)** |
| `_Wiki/README.md` | Understanding the wiki layer structure (index·log·MOC·entities·topics·syntheses) |
| `_Wiki/workflow.md` | Cross-skill process flow **and search priority** (qmd → rg → index.md) — read before vault search or multi-skill chains |
| `_Wiki/contracts.md` | Source note / wiki page / synthesis / **operational MOC** document contracts |
| `_Wiki/index.md` | Vault topic map — starting point for exploring existing wiki pages |
| `_Wiki/log.md` | Append-only ingest/event log — write here after note creation or closure |
| `docs/migration-flat-areas.md` | One-time migration guide for flat `10_Areas/` notes (reference only) |
| `docs/migration-googledrive.md` | Handling `C:\Dev\GoogleDrive` files, or checking what was already ingested into `_Sources/` |

## Golden Principles

1. **Existing notes are immutable by default** — edit an existing note only within a user-authorized scope; a general processing request does not authorize unrelated existing-body edits. The scope may name a note class or domain rather than every file, including `_Sources/` or `_Wiki/` updates. Notes created in the current task may be corrected before handoff.
2. **Follow templates** — new notes must use the matching template from `99_Template/`. Internal note links use plain `[[노트명]]`; `![[...]]` is allowed for file attachments and otherwise requires an explicit request. 기계 판정은 `.claude/lib/note_rules.py` Check 1.
3. **Normalize tags** — `#업무/` and `#부서/` tags follow the `tag-normalize` agent workflow rules. When uncertain, delegate to `tag-validator`. Mechanically enforced via `validate-tags.sh` PostToolUse hook.
4. **Follow folder rules** — no loose `.md` files in `12_Projects/` (folders only); no file creation in `90_Archive/`; `10_Areas/` depth max 2 levels (attachments → `YYYYMM_{summary}/` folder using the full title, inner file `_YYYYMM_{summary}.md` with `_` prefix; no attachments → single `.md` at area root, no wrapper folder). See `docs/conventions.md` → `10_Areas/ Depth Rules`.
5. **Inbox via skill** — all `01_Inbox/` processing (action + reference) must use the `inbox-process` skill. A single clear inline/plaintext item, including one `.txt`/`.md` file, may be executed by the main thread under the same procedures and gates; multi-item work uses the branch workers.

## Workflow Gates

Workflow gate (not a Golden Principle — threshold-based): when a domain reaches 20+ notes or 3+ recurring incident types, create or update `_Wiki/topics/{도메인}-운영-MOC.md` (structure: `_Wiki/contracts.md`); register in `_Wiki/index.md` and `_Wiki/log.md`. Details: `docs/workflows.md` → `moc` workflow.

## Delegation — Quick Reference

Never perform these directly without the designated agent/skill:

| Task | Delegate to (skill → Skill tool · agent → Agent tool) |
|------|------------|
| Error log / incident analysis | `incident-analyst` agent |
| Improvement plan authoring | `improvement-planner` agent |
| Vault search / past cases | `vault-navigator` agent |
| Tag 검증·정규화 | **1차: `.claude/lib/validate_tag.py --json`** (결정론적) · 문맥 의존 건만 `tag-validator` agent |
| 노트 품질 평가 (기본: 원본 대조 사실검증; 명시 요청 시 full-quality 5축) | `note-evaluator` agent |
| `01_Inbox/` document processing (공문·참고자료 모두) | `inbox-process` skill |
| 과업심의 요청 검토 (위원 관점 지적·판정) | `gwaeop-simui` skill |
| Training note cleanup | `training-note-manager` agent |
| Obsidian note **create**(템플릿 적용)·open·프로퍼티·앱 내 JS | `obsidian-operator` agent |
| 기존 노트 본문 **소규모 수정**(수 줄·1~2파일) | 직접 Edit — 위임 금지 (§Delegation 비용 규칙) |
| Vault cleanup (Archive) | `vault-cleanup` skill |
| Status open→closed sync | `status-sync` skill |
| Syncthing conflict files | `syncthing-conflict-cleanup` skill |
| `.hwpx` 문서 생성/읽기/편집 | `productivity:hwpx` skill |
| 대외 발신 문서 초안(공문·회신·안내·업무 메일) | `gongmun-draft` skill |
| 납품 산출물 검수 + 수행사 보완요구 메일 | `deliverable-review` skill |
| 주간업무회의 자료 생성 | `weekly-report` skill |
| 시스템 변경 이력 주간 보고서 생성 | `change-log` skill |
| Domain MOC 사전 조사 | `vault-navigator` agent |
| Domain MOC 노트 생성·등록 | `obsidian-operator` agent |

Full context manifest → `docs/delegation.md`

### 위임 비용 규칙 (2026-07-24 확립)

1. **서브에이전트는 다른 서브에이전트를 호출할 수 없다 — 단 이건 정의로 강제해야 참이 된다.** 실측 정정(2026-08-02): 에이전트 정의 frontmatter에 `tools:`가 없으면 **`Agent`를 그대로 상속**한다. 이 상태에서 `inbox-reference-worker`가 자기 자신을 자식으로 띄우고 **결과를 기다리지 않고 즉시 반환**해, 메인 스레드가 산출물 0건으로 오판 → 재디스패치 → 두 워커가 같은 배치를 중복 처리했다(228k 토큰 + 중복 노트). 무음 실패가 아니라 **async 위임 후 고아 자식**이 실제 실패 모드다.

   따라서 `.claude/agents/*.md` 전부에 `tools:` 화이트리스트를 명시해 `Agent`·`Task`·`Workflow`를 제외한다(`Bash, Read, Write, Edit, Glob, Grep, Skill, WebFetch, WebSearch, ToolSearch`). 새 에이전트를 추가할 때도 이 줄을 반드시 넣는다 — 빠뜨리면 규칙이 조용히 무효가 된다.

   위임이 꼭 필요하면 **보고에 적어 메인 스레드가 호출**하게 한다. `check-nested-delegation.py` 훅은 **산문 위임 지시만** 잡는 문서 린터다(런타임 Agent 호출은 검사 범위 밖) — 런타임 차단은 위 `tools:` 화이트리스트가 담당한다.
2. **스크립트 우선.** 규칙표 대조·경로 계산·해시 비교처럼 결정론적인 일은 스크립트로 끝내고, **판단이 필요한 잔여분만** 에이전트로 에스컬레이션한다 (status-sync·vault-cleanup·syncthing-cleanup이 이 패턴).
3. **소규모 편집은 직접.** 수 줄·1~2파일 수정에 풀에이전트 왕복(수만 토큰·수십 초)은 금지. `_Wiki/log.md` 한 줄 append도 직접 Edit.
4. **검증자 ≥ 생성자.** 품질 게이트 에이전트의 모델은 생성자와 같거나 강해야 한다.
5. **품질 게이트는 메인 스레드 책임 — 기계 검사가 1차, `note-evaluator`의 기본 모드는 원본 대조 사실검증** (2026-07-30 개정). 노트 생성 에이전트(`improvement-planner`·`incident-analyst`·`training-note-manager`·`inbox-action-worker`)가 반환하면 메인 스레드가 게이트를 돌린다. 생성자가 스스로 부를 수 없고(규칙 #1), 불러서도 안 된다(self-preference).

   `docs/eval-criteria.md`의 기계 검사 결과와 워커가 반환한 추출 자료를 재사용한다. 기본 평가 출력은 필드·원본 값·노트 값·결과(`PASS`/`FAIL`/`UNVERIFIED`) 표다. 값 불일치는 `FAIL`, 원본 부재는 `UNVERIFIED`로 처리하고 원본 삭제를 허용하지 않는다. 5개 기준 5축 평가는 사용자가 명시적으로 full-quality를 요청한 경우에만 수행한다. `20_Training/`의 `#업무/` 부재는 위반이 아니다.

   호출 조건·스코프 한정은 `inbox-process/SKILL.md` 5단계-3. 호출 시에도 구조·태그 재채점 금지, 원본 재추출 금지(워커가 반환한 추출 경로 재사용).

   FAIL이면 지적 항목을 수정한 뒤 사용자에게 보고한다. `UNVERIFIED`이면 원본 확인 전 삭제를 보류한다.

6. **기준을 쓸 때 "How to test"가 결정론적이면 훅/스크립트로 만든다.** 안 만들면 그 비용은 매 산출물마다 LLM 토큰으로 청구된다 — `eval-criteria.md` Template Adherence가 헤딩 대조 훅 없이 운영돼 노트 1건당 101k를 태운 사례(2026-07-30, `docs/enforcement.md` 승격 로그 #13). 동시에 **기준은 실측 관행과 대조해 쓴다**: 같은 사례에서 LLM 평가자가 템플릿 문자 그대로 채점해 다수 관행(`## 🙋‍♂️ 관련` 116/202건)을 위반으로 오판했다.

## Search Priority

Vault search order: `qmd` (semantic) → `rg`/grep (keyword) → `_Wiki/index.md` (topic map). Delegate to `vault-navigator` when scope is unclear or requires semantic matching. `qmd` index auto-refreshes via PostToolUse hook after every write.

**`rg`와 `Grep` 툴은 `--no-ignore` 없이는 노트를 못 본다** — `.gitignore`가 `*`로 전부 무시하고 하네스 파일만 화이트리스트하므로 볼트 노트는 비추적이고, `.gitignore`를 따르는 `rg`·Claude Code `Grep` 툴은 0건을 반환한다. 실측(2026-07-31): `rg -l 'type: change' 14_Changes/improvement` → 0건, `--no-ignore` 추가 → 97건. **결과 0건을 "없음"으로 오독하지 말 것.** 순수 `grep`은 `.gitignore`와 무관하다(`--no-ignore` 옵션 자체가 없음 — 붙이면 exit 2). 파일 경로에 한글·공백이 많아 Bash 단어 분할이 깨지므로 대량 스캔은 python/PowerShell로 한다.

## Branching

Direct-to-main: allowed — notes-only vault; no feature branches required.

<!-- commit-guard: allow-main -->

## Context Management

- Write `handoff-{feature}.md` at the **start** of long tasks, not when context is already full.
- **Deliberate override of the platform default:** when context overflows, prefer **reset** over
  compaction/summarization. Vault work is note-at-a-time; a summarized transcript loses the exact
  note paths and frontmatter values a resumed task needs, so a clean session + `handoff-` note
  beats a compacted one here.
- Use this file as the entry point; load `docs/` files only on demand.

## Hard Stops — Always ask the user

Global `~/.claude/CLAUDE.md` §Hard stops governs ambiguity/irreversibility. Vault-specific additions:

- Same error repeats 2+ times.
- Modifying any existing note outside the user-authorized scope appears necessary.

## Maintenance

Update this file only when the global bloat test (`~/.claude/CLAUDE.md` §Core principles) says the
rule belongs in an always-loaded file — i.e. removing it would cause a mistake, and it is not
discoverable from code / config / docs.

**Never add:** architecture summaries, directory overviews, style conventions enforced by tooling, anything visible in the repo, temporary or task-specific instructions.
