# Mode 3: archive — 오래된 업무노트 아카이빙

`10_Areas/`에서 1년 이상 지난 문서를 `90_Archive/`로 이동한다.

## 실행 절차

### Step 1: 대상 식별

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
