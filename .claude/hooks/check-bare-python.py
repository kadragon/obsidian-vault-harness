#!/usr/bin/env python3
# PostToolUse hook: 하네스 파일의 맨 `python` 호출 검출 (`python3` 강제)
#
# 배경 (2026-08-02, PR #20 리뷰 실측): cd30915에서 한 번 정리했는데 3곳이 재발했다.
# 비대화형 셸에는 `python` 별칭이 없어 `command not found`로 죽는데, 훅·스크립트의
# **무출력을 "검사 통과"로 읽으라는 문서**와 겹치면 실패가 통과로 오독된다.
# 즉 이 오타는 조용히 게이트를 통째로 꺼버린다 — 경고 하나가 아니라 검사 부재가 된다.
#
# 검사 대상: `.claude/` · `docs/` 아래 `.md` · `.sh` · `.py`
#   (문서의 예시 명령이 그대로 복사돼 실행되므로 산문 파일도 대상이다)
#
# 두 가지 모드:
#   - 기본: PostToolUse 훅 (stdin 으로 tool_input 수신, 쓰기 직후 실시간 방어)
#   - --sweep [경로...]: 저장소 전수 스캔 (잔존분 일괄 검출, CI·수동 점검용)
#     exit 1 = 발견 · 0 = 검사했고 깨끗함 · 2 = **아무것도 검사 못 함**(경로 오타 등).
#     훅 모드는 경고만 하고 항상 exit 0.
#
# 알려진 누락 — "0건"을 전수 무결로 읽지 말 것 (이 훅이 막으려는 오독이 바로 그것이다).
# 인자 없는 단독 `python`(REPL·`echo x | python`), `python $SCRIPT`(따옴표 없는 변수),  # bare-python-ok: 규칙을 설명하는 예시
# `PYTHON=python` 대입, `alias py=python`, heredoc `python <<EOF`,
# 확장자 없는 상대경로(`python bin/tool`), `python2`.
# 전부 산문 오탐을 피하려고 일부러 뺐다. 넓히려면 오탐 실측을 먼저 하라.
import json
import re
import sys
import pathlib

SCAN_DIRS = (".claude", "docs")
SCAN_SUFFIXES = (".md", ".sh", ".py")

# `python` 뒤에 **인자가 붙은 형태만** 잡는다. 산문("`python` 별칭이 없어", "python 3.11")을
# 오탐하지 않으려면 "명령처럼 보이는가"가 유일하게 신뢰할 만한 신호다.
# `(?![\w.-])` 로 `python3`·`python_files`·`python.org` 를 먼저 배제한다.
_BARE = r"(?<![\w.-])python(?![\w.-])"

# 경로 인자는 **명시적으로 경로처럼 생긴 것만** 인정한다. "`/` 를 포함한 ASCII 토큰"으로
# 넓게 잡았더니 영어 산문이 줄줄이 걸렸다(QA 실측: `python and/or python3`, `python I/O`,
# `python A/B testing`, `python this/that`). 그래서 두 형태로 좁힌다 —
# 경로 접두사(`./` `../` `/` `~/` `$`)로 시작하거나, `.py` 로 끝나거나.
# 대가로 확장자 없는 상대경로(`python bin/tool`)는 놓친다. 아래 '알려진 누락' 참고.
_PATHARG = r"(?:(?:\.{0,2}/|~/|\$)[^\s\"';|&]*|[A-Za-z0-9_.~$/\\-]*\.[Pp][Yy]\b)"

# 런처는 **명령 위치에 있을 때만** 인정한다. 위치를 안 보면 산문이 걸린다
# (QA 실측: `the env python var is unset`, `the type python is dynamic`).
_CMDPOS = r"(?:^|[|;&`(]|&&|\|\||\$\()[ \t]*"

