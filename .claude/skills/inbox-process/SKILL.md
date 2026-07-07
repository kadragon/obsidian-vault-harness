---
name: inbox-process
description: "This skill should be used when the user asks to process 01_Inbox/ — 문서를 분석하여 '업무사안(action)'으로 다룰지 '참고자료(reference)'로 정리할지 판단한 뒤, 각각 10_Areas/{area}/ 업무사안 노트 또는 _Sources·_Wiki/에 반영한다. 트리거 문구: 'inbox 처리', 'inbox 정리', 'inbox 비워줘', '01_Inbox 처리', '공문 처리', '공문 읽어줘', '받은 문서 정리', '받은 자료 정리', '수집함 처리', 'InfoBox 처리', '문서 정리해줘', '자료 정리해줘', '위키에 반영해줘'. inbox·공문·받은 문서·수집함·참고자료 처리 요청이면 '01_Inbox'를 명시적으로 언급하지 않아도 이 스킬이 해당된다."
---

# Inbox 처리 오케스트레이터

`01_Inbox/` 처리를 오케스트레이션하는 스킬. **실제 파일 처리는 두 서브에이전트에 위임**한다:

- **action 갈래** (공문·업무요청) → `inbox-action-worker` (sonnet)
- **reference 갈래** (참고자료·수집물) → `inbox-reference-worker` (sonnet)

오케스트레이터의 책임은 스캔, 루트 triage, 유사 노트 사전 수집(vault-navigator), 에이전트 디스패치, 사용자 확인, **태그 확정(tag-validator)**, 삭제 일괄 처리, 최종 보고다. 파일 내용 Read·노트 작성은 하지 않는다.

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
- 이 경우 1~5단계를 건너뛰고 곧바로 워커 디스패치로 이동한다.

### 0단계: HWP 사전 변환

스캔 전에 `01_Inbox/` 전체에서 `.hwp` 파일 존재 여부를 Glob으로 확인한다.

`.hwp` 파일이 없으면 이 단계를 건너뛴다.

`.hwp` 파일이 있으면:

1. 사용자에게 알림: "한컴 보안 팝업이 뜨면 **모두 허용(N)** 을 클릭하세요"
2. 변환 스크립트 실행:

```powershell
pwsh -File ".claude/skills/inbox-process/scripts/hwp_to_hwpx.ps1" -InboxPath ".\01_Inbox"
```

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
3. 필요 시 `vault-navigator` 에이전트 호출 → 유사 과거 노트 후보 수집 (중첩 서브에이전트 방지)

이후 `inbox-action-worker` 에이전트를 Agent 도구로 호출한다. 호출 프롬프트 구조는 `references/dispatch-guide.md` 참조. 워커 세부 절차는 `references/action-branch.md`에 있으며, 호출 프롬프트에 해당 경로를 포함시켜 워커가 읽도록 한다.

### 4단계: Reference 갈래 디스패치

`01_Inbox/reference/`와 `01_Inbox/scraps/`에 파일이 있으면 (둘 중 하나만 있어도) `inbox-reference-worker` 에이전트를 Agent 도구로 호출한다. 두 디렉터리 파일을 하나의 처리 단위 목록으로 합쳐 전달한다. 호출 프롬프트 구조는 `references/dispatch-guide.md` 참조. 워커 세부 절차는 `references/reference-branch.md`에 있으며, 호출 프롬프트에 해당 경로를 포함시켜 워커가 읽도록 한다.

### 병렬 실행

3단계와 4단계 모두 처리 대상이 있으면, **두 Agent 호출을 하나의 메시지에 함께 보내 병렬 실행**한다 (두 갈래는 상태 독립).

### 5단계: 태그 확정 → 일괄 삭제 → 최종 보고

두 서브에이전트의 결과가 도착하면 다음 순서로 마무리한다:

1. **태그 확정**: action 워커가 각 노트 `## 관련`에 기재한 **후보 태그**를 `tag-validator` 에이전트(validate 모드)로 검증·정규화한다. 워커는 tag-validator를 호출할 수 없으므로 이 단계는 오케스트레이터가 수행한다. (reference 갈래는 태그 노트를 만들지 않으므로 해당 없음.)
2. **일괄 삭제**: 성공적으로 처리된 원본 파일을 워커의 `## 삭제 권고` 목록 기준으로 **즉시 삭제**한다. 사용자 승인을 기다리지 않는다.
3. **최종 보고**.

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
