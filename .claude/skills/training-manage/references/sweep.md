# Mode 4: 일괄 정리 (sweep) — 상세 절차

## Step 1: 전체 스캔

```bash
find 20_Training/ -type f | sort
```

## Step 2: 구조 점검 항목

| 점검 항목 | 조건 | 조치 |
|----------|------|------|
| 루트 레벨 파일 | `20_Training/*.md` 또는 `*.hwp` | 연도 폴더로 이동 |
| 고아 이미지 | 본문에서 참조되지 않는 이미지 | 삭제 권고 |
| 빈 인덱스 노트 | 링크만 있는 목차 파일 | 삭제 권고 (하위 노트 존재 시) |
| frontmatter 불일치 | `type: training` 없음 | 표준화 대상 |
| 연도 폴더 미존재 | 해당 연도 파일이 있으나 폴더 없음 | 폴더 생성 |

## Step 3: 순차 실행

품질 평가(Mode 1) → 사용자 확인 → 표준화(Mode 2) 순으로 진행한다.
삭제/이동/표준화는 사용자 확인 후 일괄 수행한다.

## Step 4: Wiki MOC 제안

스캔으로 파악한 교육 노트 총 수가 5건 이상이면 운영 MOC 생성을 제안한다:

```bash
find 20_Training/ -name "*.md" | wc -l
```

5건+이고 `_Wiki/topics/교육-운영-MOC.md`가 없으면 사용자에게 보고:

> "교육 노트가 N건 누적되었습니다. `_Wiki/topics/교육-운영-MOC.md` 생성을 권장합니다."

MOC 생성은 `_Wiki/contracts.md` Operational MOC 스키마에 따라 **직접 작성**한다 (obsidian-operator 위임 불가 — 서브에이전트는 다른 서브에이전트를 부르지 못한다). 자동 생성하지 않고 사용자 승인을 먼저 받는다.
