#!/usr/bin/env python3
"""과업심의 자료 번들을 일괄 텍스트 추출한다.

.hwpx      → prod:hwpx 플러그인의 text.py (표 포함 markdown)
.hwp       → 레거시 바이너리. 변환 필요로만 표시 (NEEDS_HWPX)
.pdf       → PyMuPDF 텍스트 레이어. 페이지 단위로 판정해 전면 스캔본은
             SCANNED, 텍스트/이미지 혼재본은 OK+OCR 로 표시 (둘 다 OCR 대상)
.zip       → 풀어서 재귀 처리
그 외 텍스트 파일은 그대로 복사.

출력: <out>/<원본 상대경로>.txt + <out>/INDEX.md
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

TEXTLIKE = {".md", ".txt", ".csv", ".json", ".xml"}
SKIP = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff",
        ".pptx", ".ppt", ".docx", ".doc", ".zip"}
XLSX = {".xlsx", ".xlsm"}


def extract_xlsx(src: str, dst: str) -> str:
    """산출내역서 등 엑셀 파일을 시트별 `셀 | 셀` 행 텍스트로. 수식 셀은 저장된 계산값, 없으면 수식 그대로."""
    try:
        import openpyxl
    except ImportError:
        return "SKIP (openpyxl 미설치)"
    try:
        values = openpyxl.load_workbook(src, data_only=True, read_only=True)
        formulas = openpyxl.load_workbook(src, data_only=False, read_only=True)
    except Exception as exc:                          # noqa: BLE001 - 손상 파일 방어
        return f"ERROR: {exc}"[:120]
    parts = []
    for ws_v, ws_f in zip(values.worksheets, formulas.worksheets):
        parts.append(f"\n===SHEET {ws_v.title}===")
        for row_v, row_f in zip(ws_v.iter_rows(values_only=True), ws_f.iter_rows(values_only=True)):
            cells = ["" if v is None and f is None else str(f if v is None else v)
                     for v, f in zip(row_v, row_f)]
            if any(c.strip() for c in cells):
                parts.append(" | ".join(cells).rstrip(" |"))
    values.close()
    formulas.close()
    body = "\n".join(parts)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(body)
    return "OK (값만 — 서식·병합 없음)" if body.strip() else "EMPTY"


def extract_xls(src: str, dst: str) -> str:
    """레거시 .xls(BIFF) 산출내역서를 extract_xlsx 와 같은 형식으로. xlrd 는 저장된 계산값만 준다."""
    try:
        import xlrd
    except ImportError:
        return "SKIP (xlrd 미설치)"
    try:
        book = xlrd.open_workbook(src, on_demand=True)
    except Exception as exc:                          # noqa: BLE001 - 손상 파일 방어
        return f"ERROR: {exc}"[:120]
    parts = []
    for sheet in book.sheets():
        parts.append(f"\n===SHEET {sheet.name}===")
        for i in range(sheet.nrows):
            # xlrd 는 숫자를 모두 float 로 준다 — 정수값은 1000000.0 이 아니라 1000000 으로.
            cells = [str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
                     for v in sheet.row_values(i)]
            if any(c.strip() for c in cells):
                parts.append(" | ".join(cells).rstrip(" |"))
    body = "\n".join(parts)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(body)
    return "OK (값만 — 서식·병합 없음)" if body.strip() else "EMPTY"

HWPX_GLOBS = [
    os.path.expanduser("~/.claude/plugins/marketplaces/*/prod/skills/hwpx/scripts/text.py"),
    os.path.expanduser("~/.claude/plugins/cache/*/prod/*/skills/hwpx/scripts/text.py"),
]


def find_hwpx_text_py() -> str | None:
    """prod:hwpx 플러그인의 text.py 경로. marketplaces 우선, cache는 최신 버전."""
    for pattern in HWPX_GLOBS:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


def extract_hwpx(src: str, dst: str, text_py: str | None) -> str:
    if not text_py:
        return "NO_HWPX_TOOL"
    try:
        r = subprocess.run(
            [sys.executable, text_py, "extract", src, "-f", "markdown"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    if r.returncode != 0:
        # stderr 가 비는 실패(도구가 stdout 으로 찍거나 시그널로 죽는 경우)에도
        # 배치 전체가 IndexError 로 중단되지 않도록 한다.
        lines = (r.stderr or "").strip().splitlines()
        return "ERROR: " + (lines[-1][:120] if lines else f"exit code {r.returncode}")
    body = r.stdout or ""
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(body)
    return "OK" if body.strip() else "EMPTY"


HWPTAG_PARA_TEXT = 67
# HWP 5.0 제어문자: 확장·인라인 컨트롤은 8 wchar(16 byte)를 차지한다. 나머지(10·13 등)는 1 wchar.
HWP_WIDE_CTRL = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}


def hwp_section_text(data: bytes) -> str:
    """압축 해제된 BodyText/Section 레코드 스트림에서 PARA_TEXT 만 문단 단위로 뽑는다.

    표·도형 안의 문단도 PARA_TEXT 레코드라 텍스트는 나오지만 표 구조(행·열)는 사라진다.
    """
    import struct

    paras, pos = [], 0
    while pos + 4 <= len(data):
        (hdr,) = struct.unpack_from("<I", data, pos)
        pos += 4
        tag, size = hdr & 0x3FF, (hdr >> 20) & 0xFFF
        if size == 0xFFF:
            (size,) = struct.unpack_from("<I", data, pos)
            pos += 4
        body = data[pos:pos + size]
        pos += size
        if tag != HWPTAG_PARA_TEXT:
            continue
        chars, i = [], 0
        while i + 2 <= len(body):
            (c,) = struct.unpack_from("<H", body, i)
            if c >= 32:
                chars.append(chr(c))
                i += 2
            elif c in HWP_WIDE_CTRL:
                if c == 9:
                    chars.append("\t")
                i += 16
            else:
                if c in (10, 13):
                    chars.append("\n")
                i += 2
        paras.append("".join(chars).rstrip("\n"))
    return "\n".join(paras)


def extract_hwp(src: str, dst: str) -> str:
    """레거시 바이너리 .hwp(HWP 5.0, OLE) 본문 텍스트. NIPA 권고서 등이 이 형식으로 온다."""
    try:
        import olefile
    except ImportError:
        return "NEEDS_HWPX (olefile 미설치 — 한글에서 .hwpx 로 변환 후 재실행)"
    import struct
    import zlib

    try:
        if not olefile.isOleFile(src):
            return "ERROR: OLE 형식 아님 (HWP 3.x 이하 또는 손상)"
        with olefile.OleFileIO(src) as ole:
            (props,) = struct.unpack_from("<I", ole.openstream("FileHeader").read(), 36)
            if props & 0x2:
                return "NEEDS_HWPX (암호 설정 문서)"
            sections = sorted(
                (e for e in ole.listdir() if e[0] == "BodyText" and e[1].startswith("Section")),
                key=lambda e: int(e[1][len("Section"):]),
            )
            if not sections:
                return "NEEDS_HWPX (BodyText 없음 — 배포용 문서)"
            parts = []
            for entry in sections:
                raw = ole.openstream(entry).read()
                if props & 0x1:
                    raw = zlib.decompress(raw, -15)
                parts.append(f"\n===SECTION {entry[1]}===\n" + hwp_section_text(raw))
    except Exception as exc:                          # noqa: BLE001 - 손상 파일 방어
        return f"ERROR: {exc}"[:120]
    body = "".join(parts)
    # HWP 문자 코드에 짝 없는 UTF-16 서로게이트가 섞여 오면 utf-8 인코딩이 실패한다
    with open(dst, "w", encoding="utf-8", errors="replace") as fh:
        fh.write(body)
    return "OK (텍스트만 — 표 구조 없음)" if body.strip() else "EMPTY"


def to_ranges(pages: list[int]) -> list[str]:
    """1-based 페이지 번호를 ocr_pdf.py `--pages` 인자로 압축. [3,4,5,9] → ["3-5","9"]."""
    out: list[list[int]] = []
    for page in pages:
        if out and page == out[-1][1] + 1:
            out[-1][1] = page
        else:
            out.append([page, page])
    return [str(a) if a == b else f"{a}-{b}" for a, b in out]


def extract_pdf(src: str, dst: str) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "NO_PYMUPDF"
    try:
        doc = fitz.open(src)
    except Exception as exc:                      # noqa: BLE001 - 손상 파일 방어
        # 결재시스템(Handysoft) 내려받기본은 PDF 앞에 고정 헤더를 덧붙여 저장한다.
        # 헤더만 잘라내면 그대로 열린다 — 암호화가 아니라 접두 바이트다.
        try:
            raw = open(src, "rb").read()
            off = raw.find(b"%PDF-")
            if off <= 0:
                return f"ERROR: {exc}"[:120]
            doc = fitz.open(stream=raw[off:], filetype="pdf")
        except Exception:                         # noqa: BLE001
            return f"ERROR: {exc}"[:120]
    try:
        parts, blank = [], []
        for i, page in enumerate(doc, 1):
            text = page.get_text()
            if not text.strip():
                blank.append(i)
            parts.append(f"\n===PAGE {i}===\n" + text)
        pages = doc.page_count
    finally:
        # 닫지 않으면 핸들이 쌓이고, Windows 에서는 ZIP 임시폴더 정리까지 막는다.
        doc.close()
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))

    # 판정은 파일 단위가 아니라 페이지 단위로 한다. 견적서·시장조사 결과는
    # 표지만 텍스트이고 결정적 근거가 담긴 본문이 스캔 이미지인 경우가 많아,
    # 파일 전체 텍스트가 비지 않았다는 이유로 OK 처리하면 그대로 누락된다.
    if not blank:
        return "OK"
    if len(blank) >= pages:
        return f"SCANNED ({pages}p)"
    return f"OK+OCR ({len(blank)}/{pages}p: {','.join(to_ranges(blank))})"


def walk(root: str, out: str, text_py: str | None, rel_prefix: str = "") -> list[tuple]:
    rows: list[tuple] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in sorted(filenames):
            src = os.path.join(dirpath, name)
            rel = os.path.join(rel_prefix, os.path.relpath(src, root))
            ext = os.path.splitext(name)[1].lower()
            size = os.path.getsize(src)

            if ext == ".zip":
                tmp = tempfile.mkdtemp(prefix="gwaeop_zip_")
                try:
                    with zipfile.ZipFile(src) as zf:
                        zf.extractall(tmp)
                    rows.append((rel, size, f"ZIP → {rel}/"))
                    rows.extend(walk(tmp, out, text_py, rel_prefix=rel))
                except Exception as exc:          # noqa: BLE001
                    rows.append((rel, size, f"ZIP ERROR: {exc}"[:120]))
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                continue

            if ext in SKIP:
                rows.append((rel, size, "SKIP (비텍스트)"))
                continue

            dst = os.path.join(out, rel + ".txt")
            os.makedirs(os.path.dirname(dst), exist_ok=True)

            if ext == ".hwpx":
                status = extract_hwpx(src, dst, text_py)
            elif ext == ".hwp":
                # prod:hwpx 의 text.py 는 ZIP 기반 HWPX 만 읽으므로 OLE 본문을 직접 읽는다.
                # 암호·배포용 문서처럼 못 읽는 경우만 NEEDS_HWPX 로 변환을 요구한다.
                status = extract_hwp(src, dst)
            elif ext == ".pdf":
                status = extract_pdf(src, dst)
            elif ext in XLSX:
                status = extract_xlsx(src, dst)
            elif ext == ".xls":
                status = extract_xls(src, dst)
            elif ext in TEXTLIKE:
                shutil.copyfile(src, dst)
                status = "OK (복사)"
            else:
                status = "SKIP (미지원)"
            rows.append((rel, size, status))
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="과업심의 자료 번들 일괄 텍스트 추출")
    p.add_argument("bundle", help="심의자료 폴더 경로")
    p.add_argument("-o", "--out", required=True, help="추출 결과를 담을 폴더")
    args = p.parse_args(argv)

    if not os.path.isdir(args.bundle):
        print(f"폴더가 아님: {args.bundle}", file=sys.stderr)
        return 2

    os.makedirs(args.out, exist_ok=True)
    text_py = find_hwpx_text_py()
    if not text_py:
        print("[warn] prod:hwpx text.py 를 찾지 못함 — .hwpx 추출 생략", file=sys.stderr)

    rows = walk(args.bundle, args.out, text_py)

    index = os.path.join(args.out, "INDEX.md")
    # 전면 스캔본(SCANNED)과 혼재본(OK+OCR) 모두 OCR 대상이다.
    scanned = [r for r in rows if str(r[2]).startswith(("SCANNED", "OK+OCR"))]
    needs_hwpx = [r for r in rows if str(r[2]).startswith("NEEDS_HWPX")]
    with open(index, "w", encoding="utf-8") as fh:
        fh.write(f"# 추출 인덱스\n\n원본: `{args.bundle}`\n\n")
        fh.write("| 파일 | 크기 | 상태 |\n|---|---:|---|\n")
        for rel, size, status in rows:
            fh.write(f"| `{rel}` | {size:,} | {status} |\n")
        if scanned:
            fh.write("\n## OCR 필요 (스캔본·혼재본)\n\n")
            for rel, _, status in scanned:
                fh.write(f"- `{rel}` — {status}\n")
            fh.write(
                "\n> `uv run .claude/skills/inbox-process/scripts/ocr_pdf.py \"<pdf>\" --pages 1-5`\n"
                "> `--pages` 는 단일 페이지나 연속 구간 하나만 받는다 — 위 괄호 안 구간마다 한 번씩 호출한다.\n"
                "> 또는 PyMuPDF로 페이지를 PNG 렌더 후 Read 로 직접 읽는다.\n"
                "> 시장조사 결과·견적서가 스캔본인 경우가 많고 결정적 근거를 담고 있다.\n"
            )
        if needs_hwpx:
            fh.write("\n## HWPX 변환 필요 (레거시 .hwp)\n\n")
            for rel, _, status in needs_hwpx:
                fh.write(f"- `{rel}`\n")
            fh.write("\n> 한글에서 `.hwpx` 로 저장한 뒤 이 스크립트를 다시 돌린다.\n")

    for rel, size, status in rows:
        print(f"{status:<20} {size:>10,}  {rel}")
    print(f"\n인덱스: {index}")
    if scanned:
        print(f"** OCR 대상 {len(scanned)}건 (스캔본·혼재본) — OCR 또는 이미지 판독 필요")
    if needs_hwpx:
        print(f"** 레거시 .hwp {len(needs_hwpx)}건 — .hwpx 로 변환 후 재실행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
