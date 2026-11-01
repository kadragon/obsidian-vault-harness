# 확정 페이지 구간표로 PDF 분리·병합

Step 11·12에서 원본 PDF를 확인해 사업·위원·문서별 페이지 구간과 출력 파일명을 확정한 뒤 쓴다.
스크립트는 문서 경계를 추론하거나 승인 여부를 판단하지 않는다. 필요한 프로세스 Step만 읽는 기존 절차를 유지한다.

## 구간표 계약

UTF-8 JSON 파일 하나에 원본 경로와 출력 순서를 적는다. 페이지는 1부터 세고 양끝을 포함한다.
다음 예는 원본 3쪽을 결과서 2쪽과 서약서 1쪽으로 나눈 뒤, 붙임 묶음에 다시 배치한다.

```json
{
  "version": 1,
  "allow_unused_pages": false,
  "allow_reuse": true,
  "sources": {
    "member_a": "원본/위원A 회신.pdf"
  },
  "outputs": [
    {
      "path": "결과물/위원A 심의결과서.pdf",
      "parts": [{"source": "member_a", "pages": [[1, 2]]}]
    },
    {
      "path": "결과물/위원A 서약서.pdf",
      "parts": [{"source": "member_a", "pages": [[3, 3]]}]
    },
    {
      "path": "결재상신/붙임 1. 위원A 서명서류.pdf",
      "parts": [{"source": "member_a", "pages": [[3, 3], [1, 2]]}]
    }
  ]
}
```

- `sources`: 원본 별칭 → PDF 경로. 상대경로는 JSON 파일의 폴더 기준이며 절대경로도 가능하다. 같은 원본 경로에 별칭을 여러 개 붙이지 않는다.
- `outputs`: 생성할 파일 목록. `path`는 `--output-root` 기준 상대경로이며 `.pdf`로 끝나야 한다. 파일명과 폴더명은 확정된 값을 쓴다.
- `parts`: 나열한 순서대로 결합한다. 각 `pages`도 나열한 구간 순서를 유지한다. 여러 원본을 하나의 출력에 넣어도 된다.
- `allow_unused_pages`: 기본 `false`. 선언된 원본의 모든 페이지가 하나 이상의 출력에 포함되어야 한다. 일부만 처리할 때 `true`로 정하고 결과의 `unused_pages`를 확인한다.
- `allow_reuse`: 기본 `false`. 한 페이지를 여러 출력 묶음에 재사용하려면 `true`로 정한다. 결과의 `reused_pages`를 확인한다. 같은 출력 안의 중복·겹침은 이 값과 무관하게 거부한다.
- 빈 원본·빈 출력 목록·빈 구간·범위 초과·역순 구간·누락 원본·암호화 원본은 오류다.
- 출력 경로의 `..`·절대경로·역슬래시·예약 파일명·제어문자·출력 루트 밖으로 향하는 링크를 거부한다. 대소문자·유니코드 정규화만 다른 중복 출력도 거부한다.

## 실행

```bash
# 기본은 사전검사. 출력 폴더나 파일을 만들지 않는다.
uv run --no-project --with 'pypdf>=4,<7' python .claude/skills/gwaeop-round-manage/scripts/pdf_pages.py \
  "<확정 구간표.json>" --output-root "<회차 폴더>" --dry-run

# 사전검사 결과의 파일명·페이지 순서·제외/재사용 페이지를 확인한 뒤 실행
uv run --no-project --with 'pypdf>=4,<7' python .claude/skills/gwaeop-round-manage/scripts/pdf_pages.py \
  "<확정 구간표.json>" --output-root "<회차 폴더>" --apply
```

위 명령은 `uv`의 격리 환경에 `pypdf`를 준비한다. 시스템 Python에 별도로 설치할 필요가 없다.
출력 JSON의 `ok: true`와 exit 0을 함께 확인한다.
입력 전체를 읽어 사전검사한 후 쓰며, 기존 파일은 원본·이전 출력 여부에 관계없이 덮어쓰지 않는다.
각 파일을 쓴 뒤 다시 읽어 쪽수가 구간표와 같은지 확인한다. 원본은 수정·삭제하지 않는다.

## 실패와 마무리

- 사전검사 실패: 아무 출력도 만들지 않는다. `errors`를 고친 뒤 다시 dry-run한다.
- 쓰기·재읽기 실패: 즉시 중단한다. `created`는 쪽수 검증까지 끝난 파일, `failed`는 실패한 파일,
  `not_written`은 이후 실행하지 않은 파일이다. `created_unverified: true`면 실패한 파일이 디스크에 남아 있을 수 있다.
- 완료된 출력과 미검증 파일을 자동 삭제하거나 덮어쓰지 않는다. JSON 결과를 작업 기록으로 남기고,
  다음 시도는 새 출력 폴더 또는 이미 검증된 출력을 제외한 구간표로 실행한다. 부분 재시도의 페이지 제외는 명시적으로 설정한다.
- 원본 PDF의 암호학적 전자서명 검증 상태를 새 PDF에 승계하는 기능은 아니다. 서명 원본은 계속 보존한다.
- 결과 PDF를 열어 서명·본문의 잘림과 방향을 확인한다. 스크립트의 쪽수 검사는 육안 확인을 대신하지 않는다.

회귀 테스트는 합성 PDF만 사용한다:

```bash
python3 .claude/lib/run_tests.py .claude/skills/gwaeop-round-manage/tests
```
