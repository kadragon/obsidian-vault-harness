# Reference Branch — 참고자료·수집물 → `_Sources` + `_Wiki`

`01_Inbox/reference/`에 사용자가 넣은 파일(PDF, HWPX, 웹 클립, 참고 문서)을 반자동으로 위키 레이어에 반영한다.

## 먼저 확인할 파일

- `AGENTS.md`
- `_Wiki/workflow.md`
- `_Wiki/contracts.md`

세 파일을 기준으로 레이어 역할과 문서 계약을 맞춘다.

## 기본 원칙

- `01_Inbox/reference/`는 LLM 수집함이다.
- `01_Inbox/action/`은 별도 갈래(action-branch.md)에서 처리한다.
- `90_Archive/`, `99_Template/`, `.obsidian/`은 수정하지 않는다.
- 기존 활성 노트를 갱신할 때는 관련 링크를 얇게 추가하는 수준을 우선한다.

## 트리거 해석

- 사용자가 파일명을 명시하면 그 파일만 처리한다.
- 파일명을 말하지 않고 `01_Inbox/reference`만 언급하면 최신 파일부터 확인한다.
- 최신 파일이 여러 개면, 바로 처리하기보다 후보를 짧게 보여주고 어느 파일인지 확인한다.

## 처리 순서

### 1. 소스 확인

- `01_Inbox/reference/`에서 대상 파일을 찾는다.
- 파일 형식과 제목, 관련 업무 맥락을 파악한다.
- 필요하면 `qmd`, `rg`, 기존 wiki 페이지로 관련 노트를 찾는다.

### 2. source note 작성

- 장기적으로 다시 볼 가치가 있는 자료면 `19_Reference/_Sources/` 아래에 source note를 만든다.
- source note에는 최소한 아래 내용을 넣는다.
  - 원문 식별 정보 또는 파일 경로 (신규는 `01_Inbox/reference/...` 경로를 기록)
  - 짧은 요약
  - 핵심 포인트
  - 적용 포인트
  - 관련 페이지

### 3. wiki 반영

- 관련 topic, entity, synthesis 페이지가 이미 있으면 갱신한다.
- 없고 재사용 가치가 분명하면 새 page를 만든다.
- 새 page는 `_Wiki/contracts.md`의 섹션 계약을 따른다.

### 4. 활성 노트 연결

- `10_Areas`, `12_Projects`, `14_Changes` 중 직접 관련 있는 노트가 있으면 관련 링크를 추가한다.
- 링크는 상위 요약 또는 synthesis로 연결하고, 원문 링크만 던져놓지 않는다.

### 5. 색인과 로그 갱신

- `_Wiki/index.md`에 새 진입점이 필요하면 추가한다.
- `_Wiki/log.md`에 `## [YYYY-MM-DD] ingest | 제목` 형식으로 기록한다.

### 6. 원본 파일 삭제

1~5단계가 모두 성공적으로 끝나면 `01_Inbox/reference/`의 원본 파일을 **즉시 삭제**한다. 내용은 `_Sources/`와 `_Wiki/`에 이미 반영되어 있으므로 수집함에 남겨둘 이유가 없다.

**삭제하지 않는 조건:**
- ingest가 부분 실패이거나 열린 질문이 남아 있는 건
- 사용자가 이번 요청에서 "파일은 남겨줘" 등 보존 의사를 명시한 경우

보존 조건에 해당하면 사용자에게 상태를 보고하고 지시를 기다린다.

삭제는 `rm` 한 번으로 끝낸다. 휴지통 이동이나 아카이브는 사용하지 않는다.

## 파일 형식 주의

- `.pdf`: Read 도구로 직접 읽는다. 10페이지 초과는 `pages: "1-5"`로 먼저 앞부분만 확인.
- `.txt`, `.md`: Read 도구로 읽는다.
- `.hwp`, `.hwpx`, `.xlsx`, `.docx`: 내용 직접 파싱 불가. 파일명·사용자 설명·주변 맥락으로 판단. 필요하면 사용자에게 핵심 내용을 묻는다.
- `.pdf` 중 Handysoft 포맷은 `scripts/extract_handysoft_pdf.py`로 추출 후 읽을 수 있다(action-branch와 동일).

## 기본 산출물

가능하면 한 번의 ingest에서 아래를 끝낸다.

1. source note 1건 생성 또는 갱신
2. wiki page 1건 이상 생성 또는 갱신
3. 관련 active note 링크 추가
4. `index.md`, `log.md` 갱신
5. `01_Inbox/reference/` 원본 파일 삭제

## 출력 방식

사용자에게는 아래를 짧게 보고한다.

- 어떤 파일을 처리하고 삭제했는지 (또는 삭제를 보류했다면 그 이유)
- 어떤 source/wiki/active note를 만들거나 갱신했는지
- 아직 남은 열린 질문이 있는지
