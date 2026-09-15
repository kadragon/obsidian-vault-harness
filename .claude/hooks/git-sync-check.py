#!/usr/bin/env python3
"""SessionStart hook: realign local main with origin/main.

Syncthing syncs the working tree but `.stignore` excludes `.git/`, so commits
made and pushed on another machine arrive here as plain file edits while this
machine's HEAD stays behind. Left alone, a later commit here diverges history.

- in sync, or not on main, or not a git repo -> silent
- behind only -> `git reset --mixed origin/main` (working files untouched)
- staged changes while behind -> warn, no reset (reset would drop the index)
- diverged (local-only commits) -> warn, no reset (needs content comparison)
- fetch failure -> warn

Warning-only; always exits 0.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REMOTE_REF = "origin/main"
MAX_LISTED = 10


def git(repo: Path, *args: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def emit(message: str) -> None:
    print(json.dumps({
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        },
    }))


def check(repo: Path) -> str:
    if git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return ""
    if git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip() != "main":
        return ""

    try:
        fetch = git(repo, "fetch", "--quiet", "origin")
    except subprocess.TimeoutExpired:
        return "[git-sync] git fetch 시간 초과 — 원격 동기화 상태 미확인. 커밋 전 `git fetch` 후 `git status -sb` 확인."
    if fetch.returncode != 0:
        return f"[git-sync] git fetch 실패 — 원격 동기화 상태 미확인: {fetch.stderr.strip()[:200]}"

    counts = git(repo, "rev-list", "--left-right", "--count", f"HEAD...{REMOTE_REF}")
    if counts.returncode != 0:
        return ""
    ahead, behind = (int(n) for n in counts.stdout.split())

    if ahead == 0 and behind == 0:
        return ""

    if ahead > 0:
        return (
            f"[git-sync] 로컬 main이 {REMOTE_REF}와 갈라짐 (로컬 전용 {ahead}커밋 · 원격 전용 {behind}커밋). "
            "자동 정리 안 함. 로컬 커밋 내용이 원격에 포함됐는지 대조 → "
            "`git branch backup/local-main-<날짜> main` → `git reset --mixed origin/main`. "
            "커밋·push 금지 (대조 전)."
        )

    if git(repo, "diff", "--cached", "--quiet").returncode != 0:
        return (
            f"[git-sync] 로컬 main이 {REMOTE_REF}보다 {behind}커밋 뒤처졌지만 스테이징된 변경이 있어 reset 안 함. "
            "스테이징 내용 확인 후 `git reset --mixed origin/main`."
        )

    reset = git(repo, "reset", "--mixed", "--quiet", REMOTE_REF)
    if reset.returncode != 0:
        return f"[git-sync] reset --mixed 실패: {reset.stderr.strip()[:200]}"

    changed = [line for line in git(repo, "diff", "--name-only").stdout.splitlines() if line]
    message = (
        f"[git-sync] 로컬 main이 {REMOTE_REF}보다 {behind}커밋 뒤처져 `git reset --mixed {REMOTE_REF}` 적용 "
        "(작업 파일 무변경)."
    )
    if changed:
        listed = ", ".join(changed[:MAX_LISTED])
        more = f" 외 {len(changed) - MAX_LISTED}건" if len(changed) > MAX_LISTED else ""
        message += (
            f" 원격과 다른 파일 {len(changed)}건: {listed}{more}. "
            "Syncthing 미도착 파일이면 커밋 시 원격 변경을 되돌리므로 커밋 전 `git diff` 확인."
        )
    return message


def main() -> int:
    try:
        sys.stdin.read()
    except OSError:
        pass
    repo = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
    try:
        message = check(repo)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        message = f"[git-sync] 동기화 검사 오류: {exc}"
    if message:
        emit(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
