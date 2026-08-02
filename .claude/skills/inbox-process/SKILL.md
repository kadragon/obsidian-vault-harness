---
name: inbox-process
description: "This skill should be used when the user asks to process 01_Inbox/ — 문서를 분석하여 '업무사안(action)'으로 다룰지 '참고자료(reference)'로 정리할지 판단한 뒤, 각각 10_Areas/{area}/ 업무사안 노트 또는 _Sources·_Wiki/에 반영한다. 트리거 문구: 'inbox 처리', 'inbox 정리', 'inbox 비워줘', '01_Inbox 처리', '공문 처리', '공문 읽어줘', '받은 문서 정리', '받은 자료 정리', '수집함 처리', 'InfoBox 처리', '문서 정리해줘', '자료 정리해줘', '위키에 반영해줘', 'scraps 처리해줘', '웹 클립 정리해줘'. inbox·공문·받은 문서·수집함·참고자료·웹 클립 처리 요청이면 '01_Inbox'를 명시적으로 언급하지 않아도 이 스킬이 해당된다."
---

# Inbox 처리 오케스트레이터

`01_Inbox/` 처리를 오케스트레이션하는 스킬. **실제 파일 처리는 두 서브에이전트에 위임**한다:

- **action 갈래** (공문·업무요청) → `inbox-action-worker` (sonnet)
- **reference 갈래** (참고자료·수집물) → `inbox-reference-worker` (sonnet)

오케스트레이터의 책임은 스캔, 루트 triage, 유사 노트 사전 수집(vault-navigator), **모호성 grill(§Grill 게이트)**, 에이전트 디스패치, **태그 확정(tag-validator)**, **품질 게이트(note-evaluator)**, 삭제 일괄 처리, 최종 보고다. 파일 내용 Read·노트 작성은 하지 않는다. 단, grill 결과를 노트에 반영하는 소규모 수정은 직접 Edit으로 한다(§Grill 게이트).

> **서브에이전트 호출 규약**: 워커(`inbox-action-worker`·`inbox-reference-worker`)는 서브에이전트이므로 **다른 서브에이전트를 호출하거나 사용자와 직접 대화할 수 없다.** 따라서 vault-navigator·tag-validator·incident-analyst·improvement-planner 호출과 모든 사용자 확인은 **오케스트레이터가 전담**한다. 워커는 후보 태그·열린 질문·삭제 권고를 보고로만 반환한다.

## 디렉터리 구조

```
01_Inbox/
├── action/        # 확신 있는 action → inbox-action-worker에 위임
├── reference/     # 확신 있는 reference → inbox-reference-worker에 위임
├── scraps/        # 웹 클립 수집함 → reference 갈래와 동일하게 inbox-reference-worker에 위임
└── (root)         # 분류 모호 → 오케스트레이터가 triage 후 하위 이동
```

## 처리 흐름

### 사전 확인: 인라인 텍스트 입력

사용자가 **파일 없이 텍스트를 직접 붙여넣거나 제공**한 경우 (공문 내용, 메모, 업무 요청 등):

- **`.txt` 파일을 생성하지 않는다** — 임시 파일 우회는 불필요한 흔적을 남긴다.
- 텍스트 내용을 바로 분석하여 action/reference 분류한다 (`references/dispatch-guide.md` §분류 힌트 참조).
- action인 경우 → `inbox-action-worker`를 호출한다. 호출 프롬프트 구조는 `references/dispatch-guide.md` §인라인 텍스트 Action 워커 참조.
- reference인 경우 → `inbox-reference-worker`를 호출한다. 호출 프롬프트 구조는 `references/dispatch-guide.md` §인라인 텍스트 Reference 워커 참조.
- 처리 완료 후 원본 삭제 불필요 (파일이 없으므로).
- 이 경우 1~5단계를 건너뛰고 곧바로 **§Grill 게이트 → 워커 디스패치**로 이동한다.

### Grill 게이트 (모호성 해소)

이 절에 필요한 규칙을 모두 담는다 — 저장소 밖 설정(전역 `CLAUDE.md`)에 의존하지 않는다. 전역 설정이 있으면 그 §Grill protocol과 동일하다.

