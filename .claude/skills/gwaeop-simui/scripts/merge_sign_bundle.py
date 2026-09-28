#!/usr/bin/env python3
"""위원별 전자서명 통합본을 만든다 (과업심의_프로세스 Step 7-2).

여러 .hwp/.hwpx를 입력 순서대로 한 .hwpx로 합친다.

1. 입력을 임시 폴더에 복사 — 한글 COM Open()은 원본을 덮어쓸 수 있다.
2. 한글 COM으로 첫 파일을 열고 나머지를 문서 끝에 InsertFile.
   파일마다 구역이 새로 생겨 쪽이 나뉜다 (BreakPage를 넣으면 빈 쪽이 생김).
3. 같은 서식에서 온 문단의 hp:p id 중복을 해소 (validate.py INVALID 원인).
4. --replace 값 교체 (예: 동의서의 직전 회차 값) → strip-lineseg.
5. pack → validate.py → (선택) 쪽수 확인·PDF 저장.

Windows + 한글 + pywin32 필요. prod:hwpx 플러그인 스크립트를 사용한다.

예:
  python3 merge_sign_bundle.py -o "202609_제9차과업심의_윤인자.hwpx" --expect-pages 5 \\
    --replace "제8회" "제9회" --replace "2026년 8월 21일" "2026년 9월 23일" \\
    --replace "하 진 석" "윤 인 자" \\
    "공통/개인정보 수집이용 동의서 서식(외부위원 용).hwp" \\
    2026-033/2026-033_1_서약서_윤인자.hwpx \\
    "2026-033/2026-033_2_과업내용 확정 위원별 심의 결과서_윤인자.hwpx" ...
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HWPX_GLOBS = [
    os.path.expanduser("~/.claude/plugins/marketplaces/*/prod/skills/hwpx/scripts"),
    os.path.expanduser("~/.claude/plugins/cache/*/prod/*/skills/hwpx/scripts"),
]
PLACEHOLDER_ID = "2147483648"  # 한글이 여러 문단에 쓰는 자리표시 id — 중복 허용
P_ID = re.compile(r'(<hp:p id=")(\d+)(")')


def find_hwpx_scripts() -> Path:
    for pattern in HWPX_GLOBS:
        hits = sorted(glob.glob(pattern))
        if hits:
            return Path(hits[-1])
    sys.exit("prod:hwpx 플러그인 scripts 폴더를 찾지 못함")


def dedupe_para_ids(sections: list[str]) -> tuple[list[str], int]:
    """섹션 XML 목록에서 hp:p id 중복을 두 번째 등장부터 미사용 번호로 바꾼다.

    XML 재직렬화 없이 정규식 치환만 한다. 반환: (수정된 섹션들, 바꾼 개수)
    """
    ids = [m.group(2) for s in sections for m in P_ID.finditer(s)]
    used = set(ids)
    numeric = [int(i) for i in used if i != PLACEHOLDER_ID]
    next_id = (max(numeric) + 1) if numeric else 1
    seen: set[str] = set()
    changed = 0

    def repl(m: re.Match) -> str:
        nonlocal next_id, changed
        pid = m.group(2)
        if pid == PLACEHOLDER_ID:
            return m.group(0)
        if pid not in seen:
            seen.add(pid)
            return m.group(0)
        while str(next_id) in used:
            next_id += 1
        new = str(next_id)
        used.add(new)
        changed += 1
        return m.group(1) + new + m.group(3)

    return [P_ID.sub(repl, s) for s in sections], changed


def apply_replacements(sections: list[str], pairs: list[tuple[str, str]]) -> list[str]:
    """<hp:t> 텍스트 안의 OLD를 NEW로. OLD는 전체 섹션 합계로 정확히 1회 등장해야 한다."""
    out = list(sections)
    for old, new in pairs:
        pat = re.compile(r"(<hp:t>[^<]*?)" + re.escape(old) + r"([^<]*</hp:t>)")
        total = sum(len(pat.findall(s)) for s in out)
        if total != 1:
            sys.exit(f"--replace {old!r}: {total}회 등장 (1회여야 함)")
        out = [pat.sub(lambda m: m.group(1) + new + m.group(2), s) for s in out]
    return out


def com_merge(parts: list[Path], out: Path, pdf: Path | None) -> int:
    import win32com.client  # pywin32

    hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
    try:
        try:
            hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
        except Exception:
            pass
        fmt = "HWP" if parts[0].suffix.lower() == ".hwp" else "HWPX"
        if not hwp.Open(str(parts[0]), fmt, "forceopen:true"):
            sys.exit(f"한글 Open 실패: {parts[0]}")
        for p in parts[1:]:
            hwp.MovePos(3, 0, 0)  # 문서 끝
            ps = hwp.HParameterSet.HInsertFile
            hwp.HAction.GetDefault("InsertFile", ps.HSet)
            ps.filename = str(p)
            ps.KeepSection = ps.KeepCharshape = ps.KeepParashape = ps.KeepStyle = 1
            if not hwp.HAction.Execute("InsertFile", ps.HSet):
                sys.exit(f"InsertFile 실패: {p}")
        if not hwp.SaveAs(str(out), "HWPX", ""):
            sys.exit(f"SaveAs 실패: {out}")
        pages = hwp.PageCount
        if pdf:
            hwp.SaveAs(str(pdf), "PDF", "")
        hwp.Clear(1)
        return pages
    finally:
        hwp.Quit()


def run(script: Path, *args: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parts", nargs="+", type=Path, help="합칠 파일 (쪽 순서대로)")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--replace", nargs=2, action="append", default=[], metavar=("OLD", "NEW"))
    ap.add_argument("--expect-pages", type=int, help="한글 PageCount가 이 값이 아니면 실패")
    ap.add_argument("--pdf", type=Path, help="검증용 PDF 저장 경로 (병합 직후, 값 교체 전)")
    a = ap.parse_args()

    for p in a.parts:
        if not p.is_file():
            sys.exit(f"입력 없음: {p}")
    scripts = find_hwpx_scripts()

    with tempfile.TemporaryDirectory(prefix="merge_sign_") as tmp:
        t = Path(tmp)
        copies = []
        for i, p in enumerate(a.parts):  # ASCII 이름 복사본 — COM 경로 인코딩 문제 회피
            c = t / f"part{i}{p.suffix.lower()}"
            shutil.copy2(p, c)
            copies.append(c)
        merged = t / "merged.hwpx"
        pages = com_merge(copies, merged, a.pdf.resolve() if a.pdf else None)
        print(f"merged: {len(copies)} files, {pages} pages")
        if a.expect_pages is not None and pages != a.expect_pages:
            sys.exit(f"쪽수 불일치: {pages} (기대 {a.expect_pages})")

        d = t / "unpacked"
        r = run(scripts / "office.py", "unpack", merged, d)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
        secs = sorted((d / "Contents").glob("section*.xml"), key=lambda p: int(p.stem.removeprefix("section")))
        texts = [s.read_text(encoding="utf-8") for s in secs]
        texts, n = dedupe_para_ids(texts)
        print(f"hp:p id 중복 해소: {n}건")
        if a.replace:
            texts = apply_replacements(texts, [tuple(x) for x in a.replace])
        for s, txt in zip(secs, texts):
            s.write_text(txt, encoding="utf-8")
            if a.replace:
                r = run(scripts / "table.py", "strip-lineseg", s, "--inplace")
                if r.returncode:
                    sys.exit(r.stdout + r.stderr)

        final = t / "final.hwpx"
        r = run(scripts / "office.py", "pack", d, final)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
        r = run(scripts / "validate.py", "validate", final)
        print(r.stdout.strip())
        if r.returncode:
            sys.exit(r.stderr or "validate 실패")
        a.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final, a.output)
    print(f"[done] {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
