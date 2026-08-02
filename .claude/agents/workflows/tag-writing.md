> **Agent workflow — not a skill.** 노트를 생성하는 에이전트가 `## 관련` 섹션 태그를 쓸 때 Read로 읽는 공용 절차서다.
> 공유 소유자: `improvement-planner` · `incident-analyst` · `training-note-manager`

# 태그 작성 절차 (공용)

`## 관련` 섹션의 태그는 **에이전트가 직접 작성**한다. 어느 태그를 쓰는지는 노트 종류에 따른다 — 호출한 에이전트 정의 §태그 작성을 따른다.

> **`tag-validator`에 위임하지 말 것.** 서브에이전트 정의는 `tools:` 화이트리스트로 `Agent`·`Task`가 제외돼 있어 위임 지시는 런타임에 실행되지 않는다. 화이트리스트가 없던 시절에는 이 자리의 `Agent(subagent_type: "tag-validator")` 지시가 무음 실패해 태그가 조용히 누락됐다 (AGENTS.md 위임 비용 규칙 #1).

## 절차

1. 후보 태그를 정한 뒤 **스크립트로 검증**한다 (결정론적 — AGENTS.md 위임 비용 규칙 #2):

   ```bash
   printf '%s\n' '#업무/...' '#부서/...' | python3 .claude/lib/validate_tag.py --json -
   ```

   `#업무`만 쓰는 노트(교육 등)는 해당 줄만 넘긴다.

2. `valid: false`이고 `normalized`가 `original`과 **다르면** 스크립트가 고쳐준 것이다(금지 접두어 제거·직급 매핑 등). 그 `normalized` 값을 노트 `## 관련`에 기재한다.
3. `valid: false`인데 `normalized`가 `original`과 **같으면** 스크립트가 고칠 수 없는 건이다(미등록 area 등). 그 태그를 그대로 쓰지 말고 `issues`와 함께 **보고에 적는다**. 스크립트가 못 푸는 문맥 의존 건(팀 직함 확정, 신규 area 신설 여부)도 동일하게 후보 태그로 남기고 보고한다 — 메인 스레드가 `tag-validator`로 확정한다.
4. 쓰기 시 PostToolUse `validate-tags.sh` 훅이 재검증한다.

규칙 전문(area 목록, 부서명·직급 매핑) → `.claude/agents/workflows/tag-normalize/WORKFLOW.md`