# 분기를 리스트로 모아 `|` 로 잇는다. 이전 판은 줄바꿈 암묵적 문자열 연결에 기대고 있어,
# 주석 한 줄을 끼우자 `_PATHARG`(이름) 다음 문자열에서 SyntaxError 가 났다.
BARE_PY_PAT = re.compile("|".join([
    # (a) 인터프리터 플래그: `python -c` · `python -m` · `python --version`  # bare-python-ok: 규칙을 설명하는 예시
    _BARE + r"[ \t]+(?:-[cmuBEIOWXqsv]\b|-{1,2}[A-Za-z])",
    # (b) 따옴표 없는 경로 인자: `python scripts/foo.py` · `python ./x.py`  # bare-python-ok: 규칙을 설명하는 예시
    _BARE + r"[ \t]+" + _PATHARG,
    # (c) 따옴표로 감싼 경로 — 공백 있는 경로·변수를 놓치던 형태 (QA 실측)
    _BARE + r"[ \t]+[\"'](?:(?:\.{0,2}/|~/|\$)[^\"']*|[^\"']*\.[Pp][Yy])[\"']",
    # (d) 런처가 인터프리터를 실행: `| xargs python` · `env python` · `exec python`  # bare-python-ok: 규칙을 설명하는 예시
    _CMDPOS + r"(?:xargs|exec|env|nohup|sudo|time)"
    r"(?:[ \t]+-{1,2}[^\s|;&]+)*[ \t]+python(?![\w.-])",
    # (e) 명령치환으로 경로를 집어옴: `$(which python)` · `` `command -v python` ``  # bare-python-ok: 규칙을 설명하는 예시
    r"(?:\$\(|`)[ \t]*(?:which|command[ \t]+-v|type)[ \t]+python(?![\w.-])",
]))

# 셔뱅은 인자가 없으므로 별도로 잡는다 (예시).
# 마크다운 코드블록 안의 들여쓴 셔뱅도 대상이라 선행 공백을 허용한다(QA 실측 누락).
SHEBANG_PAT = re.compile(r"^\s*#!.*[/ ]python(?![\w.-])")

# 면제는 **오직** 아래 `bare-python-ok:` 마커뿐이다.
# 이전 판에는 `금지`·`오탐`·`check-bare-python` 같은 키워드가 줄 전체를 면제하는
# ALLOW_PAT 이 있었는데, QA 실측 결과 28개 파일 75줄이 조용히 면제됐고
# 진짜 위반(가드 자신의 호출 예시)까지 통과시켰다.
# 가드가 막으려던 "검사 부재"를 가드가 재현한 셈이라 통째로 삭제했다.

# 명시적 억제 — **이유 필수**. 이유 없는 마커는 억제로 인정하지 않는다(무언의 무력화 방지).
# 두 가지 스코프:
#   - 헤딩 줄에 붙이면 다음 헤딩 전까지 (runbook 의 `### 항목` 단위 억제)
#   - 그 외 줄에 붙이면 그 줄만
# 용례: 맨 `python` 자체를 **주제로 설명하는** 문서 (Windows 스토어 스텁 해석 등).
# `(?!-->)` 가 없으면 `<!-- bare-python-ok: -->` 의 닫는 `-->` 가 이유 노릇을 해
# 이유 없는 마커가 통과한다(QA 실측). 마크다운에서 쓰는 형태가 바로 이거라 중요하다.
SUPPRESS_PAT = re.compile(r"bare-python-ok:[ \t]*(?!-->)\S")
# 헤딩 스코프 억제는 **마크다운 전용**이다. `.py`·`.sh` 에서는 `# 주석` 이 전부
# 헤딩으로 보여 억제 범위가 주석 한 줄마다 열리고 닫힌다(의미 없는 동작).
HEADING_PAT = re.compile(r"^#{1,6}\s")
FENCE_PAT = re.compile(r"^\s*(?:```|~~~)")


def in_scope(path: pathlib.Path, root: pathlib.Path) -> bool:
    if path.suffix not in SCAN_SUFFIXES:
        return False
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return False
    return rel.parts and rel.parts[0] in SCAN_DIRS


