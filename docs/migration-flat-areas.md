# 10_Areas 평탄화 마이그레이션 가이드

적용 배경: **첨부가 없는데도** 폴더-안-동명파일(`YYYYMM_{title}/_YYYYMM_{title}.md`)로 감싸는 패턴이 굳어져 경로가 800자 초과 사례가 발생함. 기존 노트는 접근 시 아래 절차로 점진 정리.

> **신규 노트 기준은 여기에 두지 않는다.** 단일 진실 원천은 `docs/conventions.md → 10_Areas/ Depth Rules`이며, 생성기는 `.claude/skills/inbox-process/scripts/new_work_path.py`다. 이 문서는 **기존 노트 정리 절차 전용**이다.
>
> 요약(2026-07-24 확정, 상세는 conventions.md): 첨부 없음 → area 루트에 단일 `.md`, 래퍼 폴더 금지. 첨부 있음 → `YYYYMM_{summary}/` 폴더(전체 제목, 길이 캡 없음) + 내부 `_YYYYMM_{summary}.md`(`_` prefix 유지).

---

## 기존 노트 점진 정리 절차

### 전제 조건

- Obsidian에서 "Files & Links → Automatically update internal links" ON 상태 권장. OFF면 grep 수동 보정 필요.

### 케이스 A — 첨부 없는 폴더(단일 .md만 있는 폴더)

```bash
# 단일 .md만 있는 폴더 식별
find /Users/kadragon/ObsidianVault/10_Areas -mindepth 2 -maxdepth 2 -type d | while read d; do
  count=$(find "$d" -maxdepth 1 -type f | wc -l)
  mdcount=$(find "$d" -maxdepth 1 -name "*.md" | wc -l)
  if [ "$count" -eq 1 ] && [ "$mdcount" -eq 1 ]; then echo "$d"; fi
done
```

처리 순서 (Obsidian 열린 상태에서):
1. 내부 `_<이름>.md` 파일명에서 `_` prefix 제거 → Obsidian이 자동 링크 갱신
2. 파일을 부모 area 폴더로 이동 → Obsidian이 자동 링크 갱신
3. 빈 폴더 삭제

### 케이스 B — 첨부 있는 폴더

**정리 대상이 아니다.** 첨부가 있는 노트는 래퍼 폴더 + `_` prefix 내부 파일이 현행 canonical 형태다(`conventions.md`). 폴더명을 짧은 slug로 rename하거나 `_` prefix를 제거하면 **규약을 되돌리는 것**이므로 하지 말 것.

확인만 한다 — 폴더명이 `YYYYMM_{summary}`이고 내부 노트가 같은 이름에 `_`를 붙인 `_YYYYMM_{summary}.md`인지. 어긋나면 rename 대신 사용자에게 보고한다(기존 노트 불변 — Golden Principle #1, 링크 일괄 편집 사고 이력).

---

## 과업심의 → `12_Projects/` 이전

과업심의는 회차별 시작/종료가 있는 프로젝트 성격이므로 `12_Projects/`로 이전.

```bash
# 이전 전 확인
ls /Users/kadragon/ObsidianVault/10_Areas/과업심의/
ls /Users/kadragon/ObsidianVault/12_Projects/
```

**obsidian-operator agent에 위임** — Obsidian 열린 상태에서 이동해야 링크가 자동 갱신됨:
- 소스: `10_Areas/과업심의/`
- 대상: `12_Projects/2026_과업심의/` (연도 프로젝트 단위로 통합)
- 이전 후: `10_Areas/과업심의/` 폴더 삭제
- 확인: `_Wiki/` 내 과업심의 링크 깨짐 여부 grep

---

## 링크 깨짐 수동 검증 (Obsidian Update Links 미사용 시)

```bash
# 구 경로(_prefix .md) 참조 검색
grep -r "_202[0-9]" /Users/kadragon/ObsidianVault --include="*.md" -l

# 특정 폴더 참조 검색
grep -r "과업심의" /Users/kadragon/ObsidianVault --include="*.md" -l
```

---

## 완료 기준 검증

```bash
# 10_Areas 최대 깊이 확인 (3 이상이면 잔여 중첩)
find /Users/kadragon/ObsidianVault/10_Areas -mindepth 3 -type f -name "*.md"

# 경로 길이 분포 (200자 초과 항목)
find /Users/kadragon/ObsidianVault/10_Areas -name "*.md" | awk '{print length, $0}' | sort -rn | awk '$1 > 200'

# area 루트에 남은 _ prefix 파일 확인 (래퍼 폴더 안의 _*.md 는 canonical 이므로 제외)
find /Users/kadragon/ObsidianVault/10_Areas -mindepth 2 -maxdepth 2 -name "_*.md"
```
