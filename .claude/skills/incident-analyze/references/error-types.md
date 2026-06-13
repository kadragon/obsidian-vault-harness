# 에러 타입별 진단 가이드

## 분류표

| 에러 타입 | 주요 원인 | 확인 포인트 |
|----------|----------|------------|
| `SQLIntegrityConstraintViolation` | PK 중복, UNIQUE 제약 위반 | 데이터 변환 로직, 키 생성 로직, 배치 처리 경계 |
| `NullPointerException` | 조회 결과 없음 상태에서 접근 시도 | null 체크 누락, 쿼리 결과 0건 처리 |
| `ArrayIndexOutOfBounds` | 데이터셋 크기 불일치 | 루프 인덱스, 멀티행 데이터셋 크기 |
| `SQLDataException` | 데이터 타입 불일치, 값 범위 초과 | 컬럼 타입·길이 제약, 날짜 형식 |
| `Timeout` | 쿼리 성능 문제 | 실행 계획, 인덱스 누락, 풀스캔 여부 |
| `OracleException (ORA-*)` | DB 제약 조건 위반 다양 | ORA 코드별 원인 별도 확인 |

## 공통 진단 원칙

- 로그 근거 기반 진단. 추측은 반드시 "추정"으로 명시.
- `PARAMETER_INFO`의 YEAR, HAKGI, HAKBEON — 학사 데이터 핵심 키. 누락·오류 여부 먼저 확인.
- 파라미터에서 업무 맥락(학년도·학기·학번 등) 파악 후 해당 도메인 MOC 참조.

## 통합학사시스템 반복 패턴

### SQLIntegrityConstraintViolation
- 학적 이동(복학·재입학) 후 중복 키 — 학번+학년도+학기 복합 PK 확인
- 성적 일괄 저장 시 동일 강좌 중복 처리 — 배치 트랜잭션 경계 확인

### NullPointerException
- 미개설 강좌·미등록 학생 조회 후 `.get()` 직접 접근 — Optional/null 체크 누락
- 세션 만료 후 사용자 객체 접근

### Timeout
- 학적 일괄 배치 — 대용량 시 커서 방식·페이징 미적용
- 집계 쿼리 인덱스 미사용 — YEAR, HAKGI 조건 인덱스 활용 여부 확인
