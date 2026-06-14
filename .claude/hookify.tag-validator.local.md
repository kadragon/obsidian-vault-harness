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

> **루프 방지:** `tag-validator`의 Edit도 이 hook을 재트리거한다. 안전한 이유는 **멱등성(idempotence)**: 태그가 이미 정규화된 상태라면 두 번째 실행에서 위반이 없어 에이전트를 재호출하지 않는다. 단, normalization이 매 실행마다 파일을 변경한다면 루프가 발생할 수 있으므로, 수정 후 재검증 결과가 "위반 없음"이어야 한다.
