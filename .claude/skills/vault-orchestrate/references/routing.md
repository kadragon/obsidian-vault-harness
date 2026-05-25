# Vault Routing Rules

## 라우팅 대상

### 에이전트 (Agent 호출)

| 에이전트 | subagent_type | 역할 | 스킬 | 출력 |
|---------|--------------|------|------|------|
| incident-analyst | incident-analyst | 에러 로그 분석, 인시던트 노트 생성 | incident-analyze | `14_Changes/incident/` |
| improvement-planner | improvement-planner | 개선 계획 수립, 개선 노트 생성 | improvement-plan | `14_Changes/improvement/` |
| vault-navigator | vault-navigator | 볼트 검색, 패턴 분석 | — | 검색 결과 요약 |
| obsidian-operator | obsidian-operator | Obsidian 조작 (노트 생성, 검색, 프로퍼티) | — | 실행 결과 |
| tag-validator | tag-validator | 노트 태그 검증·수정 (haiku) | tag-normalize | 검증 결과 보고 |
| training-note-manager | general-purpose | 교육 노트 품질 평가, 템플릿 표준화, 리팩토링 | training-manage | `20_Training/` |

### 스킬 (Skill 호출)

| 스킬 | 트리거 영역 | 출력 |
|-----|------------|------|
| inbox-process | `01_Inbox/` 처리, 공문·받은 자료·수집함 정리 | `10_Areas/` 또는 `19_Reference/` |
| status-sync | open→closed 동기화, 완료된 업무 정리, status 닫기 | 프론트매터 갱신 |
| vault-cleanup | `90_Archive/` 정리, 중복 정리, 폴더 구조 통일, 오래된 노트 아카이빙 | 폴더/파일 정리 |
| syncthing-conflict-cleanup | `*.sync-conflict-*` 파일 정리, 동기화 충돌 | 충돌 파일 제거/리뷰 |
| tag-normalize | 태그 규칙·매핑 사전 조회만 필요한 경우. 실제 태그 검증·수정은 tag-validator 에이전트 사용 | 매핑 결과 |

## 요청 분류 룰

| 요청 유형 | 키워드 | 라우팅 대상 |
|----------|--------|------------|
| 에러 분석 | 에러, 오류, exception, 스택 트레이스, PARAMETER_INFO, ERR_INFO | incident-analyst |
| 시스템 개선 | 개선, 수정, 변경, 최적화, 쿼리 수정, 기능 추가, 프로시저 변경 | improvement-planner |
| 볼트 검색 | 찾기, 검색, 이전에, 과거, 비슷한, 관련, 패턴, 몇 번 | vault-navigator |
| 볼트 조작 | 노트 만들어줘, 열어줘, 프로퍼티 설정, 템플릿 적용 | obsidian-operator |
| 태그 검증·수정 | 태그 정리, 태그 검증, 태그 수정 | tag-validator |
| 태그 규칙 조회 | 태그 규칙이 뭐야, 태그 매핑 확인 | tag-normalize 스킬 |
| 교육 노트 관리 | 교육 정리, 연수 기록, 교육 템플릿, 20_Training | training-note-manager |
| Wiki/MOC 조작 | wiki, 운영 MOC, MOC 갱신, MOC 만들어, log 갱신, wiki 업데이트 | obsidian-operator |
| Wiki 탐색 | synthesis, wiki 검색, 정리 결과, wiki에 뭐가 있어 | vault-navigator |
| Inbox 처리 | inbox 정리, inbox 비워줘, 공문 처리, 받은 문서, 받은 자료, 수집함, 01_Inbox | inbox-process 스킬 |
| 상태 동기화 | 완료된 업무 정리, status 동기화, open 상태 정리, status 닫아줘, 끝난 거 닫기 | status-sync 스킬 |
| 볼트 청소 | 아카이브 정리, 중복 정리, 폴더 구조 통일, 오래된 노트, 볼트 청소, cleanup | vault-cleanup 스킬 |
| Syncthing 충돌 | sync-conflict, 동기화 충돌, conflict 파일, 충돌 파일, conflict 치워줘 | syncthing-conflict-cleanup 스킬 |
| 복합: 분析+개선 | 에러 분석 + "개선 방안도 정리해줘" | incident-analyst → improvement-planner |
| 복합: 검색+분析 | "비슷한 에러 찾고 인시던트 노트 만들어줘" | vault-navigator → incident-analyst |
| 복합: 검색+개선 | "과거 사례 참고해서 개선안 작성해줘" | vault-navigator → improvement-planner |
| 복합: 검색+Wiki갱신 | "정리해서 MOC에 반영해줘", "synthesis 만들어줘" | vault-navigator → obsidian-operator |
| 분류 불가 | 위 유형에 해당하지 않음 | 베스트 추측 대상으로 진행 + 1줄 알림 |

## 호출 패턴

### 단일 스킬

```
Skill(skill: "<스킬명>", args: "<선택>")
```

스킬은 자체 워크플로우를 가지므로 추가 컨텍스트 주입이 필요 없는 경우가 많다.
복합 작업의 한 단계로 스킬을 끼워 넣을 때(예: inbox-process 후 tag-validator)는 앞 단계의 산출물 경로를 다음 에이전트 프롬프트에 명시한다.

### 단일 에이전트

```
Agent(
  name: "{agent-name}",
  subagent_type: "{agent-type}",
  prompt: "{사용자 요청 + 맥락 정보}"
)
```

에이전트는 자신의 정의에 명시된 스킬 파일을 Read로 읽고 절차를 따라 작업한다.

### 복합 순차 실행 (incident → improvement)

```
# Step 1: incident-analyst 실행 → 결과에서 노트 경로와 진단 요약 수집
# Step 2: improvement-planner 실행
Agent(
  name: "improvement-planner",
  subagent_type: "improvement-planner",
  prompt: "이전 인시던트 분석 결과: {진단 요약}. 생성된 인시던트 노트: {노트 경로}. 이를 기반으로 개선 노트를 작성하라. 인시던트 노트를 Read로 읽고 맥락을 파악한 뒤 작업하라."
)
```

### 병렬 실행 (독립 작업)

검색과 분석이 동시에 필요한 경우 두 에이전트를 병렬 실행한다:

```
Agent(vault-navigator, run_in_background: true)  -- 유사 사례 검색
Agent(incident-analyst, run_in_background: true)  -- 에러 분석
```

두 결과를 수집하여 통합 보고한다.

## 에러 핸들링

| 상황 | 전략 |
|------|------|
| 에이전트 1개 실패 | 1회 재시도. 재실패 시 부분 결과 보고 |
| 복합 작업 중 2번째 실패 | 1번째 결과는 보존하고, 부분 완료로 보고 |
| 요청 분류 불확실 | 사용자에게 확인 후 진행 |
| 볼트 검색 결과 없음 | 검색 범위 확장 시도 후 "결과 없음" 보고 |
| 노트 생성 경로 충돌 | 파일명에 순번 추가하여 회피 |