**대상 판별 — 반드시 둘로 나눈다:**

| 분류 | 처리 |
|------|------|
| **사실(fact)** — 볼트·파일에서 찾을 수 있음 (화면 XML, 테이블·컬럼, 메뉴코드, 과거 처리 이력) | **묻지 않는다.** `vault-navigator`·Grep으로 조사. 못 찾으면 노트 `## 할 일`에 조사 항목으로 남긴다 |
| **결정(decision)** — 사용자만 답할 수 있음 (작업 범위, 처리 방식, 대상 확정, 우선순위, 기한) | **grill 한다** |

**적용 지점 2곳:**

1. **워커 디스패치 전** — 오케스트레이터가 내용을 이미 보유한 경우(인라인 텍스트, 2단계 triage에서 읽은 루트 파일). 결정 항목을 워커에 넘기기 전에 확정 → 노트가 첫 작성부터 정확해진다.
2. **워커 반환 후** — 워커가 `## 열린 질문`으로 올린 항목 중 **결정**에 해당하는 것. 5단계 태그 확정 **전**에 grill한다.

**규칙:**
- 한 번에 **한 질문**. 각 질문에 **추천 답 + 근거** 병기. `AskUserQuestion` 사용.
- 결정 항목이 없으면 게이트를 건너뛴다 — 물을 것이 없는데 묻지 않는다.
- 확정된 답은 노트 `## 현황`에 `[사용자 확인(YYYY-MM-DD)]` 출처와 함께 기재하고, 대응하는 `## 할 일`·`## 열린 질문` 항목을 해결 표시한다.
- **이 반영은 오케스트레이터가 직접 Edit으로 한다.** obsidian-operator 위임 금지 — 수 줄 수정에 서브에이전트 왕복은 토큰·시간 낭비이며 섹션 누락 위험이 있다.

### 0단계: HWP 사전 변환

스캔 전에 `01_Inbox/` 전체에서 `.hwp` 파일 존재 여부를 Glob으로 확인한다.

`.hwp` 파일이 없으면 이 단계를 건너뛴다.

`.hwp` 파일이 있으면:

1. 사용자에게 알림: "한컴 보안 팝업이 뜨면 **모두 허용(N)** 을 클릭하세요"
2. 변환 스크립트 실행:

```powershell
powershell -File ".claude/skills/inbox-process/scripts/hwp_to_hwpx.ps1" -InboxPath ".\01_Inbox"
```

> 이 환경엔 `pwsh`(PowerShell Core) 미설치 — `powershell`(Windows PowerShell) 사용.

3. 출력에서 `FAIL:` 줄 추출 → 해당 파일 경고 후 제외하고 계속
4. 출력에 `ERROR: Hancom not installed` 포함 시 → "한컴 미설치 — HWP 파일 건너뜀" 경고 후 해당 파일 제외하고 계속
5. 변환 성공·원본 삭제는 스크립트 내부에서 처리됨

### 1단계: Inbox 스캔

`01_Inbox/` 존재 여부 확인. 없으면 "01_Inbox 폴더가 없습니다. 생성할까요?"라고 묻고 종료.

Glob으로 네 영역을 각각 스캔:

- `01_Inbox/` 루트 (하위폴더 제외, 파일만)
- `01_Inbox/action/` — 바로 아래 폴더·단독 파일 각각이 업무 단위. 폴더만 있어도 정상. 빈 폴더는 건너뜀.
- `01_Inbox/reference/`
- `01_Inbox/scraps/` — 웹 클립 수집함. reference 갈래와 동일하게 처리(디스패치는 4단계 참조).

모두 비어 있으면 "01_Inbox가 비어 있습니다" 알리고 종료.

비어 있지 않으면 영역별 개수를 요약하고 사용자 선택을 기다린다:

```
01_Inbox 스캔 결과:
- 루트: 2건 (분류 필요)
- action/: 1건
- reference/: 3건
- scraps/: 12건
전체 처리할까요? 아니면 특정 영역만?
```

### 2단계: 루트 Triage (루트 파일이 있을 때만)

