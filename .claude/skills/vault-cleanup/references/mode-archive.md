# Mode 3: archive — 오래된 업무노트 아카이빙

`10_Areas/`에서 아카이브 대상을 식별해 `90_Archive/`로 이동한다. 두 가지 staleness 신호가 있다:

- **종결 기반** (권장 1차 신호): `status: closed` 처리된 뒤 N일(기본 90일) 경과 — `status-sync`가 닫은 업무를 적시에 정리. close-date는 `_Wiki/log.md`의 `#closed` 이벤트에서 읽는다.
- **연식 기반**: 폴더 날짜(`YYYYMM_`)가 12개월 이상 경과 — 닫히지 않았어도 오래된 문서 정리.

> 14_Changes(인시던트·개선)는 영구 변경 이력이므로 아카이브하지 않는다 — 종결 신호는 `10_Areas/`에만 적용.

## 실행 절차

### Step 1: 대상 식별

**종결→아카이브 (status-sync 연계):**

```
scripts/reorg_archive.py find-closed . --archive-root 90_Archive --json
```

`_Wiki/log.md` `#closed` 이벤트 중 N일(기본 90, `--days`로 조정) 이상 경과하고 아직 `10_Areas/`에 남은 노트를 후보로 낸다. 폴더형 노트는 `{YYYYMM}_slug/` 폴더 전체, 단일파일 노트는 그 `.md`가 단위. 추가로 `status: closed`인데 `#closed` 로그가 없는 **미기록 종결**(`unlogged_closed`)도 함께 보고한다 — 이건 close-date를 모르니 `status-sync`로 다시 닫아 로그를 남기거나 수동 처리한다.

**연식 기반:**

`scripts/reorg_archive.py find-stale 10_Areas --archive-root 90_Archive --json`에 위임한다. 스크립트 기본 cutoff은 오늘 − 12개월.

수동 계산이 필요하면:

```python
from datetime import datetime
cutoff = datetime(현재년-1, 현재월, 현재일)

for area in 10_Areas의 각 폴더:
    for 문서폴더 in area의 YYYYMM_문서:
        YYYY, MM = 문서폴더명에서 추출
        if datetime(YYYY, MM, 1) < cutoff:
            이동 대상에 추가
```

### Step 2: 이동 목록 제시

```markdown
## 아카이빙 대상 (1년 이상 경과)

| 현재 위치 | 이동 위치 | 문서명 |
|----------|----------|--------|
| 10_Areas/예산관리/ | 90_Archive/예산관리/2025/ | 202504_... |
```

**사용자 확인 후에만 이동한다.**

### Step 3: 이동 실행

개별 이동은 `scripts/reorg_archive.py apply-archive <src> 90_Archive --apply`를 사용한다. 원시 이동이 필요하면:

```bash
mkdir -p "90_Archive/{area}/YYYY"
mv "10_Areas/{area}/YYYYMM_문서" "90_Archive/{area}/YYYY/"
```

`90_Archive`에 해당 area 폴더가 없으면 새로 생성한다.
