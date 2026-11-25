#!/usr/bin/env python3
# PostToolUse check: 볼트 노트 Write/Edit 후 #업무/#부서 태그 검증 (구 validate-tags.sh).
#
# 태그 규칙 본문은 .claude/lib/validate_tag.py 하나뿐이다. 형태 검사(금지 접두어·괄호·미등록
# area)와 의미 검사(직급·부서명 매핑, P_ 접두어, 퇴직/ 경로)를 모두 거기서 하므로 여기서
# 재구현하지 않는다 — 두 사본이 갈라진다. 이 파일은 "본문에서 태그를 뽑아 넘기고 결과를
# 보고 문구로 바꾸는" 어댑터이고, #부서 태그의 frontmatter 위치 검사만 직접 한다
# (validate_tag.py 는 태그 문자열만 보므로 파일 안의 위치를 모른다).
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from hook_io import run_standalone

try:
    import validate_tag
except ModuleNotFoundError:
    validate_tag = None

VAULT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_DIRS = ("/.claude/", "/99_Template/", "/docs/")
FENCE_RE = re.compile(r"^\s*```")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
TAG_RE = re.compile(r'#(업무|부서)/[^ \t"]*')


def _norm(path: str) -> str:
    """Comparable form of a path: MSYS /c/... -> C:/..., links resolved, forward slashes."""
    if os.name == "nt" and re.match(r"^/[A-Za-z](/|$)", path):
        path = path[1].upper() + ":" + path[2:]
    return os.path.realpath(path).replace("\\", "/")


def _strip_code(text: str) -> list[str]:
    """Drop fenced blocks and inline code so query/example tags are not flagged."""
    kept = []
    in_fence = False
    for ln in text.split("\n"):
        if FENCE_RE.match(ln):
            in_fence = not in_fence
            continue
        if not in_fence:
            kept.append(INLINE_CODE_RE.sub("", ln))
    return kept


def _frontmatter_has_dept_tag(text: str) -> bool:
    count = 0
    for ln in text.split("\n"):
        if ln == "---":
            count += 1
            if count == 2:
                break
        if count == 1 and "#부서/" in ln:
            return True
    return False


def check(fp, tool_name=None):
    if not fp or not fp.endswith(".md"):
        return None
    if validate_tag is None:
        print("check-tags: validate_tag.py not found — tag validation skipped", file=sys.stderr)
        return None
    full = _norm(fp)
    if not full.lower().startswith(_norm(str(VAULT_ROOT)).lower() + "/"):
        return None
    if any(s in full for s in SKIP_DIRS):
        return None
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None

    violations = []

    # Placeholder tags in docs/templates ({area}, {부서명}) are markup — drop braces.
    tags = sorted({m.group(0).strip() for ln in _strip_code(text) for m in TAG_RE.finditer(ln)
                   if not re.search(r"[{}]", m.group(0))})
    report = []
    for tag in tags:
        r = validate_tag.validate(tag).to_dict()
        if r.get("valid"):
            continue
        line = "  - " + r["original"]
        if r.get("normalized") and r["normalized"] != r["original"]:
            line += " → " + r["normalized"]
        report.append(line)
        report.extend("      · " + i for i in r.get("issues", []))
    if report:
        violations.append("\n".join(report))

    if _frontmatter_has_dept_tag(text):
        violations.append("  - #부서 태그가 frontmatter에 있음 (본문으로 이동 필요)")

    if not violations:
        return None
    return ("[태그 검증 경고] " + pathlib.Path(fp).name + "\n"
            "위반 사항:" + "".join("\n" + v for v in violations) + "\n"
            "tag-validator 에이전트를 실행하여 태그를 정규화하세요.")


if __name__ == "__main__":
    sys.exit(run_standalone(check))
