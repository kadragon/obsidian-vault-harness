# 원본 사본에 점검 위치 메모 (Step 5-4 ⑤)

간사가 원문에서 직접 확인할 지점을 **심의자료 hwpx 사본**에 한글 메모로 찍는다.
대상은 노트의 지적(A·B)과 Step 5-2 검증 결과가 `UNVERIFIED`·`PLAUSIBLE`인 항목처럼 판정에 사람 눈이 필요한 곳만이다.
전달본(PDF)을 대신하지 않는다.

## 절차

1. `memos.json`을 만든다.
   ```json
   [{"anchor": "보안관리", "text": "[A-1] 확인: 보안서약서 명시 여부\n근거: 용역업체 보안관리 지침", "occurrence": 1}]
   ```
   - `anchor` — 원문에 그대로 있는 짧은 문구. Step 1 추출본에서 복사한다.
   - `text` — 첫 줄은 노트의 지적 번호로 시작한다. `\n`은 메모 안 문단 구분이다.
   - `occurrence` — 같은 문구가 여러 번 나올 때 몇 번째인지 지정한다(기본 1, 섹션 순서로 센다).
2. 원본 옆이 아니라 노트 폴더에 **새 파일로** 저장한다. 원본은 불변이다.
   ```bash
   python3 .claude/skills/gwaeop-simui-review/scripts/annotate_memo.py \
     "<심의자료/원본.hwpx>" "<{확정요청번호}/{원본명}_검토메모.hwpx>" "<scratch>/memos.json"
   ```
   | 결과 | 의미 | 조치 |
   |------|------|------|
   | `OK` | 붙임 | — |
   | `NOT_FOUND` | 문구가 한 `<hp:t>` 안에 없음(서식 경계로 쪼개짐) | 더 짧은 문구로 |
   | `UNSAFE` | 문구 앞에 표·탭 등이 있는 여러 줄 문단 — 글자 위치를 셀 수 없음 | 같은 문단의 다른 문구로 |

   종료코드 1이면 붙인 것만 저장된 상태다. 출력 파일을 지우고 문구를 고쳐 다시 돌린다(기존 출력은 덮어쓰지 않는다).
3. **한글 로드 검증 필수.** XML이 맞아도 한글이 못 여는 경우가 있다.
   ```bash
   powershell -NoProfile -ExecutionPolicy Bypass -File .claude/skills/gwaeop-simui-review/scripts/verify_hancom.ps1 "<출력.hwpx>"
   ```
   `open=True`, `pages`가 원본과 같고, `memos`가 붙인 개수와 같아야 통과다. 원본도 같은 명령으로 쪽수를 잰다.
4. `.hwp` 원본은 prod:hwpx `convert_hwp.ps1`로 hwpx로 변환한 뒤 적용한다. PDF 원본은 대상이 아니다.


규칙의 근거는 `docs/harness-log.md`, OWPML 규칙은 `annotate_memo.py` 머리 주석에 있다.