루트 파일을 짧게 읽어 action/reference를 제안한다. 파일 형식별 읽기 규칙과 분류 힌트는 `references/dispatch-guide.md` 참조.

사용자 확인 후 해당 하위폴더로 `mv`. 모호한 건은 루트에 보류.

### 3단계: Action 갈래 디스패치

`01_Inbox/action/`에 처리 단위가 있으면 **오케스트레이터가 다음을 먼저 준비**한다:

1. `ls 10_Areas/` 실행 → 실제 area 폴더 목록 확보
2. 각 처리 단위에 대해 파일명·주변 맥락으로 area 1차 판단 (모호하면 "결정 필요"로 표시)
3. 유사 과거 노트 후보 수집 — **MOC 우선, navigator는 폴백** (아래 §선례 조사 비용 규칙)
4. 2단계 triage에서 내용을 읽은 건에 한해 **§Grill 게이트 1차** 수행 (결정 항목이 있을 때만)

#### 선례 조사 비용 규칙 (2026-07-30 확립)

`vault-navigator` 호출은 실측 약 67k 토큰이다. 회차성 반복 공문(추경·정기 제출 요청 등)은 도메인 MOC가 이미 선례 링크·담당자·시즌 캘린더를 담고 있어 대부분 중복 지출이다.

| 상황 | 조사 방법 |
|------|-----------|
| `_Wiki/topics/{도메인}-운영-MOC.md` **존재** | **MOC 1건만 Read** (약 5k). 여기서 선례 노트 링크·담당자 태그·반복 주기를 얻는다. navigator 호출하지 않는다 |
| MOC 없음 · area 불명 · 시맨틱 유사 판단 필요 | `vault-navigator` 호출 |
| MOC를 읽었는데 이번 건에 대응하는 선례가 없음 | `vault-navigator` 호출 (MOC 미수록 연결 탐색) |

워커에 넘기는 선례는 **최대 1건**으로 제한한다. 2건 이상 Read시키면 토큰만 늘고 구조 판단이 흔들린다.

> **선례의 용도는 사실뿐이다** — 근거법령·담당자·네이밍 패턴·반복 주기. **구조(섹션 구성)는 선례가 아니라 `99_Template/` + `docs/eval-criteria.md`가 권위다.** "선례 섹션 구조를 그대로 승계하라"고 지시하지 말 것 — 2026-07-30 이 지시로 note-evaluator FAIL → 노트 재작성이 발생했다.

이후 `inbox-action-worker` 에이전트를 Agent 도구로 호출한다. 호출 프롬프트 구조는 `references/dispatch-guide.md` 참조. 워커 세부 절차는 `references/action-branch.md`에 있으며, 호출 프롬프트에 해당 경로를 포함시켜 워커가 읽도록 한다.

### 4단계: Reference 갈래 디스패치

`01_Inbox/reference/`와 `01_Inbox/scraps/`에 파일이 있으면 (둘 중 하나만 있어도) `inbox-reference-worker` 에이전트를 Agent 도구로 호출한다. 두 디렉터리 파일을 하나의 처리 단위 목록으로 합쳐 전달한다. 호출 프롬프트 구조는 `references/dispatch-guide.md` 참조. 워커 세부 절차는 `references/reference-branch.md`에 있으며, 호출 프롬프트에 해당 경로를 포함시켜 워커가 읽도록 한다.

### 병렬 실행

3단계와 4단계 모두 처리 대상이 있으면, **두 Agent 호출을 하나의 메시지에 함께 보내 병렬 실행**한다 (두 갈래는 상태 독립).

### 5단계: Grill 2차 → 태그 확정 → 품질 게이트 → 일괄 삭제 → 최종 보고

두 서브에이전트의 결과가 도착하면 다음 순서로 마무리한다:

