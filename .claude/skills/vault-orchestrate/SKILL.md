---
name: vault-orchestrate
description: "This skill should be used when the user asks to perform any Obsidian vault task and it is unclear which skill or agent to use. Routes requests to the appropriate agent (incident-analyst, improvement-planner, vault-navigator, obsidian-operator, tag-validator, training-note-manager) or skill (inbox-process, status-sync, vault-cleanup, syncthing-conflict-cleanup, tag-normalize). Handles both single-task routing and multi-step orchestration. Vault tasks only — non-vault skills (codex, plugin-dev, commit-commands, etc.) bypass this skill. Triggers (Korean): inbox 정리, 공문 처리, 에러 분석, 개선 계획, 노트 만들기, 태그 정리, status 동기화, 아카이브 정리, conflict 파일 정리, 볼트 검색 등 볼트 관련 모든 작업."
---

# Vault Orchestrator

Obsidian 볼트 작업을 위한 단일 진입점. 에이전트 직접 호출·스킬 위임·복합 조율 모두 처리한다.

## 워크플로우

### Phase 1: 요청 분류

`references/routing.md`를 Read로 읽어 키워드·매핑 표를 파악한 뒤, 요청에 맞는 대상과 호출 방식을 결정한다.

- **단일 에이전트** → Agent 호출 후 종료
- **단일 스킬** → Skill 호출 후 종료
- **복합(순차/병렬)** → Phase 2로 진행
- **분류 신뢰도 낮음** → 가장 가능성 높은 후보로 결정하되, 첫 출력 한 줄에 "**~로 진행합니다(다른 의도면 알려주세요)**"를 출력 후 즉시 진행. 두 후보가 명백히 동률일 때만 사용자에게 1회 확인한다.

### Phase 2: 에이전트 실행

에이전트를 호출하기 전, 복합 작업이면 먼저 컨텍스트를 pre-fetch한다:

```bash
qmd query "{사용자 요청 핵심 문장}" -n 5
```

결과에서 관련 노트 경로와 핵심 요약을 추출하여, 이후 에이전트 프롬프트의 **맥락 섹션**에 주입한다. 결과가 없거나 관련도가 낮으면 생략한다.

`references/routing.md`의 「호출 패턴」 섹션을 따라 Agent 도구를 호출한다. 선택 가능한 패턴:

- **단일 호출** — 한 에이전트에게 전체 작업 위임
- **순차 호출** — 앞 에이전트 결과(노트 경로, 진단 요약 등)를 뒤 에이전트 프롬프트에 주입
- **병렬 호출** — 독립 작업이면 `run_in_background: true`로 동시 실행 후 결과 수집

순차 실행 시 앞 단계 산출물(노트 경로·핵심 요약)을 반드시 다음 단계 프롬프트에 명시하고, "해당 노트를 Read로 읽고 맥락을 파악한 뒤 작업하라"를 지시한다.

### Phase 3: 결과 통합 및 보고

에이전트 결과를 수집하여 사용자에게 다음을 보고한다:

1. 생성된 노트 경로
2. 핵심 분석 결과 요약
3. 추가 필요 조치 (있을 경우)
4. 에이전트가 올린 열린 질문

## 데이터 흐름

```
사용자 요청 → [라우팅] → { 단일 에이전트 | 순차 체인 | 병렬 실행 }
                                  │
                                  ↓
                        볼트에 노트 생성 또는 검색 결과 반환
                                  │
                                  ↓
                            사용자에게 통합 보고
```

**복합 작업 예시:**

```
사용자 요청 → [vault-navigator] → 검색 결과 ─┐
                                              ├→ [incident-analyst | improvement-planner] → 노트 생성 → 사용자 보고
사용자 요청 → [incident-analyst] → 인시던트 노트 → [improvement-planner] → 개선 노트 → 사용자 보고
```

## 에러 핸들링

에러 전략은 `references/routing.md`의 「에러 핸들링」 섹션을 따른다. 요약:

- 1회 재시도 후 부분 결과 보고 (자동 재시도 반복 금지)
- 복합 작업 중 후속 단계 실패 시 앞 단계 결과 보존
- 분류 불확실·결과 없음은 사용자에게 즉시 보고

## Additional Resources

- **`references/routing.md`** — 에이전트 매핑 표, 요청 분류 키워드, 호출 패턴(단일·순차·병렬), 상세 에러 핸들링 룰
