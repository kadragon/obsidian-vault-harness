#!/usr/bin/env python3
"""Render an HTML file to PDF with headless Chrome — OS-independent.

Chrome 실행 파일 경로는 OS마다 다르다(macOS .app 번들, Windows Program Files, Linux PATH).
스킬 문서에 경로를 박아 두면 다른 머신에서 늘 틀리므로 탐색은 여기서 한다.

Usage:
    python3 render_pdf.py <input.html> <output.pdf>

Exit 0 on success (prints output path). Exit 1 if Chrome not found or render failed.
"""
import glob
import os
import shutil
import subprocess
import sys

CANDIDATES = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    # Windows (git-bash / native)
    "/c/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
PATH_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]


def find_chrome() -> str | None:
    for name in PATH_NAMES:
        p = shutil.which(name)
        if p:
            return p
    for c in CANDIDATES:
        if os.path.isfile(c):
            return c
    for pat in glob.glob("/Applications/*Chrome*.app/Contents/MacOS/*"):
        if os.access(pat, os.X_OK):
            return pat
    return None


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 1
    src, dst = (os.path.abspath(a) for a in sys.argv[1:3])
    if not os.path.isfile(src):
        print(f"ERROR: input not found: {src}", file=sys.stderr)
        return 1
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chrome not found — install Google Chrome or put chromium on PATH", file=sys.stderr)
        return 1
    url = "file:///" + src.replace("\\", "/").lstrip("/")
    cmd = [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={dst}", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(dst):
        print(f"ERROR: render failed (exit {r.returncode})\n{r.stderr[-800:]}", file=sys.stderr)
        return 1
    print(dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
