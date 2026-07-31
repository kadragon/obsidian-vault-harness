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
4. **Follow folder rules** — no loose `.md` files in `12_Projects/` (folders only); no file creation in `90_Archive/`; `10_Areas/` depth max 2 levels (attachments → `YYYYMM_{summary}/` folder using the full title, inner file `_YYYYMM_{summary}.md` with `_` prefix; no attachments → single `.md` at area root, no wrapper folder). See `docs/conventions.md` → `10_Areas/ Depth Rules`.
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
| Tag 검증·정규화 | **1차: `tag-normalize/scripts/validate_tag.py --json`** (결정론적) · 문맥 의존 건만 `tag-validator` agent |
| 노트 품질 평가 (생성 직후 게이트, `docs/eval-criteria.md` 루브릭) | `note-evaluator` agent |
| `01_Inbox/` document processing (공문·참고자료 모두) | `inbox-process` skill |
| Training note cleanup | `training-note-manager` agent |
| Obsidian note **create**(템플릿 적용)·open·프로퍼티·앱 내 JS | `obsidian-operator` agent |
| 기존 노트 본문 **소규모 수정**(수 줄·1~2파일) | 직접 Edit — 위임 금지 (§Delegation 비용 규칙) |
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

### 위임 비용 규칙 (2026-07-24 확립)

1. **서브에이전트는 다른 서브에이전트를 호출할 수 없다.** 실측: 서브에이전트 도구 목록에 `Agent`·`Task` 없음(`Skill`·`Read`·`Write`·`Edit`·`Bash`는 있음). 에이전트 정의·서브에이전트 전용 스킬에 "…에 위임한다"라고 쓰면 **런타임 무음 실패**한다. 위임이 꼭 필요하면 **보고에 적어 메인 스레드가 호출**하게 한다. `check-nested-delegation.py` 훅이 기계 검출한다.
2. **스크립트 우선.** 규칙표 대조·경로 계산·해시 비교처럼 결정론적인 일은 스크립트로 끝내고, **판단이 필요한 잔여분만** 에이전트로 에스컬레이션한다 (status-sync·vault-cleanup·syncthing-cleanup이 이 패턴).
3. **소규모 편집은 직접.** 수 줄·1~2파일 수정에 풀에이전트 왕복(수만 토큰·수십 초)은 금지. `_Wiki/log.md` 한 줄 append도 직접 Edit.
4. **검증자 ≥ 생성자.** 품질 게이트 에이전트의 모델은 생성자와 같거나 강해야 한다.
5. **품질 게이트는 메인 스레드 책임 — 단 기계 검사가 1차, `note-evaluator`는 조건부** (2026-07-30 개정). 노트 생성 에이전트(`improvement-planner`·`incident-analyst`·`training-note-manager`·`inbox-action-worker`)가 반환하면 메인 스레드가 게이트를 돌린다. 생성자가 스스로 부를 수 없고(규칙 #1), 불러서도 안 된다(self-preference).

   `docs/eval-criteria.md` 5개 기준 대부분은 **`check-template.py`·`validate-tags.sh`·`moc_gate.py`가 기계적으로 판정**한다. 훅 경고가 없는데 `note-evaluator`를 부르면 훅이 한 계산을 LLM으로 재실행하는 것이다(실측 노트 1건당 약 100k 토큰). **단 훅 무음 = 전면 통과가 아니다** — 형식 검증기는 값이 아예 없으면 무음이므로, `#부서/` 부재·area 배정 적합성·MOC 순방향 등록은 메인 스레드가 직접 확인한다(커버리지 표 → `docs/eval-criteria.md` §기계 검사 커버리지). 그 뒤 게이트가 잡아야 할 나머지는 **원본 대조 사실검증**(공문번호·기한·담당자·회차) 하나다.

   호출 조건·스코프 한정은 `inbox-process/SKILL.md` 5단계-3. 호출 시에도 구조·태그 재채점 금지, 원본 재추출 금지(워커가 반환한 추출 경로 재사용).

   FAIL이면 지적 항목을 수정한 뒤 사용자에게 보고한다. 자주 걸리는 항목: MOC 순방향 등록(Wiki Feedback Loop).

6. **기준을 쓸 때 "How to test"가 결정론적이면 훅/스크립트로 만든다.** 안 만들면 그 비용은 매 산출물마다 LLM 토큰으로 청구된다 — `eval-criteria.md` Template Adherence가 헤딩 대조 훅 없이 운영돼 노트 1건당 101k를 태운 사례(2026-07-30, `docs/enforcement.md` 승격 로그 #13). 동시에 **기준은 실측 관행과 대조해 쓴다**: 같은 사례에서 LLM 평가자가 템플릿 문자 그대로 채점해 다수 관행(`## 🙋‍♂️ 관련` 116/202건)을 위반으로 오판했다.

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
