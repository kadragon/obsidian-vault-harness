# Inbox·평가 하네스 규칙 충돌 정리

## Problem Statement

2026-09-09 하네스 감사에서 6건이 나왔다. 지적 2(날짜 규칙)는 선행 커밋 `91627bd`로 해소됐고,
`copy_verified.py`(`10b2c03`)와 상위 정책 문서 개정(`c3801fa`)도 들어갔다. 남은 문제는 전부
**같은 규칙이 문서마다 다르게 적혀 있어 절차대로 실행해도 잘못된 결과가 나오는** 형태다.

1. **원문이 보존 증명 없이 삭제된다.** `reference-branch.md:45`는 source note에 `01_Inbox/...`
   경로를 기록하게 하고, `SKILL.md` 4단계는 워커의 삭제 권고 목록을 "즉시 삭제"한다. 그 사이에
   durable copy를 만들거나 최종 노트의 링크가 살아남을 경로를 가리키는지 확인하는 단계가 없다.
   `copy_verified.py`는 그 게이트를 수행할 수 있게 작성됐지만 **어떤 절차서에서도 호출되지 않는다**
   (`grep -rn copy_verified` → 스크립트·테스트 외 0건). action 갈래는 첨부 복사가 있어 비대칭이다.
   같은 자리의 단계 참조도 모호하다 — `SKILL.md`의 `## 5단계` 섹션 안에 하위 항목 4번(일괄 삭제)이
   있어 "SKILL.md 5단계"가 섹션과 하위 항목 중 무엇을 가리키는지 읽는 쪽이 갈린다 (실제로 이번 감사가
   이를 오참조로 오판했다).
2. **평가자 계약이 상위 규칙과 반대다.** `AGENTS.md` 위임 비용 규칙 #5와 위임표는 이미 "기본 모드 =
   원본 대조 사실검증, 5축은 명시 요청 시"로 개정됐는데, `note-evaluator.md`는 여전히 훅 재실행
   (절차 2)·구조/태그 잔여분 확인(절차 3)·5축 점수 출력(절차 5·출력 블록)을 지시한다. `SKILL.md`
   3-b는 호출 시 "구조·태그 재채점 금지"를 요구하므로, 호출자와 피호출자가 서로 다른 계약을 말한다.
   기계 검사는 메인(3-a)과 평가자(절차 2)에서 두 번 돌아간다. reference 갈래에는 품질 게이트가
   아예 없어, 위험도가 아니라 갈래 이름으로 검증 비용이 배분돼 있다.
3. **정책이 세 곳에 부분 반영돼 서로 모순된다.**
   - 첨부 임베드: `AGENTS.md` GP#2와 `note_rules.py`는 첨부 `![[...]]`를 허용하는데
     `docs/eval-criteria.md:74-81`은 embed가 있으면 무조건 1점(binary)이다.
   - 교육 노트 `#업무/` 면제: `eval-criteria.md:43`·`:112`는 "위반 아님"으로 명시하는데
     `note-evaluator.md:35`는 "없으면 finding"으로 지시한다.
   - 기존 위키 본문 갱신: `reference-branch.md:97`은 "기존 페이지가 있으면 갱신"을 요구하고
     `inbox-reference-worker.md:54`는 "얇은 링크 추가만"으로 금지한다.
4. **HWPX 처리 능력이 진입점마다 다르다.** `gwaeop-simui`는 `extract_bundle.py`의
   `find_hwpx_text_py()`로 prod:hwpx `text.py`를 찾아 markdown을 뽑는다. 같은 볼트의
   `reference-branch.md:125`와 `inbox-reference-worker.md:58`은 `.hwpx`를 "내용 직접 파싱 불가"로
   묶어 파일명·맥락으로 추정하게 한다. `SKILL.md` 0단계만 prod:hwpx 라우팅으로 바뀌어 있어 워커
   문서와 어긋난다. 부수적으로 `AGENTS.md` 위임표는 없는 이름인 `productivity:hwpx`를 가리킨다
   (실제 설치 경로는 `~/.claude/plugins/marketplaces/kadragon/prod/skills/hwpx`).

방치하면 (1)은 자료 손실, (2)는 노트 1건당 중복 LLM 비용, (3)(4)는 실행자가 어느 문서를 읽었는지에
따라 결과가 갈리는 비결정성으로 남는다.

## Solution

