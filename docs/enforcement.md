# Enforcement

Mechanical layers that prevent Golden Principle violations.

## Current Status

Notes-only vault — no git pre-commit / CI layer. Only Claude Code PostToolUse hooks are applicable.

| Golden Principle | Enforcement method | Status |
|-----------------|-------------------|--------|
| #1 Existing notes immutable | AGENTS.md rule + Hard Stop + 대량편집 dry-run 규율 | Doc-enforced (의도적) |
| #2 Follow templates | `check-template.py` PostToolUse hook (mechanical) | Shell-enforced (committed) |
| #3 Normalize tags (form + semantic) | `validate-tags.sh` PostToolUse hook이 태그를 추출해 `validate_tag.py --json`에 파이프 (mechanical) → 문맥 의존 건만 `tag-validator` | Shell-enforced (form: committed · semantic: 2026-07-29) |
| 위임 비용 규칙 #1 (중첩 위임 금지) | `.claude/agents/*.md` `tools:` 화이트리스트 (런타임 차단) + `check-nested-delegation.py` PostToolUse hook (산문 린터) | Shell-enforced (committed) |
| #4 Folder rules | `check-folder-rules.py` PostToolUse hook (mechanical) | Shell-enforced (committed) |
| #2 Task date fields | `check-todo-due-date.py` PostToolUse hook (mechanical) | Shell-enforced |
| #5 Inbox (01_Inbox) via skill | AGENTS.md delegation rule | Doc-enforced |
| 하네스 파일의 맨 `python` 호출 (검사 무력화) | `check-bare-python.py` PostToolUse hook + `--sweep` 전수 스캔 (mechanical) | Shell-enforced (2026-08-02) |

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

`.claude/hooks/validate-tags.sh`, registered in **`settings.json`** (committed) as `PostToolUse` on `Write|Edit`.

훅 자체는 **태그를 추출해 `.claude/lib/validate_tag.py - --json`에 파이프**하고 결과를 보고할 뿐, 규칙을 스스로 판정하지 않는다 (2026-07-29). 태그 규칙의 단일 진실 원천은 `validate_tag.py` 하나다 — 예전처럼 훅이 정규식으로 같은 규칙을 재구현하면 두 사본이 드리프트한다.

`validate_tag.py`가 판정하는 것: 금지 `#업무/` 접두어 · 괄호·공백·`&`·`+` · 미등록 area(런타임에 `10_Areas/` 폴더명에서 유도) · **직급 매핑**(`행정주사보`→`주무관`) · **부서명 매핑** · `P_` 접두어 · `퇴직/` 중간 경로 · 학과 조교 경로.

훅에만 남은 검사: **`#부서/` 태그의 frontmatter 오배치** — `validate_tag.py`는 태그 문자열만 받아 파일 내 위치를 알 수 없다.

제외: 펜스·인라인 코드 블록(Dataview 쿼리 태그) · `{`/`}` 포함 플레이스홀더(`#업무/{area}`) · `.claude/`, `99_Template/`, `docs/` 경로.

`validate_tag.py` 또는 `python3` 부재 시 조용히 exit 0 (쓰기를 막지 않는다).

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

의미 수준 검증이 필요하면 `.claude/lib/validate_tag.py --json`으로 먼저 판정하고(직급 매핑·금지 접두어 제거까지 처리), 스크립트가 못 푸는 문맥 의존 건만 `tag-validator`로 에스컬레이션한다.

**해소됨 (2026-07-29):** 이 사각지대는 "`validate_tag.py`를 자동으로 부르는 훅이 없어, 생성 워크플로 밖에서 쓴 노트는 직급 매핑 같은 의미 수준 오류가 통과한다"는 것이었다. `validate-tags.sh`가 태그를 추출해 `validate_tag.py`에 파이프하도록 바뀌면서 경로와 무관하게 의미 수준 검사가 걸린다 (위 §Active 참조).

## Nested Delegation Guard

### Active: `check-nested-delegation.py` (mechanical)

`.claude/hooks/check-nested-delegation.py`, `settings.json`의 `PostToolUse` `Write|Edit`에 등록.

