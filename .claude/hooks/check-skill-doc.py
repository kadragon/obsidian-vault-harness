#!/usr/bin/env python3
# PostToolUse hook + `--sweep`: 스킬 문서(.claude/skills/**/*.md) 장황함·환경 종속 린터
#
# 규칙 문장에 근거 서사·실측치·머신 종속 사실을 함께 쓰면 문서가 부풀고 반은 틀린 채 남는다
# (볼트는 Syncthing으로 macOS·Windows를 오간다). 규칙은 명령형 한 줄, 근거는
# `docs/harness-log.md`, 환경 판단은 스크립트가 한다 — 이 훅은 그 분리를 기계적으로 지킨다.
#
# 검사 (모두 경고, 차단 없음):
#   length   SKILL.md > MAX_SKILL_LINES · 기타 .md > MAX_REF_LINES  (래칫 — 낮추기만 한다)
#   token    근거 서사·머신 종속 토큰 (`실측`, `이 머신`, `(YYYY-MM-DD 확립|개정)` 등)
#   bold     굵게 쌍 수 / 비어있지 않은 줄 수 > BOLD_RATIO
#   snippet  코드 펜스 안에서 `"\n"`이 실제 개행으로 깨진 흔적 (`= "` 로 끝나는 줄, `".join` 으로 시작하는 줄)
#
# 사용:
#   (훅) stdin JSON {"tool_input":{"file_path":...}}
#   python3 .claude/hooks/check-skill-doc.py --sweep [vault_root]   # 전수, 발견 시 exit 1
import json
import pathlib
import re
import sys

MAX_SKILL_LINES = 250
MAX_REF_LINES = 350
BOLD_RATIO = 0.35

TOKEN_PAT = re.compile(
    r"실측|이 머신|이 환경|전례가 있다|사고가 잦다|"
    r"\(\d{4}-\d{2}-\d{2}\s*(확립|개정|정정|강등|폐기)\)|"
    r"\d{4}-\d{2}-\d{2}\s*(실측|이 지시로)"
)
BROKEN_SNIPPET_PAT = re.compile(r'(=\s*"$|^"\.join)')


def is_skill_doc(path: pathlib.Path) -> bool:
    p = str(path.resolve()).replace("\\", "/")
    return "/.claude/skills/" in p and p.endswith(".md") and "/.pytest_cache/" not in p


def check(path: pathlib.Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    hits: list[str] = []

    limit = MAX_SKILL_LINES if path.name == "SKILL.md" else MAX_REF_LINES
    if len(lines) > limit:
        hits.append(f"length: {len(lines)}줄 > {limit} — references/·스크립트 --help로 분리")

    nonempty = sum(1 for ln in lines if ln.strip()) or 1
    bold_pairs = text.count("**") // 2
    if bold_pairs / nonempty > BOLD_RATIO:
        hits.append(
            f"bold: 굵게 {bold_pairs}쌍 / {nonempty}줄 = {bold_pairs / nonempty:.0%} > "
            f"{BOLD_RATIO:.0%} — 표 셀 라벨·격줄 강조 제거"
        )

    in_fence = False
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            if BROKEN_SNIPPET_PAT.search(ln.strip()):
                hits.append(f"snippet L{i}: 깨진 이스케이프 의심 — {ln.strip()[:60]}")
            continue
        m = TOKEN_PAT.search(ln)
        if m:
            hits.append(f"token L{i}: `{m.group(0)}` — 근거·환경 사실은 docs/harness-log.md 또는 스크립트로")
    return hits


def sweep(root: pathlib.Path) -> int:
    total = 0
    for p in sorted((root / ".claude" / "skills").rglob("*.md")):
        if not is_skill_doc(p):
            continue
        hits = check(p)
        if hits:
            total += len(hits)
            print(f"{p.relative_to(root)}")
            for h in hits:
                print(f"  {h}")
    print(f"\n{total} finding(s)")
    return 1 if total else 0


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--sweep":
        root = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else ".").resolve()
        sys.exit(sweep(root))

    try:
        d = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)
    fp = (d.get("tool_input") or {}).get("file_path", "")
    if not fp:
        sys.exit(0)
    path = pathlib.Path(fp)
    if not path.is_file() or not is_skill_doc(path):
        sys.exit(0)
    hits = check(path)
    if not hits:
        sys.exit(0)
    msg = (
        f"[스킬 문서 경고] {path.name}\n" + "\n".join(f"  {h}" for h in hits)
        + "\n조치: 규칙은 명령형 한 줄로, 근거는 docs/harness-log.md로, 환경 판단은 스크립트로 옮겨라."
    )
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}
    }))


if __name__ == "__main__":
    main()