문서를 더 쓰지 않고 **충돌하는 쪽을 SSOT 한 곳으로 접는다.** 네 갈래:

- **삭제 게이트 배선** — `copy_verified.py`를 reference 갈래 절차에 넣는다. 워커는 durable copy를
  만들고 `verify-link`가 통과한 건만 `## 삭제 권고`에 올린다. 오케스트레이터는 삭제 직전
  `verify-link`를 재확인한다. 검증 실패·미수행 건은 삭제 대상에서 빠지고 `UNVERIFIED`로 보고된다.
  단계 번호 참조도 함께 바로잡는다.
- **평가자 계약 재작성** — `note-evaluator.md`를 기본 모드(원본 대조 사실검증) 우선으로 재작성한다.
  출력은 `필드 | 원본 값 | 노트 값 | 결과(PASS·FAIL·UNVERIFIED)` 표. 값 불일치는 FAIL, 원본 부재는
  UNVERIFIED이며 UNVERIFIED가 있으면 원본 삭제를 보류한다. 훅은 메인이 3-a에서 한 번 돌리고 결과를
  넘기며, 평가자는 재실행하지 않는다. 5축 채점은 `full-quality` 인자를 받은 경우로 한정한다.
  reference 갈래에도 같은 기본 모드 게이트를 조건부로 적용한다(조건부 호출 규칙 자체는 유지).
- **정책 SSOT 정리** — 세 충돌 각각에 소유 문서를 하나 정하고 나머지는 참조만 남긴다.
  임베드·태그 면제는 `eval-criteria.md`(평가 규칙)와 `AGENTS.md` GP#2(볼트 규칙) 중 후자가 상위이며
  `eval-criteria.md`가 예외를 반영한다. 기존 노트 수정 범위는 `AGENTS.md` GP#1이 SSOT이고
  절차서·워커는 그 문장을 참조한다.
- **HWPX 추출 경로 공유** — `find_hwpx_text_py()` 상당의 해석 로직을 두 진입점이 함께 쓰는 형태로
  올리고(`gwaeop-simui` 전용 스크립트 안에 갇혀 있는 현재 위치에서 공용 위치로), reference 갈래는
  `.hwpx`를 추출 시도 대상으로 재분류한다. 도구 부재·실제 추출 실패일 때만 맥락 기반 보류로 내려간다.
  `.hwp`(레거시 바이너리)는 변환 없이는 추출 불가라는 현재 판정을 유지한다.

## User Stories

- 볼트 운영자로서, Inbox 원문이 삭제되기 전에 durable copy와 노트 링크가 검증되기를 원한다 — 요약
  노트가 사라진 파일을 가리키지 않도록.
- 볼트 운영자로서, 품질 게이트가 원본과 노트 값의 불일치를 표로 보여주기를 원한다 — 구조 점수
  재채점이 아니라 사실 오류를 잡는 것이 게이트의 목적이므로.
- 하네스 관리자로서, 한 규칙이 한 문서에만 정의되기를 원한다 — 어느 문서를 읽었는지에 따라 실행
  결과가 갈리지 않도록.
- Inbox 처리자로서, `.hwpx`가 진입점과 무관하게 같은 방식으로 읽히기를 원한다 — 같은 형식이
  gwaeop-simui에서는 읽히고 inbox에서는 추정되는 상태를 없애도록.

## Implementation Decisions

- **삭제 조건은 세 항목의 AND** — durable copy 생성 성공, source/copy SHA-256 일치, 최종 노트에
  vault-relative wikilink 존재. `copy_verified.py verify-link`가 이미 이 셋을 판정하므로 새 판정
  로직을 쓰지 않는다(재사용 우선).
- **durable 목적지는 호출자가 정한다** — 스크립트가 이미 그렇게 설계돼 있다. reference 갈래는
  `_Sources/_Assets/{도메인}/`을 기본으로 쓰고 예외는 열린 질문으로 보고한다.
- **워커는 삭제하지 않는다** — 현행 유지. 게이트만 앞당기고 삭제 주체는 오케스트레이터로 둔다.
- **평가자 출력 형식 변경은 호출자 동시 수정을 요구한다** — `SKILL.md` 3-b가 소비 형식을 명시하므로
  같은 티켓에서 함께 고친다.
- **훅 1회 실행 원칙** — 메인이 `check-template.py`·`validate-tags.sh`를 돌리고 결과 텍스트를
  평가자 프롬프트에 넣는다. 평가자 문서에서 훅 실행 절차를 제거한다.
