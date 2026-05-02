# Status Sync — Design Rationale

판정은 사실상 이진 분류이고 후보는 수십 개 규모. 토큰을 세 단계로 깎는다:

1. `scan.py`가 명확한 케이스(`auto_close`/`keep_open`)를 결정적으로 분리.
2. review 후보는 scan.py가 **맥락·할 일 섹션 발췌**만 JSONL 번들로 추출 —
   메인도 서브도 원본 `.md`는 Read하지 않는다.
3. 판정은 Read만 가진 haiku 전용 `status-judge`를 **1회 배치 호출**. N번 spawn
   하지 않으므로 부팅 오버헤드가 노트 수와 무관.

폴더별 템플릿 차이(할 일/맥락/결과 헤딩)는 `scan.py`의 `PROFILES` 목록에서만
정의하고, 그 뒤 파이프라인은 폴더를 구분하지 않는다. 새 폴더가 생기면 프로파일
한 줄만 추가하면 된다.

승인 루프 중간에 메인이 본문을 재확인하지 않는다 — scan 결과와 judge TSV만으로
적용한다.