1. **Grill 2차**: 워커가 올린 `## 열린 질문` 중 **결정** 항목을 §Grill 게이트 규칙대로 처리하고, 확정된 답을 노트에 직접 Edit으로 반영한다. 조사 항목은 grill하지 않는다.
2. **태그 확정 — 스크립트 우선**: action 워커가 각 노트 `## 관련`에 기재한 **후보 태그**를 먼저 스크립트로 검사한다. 워커는 tag-validator를 호출할 수 없으므로 이 단계는 오케스트레이터가 수행한다. (reference 갈래는 태그 노트를 만들지 않으므로 해당 없음.)

   ```bash
   printf '%s\n' '#업무/...' '#부서/...' | python3 .claude/skills/tag-normalize/scripts/validate_tag.py --json -
   ```

   - `valid: true` → 그대로 확정. **에이전트 호출하지 않는다.**
   - `valid: false` + `normalized ≠ original` → 스크립트가 고쳐준 건(금지 접두어 제거·직급 매핑 등). `normalized` 값을 노트에 직접 Edit으로 반영한다.
   - `valid: false` + `normalized == original` → 스크립트가 고칠 수 없는 건(미등록 area 등). 후보 태그를 그대로 확정하지 말고 `issues`와 함께 `tag-validator`(validate 모드)로 **에스컬레이션**한다.
   - 스크립트가 판단하지 못하는 문맥 의존 건(예: 팀 직함 확정, 신규 area 신설 여부)도 동일하게 **에스컬레이션**한다.

   > 근거: 규칙표 대조는 `validate_tag.py`로 결정론적으로 끝난다. status-sync·vault-cleanup이 쓰는 "스크립트 우선 → 애매한 것만 에이전트" 패턴과 동일하게 맞춘다.
3. **품질 게이트 — 기계 검사 먼저, `note-evaluator`는 조건부** (2026-07-30 개정). 워커는 서브에이전트를 호출할 수 없으므로 이 게이트는 오케스트레이터 책임이다. reference 갈래는 해당 없음.

   **3-a. 기계 검사 (항상)**: `check-template.py`·`validate-tags.sh`는 워커의 Write에 PostToolUse로 이미 발동했다. 확실치 않으면 **절대경로로** 직접 재실행한다 (상대경로면 훅이 파일을 못 찾아 무음 종료한다):

   ```bash
   printf '{"tool_input":{"file_path":"<노트 절대경로>"}}' | python3 .claude/hooks/check-template.py
   printf '{"tool_input":{"file_path":"<노트 절대경로>"}}' | bash .claude/hooks/validate-tags.sh
   python3 .claude/skills/vault-cleanup/scripts/moc_gate.py . --json   # 기준 5 임계 검출
   ```

   앞 둘이 무출력 = `docs/eval-criteria.md` 기준 1·3·4 + 기준 2의 형식·`#업무/` 존재분 통과. 경고가 나오면 지적 항목을 직접 Edit으로 수정한다.

   **훅 무음이 통과가 아닌 잔여분 2개는 여기서 직접 확인한다** (`eval-criteria.md` §기계 검사 커버리지 표):
   - `#부서/` 태그 부재 — 어느 훅도 잡지 않는다(관행 아님, 실측 28% 미보유). 담당 부서가 특정되는 건이면 채운다.
   - **기준 5 MOC 순방향 등록** — `moc_gate.py`가 이번 노트의 도메인을 임계 도달로 보고했으면 두 경우로 갈린다. `note-evaluator` 호출 여부와 무관하게 **항상** 돌리고, 원본 삭제(4단계) 전에 끝낸다.
     - **MOC가 이미 있음**: **노트가 MOC를 링크하고 MOC가 노트를 등록했는지** grep으로 확인하고, 빠졌으면 채운 뒤 `_Wiki/index.md`·`_Wiki/log.md` 등록까지 마친다.
     - **MOC가 없음(gap)**: `docs/workflows.md` → `moc` 워크플로를 그대로 수행한다 — 메인 스레드가 `vault-navigator`로 사전 조사, `obsidian-operator`로 MOC 생성, 그다음 `_Wiki/index.md`·`_Wiki/log.md` 등록. **확인만 하고 넘어가지 말 것** — MOC를 만들지 않으면 노트는 임계를 넘긴 채 Wiki Feedback Loop가 빈 상태로 수락된다.

   **3-b. `note-evaluator` 호출 (아래 중 하나라도 해당할 때만)**:
   - 3-a 기계 검사 경고가 남아 있고 수정 방향이 자명하지 않다
   - 원본이 **OCR·스캔 PDF**이거나 워커가 추출 품질에 의문을 보고했다 (사실 오독 위험)
   - 워커가 **신규 area를 생성**했다
   - `## 열린 질문`이 남아 있다 (Grill 2차로 해소되지 않은 건)
   - 회차성 반복 공문에서 **선례를 참조해 작성**했다 → stale 값(공문번호·기한·회차) 혼입 검증

   해당 없으면 **호출하지 않는다.** 실측 약 100k 토큰이며, 훅이 검사하는 범위는 3-a에서 이미 끝났고 훅이 못 잡는 잔여분도 3-a에서 직접 확인했다.

   호출할 때는 스코프를 **원본 대조 사실검증 + Wiki Feedback Loop**로 한정하고, 구조·태그 재채점을 금지한다. **원본 경로(`01_Inbox/` 파일)를 넘기고, 재추출은 검증 대상 필드(공문번호·시행/접수일·기한·담당자·회차)에 한정하라고 지시한다** — 워커의 반환 계약에 추출본 경로는 없고 `/tmp/extracted_*.pdf`는 워커가 정리했을 수 있다(`references/action-branch.md`). 근거: `docs/eval-criteria.md` → §기계 검사 커버리지.

   FAIL이면 지적 항목을 수정한 뒤 진행한다 — 자주 걸리는 항목은 MOC 순방향 등록(Wiki Feedback Loop).
