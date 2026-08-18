#!/usr/bin/env python3
"""과업심의 자료 번들을 일괄 텍스트 추출한다.

.hwpx/.hwp → prod:hwpx 플러그인의 text.py (표 포함 markdown)
.pdf       → PyMuPDF 텍스트 레이어. 비면 SCANNED 로 표시 (OCR 대상)
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
        return "ERROR: " + (r.stderr or "").strip().splitlines()[-1][:120]
    body = r.stdout or ""
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(body)
    return "OK" if body.strip() else "EMPTY"


def extract_pdf(src: str, dst: str) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "NO_PYMUPDF"
    try:
        doc = fitz.open(src)
    except Exception as exc:                      # noqa: BLE001 - 손상 파일 방어
        return f"ERROR: {exc}"[:120]
    parts, raw = [], []
    for i, page in enumerate(doc, 1):
        text = page.get_text()
        raw.append(text)
        parts.append(f"\n===PAGE {i}===\n" + text)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    # 페이지 구분자는 본문이 아니다 — 스캔본 판정은 추출 텍스트 자체로 한다.
    return "OK" if "".join(raw).strip() else f"SCANNED ({doc.page_count}p)"


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

            if ext in (".hwpx", ".hwp"):
                status = extract_hwpx(src, dst, text_py)
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
    scanned = [r for r in rows if str(r[2]).startswith("SCANNED")]
    with open(index, "w", encoding="utf-8") as fh:
        fh.write(f"# 추출 인덱스\n\n원본: `{args.bundle}`\n\n")
        fh.write("| 파일 | 크기 | 상태 |\n|---|---:|---|\n")
        for rel, size, status in rows:
            fh.write(f"| `{rel}` | {size:,} | {status} |\n")
        if scanned:
            fh.write("\n## OCR 필요 (스캔본)\n\n")
            for rel, _, status in scanned:
                fh.write(f"- `{rel}` — {status}\n")
            fh.write(
                "\n> `python3 .claude/skills/inbox-process/scripts/ocr_pdf.py \"<pdf>\" --pages 1-5`\n"
                "> 또는 PyMuPDF로 페이지를 PNG 렌더 후 Read 로 직접 읽는다.\n"
                "> 시장조사 결과·견적서가 스캔본인 경우가 많고 결정적 근거를 담고 있다.\n"
            )

    for rel, size, status in rows:
        print(f"{status:<20} {size:>10,}  {rel}")
    print(f"\n인덱스: {index}")
    if scanned:
        print(f"** 스캔본 {len(scanned)}건 — OCR 또는 이미지 판독 필요")
    return 0


if __name__ == "__main__":
    sys.exit(main())
