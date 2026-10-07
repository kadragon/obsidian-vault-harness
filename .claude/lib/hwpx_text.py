#!/usr/bin/env python3
"""Extract text from a .hwpx file through the installed prod:hwpx ``text.py``.

Shared by gwaeop-simui ``extract_bundle.py`` and the inbox-process reference
branch so both entry points resolve the same tool the same way. stdlib only.

CLI::

    python3 .claude/lib/hwpx_text.py <file.hwpx> [--out <path.md>]

Exit codes: 0 extracted (markdown to ``--out`` or stdout) · 3 ``UNVERIFIED``
(tool missing, source missing, or extraction failed — never a traceback) ·
4 ``NEEDS_HWPX`` (legacy binary ``.hwp``; convert to ``.hwpx`` first) · 2 usage.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile

# Expanded per call, not at import, so HOME/USERPROFILE overrides take effect.
HWPX_GLOBS = [
    "~/.claude/plugins/marketplaces/*/prod/skills/hwpx/scripts/text.py",
    "~/.claude/plugins/cache/*/prod/*/skills/hwpx/scripts/text.py",
]


def find_text_py() -> str | None:
    """prod:hwpx 플러그인의 text.py 경로. marketplaces 우선, cache는 최신 버전."""
    for pattern in HWPX_GLOBS:
        # Natural sort so cache version 0.10.0 outranks 0.9.0.
        hits = sorted(glob.glob(os.path.expanduser(pattern)),
                      key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p)])
        if hits:
            return hits[-1]
    return None


def extract_hwpx(src: str, dst: str, text_py: str | None) -> str:
    """Write markdown for ``src`` to ``dst``; return OK·EMPTY or a failure status."""
    if not text_py:
        return "NO_HWPX_TOOL"
    try:
        r = subprocess.run(
            [sys.executable, text_py, "extract", src, "-f", "markdown"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
            # Force the child to emit UTF-8; a cp949 console default would decode as mojibake yet pass as OK.
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    if r.returncode != 0:
        # stderr 가 비는 실패(도구가 stdout 으로 찍거나 시그널로 죽는 경우)에도
        # 배치 전체가 IndexError 로 중단되지 않도록 한다.
        lines = (r.stderr or "").strip().splitlines()
        return "ERROR: " + (lines[-1][:120] if lines else f"exit code {r.returncode}")
    body = r.stdout or ""
    try:
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(body)
    except OSError as exc:
        return f"ERROR: cannot write {dst}: {exc}"[:160]
    return "OK" if body.strip() else "EMPTY"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src")
    p.add_argument("--out", help="write markdown here instead of stdout")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ext = os.path.splitext(args.src)[1].lower()
    if ext == ".hwp":
        print(f"NEEDS_HWPX: legacy .hwp — convert to .hwpx first: {args.src}", file=sys.stderr)
        return 4
    if ext != ".hwpx":
        print(f"not a .hwpx file: {args.src}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.src):
        print(f"UNVERIFIED: source not found: {args.src}", file=sys.stderr)
        return 3
    text_py = find_text_py()
    if not text_py:
        print("UNVERIFIED: prod:hwpx text.py not found (plugin not installed)", file=sys.stderr)
        return 3

    if args.out:
        status = extract_hwpx(args.src, args.out, text_py)
    else:
        fd, tmp = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        try:
            status = extract_hwpx(args.src, tmp, text_py)
            if status == "OK":
                with open(tmp, encoding="utf-8") as fh:
                    try:
                        sys.stdout.write(fh.read())
                        sys.stdout.flush()
                    except BrokenPipeError:
                        # Reader (e.g. `head`) closed early — not an extraction failure.
                        sys.stdout = open(os.devnull, "w")
        finally:
            os.remove(tmp)
    if status != "OK":
        print(f"UNVERIFIED: {status}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
