# PDF 읽기 절차 (action·reference 워커 공통)

Read 도구로 PDF를 직접 열지 않는다. 분류 → 본문 읽기 → (필요 시) OCR 순서다.

## 1. 분류 — 항상 먼저

```bash
uv run .claude/skills/inbox-process/scripts/classify_pdf.py "a.pdf" ["b.pdf" ...]
```

Handysoft 언랩·스캔본 판별을 이 한 번의 호출이 처리한다. 파일별 JSON이 나온다.

- **`type`이 아니라 `action`을 따른다** (`mixed`인데 OCR 대상 페이지가 없는 경우가 있다).
- **원본이 아니라 항상 `read_path`를 읽는다** (Handysoft면 추출된 임시 PDF, 아니면 원본).
- `error` 필드가 있으면 그 파일은 건너뛰고 보고에 기록한다.

| `action` | 처리 |
|---|---|
| `read` | `read_path`를 PyMuPDF로 읽는다 (§2) |
| `ocr` | 전 페이지 스캔본. 바로 OCR (§3) |
| `read+ocr` | §2 후 `ocr_ranges` 항목마다 §3 한 번씩 |

## 2. 본문 읽기 — PyMuPDF

```python
import fitz
doc = fitz.open(read_path)          # classify_pdf.py 가 반환한 경로
text = "\n".join(page.get_text() for page in doc)
doc.close()
```

대용량은 앞 1~5쪽만 먼저 뽑아 제목·발신부서·요청사항을 잡고 필요한 범위만 넓힌다.

## 3. OCR — `action`이 `ocr`·`read+ocr`일 때만

```bash
uv run .claude/skills/inbox-process/scripts/ocr_pdf.py "<read_path>" --pages 3-5
```

- `--pages`는 단일 페이지(`7`) 또는 연속 구간(`3-5`) **하나만** 받는다. `ocr_ranges`가 그 형태로 나오므로 항목마다 한 번씩 호출한다.
- 페이지당 수 초 — 앞부분을 먼저 샘플하고 필요한 범위만 추가한다. 표·순서가 흐트러질 수 있으니 핵심 사실 위주로 정리한다.
- Tesseract 바이너리가 없으면 `ERROR: OCR failed: ...`로 실패한다(설치 안내는 `ocr_pdf.py` 헤더). 그 파일은 건너뛰고 열린 질문으로 보고한다 — 빈 추출을 성공으로 오독하지 않는다.

## Handysoft 전자결재 파일

`.pdf` 확장자이지만 독자 포맷이며 내부에 PDF가 임베딩돼 있다. §1이 추출까지 처리하므로 별도 호출은 불필요하다. 추출만 따로 필요하면:

```bash
python3 .claude/skills/inbox-process/scripts/extract_handysoft_pdf.py "원본.pdf"
```

시스템 임시폴더의 `extracted_{md5앞8자}.pdf`에 저장하고 절대경로를 stdout 첫 줄에 찍는다. exit 1(임베딩 PDF 없음 등)이면 건너뛰고 보고한다.
