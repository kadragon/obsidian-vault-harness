---
name: inbox-process
description: |
  01_Inbox/ 문서를 '업무사안(action)'과 '참고자료(reference)'로 판별해 각각 10_Areas/{area}/ 업무사안 노트 또는 _Sources·_Wiki/에 반영.
  트리거: 'inbox 처리', 'inbox 정리', 'inbox 비워줘', '01_Inbox 처리', '공문 처리', '공문 읽어줘', '받은 문서 정리', '받은 자료 정리', '수집함 처리', 'InfoBox 처리', 'scraps 처리해줘', '웹 클립 정리해줘'.
  '문서 정리해줘'·'자료 정리해줘'·'위키에 반영해줘'는 01_Inbox/수집함 대상일 때만 해당된다.
  inbox·공문·받은 문서·수집함·참고자료·웹 클립 처리 요청이면 '01_Inbox'를 명시하지 않아도 해당된다. 발신 공문 작성은 knue-gongmun-draft.
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
- 여기서 처리 목록과 실행 주체(메인 또는 워커)를 확정하고 이후 단계에서 유지한다. 메인 실행도 해당 갈래의 references 절차와 5단계 게이트를 따른다.

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
- 파일 스캔·이동은 건너뛰고 §Grill 게이트를 거친 뒤, 위에서 확정한 실행 주체가 해당 갈래를 처리한다. 워커 실행일 때만 `dispatch-guide.md` §인라인 텍스트 프롬프트를 쓴다.
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

- `.hwpx`는 `python3 .claude/lib/hwpx_text.py "<파일>" --out "$(python3 -c 'import tempfile;print(tempfile.gettempdir())')/hwpx_<파일명>.md"`로 추출한다(`prod:hwpx` `text.py` 공용 해석 — gwaeop-simui-review와 같은 경로). HWPX를 일괄적으로 미지원 첨부로 분류하지 않는다. exit 3은 `UNVERIFIED`(도구 부재·추출 실패) — 그때만 맥락 기반 보류로 내려간다.
- `.hwp`는 legacy binary라 HWPX와 같은 형식으로 취급하지 않는다. `prod:hwpx`의 변환 절차로 `.hwpx`를 만든 뒤 읽는다. 변환·추출 capability가 없거나 실패하면 `UNVERIFIED: HWP conversion/extraction unavailable`로 보고하고 원본을 보존한다.
- 변환 성공은 Inbox 원본 삭제 승인이 아니다. durable copy·최종 노트 링크·품질 게이트가 모두 확인된 뒤에만 삭제 권고한다.
- `prod:hwpx` skill 경로·스크립트가 현재 환경에서 해석되지 않으면 실패 원인과 대상 경로를 보고한다. HWP를 HWPX라고 가장하거나 내용을 추정하지 않는다.

## 1단계: Inbox 스캔

`01_Inbox/`가 없으면 "01_Inbox 폴더가 없습니다. 생성할까요?" 묻고 종료.

확정된 범위만 Glob으로 스캔한다. 범위가 없으면 네 영역을 스캔한다: 루트(파일만), `action/`(바로 아래 폴더·단독 파일 각각이 업무 단위, 빈 폴더 무시), `reference/`, `scraps/`. 대상이 비면 알리고 종료한다. 범위가 확정됐으면 건수만 보고하고 진행하며, 미확정일 때만 아래처럼 선택을 묻는다:

```
01_Inbox 스캔 결과:
- 루트: 2건 (분류 필요)
- action/: 1건
- reference/: 3건
- scraps/: 12건
전체 처리할까요? 아니면 특정 영역만?
```

## 2단계: 루트 Triage (루트 파일이 있을 때만)

대상 루트 파일을 짧게 읽어 action/reference로 분류한다 (읽기 규칙·분류 힌트: `dispatch-guide.md`). 확정된 처리 범위 안에서 분류가 명확하면 하위폴더로 `mv`하고, 분류가 모호한 건만 사용자에게 확인할 때까지 루트에 보류한다.

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

메인 실행이면 `references/action-branch.md`를 읽고 직접 처리한다. 워커 실행이면 `inbox-action-worker`를 호출한다. 프롬프트 구조는 `dispatch-guide.md`이며, `references/action-branch.md` 경로를 넣어 워커가 읽게 한다.

## 4단계: Reference 갈래 디스패치

`reference/`·`scraps/` 중 확정된 범위의 파일만 하나의 목록으로 합친다. 메인 실행이면 `references/reference-branch.md`를 읽고 직접 처리하고, 워커 실행이면 `dispatch-guide.md` 프롬프트로 `inbox-reference-worker`를 호출한다.