4. **일괄 삭제**: 성공적으로 처리된 원본 파일을 워커의 `## 삭제 권고` 목록 기준으로 **즉시 삭제**한다. 사용자 승인을 기다리지 않는다.
5. **최종 보고**.

**삭제 제외 조건** (아래 중 하나라도 해당하면 삭제하지 않는다):
- 처리가 부분 실패이거나 열린 질문이 남아 있는 건
- 사용자가 이번 요청에서 "파일은 남겨줘" 등 보존 의사를 명시한 경우

**자동 승인 정책 차단 시**: 삭제 명령이 auto-mode 분류기에 의해 차단될 수 있다(비가역적 삭제 + 미파싱 첨부 등). 차단되면 재시도하지 말고, 삭제 대상 전체를 하나의 `AskUserQuestion`으로 묶어 사용자 승인을 받은 뒤 진행한다.

보고 형식은 `references/dispatch-guide.md` 참조. 처리 완료 후 Handysoft 임시 파일도 함께 정리한다: `rm -f /tmp/extracted_*.pdf`

## 공통 규칙

- `90_Archive/`, `99_Template/`, `.obsidian/`은 수정하지 않는다.
- Golden Principle #1(기존 노트 불변) 준수 — 본문 수정이 필요하면 사용자 확인을 받는다.
- 위키링크는 `[[노트명]]`. embed `!` 접두는 사용자가 명시적으로 요청할 때만.
- 서브에이전트가 "열린 질문"으로 올린 항목은 묵살하지 않고 사용자에게 보고한다.

## 트리거 해석

- **사용자가 텍스트를 직접 붙여넣은 경우** → §사전 확인: 인라인 텍스트 입력으로 처리. `.txt` 파일 생성 금지.
- 사용자가 파일명을 명시하면 해당 영역의 갈래만 디스패치.
- "action만", "reference만", "공문만", "자료만" → 해당 갈래만 실행.
- "공문 처리해줘" → action 중심, "수집함·InfoBox 정리해줘" → reference 중심 (기존 호칭 호환).
- "scraps 처리해줘", "웹 클립 정리해줘" → `01_Inbox/scraps/`만 reference 갈래로 디스패치.
- 지시가 없으면 스캔 결과를 요약하고 사용자 선택 대기.

## 참고 자료

- **`references/dispatch-guide.md`** — 루트 triage 읽기 방법, 분류 힌트, 워커 호출 프롬프트 구조, 최종 보고 형식
- **`references/action-branch.md`** — action 워커 세부 절차 (inbox-action-worker가 읽음)
- **`references/reference-branch.md`** — reference 워커 세부 절차 (inbox-reference-worker가 읽음)