def scan(path: pathlib.Path) -> list:
    """읽기 실패는 OSError 로 전파한다 — 삼키면 '읽지 못함'이 '0건 = 통과'가 된다."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = []
    md = path.suffix == ".md"
    section_suppressed = False
    fenced = False
    for i, ln in enumerate(lines, 1):
        if md and FENCE_PAT.match(ln):
            fenced = not fenced
        marked = bool(SUPPRESS_PAT.search(ln))
        # 펜스 안의 `# 주석` 은 헤딩이 아니다. 구분하지 않으면 코드블록 한 줄이
        # 진행 중인 섹션 억제를 조용히 닫아버린다(QA 실측).
        if md and not fenced and HEADING_PAT.match(ln):
            # 헤딩을 만나면 이전 섹션의 억제는 끝난다. 이 헤딩에 마커가 있으면 새로 켠다.
            section_suppressed = marked
        if section_suppressed or marked:
            continue
        if BARE_PY_PAT.search(ln) or SHEBANG_PAT.search(ln):
            hits.append((i, ln.strip()[:120]))
    return hits


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent.parent


def warn_text(path: pathlib.Path, hits: list) -> str:
    body = "\n".join(f"  L{i}: {ln}" for i, ln in hits)
    return (
        f"[맨 python 호출 경고] {path.name}\n"
        "비대화형 셸에는 `python` 별칭이 없다. 이 줄은 `command not found`로 죽는데, "
        "그 무출력이 '검사 통과'로 오독된다.\n"
        f"{body}\n"
        "조치: `python3`로 바꿔라 (셔뱅은 `#!/usr/bin/env python3`)."
    )


def sweep(argv: list) -> int:
    root = repo_root()
    targets = [pathlib.Path(a) for a in argv] or [root / d for d in SCAN_DIRS]
    found = 0
    scanned = 0
    unreadable = 0
    for t in targets:
        # 오타·범위 밖 경로가 "0건 = 통과"로 읽히면 이 훅이 막으려는 바로 그 오독이다.
        # 대상이 실제로 검사됐는지 세어, 하나도 안 봤으면 exit 2 로 구분한다.
        if not t.exists():
            print(f"대상 없음: {t}", file=sys.stderr)
            continue
        files = sorted(t.rglob("*")) if t.is_dir() else [t]
        for f in files:
            if not f.is_file() or not in_scope(f, root):
                continue
            try:
                hits = scan(f)
            except OSError as e:
                # 못 읽은 파일을 scanned 로 세면 "0건 = 통과"가 된다. 세지 않고 알린다.
                unreadable += 1
                print(f"읽기 실패(검사 못 함): {f} — {e}", file=sys.stderr)
                continue
            scanned += 1
            if hits:
                found += len(hits)
                rel = f.resolve().relative_to(root)
                for i, ln in hits:
                    print(f"{rel}:{i}: {ln}")
    if found:
        print(f"\n{found}건 발견 — `python3`로 교체하라.", file=sys.stderr)
        return 1
    if unreadable:
        print(f"{unreadable}개 파일을 읽지 못했다 — '이상 없음'이 아니다.", file=sys.stderr)
        return 2
    if not scanned:
        print(
            f"검사 대상 0개 — 경로가 {'/'.join(SCAN_DIRS)} 밖이거나 확장자가 "
            f"{'/'.join(SCAN_SUFFIXES)} 가 아니다. '이상 없음'이 아니다.",
            file=sys.stderr,
        )
        return 2
    return 0


def main() -> None:
    if "--sweep" in sys.argv[1:]:
        sys.exit(sweep([a for a in sys.argv[1:] if a != "--sweep"]))

    # 훅 모드는 **무슨 일이 있어도 exit 0** 이어야 한다 — 훅이 죽으면 도구 호출이
    # 실패한 것처럼 보인다. stdin 파싱뿐 아니라 페이로드 형태 접근까지 감싼다.
    try:
        d = json.loads(sys.stdin.read())
        fp = d["tool_input"]["file_path"]
        if not isinstance(fp, str):
            raise TypeError
    except Exception:
        sys.exit(0)

    path = pathlib.Path(fp)
    if not fp or not path.is_file() or not in_scope(path, repo_root()):
        sys.exit(0)

    try:
        hits = scan(path)
    except OSError:
        sys.exit(0)  # 훅 모드는 항상 exit 0 — 못 읽으면 조용히 넘어간다.
    if not hits:
        sys.exit(0)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": warn_text(path, hits),
        }
    }))


if __name__ == "__main__":
    main()