**병렬 실행**: 3·4단계 모두 워커 실행 대상이면 두 Agent 호출을 한 메시지에 담아 병렬로 보낸다.

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

   3-a 경고가 남았는데 수정 방향이 자명하지 않으면 평가자에게 넘기지 않는다 — 평가자 기본 모드는 구조·태그를 보지 않는다. 메인이 해당 템플릿·`eval-criteria.md`를 보고 고치고, 그래도 남으면 그 노트를 4단계 삭제에서 제외한다. 워커가 신규 area를 만든 건은 `tag-validator`(validate 모드)로 area 적합성을 확인한다.

   **3-b. `note-evaluator` 호출 — 아래 중 하나라도 해당할 때만** (전부 원본 값이 틀렸을 위험이다):
   - 원본이 OCR·스캔 PDF이거나 워커가 추출 품질에 의문을 보고했다
   - Grill 2차로 해소되지 않은 `## 열린 질문`이 남았다
   - 회차성 반복 공문을 선례 참조로 작성했다 (stale 값 혼입 검증)

   해당 없으면 호출하지 않는다. 호출은 **기본 모드(원본 대조 사실검증)** 다 — `full-quality`를 넣지 않는다. 구조·태그·MOC는 3-a에서 끝났으므로 평가자에게 넘기지 않고, 평가자도 훅을 재실행하지 않는다. 프롬프트에는 노트 경로(이번 작업에서 새로 만든 노트임을 명시), 원본 경로(`01_Inbox/` 파일)와 워커가 남긴 추출본 경로(있으면), 검증 대상 필드(공문번호·시행/접수일·기한·담당자·회차)를 넣는다.

   반환은 노트별 `필드 | 원본 값 | 노트 값 | 결과` 표와 `VERDICT`·`HOLD_DELETE` 줄이다. `FAIL`은 평가자가 고친 `FIXES`를 확인하고, 수정 후에도 `FAIL`이 남으면 직접 원본 값으로 고친다. `HOLD_DELETE: yes`인 노트의 원본은 4단계에서 삭제하지 않는다 — 단 `UNVERIFIED` 행 없이 `FAIL`만 원인이었고 메인이 그 행을 원본 값과 다시 대조해 일치시켰으면 보류를 해제한다.
4. **완료 원본 자동 삭제**: `references/cleanup-manifest.md` 계약으로 이번 처리 범위와 파일별 완료·품질·보류 상태, 원본·최종 노트 해시를 manifest에 기록한다. 워커 반환을 검증하고 품질 게이트가 끝난 시점의 해시를 사용한다.

   ```bash
   python3 .claude/skills/inbox-process/scripts/cleanup_completed.py "<scratch>/cleanup.json" --vault .
   python3 .claude/skills/inbox-process/scripts/cleanup_completed.py "<scratch>/cleanup.json" --vault . --apply
   ```

   처리 요청에는 검증된 완료 원본 정리가 포함된다. dry-run 보고로 끝내거나 재승인을 묻지 않고, 검증된 완료건은 `--apply`까지 실행한다. 실제 파일 삭제(`unlink`)이며 휴지통 이동이 아니다. 개별 항목 오류·부분 보류(exit 1)가 있어도 성공건을 적용하고 보류건만 남긴다. manifest 최상위 형식·scope 오류(exit 2)는 수정 전 적용하지 않는다.

   - reference: 사본 SHA-256 일치와 최종 source note의 정확한 wikilink를 삭제 직전에 재확인한다.
   - action: 최종 업무 노트의 존재·범위, 사본 SHA-256 일치를 확인한다. `text-absorbed`는 `.txt`·`.md` UTF-8 원문 전체가 노트 본문에 정확히 포함된 경우만 허용한다. 요약·의미상 반영만으로 삭제하지 않는다.
   - 원본·노트 해시 변경, 미완료·품질 미통과·보류·미등록 파일은 보존한다. OS 부산물도 미등록이면 남긴다. `rmtree`·폴더째 삭제·별도 `rm`은 사용하지 않는다. 스크립트가 검증된 파일을 개별 삭제하고 빈 하위 폴더만 정리한다.
   - 승인 검토 시스템이 삭제를 차단하면 우회하지 않고 차단 사유와 미삭제 목록을 보고한다. 기존 사용자 권한을 근거로 반복 승인 요청하지 않는다.

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
- `references/cleanup-manifest.md` — 완료 원본 자동 삭제 manifest·실행·보류 계약