- **`eval-criteria.md` Wikilink Style은 binary를 유지하되 대상을 노트 임베드로 한정** — 첨부 파일
  임베드는 채점 대상에서 제외한다. 가중치·임계는 건드리지 않는다.
- **HWPX 공용 헬퍼는 신규 의존성 없이 stdlib만** — 현행 `extract_bundle.py`와 같은 제약.
  `gwaeop-simui` 동작은 회귀 테스트로 고정한 뒤 이동한다.
- **`AGENTS.md`의 `productivity:hwpx` 표기는 `prod:hwpx`로 정정** — 실제 설치 경로 기준.

## Testing Decisions

- **결정론적인 것은 스크립트·테스트로** (AGENTS.md 위임 비용 규칙 #6): 삭제 게이트와 HWPX 경로
  해석은 파이썬 테스트로 고정한다. 기존 러너 관행을 따른다 —
  `python3 .claude/skills/inbox-process/tests/test_copy_verified.py` 처럼 파일 단위 실행, exit 0.
- 삭제 게이트: 검증 실패 시 삭제 권고 목록에 오르지 않음을 테스트로 표현한다(권고 산출 함수가
  스크립트화되는 경우). 순수 문서 규칙으로 남는 부분은 문서 상호 참조가 서로 모순되지 않는지
  grep 기반으로 확인한다.
- HWPX: 텍스트 추출기 경로 해석이 marketplaces·cache 양쪽에서 동작하고, 미설치 시 예외가 아니라
  `UNVERIFIED` 신호를 내는지 테스트한다. `.hwp`는 변환 필요 상태를 유지하는지 함께 고정한다.
- 문서 계약(평가자 출력 형식, 정책 SSOT)은 테스트 대상이 아니다 — 변경 후 실제 호출 1회로
  관찰 검증하고, 상충 문장이 남아 있지 않은지 `grep`으로 확인한다.
- 회귀: `python3 .claude/skills/status-sync/tests/test_contract.py`,
  `python3 .claude/hooks/tests/test_check_todo_due_date.py`, `python3 .claude/lib/vault_lint.py --strict`.

## Out of Scope

- 스킬 9개 병합·이름 통일 — 역할 분리는 타당하다고 판정됨.
- 유지 권고 항목 변경 금지: MOC 우선 검색, 조건부 평가자 호출 규칙, 중첩 위임 차단
  (`tools:` 화이트리스트), 정리 스크립트의 dry-run·휴지통 이동.
- 기존 노트 본문 일괄 수정 — `tasks.md`의 레거시 백필(태그·앵커 누락)은 별건이며 사용자 승인 대상.
- 지적 2(날짜 규칙) 추가 작업 — `91627bd`로 완료.
- 삭제된 원문의 소급 복구 — 실제 손실 발생 여부는 감사 범위 밖이었고 이번에도 조사하지 않는다.

## Not yet specified

- 지적 6(반복 확인·단건 위임 간소화)의 잔여분 — `SKILL.md` §범위 선택으로 재확인 루프는 줄었으나,
  스캔·triage 단계에서 어떤 확인이 여전히 중복인지는 호출 비용을 실측하기 전에는 질문을 날카롭게
  세울 수 없다. 재방문 지점: `SKILL.md` 1~2단계 + `dispatch-guide.md` triage 절차.
- reference 갈래 품질 게이트의 **조건** — 기본 모드를 적용한다는 것까지는 정해졌으나, action 갈래의
  5개 조건(3-b) 중 어느 것이 reference에 그대로 옮겨지는지는 첫 실행 관찰 후 정하는 편이 낫다.

## Further Notes

- 위험 순서: (1) 삭제 게이트가 가장 높다 — 유일하게 데이터 손실로 이어진다. (2)는 비용, (3)(4)는
  비결정성.
- `copy_verified.py`는 이미 커밋돼 있으므로 배선 티켓은 스크립트를 쓰지 않고 절차서만 고친다 —
  단, 워커가 실제로 호출 가능한 인터페이스인지 첫 티켓에서 확인한다.
- `AGENTS.md`는 always-loaded 파일이므로 이번 작업으로 줄 수가 늘어나면 안 된다. 정책 SSOT 정리는
  참조를 남기고 중복을 지우는 방향이어야 한다.
