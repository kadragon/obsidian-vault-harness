#!/usr/bin/env python3
# PostToolUse hook (Write|Edit): project hub length advisory.
# A project hub is `12_Projects/.../{folder}/_{folder}.md`. When it grows past
# MAX_LINES, suggest the project-restructure skill (split into stage notes).
# Advisory only — never blocks.
import pathlib
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from hook_io import run_standalone

MAX_LINES = 120


def check(fp, tool_name=None):
    if not fp or not fp.endswith(".md"):
        return None

    # leading "/" so a vault-relative `12_Projects/...` path also matches
    fp_norm = "/" + unicodedata.normalize("NFC", fp.replace("\\", "/")).lstrip("/")
    if "/12_Projects/" not in fp_norm:
        return None

    path = pathlib.PurePosixPath(fp_norm)
    if path.stem != "_" + path.parent.name:
        return None
    # Project folder sits at 12_Projects/{folder} or 12_Projects/{YYYY}/{folder};
    # deeper matches are stage-folder notes such as `3. 과업심의/_3. 과업심의.md`.
    container = path.parent.parent
    if not (container.name == "12_Projects"
            or (container.name.isdigit() and len(container.name) == 4
                and container.parent.name == "12_Projects")):
        return None

    try:
        with open(fp, encoding="utf-8") as f:
            lines = sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        return None

    if lines <= MAX_LINES:
        return None

    return (f"[프로젝트 허브 길이] {path.name} — {lines}줄 (기준 {MAX_LINES}줄 초과). "
            "완료 단계의 진행 기록을 단계 노트로 나누려면 project-restructure 스킬을 제안할 것. "
            "사용자 승인 없이 분리하지 말 것.")


if __name__ == "__main__":
    sys.exit(run_standalone(check))
