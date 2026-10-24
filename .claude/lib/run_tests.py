#!/usr/bin/env python3
"""Run every harness test file under `.claude/` in one command.

Why: test files use three styles — unittest with `__main__`, bare pytest functions,
and plain assert scripts. Run with `python3 <file>`, a pytest-style file executes
nothing and exits 0, so a red suite reads as green. Third-party imports (bs4, pypdf,
openpyxl, xlrd) are also missing from the system interpreter, so ad-hoc runs mix
environment errors with real regressions.

This runner gives every file its own subprocess inside a `uv` environment built from
`requirements-test.txt` (the interpreter is uv's, not the system one):
  - file has `if __name__ ==`  -> run the file (it owns its runner)
  - else file has `def test_`  -> run it under `-m pytest -q`
  - else                       -> run the file (assert script)

Usage:
  python3 .claude/lib/run_tests.py            # all tests
  python3 .claude/lib/run_tests.py <path>...  # files or directories

Exit: 0 = every file passed · 1 = at least one failed · 2 = nothing was checked
(no uv, no matching files).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQ = Path(__file__).resolve().parent / "requirements-test.txt"
MAIN_RE = re.compile(r"^if __name__ == ['\"]__main__['\"]", re.M)
TEST_RE = re.compile(r"^\s*def test_", re.M)


def discover(args: list[str]) -> list[Path]:
    bases = [Path(a).resolve() for a in args] or [ROOT / ".claude"]
    found: set[Path] = set()
    for base in bases:
        if base.is_file():
            found.add(base)
            continue
        for p in base.rglob("test_*.py"):
            if p.parent.name == "tests" and ".cache" not in p.parts:
                found.add(p)
    return sorted(found)


def command(path: Path, uv: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    base = [uv, "run", "--quiet", "--no-project", "--with-requirements", str(REQ), "python"]
    if not MAIN_RE.search(text) and TEST_RE.search(text):
        return base + ["-m", "pytest", "-q", "-p", "no:cacheprovider", str(path)]
    return base + [str(path)]


def main(argv: list[str]) -> int:
    uv = shutil.which("uv")
    if not uv:
        print("ERROR: uv not found — install uv; nothing was checked", file=sys.stderr)
        return 2
    files = discover(argv)
    if not files:
        print("ERROR: no test files matched; nothing was checked", file=sys.stderr)
        return 2
    failed: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        proc = subprocess.run(command(path, uv), cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            print(f"PASS {rel}")
        else:
            failed.append(str(rel))
            print(f"FAIL {rel} (exit {proc.returncode})")
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-25:]
            print("\n".join("    " + line for line in tail))
    print(f"\n{len(files) - len(failed)}/{len(files)} files passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
