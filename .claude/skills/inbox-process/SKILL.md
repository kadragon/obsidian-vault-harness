---
name: inbox-process
description: |
  01_Inbox/ 문서를 '업무사안(action)'과 '참고자료(reference)'로 판별해 각각 10_Areas/{area}/ 업무사안 노트 또는 _Sources·_Wiki/에 반영.
  트리거: 'inbox 처리', 'inbox 정리', 'inbox 비워줘', '01_Inbox 처리', '공문 처리', '공문 읽어줘', '받은 문서 정리', '받은 자료 정리', '수집함 처리', 'InfoBox 처리', '문서 정리해줘', '자료 정리해줘', '위키에 반영해줘', 'scraps 처리해줘', '웹 클립 정리해줘'.
  inbox·공문·받은 문서·수집함·참고자료·웹 클립 처리 요청이면 '01_Inbox'를 명시하지 않아도 해당된다. 발신 공문 작성은 gongmun-draft.
---

# Inbox 처리 오케스트레이터

`01_Inbox/` 처리를 오케스트레이션한다. 기본 파일 처리는 두 워커에 위임한다:

- **action 갈래** (공문·업무요청) → `inbox-action-worker`
- **reference 갈래** (참고자료·수집물·웹 클립) → `inbox-reference-worker`

오케스트레이터가 하는 일: 스캔, 루트 triage, 선례 수집, Grill, 디스패치, 태그 확정, 품질 게이트, 일괄 삭제, 최종 보고. 명확한 단일 인라인·`.txt`·`.md` 건은 같은 갈래 절차를 메인에서 직접 실행할 수 있다. OCR·배치·모호한 건은 워커로 보낸다.

워커는 서브에이전트라 사용자 대화·다른 에이전트 호출을 못 한다. vault-navigator·tag-validator·incident-analyst·improvement-planner 호출과 모든 사용자 확인은 오케스트레이터 몫이고, 워커는 후보 태그·열린 질문·삭제 권고를 보고로만 돌려준다.

## 범위 선택과 실행 경로

- 사용자가 `전체`·`모두`·`비워줘`처럼 전체 범위를 명시하면 한 번만 스캔하고 그 범위를 끝까지 처리한다. 중간에 같은 범위 재승인·재스캔을 요구하지 않는다.
- 파일·폴더·`action/`·`reference/`·`scraps/`를 지정하면 지정 대상만 처리한다. 전체 Inbox를 다시 훑거나 이미 확정한 triage를 반복하지 않는다.
- 범위가 없으면 한 번 스캔해 건수와 루트 분류 후보를 제시하고 범위를 한 번 묻는다. 답을 받은 뒤 목록을 고정한다.
- 인라인 텍스트 또는 내용이 분명한 단일 `.txt`·`.md`는 메인이 해당 action/reference 절차를 그대로 수행할 수 있다. 파일 탐색·첨부 복사·원본 삭제 단계만 해당 입력에 맞게 건너뛴다.
- 여러 건·하위 폴더·OCR/스캔·`.hwpx`/`.hwp` 해석·분류가 모호한 건은 워커에 보낸다. 워커는 사용자에게 묻거나 다른 에이전트를 호출하지 않는다.

## 디렉터리 구조

```
01_Inbox/
├── action/        # 확신 있는 action → inbox-action-worker
├── reference/     # 확신 있는 reference → inbox-reference-worker
├── scraps/        # 웹 클립 수집함 → reference 갈래와 동일
└── (root)         # 분류 모호 → 오케스트레이터가 triage 후 하위 이동
```

## 사전 확인: 인라인 텍스트 입력

사용자가 파일 없이 텍스트를 직접 준 경우(공문 내용·메모·업무 요청):

- `.txt` 파일을 만들지 않는다.
- 텍스트를 바로 action/reference로 분류한다 (`references/dispatch-guide.md` §분류 힌트).
- 1~4단계를 건너뛰고 **§Grill 게이트 → 워커 디스패치**로 간다. 호출 프롬프트는 `dispatch-guide.md` §인라인 텍스트.
- 삭제할 원본이 없다.

## Grill 게이트 (모호성 해소)

| 분류 | 처리 |
|------|------|
| **사실** — 볼트·파일에서 찾을 수 있음 (화면 XML, 테이블·컬럼, 메뉴코드, 과거 이력) | 묻지 않는다. `vault-navigator`·Grep으로 조사. 못 찾으면 노트 `## 할 일`에 조사 항목으로 남긴다 |
| **결정** — 사용자만 답할 수 있음 (범위, 처리 방식, 대상 확정, 우선순위, 기한) | grill 한다 |

적용 지점 2곳: ① 워커 디스패치 전 — 오케스트레이터가 내용을 이미 보유한 경우(인라인 텍스트, triage에서 읽은 루트 파일). ② 워커 반환 후 — `## 열린 질문` 중 결정 항목, 5단계 태그 확정 **전**.

