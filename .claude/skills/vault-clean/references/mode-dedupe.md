# Mode: Dedupe — 중복 후보·deadlink 점검

파일명·키워드가 겹치는 노트 짝을 후보로 뽑아 검토 리스트를 제시하고, wiki deadlink를 점검한다. 의미 유사도(벡터) 탐지는 하지 않는다.
**자동 삭제·통합 금지 — 목록 제시 후 사용자 결정.**

## Step 1: 탐지 범위 확정

사용자 요청에서 탐지 대상을 확인한다. 명시 없으면 기본 범위:

- `14_Changes/incident/` + `14_Changes/improvement/` (가장 중복이 많은 영역)
- `10_Areas/` 는 사용자 요청 시에만 추가
- `90_Archive/` 는 기본 제외 (--include-archive 명시 시만)

## Step 2: 중복 후보 추리기

1. **파일명 유사성**: `ls 14_Changes/ | sort`로 같은 날짜·유사 제목 짝을 확인
2. **동일 프로시저 + 동일 날짜**: `rg --no-ignore -l "{프로시저명}" 14_Changes/incident`로 확인
3. **사용자 지정 키워드**: 특정 업무 도메인만 검사하는 경우 그 키워드로 `rg --no-ignore -l`

`rg`는 `--no-ignore` 없이는 노트를 못 본다(AGENTS.md §Search Priority).

## Step 3: 중복 후보 목록 제시

후보 짝은 두 노트를 Read해 판정한다:

- **MERGE 검토** — 같은 사안을 두 번 기록했다
- **REVIEW** — 겹치지만 구분되는 사안일 수 있다
- 그 외는 보고하지 않는다

보고 형식:

```
## 중복 후보

- [[노트A]] ↔ [[노트B]] — MERGE 검토 — {근거 1줄}
```

후보가 없으면 "중복 후보 없음"으로 보고하고 종료.

## Step 4: Wiki Deadlink 점검 (archive 이동 후 선택 실행)

`mode-archive.md` 실행으로 노트가 90_Archive로 이동된 직후, 선택적으로 실행한다.

이동된 노트 파일명이 `_Wiki/`에서 wikilink로 참조되고 있는지 확인:

```bash
grep -rn "{이동된 노트 파일명}" \
  "_Wiki/index.md" "_Wiki/log.md" "_Wiki/topics/" 2>/dev/null
```

발견된 deadlink 목록을 보고한다. 자동 수정은 하지 않으며, 수정 여부를 사용자에게 확인한다. 승인 시 **직접 Edit**으로 고친다 (링크 한두 줄 수정에 에이전트 왕복 금지 — AGENTS.md 위임 비용 규칙 #3).