**배경 (2026-07-24 실측):** `improvement-planner`·`incident-analyst`·`training-note-manager` 3개 정의가 `Agent(subagent_type: "tag-validator")`를 호출하도록 지시하고 있었다 → 도구가 없는 상태에서 런타임 **무음 실패**로 태그 작성이 조용히 누락됐다.

**정정 (2026-08-02 실측):** "서브에이전트에 `Agent`·`Task`가 없다"는 **자동이 아니다.** 정의 frontmatter에 `tools:`가 없으면 `Agent`를 그대로 **상속**한다. 이 상태에서 `inbox-reference-worker`가 자기 자신을 자식으로 띄운 뒤 **결과를 기다리지 않고 즉시 반환** → 메인 스레드가 산출물 0건으로 오판하고 재디스패치 → 두 워커가 같은 배치를 중복 처리(228k 토큰 + 중복 노트 생성 후 정리). 실제 실패 모드는 무음 실패가 아니라 **고아 자식**이다.

**이 훅은 문서 린터다** — 서브에이전트가 읽는 `.md`의 **산문 위임 지시**만 검출하며, 런타임 `Agent` 호출은 검사 범위 밖이다. 위 사고에서도 산문 지시는 0건이었고 훅은 정상적으로 무음이었다.

### Active: `tools:` 화이트리스트 (mechanical, 2026-08-02)

런타임 차단 담당. `.claude/agents/*.md` 전부에 다음을 명시해 `Agent`·`Task`·`Workflow`를 제외한다:

```yaml
tools: Bash, Read, Write, Edit, Glob, Grep, Skill, WebFetch, WebSearch, ToolSearch
```

(`status-judge`는 이전부터 `tools: Read`로 더 좁게 제한.) **새 에이전트 추가 시 이 줄을 반드시 넣는다** — 빠뜨리면 규칙이 조용히 무효가 된다.

**검사 대상** (서브에이전트가 읽는 파일만): `.claude/agents/` 이하 모든 `.md` — 에이전트 정의와 `workflows/` 절차서를 함께 포함한다 · `inbox-process/references/{action,reference}-branch.md` · `description`에 `Do NOT invoke directly`가 있는 스킬 디렉터리 전체(2026-08-02 현재 해당 스킬 없음 — 에이전트 전용 절차서는 `agents/workflows/`로 옮겼다. 규약을 어기고 다시 생기는 경우에 대비한 잔여 가드).

**에이전트명 목록**은 `.claude/agents/*.md`에서 **런타임에 유도**한다. 하드코딩하면 에이전트 추가 시 갱신을 잊어 산문 탐지가 조용히 꺼진다 — 훅이 막으려는 바로 그 무음 실패다.

**검출:** `subagent_type` / `Agent(` / `Task(` / "{에이전트명} … 위임·호출·맡기·기동" + **어미** 패턴. 어미는 `한다`·`하라`·`할 것`·`할 수 있`·`해야`·`하도록`·`하고`·`하거나`·`하여`·`해서`·`한 뒤`와 **줄끝**·**여는 괄호 앞**까지 포함한다(명사형 `…에 위임`으로 끝나는 줄, `…에 위임 (`, `…에 위임하거나`가 실제 누락됐다). "위임 금지/불가", "호출할 수 없다" 같은 **부정문은 제외**(규칙을 문서화한 줄은 위반이 아님).

> **어미 그룹을 선택(`?`)으로 풀지 말 것.** 에이전트명 근처의 모든 `위임`·`호출`이 걸려, 규칙이 **권장하는** 표현("보고에 적어 메인 스레드가 호출하게 한다", "오케스트레이터가 수행한다", "incident-analyst 추가 호출 필요?로 반환")까지 오탐한다 — 실측 8건. `하게`·`하지`·` 불가`·` 필요`는 의도적으로 어미 목록에서 뺐다.

검증: 위반 6종(`Agent(subagent_type:…)`, `…에 위임한다`, `…를 위임할 수 있다`, 명사형 줄끝 `…에 위임`, `…에 위임하거나`, `…에 위임 (`) 탐지 + 부정문·"메인 스레드가 호출하게 한다" 무시 확인, 현행 하네스 전체 파일 스윕 **오탐 0**.

