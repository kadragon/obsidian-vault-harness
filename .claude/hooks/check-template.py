#!/usr/bin/env python3
# PostToolUse hook: GP#2 template check
# 규칙 본문은 `.claude/lib/note_rules.py` 하나뿐이다 (vault_lint.py도 같은 함수를 쓴다).
# 이 파일은 stdin 페이로드 → note_rules.check_file → hookSpecificOutput 어댑터일 뿐,
# 규칙을 재구현하지 않는다 (`validate_tag.py` 를 부르는 태그 검사와 같은 구조).
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from hook_io import run_standalone

try:
    import note_rules
except ModuleNotFoundError:
    note_rules = None   # 라이브러리 부재 시 조용히 통과 — 쓰기를 막지 않는다
# 그 외 예외(SyntaxError 등)는 삼키지 않는다 — 규칙 파일이 깨지면 훅이 전 노트에 대해
# 조용히 무음 통과해 검사가 통째로 사라진다(실측 2026-08-25: 편집 실수로 findings 133→0).
# post-write.py 러너는 import 실패를 경고 메시지로 노출한다.


def check(fp, tool_name=None):
    if note_rules is None or not fp or not fp.endswith(".md"):
        return None
    violations = note_rules.check_file(fp)
    if violations:
        return ("[GP#2 템플릿 경고] " + pathlib.Path(fp).name + "\n"
                + "\n".join("  - " + v for v in violations))
    return None


if __name__ == "__main__":
    sys.exit(run_standalone(check))
