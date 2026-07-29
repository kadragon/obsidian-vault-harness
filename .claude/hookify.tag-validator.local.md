---
name: tag-validator
enabled: false
event: file
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.md$
  - field: new_text
    operator: regex_match
    pattern: "#(업무|부서)/"
---

> **비활성화됨 (2026-07-24).** `.claude/hooks/validate-tags.sh`(PostToolUse)가 동일 검증을 결정론적으로 수행하고 **위반이 있을 때만** 경고하며, 그 경고문이 이미 "tag-validator 에이전트를 실행하여 태그를 정규화하세요"로 안내한다. 이 룰은 위반이 없어도 매 쓰기마다 풀에이전트(~39k 토큰/40초)를 기동시켜 순수 중복 비용이었다. 되살리려면 `enabled: true`로 바꾸되 `validate-tags.sh`와의 중복을 먼저 해소할 것.

**태그 검증 위임 필요!** `.md` 파일에 `#업무` 또는 `#부서` 태그가 포함되어 있습니다.

`tag-validator` 에이전트를 **validate 모드**로 위임하여 태그 규칙 위반을 자동 검출하세요:

```
Agent(tag-validator, mode=validate, target=<작성한 파일 경로>)
```

직접 검증하지 말 것 — 반드시 에이전트에 위임할 것.

> **루프 방지:** `tag-validator`의 Edit도 이 hook을 재트리거한다. 안전한 이유는 **멱등성(idempotence)**: 태그가 이미 정규화된 상태라면 두 번째 실행에서 위반이 없어 에이전트를 재호출하지 않는다. 단, normalization이 매 실행마다 파일을 변경한다면 루프가 발생할 수 있으므로, 수정 후 재검증 결과가 "위반 없음"이어야 한다.