## Bare `python` Invocation Guard

### Active: `check-bare-python.py` (mechanical, 2026-08-02)

`.claude/hooks/check-bare-python.py`, `settings.json`의 `PostToolUse` `Write|Edit`에 등록.

**배경:** 비대화형 셸엔 `python` 별칭이 없어 맨 `python` 호출은 `command not found`로 죽는다. 그런데 이 저장소 문서는 여러 곳에서 **훅의 무출력을 "검사 통과"로 읽으라고** 지시한다 — 두 개가 겹치면 오타 하나가 경고 한 건이 아니라 **게이트 전체를 조용히 끈다.** cd30915에서 한 번 정리했는데 PR #20에서 3곳이 재발해 기계화했다.

**검사 대상:** `.claude/`·`docs/` 이하 `.md`·`.sh`·`.py`. 문서의 예시 명령이 그대로 복사돼 실행되므로 산문 파일도 포함한다.

**두 모드:** 훅(쓰기 직후 실시간, 경고만, 항상 exit 0) + `--sweep`(전수 스캔). 스윕 exit 코드는 `1`=발견 · `0`=검사했고 깨끗함 · `2`=**아무것도 검사 못 함**(경로 오타·읽기 실패). `2`를 분리한 이유가 핵심이다 — 오타 난 경로의 "0건"이 "이상 없음"으로 읽히면 이 훅이 막으려는 오독을 훅 자신이 재현한다.

**검출:** (a) 인터프리터 플래그 `python -c`/`-m`/`--version` · (b) 경로 인자 · (c) 따옴표로 감싼 경로·변수 · (d) 명령 위치의 런처 `xargs`/`exec`/`env`/`nohup`/`sudo`/`time` · (e) 명령치환 `$(which python)` · 셔뱅(들여쓰기 허용). `python3`·`python_files`·`python.org`는 배제. <!-- bare-python-ok: 규칙을 설명하는 예시 -->

**면제는 `bare-python-ok: <이유>` 마커뿐이다 — 이유 필수.** 마크다운 헤딩 줄에 붙이면 다음 헤딩까지, 그 외엔 그 줄만. 키워드 기반 면제는 두지 않는다.

> **키워드 블랭킷 면제를 만들지 말 것.** 초판엔 `금지`·`오탐`·`check-bare-python` 같은 낱말이 들어간 **줄 전체**를 면제하는 `ALLOW_PAT`이 있었다. QA 실측 결과 28개 파일 **75줄**이 조용히 면제됐고, 진짜 위반(`python <이 훅 경로> --sweep`)까지 통과시켰다. 가드가 막으려던 검사 부재를 가드가 재현한 셈이라 통째로 삭제했다.

> **탐지 폭은 오탐과 맞바꾼 값이다.** 경로 인자를 "`/` 포함 토큰"으로 넓게 잡았더니 영어 산문이 줄줄이 걸렸다(`python and/or python3`, `python I/O`, `python A/B testing`). 런처도 위치를 안 보면 `the env python var is unset`이 걸린다. 그래서 경로는 접두사(`./` `/` `~/` `$`) 또는 `.py` 종료로, 런처는 명령 위치로 좁혔다. **알려진 누락은 파일 헤더에 명시**돼 있다(단독 `python`, `python $SCRIPT`, `PYTHON=python`, heredoc, 확장자 없는 상대경로, `python2`). 넓히려면 오탐 실측을 먼저 하라. <!-- bare-python-ok: 규칙을 설명하는 예시 -->

검증: 검출 20종 + 셔뱅 3종 전부 탐지, 영·한 산문 23종 오탐 0, 비정상 훅 페이로드 18종 전부 exit 0, 저장소 전수 스윕 exit 0. 현재 마커는 `docs/runbook.md`의 Windows `python` 해석 항목 1곳과 훅 자신의 규칙 설명 주석 5줄뿐이며, 실행 가능한 호출을 가리는 마커는 없다(억제 무력화 후 원시 스캔으로 확인).

## Template Check Hook

### Active: `check-template.py` (mechanical)

