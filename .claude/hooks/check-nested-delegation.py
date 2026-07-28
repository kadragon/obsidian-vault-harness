#!/usr/bin/env python3
# PostToolUse hook: 중첩 서브에이전트 위임 지시 검출
#
# 배경 (2026-07-24 실측): 서브에이전트의 도구 목록에는 `Agent`·`Task`가 없다.
# 따라서 서브에이전트가 읽는 파일(에이전트 정의, 서브에이전트 전용 스킬)에
# "다른 에이전트에 위임하라"는 지시를 쓰면 런타임에 무음 실패한다.
# 실제로 improvement-planner / incident-analyst / training-note-manager 3곳이
# tag-validator 를 Agent()로 부르도록 되어 있었고, 태그 작성이 조용히 누락됐다.
#
# 검사 대상 (서브에이전트가 읽는 파일만):
#   - .claude/agents/*.md
#   - 서브에이전트 전용 스킬: description 에 "Do NOT invoke directly" 포함
#   - inbox-process 워커 절차서: references/action-branch.md, reference-branch.md
import json, re, sys, pathlib

# 이 볼트의 서브에이전트 이름 — 위임 지시 탐지 대상
AGENT_NAMES = (
    "tag-validator", "vault-navigator", "obsidian-operator", "note-evaluator",
    "incident-analyst", "improvement-planner", "status-judge",
    "training-note-manager", "inbox-action-worker", "inbox-reference-worker",
)

# 위임을 지시하는 표현. "위임 금지"·"호출할 수 없다" 같은 부정문은 아래에서 제외한다.
DELEGATE_PAT = re.compile(
    r"(subagent_type|\bAgent\s*\(|\bTask\s*\()"
    # 에이전트명과 위임 동사 사이에 목적어가 끼어드는 경우까지 잡는다
    # (예: "vault-navigator에게 볼트 전체 검색을 위임할 수 있다").
    r"|((" + "|".join(AGENT_NAMES) + r")[^\n]{0,40}?"
    r"(위임|호출|배포|기동|스폰)(한다|하라|할 것|할 수 있|해야|하도록|하고))"
)

# 부정·해설 문맥 — 위반이 아니다 (금지 규칙 자체를 문서화한 줄)
NEGATION_PAT = re.compile(
    r"(위임\s*금지|호출하지\s*않는다|호출할\s*수\s*없|부를\s*수\s*없|"
    r"금지\s*—|실행\s*불가|없음\s*\)|하지\s*말|not\s+call|cannot\s+call)"
)


def is_subagent_facing(path: pathlib.Path) -> bool:
    # 상대경로로 들어와도 매칭되도록 절대경로로 정규화한다.
    p = str(path.resolve()).replace("\\", "/")
    if "/.claude/agents/" in p and p.endswith(".md"):
        return True
    if p.endswith(("/references/action-branch.md", "/references/reference-branch.md")):
        return True
    # 서브에이전트 전용 스킬은 SKILL.md뿐 아니라 references/ 까지 전부 대상이다
    # (워커 절차서가 references 에 있어 여기에 위임 지시가 숨는다).
    if "/.claude/skills/" in p:
        skill_root = pathlib.Path(p.split("/.claude/skills/", 1)[0]) / ".claude" / "skills"
        rel = p.split("/.claude/skills/", 1)[1].split("/", 1)[0]
        try:
            head = (skill_root / rel / "SKILL.md").read_text(
                encoding="utf-8", errors="replace")[:2000]
        except OSError:
            return False
        return "Do NOT invoke directly" in head
    return False


def main() -> None:
    try:
        d = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    fp = (d.get("tool_input") or {}).get("file_path", "")
    if not fp or not fp.endswith(".md"):
        sys.exit(0)

    path = pathlib.Path(fp)
    if not path.is_file() or not is_subagent_facing(path):
        sys.exit(0)

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        sys.exit(0)

    hits = [
        f"  L{i}: {ln.strip()[:120]}"
        for i, ln in enumerate(lines, 1)
        if DELEGATE_PAT.search(ln) and not NEGATION_PAT.search(ln)
    ]
    if not hits:
        sys.exit(0)

    msg = (
        f"[중첩 위임 경고] {path.name}\n"
        "이 파일은 서브에이전트가 읽는다. 서브에이전트에는 `Agent`·`Task` 도구가 없어 "
        "아래 위임 지시는 런타임에 무음 실패한다.\n"
        + "\n".join(hits)
        + "\n조치: 해당 작업을 에이전트가 직접 수행하도록 바꾸거나(`Skill` 도구는 사용 가능), "
        "메인 스레드에 보고해 호출하게 하라."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        }
    }))


if __name__ == "__main__":
    main()
