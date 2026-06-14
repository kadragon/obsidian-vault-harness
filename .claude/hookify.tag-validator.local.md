---
name: tag-validator
enabled: true
event: file
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.md$
  - field: new_text
    operator: regex_match
    pattern: "#(업무|부서)/"
---

**태그 검증 위임 필요!** `.md` 파일에 `#업무` 또는 `#부서` 태그가 포함되어 있습니다.

`tag-validator` 에이전트를 **validate 모드**로 위임하여 태그 규칙 위반을 자동 검출하세요:

```
Agent(tag-validator, mode=validate, target=<작성한 파일 경로>)
```

직접 검증하지 말 것 — 반드시 에이전트에 위임할 것.

> **루프 방지:** `tag-validator`가 파일을 수정해도 이 hook이 재귀 호출되지 않는다.
> PostToolUse hook은 Claude의 tool call에만 반응하며, 에이전트 내부 Edit도 동일하게 hook을 트리거하지만 `tag-validator`는 수정 후 즉시 종료(추가 write 없음)하므로 무한 루프가 발생하지 않는다.