- 한 번에 한 질문, 추천 답 + 근거 병기, `AskUserQuestion` 사용. 결정 항목이 없으면 건너뛴다.
- 확정된 답은 노트 `## 현황`에 `[사용자 확인(YYYY-MM-DD)]`로 기재하고 대응하는 `## 할 일`·`## 열린 질문`을 해결 표시한다. 이 반영은 오케스트레이터가 직접 Edit한다.

## 0단계: HWP/HWPX 문서 라우팅

- `.hwpx`는 설치된 `prod:hwpx` skill을 `read/extract` 의도로 호출한다. HWPX를 일괄적으로 미지원 첨부로 분류하지 않는다.
- `.hwp`는 legacy binary라 HWPX와 같은 형식으로 취급하지 않는다. `prod:hwpx`의 변환 절차로 `.hwpx`를 만든 뒤 읽는다. 변환·추출 capability가 없거나 실패하면 `UNVERIFIED: HWP conversion/extraction unavailable`로 보고하고 원본을 보존한다.
- 변환 성공은 Inbox 원본 삭제 승인이 아니다. durable copy·최종 노트 링크·품질 게이트가 모두 확인된 뒤에만 삭제 권고한다.
- `prod:hwpx` skill 경로·스크립트가 현재 환경에서 해석되지 않으면 실패 원인과 대상 경로를 보고한다. HWP를 HWPX라고 가장하거나 내용을 추정하지 않는다.

## 1단계: Inbox 스캔

`01_Inbox/`가 없으면 "01_Inbox 폴더가 없습니다. 생성할까요?" 묻고 종료.

Glob으로 네 영역을 스캔: 루트(파일만), `action/`(바로 아래 폴더·단독 파일 각각이 업무 단위, 빈 폴더 무시), `reference/`, `scraps/`. 모두 비면 "01_Inbox가 비어 있습니다" 알리고 종료. 아니면 영역별 개수를 요약하고 선택을 기다린다:

```
01_Inbox 스캔 결과:
- 루트: 2건 (분류 필요)
- action/: 1건
- reference/: 3건
- scraps/: 12건
전체 처리할까요? 아니면 특정 영역만?
```

## 2단계: 루트 Triage (루트 파일이 있을 때만)

루트 파일을 짧게 읽어 action/reference를 제안한다 (읽기 규칙·분류 힌트: `dispatch-guide.md`). 사용자 확인 후 하위폴더로 `mv`. 모호한 건은 루트에 보류.

## 3단계: Action 갈래 디스패치

`01_Inbox/action/`에 처리 단위가 있으면 먼저 준비한다:

1. `ls 10_Areas/` → 실제 area 목록 확보
2. 처리 단위별 area 1차 판단 (모호하면 "결정 필요")
3. 선례 수집 — **MOC 우선, navigator 폴백**:

   | 상황 | 방법 |
   |------|------|
   | `_Wiki/topics/{도메인}-운영-MOC.md` 있음 | MOC 1건만 Read. navigator 호출하지 않는다 |
   | MOC 없음 · area 불명 · 시맨틱 유사 판단 필요 | `vault-navigator` 호출 |
   | MOC에 이번 건 선례가 없음 | `vault-navigator` 호출 |

   워커에 넘기는 선례는 **최대 1건**, 용도는 사실(근거법령·담당자·네이밍·반복 주기)뿐. 구조 권위는 `99_Template/` + `docs/eval-criteria.md`다 — 프롬프트 문구는 `dispatch-guide.md` §선례 전달 규칙.
4. triage에서 내용을 읽은 건에 한해 §Grill 게이트 1차 (결정 항목이 있을 때만)

이후 `inbox-action-worker`를 Agent 도구로 호출한다. 프롬프트 구조는 `dispatch-guide.md`, 워커 절차는 `references/action-branch.md`(프롬프트에 경로를 넣어 워커가 읽게 한다).

## 4단계: Reference 갈래 디스패치

`reference/`·`scraps/`에 파일이 있으면(하나만 있어도) 두 디렉터리를 하나의 목록으로 합쳐 `inbox-reference-worker`를 호출한다. 프롬프트 구조는 `dispatch-guide.md`, 워커 절차는 `references/reference-branch.md`.

**병렬 실행**: 3·4단계 모두 대상이 있으면 두 Agent 호출을 한 메시지에 담아 병렬로 보낸다.

## 5단계: Grill 2차 → 태그 확정 → 품질 게이트 → 일괄 삭제 → 보고

1. **Grill 2차**: 워커의 `## 열린 질문` 중 결정 항목을 §Grill 게이트대로 처리하고 답을 노트에 직접 Edit한다. 조사 항목은 grill하지 않는다.
2. **태그 확정 — 스크립트 우선** (action 갈래만):

   ```bash
   printf '%s\n' '#업무/...' '#부서/...' | python3 .claude/lib/validate_tag.py --json -
   ```

   - `valid: true` → 확정. 에이전트 호출하지 않는다.
   - `valid: false` + `normalized ≠ original` → `normalized` 값을 노트에 직접 Edit.
   - `valid: false` + `normalized == original` (미등록 area 등), 또는 문맥 의존 건(팀 직함, 신규 area 신설) → `issues`와 함께 `tag-validator`(validate 모드)로 에스컬레이션.
