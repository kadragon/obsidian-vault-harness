#!/usr/bin/env python3
# PostToolUse hook: 중첩 서브에이전트 위임 지시 검출
#
# 배경 (2026-07-24 실측 / 2026-08-02 정정): 서브에이전트에 `Agent`·`Task`가 없는 것은
# 자동이 아니다 — 정의 frontmatter에 `tools:` 화이트리스트를 명시해야 제외된다.
# `tools:` 미지정 시 Agent를 상속하며, 이때 워커가 자식을 띄우고 기다리지 않고 반환해
# 고아 자식 + 메인 스레드 중복 재디스패치가 발생한다(2026-08-02 inbox-reference-worker 실사례).
#
# 이 훅은 **문서 린터**다 — 서브에이전트가 읽는 .md의 산문 위임 지시만 검출한다.
# 런타임 Agent 호출 차단은 각 에이전트 정의의 `tools:` 화이트리스트가 담당한다.
# 서브에이전트가 읽는 파일에 "다른 에이전트에 위임하라"는 지시가 남아 있으면
# 도구가 제외된 상태에서 런타임 무음 실패로 이어진다.
# 실제로 improvement-planner / incident-analyst / training-note-manager 3곳이
# tag-validator 를 Agent()로 부르도록 되어 있었고, 태그 작성이 조용히 누락됐다.
#
# 검사 대상 (서브에이전트가 읽는 파일만):
#   - .claude/agents/*.md
#   - 서브에이전트 전용 스킬: description 에 "Do NOT invoke directly" 포함
#   - inbox-process 워커 절차서: references/action-branch.md, reference-branch.md
import json, re, sys, pathlib

# 이 볼트의 서브에이전트 이름 — 위임 지시 탐지 대상.
# `.claude/agents/*.md` 에서 런타임에 유도한다. 하드코딩이면 에이전트를 추가할 때
# 이 목록을 갱신하는 것을 잊어 산문 수준 탐지가 조용히 꺼진다(훅이 막으려는 바로 그 무음 실패).
_FALLBACK_AGENT_NAMES = (
    "tag-validator", "vault-navigator", "obsidian-operator", "note-evaluator",
    "incident-analyst", "improvement-planner", "status-judge",
    "training-note-manager", "inbox-action-worker", "inbox-reference-worker",
)


def _agent_names() -> tuple:
    try:
        agents_dir = pathlib.Path(__file__).resolve().parent.parent / "agents"
        names = tuple(sorted(p.stem for p in agents_dir.glob("*.md")))
    except OSError:
        return _FALLBACK_AGENT_NAMES
    return names or _FALLBACK_AGENT_NAMES


AGENT_NAMES = _agent_names()

# 위임을 지시하는 표현. "위임 금지"·"호출할 수 없다" 같은 부정문은 아래에서 제외한다.
#
# 어미 그룹은 **필수로 유지**한다. 선택(`?`)으로 풀면 에이전트명 근처의 모든 `위임`·`호출`이
# 걸려, 규칙이 권장하는 표현("…보고에 적어 메인 스레드가 호출하게 한다", "오케스트레이터가
# 수행한다", "incident-analyst 추가 호출 필요?로 반환")까지 전부 오탐한다(실측 8건).
# 대신 놓치던 세 형태 — 명사형 줄끝 `…에 위임`, 연결형 `…에 위임하거나`, 괄호 앞 `…에 위임 (`
# — 를 어미 목록에 명시적으로 추가한다. `하게`·`하지`·` 불가`·` 필요` 는 일부러 제외한다.
DELEGATE_PAT = re.compile(
    r"(subagent_type|\bAgent\s*\(|\bTask\s*\()"
    # 에이전트명과 위임 동사 사이에 목적어가 끼어드는 경우까지 잡는다
    # (예: "vault-navigator에게 볼트 전체 검색을 위임할 수 있다").
    r"|((" + "|".join(re.escape(n) for n in AGENT_NAMES) + r")[^\n]{0,40}?"
    r"(위임|호출|맡기|맡긴|배포|기동|스폰)"
    r"(한다|하라|할 것|할 수 있|해야|하도록|하고|하거나|하여|해서|한 뒤|\s*$|\s*\())"
)

# 부정·해설 문맥 — 위반이 아니다 (금지 규칙 자체를 문서화한 줄).
# `없음)`·`하지 말` 은 그대로 두면 "(제한 없음)" 같은 무관한 줄까지 삼켜 위반을 가린다 →
# 위임 문맥에 붙은 형태로만 좁힌다.
NEGATION_PAT = re.compile(
    r"(위임\s*(금지|불가)|호출\s*(금지|불가)|호출하지\s*않는다|호출할\s*수\s*없|"
    r"부를\s*수\s*없|(부르|호출)지\s*못한|"
    r"금지\s*—|실행\s*불가|(Agent|Task)[^\n]{0,12}없음|(위임|호출)하지\s*말|"
    r"not\s+call|cannot\s+call)"
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