`.claude/hooks/check-template.py`, registered in `settings.json` as `PostToolUse` on `Write|Edit`. Checks:

- `![[...]]` embed anywhere in file → warn (GP#2: embeds forbidden unless explicitly requested)
- Empty wikilink placeholder `[[ ]]` anywhere in file (fenced code blocks excluded) → warn (GP#2: `## 관련 문서` 등 content-conditional 섹션은 근거 없으면 섹션째 생략 — 템플릿 섹션을 기계적으로 다 채우지 말 것; 2026-07)
- Missing `type:` frontmatter in note-bearing folders (`10_Areas`, `12_Projects`, `11_Routines`, `14_Changes`, `20_Training`) → warn (GP#2: use template from `99_Template/`)
- Missing `status:` OR non-enum value in note-bearing folders → warn. Allowed: `open|in-progress|hold|closed|active` (`_메타데이터 규칙.md` 5개 고정). Catches the `done`/`resolved`/`pending-action` drift that left status-sync blind (2026-06).
- **Check 2c — `doc_date`/`recv_date` 형식:** 값이 **있으면** `YYYY-MM-DD`여야 하고, 아니면 warn. 부재도 빈 값(`doc_date:`)도 위반 아님(공문 유래 노트만 쓰는 선택 필드). 공문 표기 `2026. 7. 20.`를 그대로 넣어 정렬·Dataview가 깨지는 것을 막는다. 제목 날짜 프리픽스 규칙(폐기, 2026-07-30)을 대체한 필드 (2026-07-30). 값 추출은 **한 줄 앵커**(`^{fld}:[ \t]*(\S.*?)[ \t]*$`)여야 한다 — `\s*`를 쓰면 개행을 먹어 빈 값일 때 다음 frontmatter 키를 값으로 오인하고, 공백 포함 값(`2026. 7. 20.`)도 앞토막만 잘라 경고문이 틀린다.
- **Check 3 — change 노트 `change_type`:** `14_Changes/incident/`는 `change_type: incident`, `14_Changes/improvement/`는 `change_type: improvement` 필요, 없으면 warn. improvement 갈래는 2026-07-30 추가 — incident만 검사하던 동안 `eval-criteria.md` 기준 1의 "change 노트는 `change_type` 확인"이 개선 노트에서 기계적으로 검증되지 않았다(레거시 미보유 57/97건, 아래 백로그).
- **Check 4 — 필수 섹션 앵커 (`10_Areas/` + `type: work`, `10_Areas/과업심의/`의 심의 서식 제외):** `## 관련`·`## 할 일` 중 하나라도 없으면 warn. **템플릿 문자열 일치나 5섹션 전부 존재는 검사하지 않는다** (2026-07-30). 별칭 허용은 **두 가지 서로 다른 장치**다 — 혼동하지 말 것:
  1. 비교 전 **선행 기호(이모지·ZWJ·variation selector·구두점)를 제거**한다 → `## 🙋‍♂️ 관련` = `## 관련`.
  2. `할 일` 앵커만 **동의어 `해결 방안`을 추가로 허용**한다 → `## 🛠 해결 방안`·`## 해결 방안` 모두 통과. `관련` 앵커엔 동의어가 없다.
  - `type: work` 한정(2026-07-30 리뷰 반영): `10_Areas/` 아래에도 `type: reference` 분석 노트가 있고 업무사안 템플릿을 쓰지 않는 것이 정상이다 — 무한정 적용 시 해당 종류 2/2건 전수 오탐이었다.
  - 근거(실측 202건): `## 🙋‍♂️ 관련` 116건·`## 🛠 해결 방안` 115건으로 이모지 별칭이 다수 관행이고, 템플릿 5섹션 외 자유 섹션 보유 노트가 136건이다. "템플릿 그대로"를 강요하면 오탐 145건(72%)이 된다. 앵커 2개 + `type: work` 한정이면 잔여 20/201건(10%)이다. **이 20건은 구형 잔재가 아니다** (2026-08-02 재실측, PR #20 리뷰): 15건이 `10_Areas/과업심의/202605~202607_...`의 `심의의견_*.md`·`*_사업목록.md`로 **회차마다 재생산되는 현행 산출물**이고(업무사안이 아니라 심의 서식 — `사업 개요`/`과업내용 적정성` 구조), 나머지 5건만 구형 분석 노트다. 회차가 열릴 때마다 같은 경고가 재발했으므로 **`10_Areas/과업심의/`의 심의 서식을 제외**했다(2026-08-02 사용자 결정). 제외 후 잔여 5건은 진짜 구형 분석 노트로 계속 검출된다.
  - **폴더째가 아니라 파일명 어휘(`심의의견`·`사업목록`·`검토의견`·`과업심의_프로세스`)로 좁힌다** (PR #21 리뷰 실측). 초판은 경로 통째 제외였는데, 같은 폴더 18건 중 3건은 앵커를 갖춘 **진짜 업무사안**(회차 위원회 노트·서류 요청 노트)이고 회차마다 새로 생긴다 — 폴더째 빼면 그 갈래가 영구 무게이트가 된다. **교훈: 제외 근거가 "내용이 다르다"인데 제외 키가 "경로"면 범위가 어긋난다 — 실측으로 갈라지는 지점을 키로 써야 한다.**
  - 경로 리터럴이 한글이므로 `fp_norm`은 **NFC 정규화**를 거친다 — macOS는 한글 파일명을 NFD로 저장해 정규화 없이는 `/과업심의/` 매칭이 전부 실패한다.
  - 이 검사가 없어서 지불한 비용: 구조 이탈 판정을 `note-evaluator`(LLM)가 대신 수행 → 노트 1건당 약 101k 토큰. 게다가 템플릿 문자 그대로 채점해 다수 관행을 위반으로 오판했다.
- **Check 5 — `#업무/` 구체 태그 존재 (`10_Areas/`+`type: work` · `14_Changes/`):** 없으면 warn (2026-07-30 신설, 2026-08-02 PR #20 리뷰로 `14_Changes` 확장). `validate-tags.sh`는 **발견한 태그의 형식**만 검증하므로 태그가 전무한 노트는 무음 통과한다 — `eval-criteria.md` 기준 2가 "tag missing entirely"를 1점으로 규정하는데도 기계 검사가 비어 있던 구멍이다.
  - **적용 범위를 `14_Changes/`까지 넓힌 이유:** `_업무사안`·`_개선`·`_인시던트`·`_교육` 네 템플릿 모두 `## 관련`에 `- #업무/`를 두는데, `10_Areas`만 검사하던 동안 incident·improvement 노트가 무게이트였다(실측 미보유 24/203 = 12%로 소수 → 요구가 관행에 부합).
  - **`20_Training/`은 제외한다** (2026-08-02 사용자 결정): `_교육.md`도 `- #업무/`를 두지만 실측 미보유 25/35(71%)로 **관행이 아니다** — 기계화하면 다수가 오탐이다. 교육 노트의 `#업무/` 부재는 평가자 판단으로 남긴다. 규칙은 실측 관행과 대조해 쓴다(AGENTS.md 위임 비용 규칙 #6).
  - **"존재"가 아니라 "구체 태그"를 요구한다:** 원시 substring 검사(`#업무/`)는 템플릿 플레이스홀더 `#업무/{영역}/{하위영역}/{메뉴명}`과 인라인 코드 안의 예시 태그도 통과시켰다. `validate-tags.sh`는 중괄호 태그(`grep -v '[{}]'`)와 인라인 코드를 **제거한 뒤** 검사하므로 이 경우 양쪽 훅이 동시에 무음이었다 — 훅의 경고문 자체가 중괄호 형태를 예시하고 있어 현실적인 실패 경로다. 그래서 인라인 코드를 걷어내고 `#업무/(?![{\s])`로 판정한다.
  - `#부서/`는 검사하지 않는다: 실측 미보유 56/201(28%)로 관행이 아니어서 **선택 필드로 강등**했다(2026-08-02 사용자 결정). 있으면 `validate-tags.sh`가 형식을 보고, **부재는 위반도 감점도 아니다** — 평가자도 지적하지 않는다.

Skips: `99_Template`, `docs`, `.claude`, `90_Archive`, `_Wiki`, `_Sources`, `01_Inbox`, `_work`, `backlog.md`, `tasks.md`, `AGENTS.md`, `CLAUDE.md`. Warning-only, exit 0.

## Folder Rules Hook

### Active: `check-folder-rules.py` (mechanical)

`.claude/hooks/check-folder-rules.py`, registered in `settings.json` as `PostToolUse` on `Write`. Four path-only checks:

1. **`12_Projects/`** — loose `.md` at root (no sub-folder) → warn
2. **`90_Archive/`** — any write → warn (no file creation allowed)
3. **`10_Areas/`** — depth > 2 levels, 무첨부 래퍼 폴더(첨부 없는데 폴더로 감쌈) → warn. 길이 제한(slug 20자·summary 60자)은 2026-07-24에 제거 — `conventions.md`가 "전체 제목, 길이 캡 없음"으로 확정됐다.
   - **첨부는 재귀로 센다 (2026-07-29 수정).** 이전에는 래퍼의 **직속 자식만** 훑어서, 첨부가 `{wrapper}/2026-012/결과물/x.pdf`처럼 한 단계 아래 놓이면 "무첨부"로 읽혔다. 실볼트에서 첨부 37~147개를 가진 `10_Areas/과업심의/` 래퍼 5개가 전부 오탐으로 걸리고 있었다(해당 노트를 편집할 때마다 헛경고). `rglob`으로 바꿔 오탐 5→0.
   - **남아 있는 사각지대 (2026-07-24 실측):** 래퍼 폴더 생성 후 `GRACE_SECONDS`(60초) 이내 Write는 검사를 통째로 건너뛴다. 첨부가 노트보다 늦게 저장되는 경우의 오탐을 막으려는 유예인데, 폴더·노트를 한 번에 만드는 **최초 생성 경로에서는 항상 유예에 걸려** 무첨부 래퍼가 잡히지 않는다(재현 확인: 신규 폴더 + 노트 Write → 무경고). 이후 같은 노트를 편집하면 검사된다. 유예 자체는 의도된 오탐 방지책이라 유지한다.
   - **잔존분 검출 (2026-07-29):** `reorg_archive.py find-bare-wrappers 10_Areas --json`이 `10_Areas/` 전체를 훑어 "첨부 0 + `.md` ≤1"인 래퍼 폴더를 목록화한다. 판정 로직은 Rule 3과 동일하게 맞춰 놨다 — 어긋나면 사각지대를 하나 더 만드는 셈이다. **탐지 전용**(이동 없음); 절차는 `.claude/skills/vault-cleanup/references/mode-reorganize.md` Step 5. 1차 방어는 여전히 생성 측 `new_work_path.py --flat`.
4. **`14_Changes/incident/`** — filename must match `통합학사시스템 오류 처리 {YYYY-MM-DD}_{순번}.md` (NFC-normalized) → warn. Blocks legacy drift patterns (`Error_*`, `오류 처리 *`, `_통합학사…`). Fires on `Write` only, so editing the ~96 pre-existing legacy notes is not nagged; new incident notes must use the `incident-analyze` 워크플로우의 `new_incident_path.py`.

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
10. ✅ 의미 수준 태그 오류(직급·부서명 매핑)가 생성 워크플로 밖 쓰기에서 통과하던 문제 → `validate-tags.sh`가 태그를 추출해 `validate_tag.py - --json`에 파이프하도록 교체, 훅의 중복 정규식 판정은 삭제 (2026-07-29). 규칙 단일 진실 원천 = `validate_tag.py`.
11. ✅ `check-folder-rules.py` Rule 3의 60초 유예로 최초 생성 경로의 무첨부 래퍼가 검출되지 않던 문제 → `reorg_archive.py find-bare-wrappers` 스윕 추가 (2026-07-29). 훅은 실시간 방어, 스윕은 잔존분 일괄 검출.
12. ✅ Rule 3이 첨부를 직속 자식만 세어 하위 폴더에 첨부를 둔 래퍼를 "무첨부"로 오탐하던 문제 → 훅·스윕 양쪽 `rglob` 재귀 카운트 (2026-07-29). 스윕 도입 시 훅과의 판정 차등 테스트로 발견 — 실볼트 오탐 5건이 0건이 됐다. 판정 로직이 두 곳에 있으면 이런 차등 테스트가 가능하다는 게 부수 효과.
13. ✅ 노트 구조 검사를 기계 검사 없이 `note-evaluator`(LLM)에 맡겨 노트 1건당 약 101k 토큰을 쓰면서도, 템플릿 문자 그대로 채점해 다수 관행(`## 🙋‍♂️ 관련` 116건·`## 🛠 해결 방안` 115건)을 위반으로 오판하던 문제 → `check-template.py` Check 4(필수 앵커 2개, 별칭·자유 섹션 허용) + `eval-criteria.md` Template Adherence 기준 재정의 + `inbox-process` note-evaluator 조건부 호출 (2026-07-30). **교훈: `eval-criteria.md`의 5개 기준은 전부 "How to test"가 기계적이다 — 기준을 새로 쓸 때 훅이 없으면 그 비용은 매 노트마다 LLM 토큰으로 청구된다.**
14. ✅ `#` 제목 날짜 프리픽스 규칙이 준수율 64/202(32%)로 관행이 아니었고, 기록하는 값이 **노트 작성일**이라 업무 발생 시점을 못 담고 Linter `date created`와 의미가 겹치던 문제 → 프리픽스 규칙 폐기 + `doc_date`(공문 시행일)·`recv_date`(다를 때만) frontmatter 신설, `check-template.py` Check 2c로 `YYYY-MM-DD` 형식 기계 검사 (2026-07-30). 기존 64건은 GP#1로 불변 — 신규 노트에만 적용. 반영: `_메타데이터 규칙.md`(SSOT)·`conventions.md`·`eval-criteria.md`·`action-branch.md`·`incident-analyze`·`improvement-plan`.
15. ✅ #13이 만든 "훅 무음 = 기준 1~4 통과" 규칙에 **기계 검사가 비어 있는 구멍 3개**가 남아 있던 문제 → (1) Check 3을 `14_Changes/improvement/`로 확장(개선 노트 `change_type` 무검사였음), (2) Check 5(`#업무/` 태그 존재) 신설 — `validate-tags.sh`는 태그가 전무하면 무음이다, (3) 기준 5(Wiki Feedback Loop)를 `moc_gate.py` 실행으로 `inbox-process` 3-a 기계 검사에 편입. 더불어 Check 2c 빈 값 오탐(다음 키를 값으로 오인)·Check 4 `type: reference` 전수 오탐 수정 (2026-07-30, PR #18 리뷰). **교훈: "훅이 검사한다"를 근거로 LLM 게이트를 걷어낼 때는 훅이 *무엇을 검사하지 않는지*를 같이 실측해야 한다 — 형식 검증기는 대개 "값이 아예 없는 경우"에 무음이다.**

16. ✅ #15가 막은 구멍 옆에 **같은 종류의 구멍 3개**가 더 있던 문제 (2026-08-02, PR #20 리뷰) → (1) Check 5를 `14_Changes/`·`20_Training/`으로 확장 — `10_Areas`만 보던 동안 incident·improvement·training 노트는 무게이트였고, 그 사이 문서는 "훅 무음 = 통과"로 읽으라고 지시하고 있었다, (2) Check 5를 원시 substring에서 **구체 태그 요구**로 교체 — 플레이스홀더 `#업무/{영역}`·인라인 코드 태그가 두 훅 모두를 무음 통과시켰다, (3) Check 2c 인라인 주석 오탐·Check 3 따옴표 값 오탐 수정. 더불어 문서의 `python` 호출을 `python3`로 정정 — 비대화형 셸엔 `python` 별칭이 없어 `command not found`의 무출력이 "통과"로 오독됐다. **교훈: 검사 범위를 노트 종류로 좁혔으면, 좁힌 쪽을 무엇이 지키는지 같이 적어야 한다. 그리고 "값이 있는가"를 묻는 검사는 대부분 "플레이스홀더가 아닌 값이 있는가"를 물었어야 한다.**

17. ✅ 맨 `python` 호출이 문서·스킬에 재발하던 문제 (cd30915에서 정리했으나 PR #20에서 3곳 재발) → `check-bare-python.py` PostToolUse 훅 + `--sweep` 전수 스캔 (2026-08-02). 비대화형 셸엔 `python` 별칭이 없어 `command not found`가 되는데, **무출력을 "검사 통과"로 읽으라는 문서**와 겹치면 오타 하나가 게이트를 통째로 끈다. 도입 시 수동 grep이 놓친 실재 4건(`docs/runbook.md`)을 훅이 검출 — 1건은 진짜 드리프트로 정정, 3건은 Windows `python` 해석 자체가 주제라 이유 필수 마커로 억제. **교훈 두 가지:** (1) **키워드 블랭킷 면제를 만들지 말 것** — 초판 `ALLOW_PAT`이 `금지`·`오탐` 같은 낱말이 든 줄 전체를 면제해 28개 파일 75줄이 조용히 빠졌고 진짜 위반까지 통과시켰다(#13·#15가 반복해 만난 "검사가 비어 있는 구멍"의 또 다른 형태 — 이번엔 가드 스스로 만들었다). 면제는 이유를 강제하는 명시 마커여야 한다. (2) **"0건"은 세 가지 뜻이다** — 검사했고 깨끗함 / 경로가 틀려 아무것도 안 봄 / 읽기 실패. 스윕이 셋을 exit `0`·`2`로 구분하지 않으면, 이 훅이 막으려는 바로 그 오독을 훅 자신이 재현한다. 개발 중 실제로 SyntaxError 난 스크립트가 `2>/dev/null` 뒤에서 "0건"을 반환했다.

18. ✅ #16이 넓힌 검사 범위 중 **관행과 어긋난 두 곳**과, 회차마다 재생산되는 서식을 구형 잔재로 오판하던 문제 (2026-08-02 사용자 결정) → (1) Check 4에서 `10_Areas/과업심의/`의 심의 서식 제외 — 미통과 20건 중 15건이 이 서식이었고 회차가 열릴 때마다 같은 경고가 재발했다(제외 후 잔여 5건은 진짜 구형 노트). **초판은 경로 통째 제외였고 리뷰에서 되돌렸다** — 같은 폴더 3건이 앵커를 갖춘 진짜 업무사안이라 폴더째 빼면 영구 무게이트가 됐다, (2) Check 5에서 `20_Training/` 제외 — 미보유 25/35(71%)로 관행이 아니어서 다수가 오탐이었다(`14_Changes`는 12%라 유지), (3) `#부서/`를 선택 필드로 강등 — 미보유 56/201(28%)이라 `note-evaluator`·`inbox-process`가 매 노트마다 지적하던 것을 중단. 더불어 `fp_norm`에 NFC 정규화 추가 — macOS는 한글 파일명을 NFD로 저장해 한글 경로 리터럴이 정규화 없이는 전부 불일치한다. **교훈: #16이 "검사 범위를 좁혔으면 좁힌 쪽을 무엇이 지키는지 적으라"고 했는데, 그 역도 참이다 — 범위를 *넓힐* 때는 넓힌 쪽의 실측 준수율을 먼저 재야 한다. `14_Changes` 12%와 `20_Training` 71%는 같은 템플릿 근거에서 나왔지만 정반대 결론을 요구했다.**

## Generator Config (not version-controlled)

`.obsidian/` is **gitignored** — these fixes live only on the local machine (Syncthing-synced), not in git:

- **Obsidian Linter timestamp format** (`.obsidian/plugins/obsidian-linter/data.json` → `yaml-timestamp.format`): was `YYYY-MM-DD HH:MM:SS` (moment.js `MM`=month, `SS`=fractional-second → minute slot showed month, seconds >59). Fixed to `YYYY-MM-DD HH:mm:ss` (2026-06). This was the root cause of ~485 impossible-timestamp frontmatter values vault-wide (since batch-corrected). `update-on-file-contents-updated: never` limits re-stamping. If `.obsidian` is reset/reinstalled, re-apply this format.
