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
        ".xlsx", ".xls", ".pptx", ".ppt", ".docx", ".doc", ".zip"}

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
                # prod:hwpx 의 text.py 는 ZIP 기반 HWPX 만 읽는다. 레거시 바이너리
                # .hwp 를 넘기면 "not a valid HWPX (ZIP) file" 로 끝나므로,
                # 변환이 선행돼야 함을 상태로 드러낸다 (프로세스.md HWP→HWPX 단계).
                status = "NEEDS_HWPX (레거시 .hwp — 한글에서 .hwpx 로 변환 후 재실행)"
            elif ext == ".pdf":
                status = extract_pdf(src, dst)
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
