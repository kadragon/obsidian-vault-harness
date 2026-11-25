#!/usr/bin/env python3
# PostToolUse hook (Write|Edit): markdownlint advisory for the file just written.
# Rules and ignores live in `.markdownlint-cli2.jsonc` at the vault root
# (Obsidian-aware whitelist). Advisory only — never blocks, never fixes.
# Silently skips when node/npm is missing, the file is outside the vault, or the
# linter fails or times out, so a broken Node setup never interrupts note writing.
#
# Runs a pinned local copy of markdownlint-cli2 instead of `npx --yes`: npx re-resolves the
# package against the registry on every call (~5 s per edit); the local copy starts in ~1 s.
# The copy lives outside the vault (the vault is Syncthing-synced across OSes) and is
# installed lazily on first use; a failed install is not retried for FAIL_RETRY_SECONDS.
# Kept as its own hook (not inside post-write.py) so the Node process runs in parallel
# with the in-process Python checks.
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from hook_io import run_standalone

VERSION = "0.17.2"
TIMEOUT = 20
INSTALL_TIMEOUT = 25
FAIL_RETRY_SECONDS = 3600
MAX_SHOWN = 10
HIT_RE = re.compile(r"^(?P<file>.+?\.md):(?P<line>\d+)(?::\d+)? (?P<rule>MD\d{3})/\S+ (?P<msg>.*)$")


def cache_dir() -> pathlib.Path:
    override = os.environ.get("MARKDOWNLINT_CACHE_DIR")
    if override:
        return pathlib.Path(override)
    return pathlib.Path.home() / ".cache" / "knue-vault-harness" / f"markdownlint-cli2-{VERSION}"


def entry_point(cache: pathlib.Path) -> pathlib.Path:
    return cache / "node_modules" / "markdownlint-cli2" / "markdownlint-cli2-bin.mjs"


def ensure_installed() -> pathlib.Path | None:
    """Return the linter entry point, installing it once when missing."""
    cache = cache_dir()
    entry = entry_point(cache)
    if entry.is_file():
        return entry
    marker = cache.with_name(cache.name + ".install-failed")
    try:
        if time.time() - marker.stat().st_mtime < FAIL_RETRY_SECONDS:
            return None
    except OSError:
        pass
    npm = shutil.which("npm")
    if not npm:
        return None
    # Install beside the target, then rename: concurrent sessions never see a half install.
    staging = cache.with_name(f"{cache.name}.tmp-{os.getpid()}")
    ok = False
    try:
        staging.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [npm, "install", "--no-audit", "--no-fund", "--silent", "--prefix", str(staging),
             f"markdownlint-cli2@{VERSION}"],
            capture_output=True, text=True, encoding="utf-8", timeout=INSTALL_TIMEOUT)
        ok = r.returncode == 0 and entry_point(staging).is_file()
        if ok:
            try:
                os.replace(staging, cache)
            except OSError:
                pass  # another session installed first
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    if entry.is_file():
        return entry
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        pass
    return None


def check(fp, tool_name=None):
    if not fp or not fp.endswith(".md"):
        return None

    root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR")
                        or pathlib.Path(__file__).resolve().parents[2]).resolve()
    if not (root / ".markdownlint-cli2.jsonc").is_file():
        return None
    try:
        rel = pathlib.Path(fp).resolve().relative_to(root)
    except ValueError:
        return None

    node = shutil.which("node")
    if not node:
        return None
    entry = ensure_installed()
    if entry is None:
        return None

    try:
        r = subprocess.run([node, str(entry), rel.as_posix()], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None

    hits = [m for m in (HIT_RE.match(l) for l in (r.stdout + r.stderr).splitlines()) if m]
    if not hits:
        return None

    lines = [f"  L{m['line']} {m['rule']} {m['msg']}" for m in hits[:MAX_SHOWN]]
    if len(hits) > MAX_SHOWN:
        lines.append(f"  … 외 {len(hits) - MAX_SHOWN}건")
    return (f"[markdownlint] {rel.name} — {len(hits)}건 (경고, 차단 아님)\n" + "\n".join(lines) +
            "\n방금 작성한 부분이면 고칠 것. 기존 본문은 사용자 승인 범위 밖이면 손대지 말 것(GP#1).")


if __name__ == "__main__":
    sys.exit(run_standalone(check))