3. **품질 게이트 — 기계 검사 먼저, `note-evaluator`는 조건부** (action 갈래만):

   **3-a. 기계 검사 (항상)**. 훅은 워커의 Write에 이미 발동했다. 확실치 않으면 **절대경로로** 재실행한다(상대경로면 무음 종료):

   ```bash
   printf '{"tool_input":{"file_path":"<노트 절대경로>"}}' | python3 .claude/hooks/check-template.py
   printf '{"tool_input":{"file_path":"<노트 절대경로>"}}' | bash .claude/hooks/validate-tags.sh
   python3 .claude/lib/moc_gate.py . --json   # 기준 5 임계 검출
   ```

   앞 둘이 무출력 = `eval-criteria.md` 기준 1·3·4 + 기준 2 형식 통과. 경고는 직접 Edit으로 수정한다. 훅 무음이 통과가 아닌 잔여분 2개는 직접 확인한다:
   - **태그 area 배정이 내용과 맞는지** — 훅은 `#업무/` 존재만 본다. `#부서/`는 선택 필드다: 부재를 지적하거나 억지로 채우지 않고, 원본에 담당 부서가 명시돼 있을 때만 넣는다.
   - **기준 5 MOC 순방향 등록** — `moc_gate.py`가 임계 도달을 보고했으면 원본 삭제 전에 끝낸다. MOC가 있으면 노트→MOC 링크와 MOC→노트 등록을 grep으로 확인해 채우고 `_Wiki/index.md`·`_Wiki/log.md`까지 등록. MOC가 없으면 `docs/workflows.md` → `moc` 워크플로를 수행한다(`vault-navigator` 사전 조사 → `obsidian-operator` 생성 → index·log 등록). 확인만 하고 넘어가지 않는다.

   **3-b. `note-evaluator` 호출 — 아래 중 하나라도 해당할 때만**:
   - 3-a 경고가 남았는데 수정 방향이 자명하지 않다
   - 원본이 OCR·스캔 PDF이거나 워커가 추출 품질에 의문을 보고했다
   - 워커가 신규 area를 생성했다
   - Grill 2차로 해소되지 않은 `## 열린 질문`이 남았다
   - 회차성 반복 공문을 선례 참조로 작성했다 (stale 값 혼입 검증)

   해당 없으면 호출하지 않는다. 호출 시 스코프를 **원본 대조 사실검증 + Wiki Feedback Loop**로 한정하고 구조·태그 재채점을 금지한다. 원본 경로(`01_Inbox/` 파일)를 넘기고 재추출은 검증 대상 필드(공문번호·시행/접수일·기한·담당자·회차)로 한정한다. FAIL이면 지적 항목을 수정한 뒤 진행한다.
4. **일괄 삭제**: 워커의 `## 삭제 권고` 목록을 즉시 삭제한다. 사용자 승인을 기다리지 않는다. 제외: 부분 실패·열린 질문 잔존 건, 사용자가 보존 의사를 명시한 건. auto-mode가 삭제를 차단하면 재시도하지 말고 대상 전체를 `AskUserQuestion` 하나로 묶어 승인 후 진행한다.
5. **최종 보고** (`dispatch-guide.md` §최종 보고 형식). 임시 파일 정리: `rm -f /tmp/extracted_*.pdf`.

## 공통 규칙

- `90_Archive/`, `99_Template/`, `.obsidian/`은 수정하지 않는다.
- Golden Principle #1 — 기존 노트 본문 수정은 사용자 확인 후.
- 위키링크는 `[[노트명]]`. embed `!`는 명시 요청 시만.
- 워커의 열린 질문은 묵살하지 않고 사용자에게 보고한다.

## 트리거 해석

- 텍스트 직접 붙여넣기 → §사전 확인. `.txt` 생성 금지.
- 파일명 명시 → 해당 갈래만. "action만"·"공문만" → action, "reference만"·"자료만"·"수집함·InfoBox" → reference, "scraps"·"웹 클립" → `scraps/`만 reference 갈래로.
- 지시가 없으면 스캔 결과를 요약하고 선택 대기.

## 참고 자료

- `references/dispatch-guide.md` — triage 읽기 방법, 분류 힌트, 워커 호출 프롬프트, 최종 보고 형식
- `references/action-branch.md` — action 워커 절차 (워커가 읽음)
- `references/reference-branch.md` — reference 워커 절차 (워커가 읽음)
- `references/pdf-reading.md` — PDF 분류·읽기·OCR 절차 (두 워커 공통)
