#!/usr/bin/env python3
"""볼트 전수 lint — 읽기 전용, 결정론적. 쓰기·수정은 절대 하지 않는다.

훅(`check-template.py`)은 쓰기 시점 단건만 본다. Bash `sed -i`·스크립트 대량 변경과
링크 그래프(deadlink·orphan)는 훅이 구조적으로 못 잡으므로 여기서 전수로 본다.
템플릿·frontmatter 규칙은 재구현하지 않고 `note_rules.check()`를 호출한다 (SSOT 1개).

검사:
  deadlink    [[대상]]이 어떤 파일로도 해석되지 않음
  ambiguous   경로 미지정 링크가 같은 이름의 노트 2건 이상에 걸림
  orphan      inbound 링크 0 (관행상 잎 노트인 폴더는 대상에서 제외 — ORPHAN_SCOPE)
  template    note_rules 위반 (embed·frontmatter·status·앵커·태그)

사용:
  python3 .claude/lib/vault_lint.py                    # 전체, 텍스트 요약
  python3 .claude/lib/vault_lint.py --check deadlink   # 검사 선택 (반복 가능)
  python3 .claude/lib/vault_lint.py --format markdown  # 보고용
  python3 .claude/lib/vault_lint.py --format json      # 기계 소비용
  python3 .claude/lib/vault_lint.py --strict           # 발견 시 exit 1 (자동화용)
"""
import argparse
import json
import os
import pathlib
import re
import sys
import unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import note_rules  # noqa: E402

# 전 검사 제외: 하네스·템플릿·미처리 수집함·불변 보관소
#   90_Archive/는 orphan 57%(972건 중 554)로 신호가 아니라 소음이고, 폴더 규칙상
#   파일 생성이 금지된 보관소라 고칠 대상도 아니다 (2026-08-25 사용자 결정).
GLOBAL_SKIP = ("/.git/", "/.obsidian/", "/.claude/", "/docs/", "/99_Template/",
               "/90_Archive/", "/01_Inbox/", "/tmp/", "/__pycache__/",
               "/_work", "backlog.md", "tasks.md", "AGENTS.md", "CLAUDE.md", "README.md")

# orphan 검사 대상 폴더 — 실측 orphan율 10% 안팎이라 부재가 위반으로 읽히는 갈래만 넣는다.
#   `10_Areas/`(30%)·`14_Changes/`(38%)는 원래 잎 노트라 generic orphan이 다수 오탐이 된다.
#   그 둘은 stale-index(MOC·index 미등록) 검사로 잡는다 — 검사 6, 별도 도입.
ORPHAN_SCOPE = ("_Wiki/", "_Sources/", "12_Projects/", "11_Routines/", "20_Training/")

# orphan 예외: `_Wiki/entities/`는 이름으로 조회하는 인물·조직 사전이라 inbound 링크가
#   없는 게 다수 관행이다 (실측 2026-08-25: people 77건 중 48건 orphan = 62%).
#   기계화하면 다수가 오탐 — `check-template.py`가 과업심의 서식에서 겪은 것과 같은 실패.
ORPHAN_EXCEPT = ("_Wiki/entities/",)

CHECKS = ("deadlink", "ambiguous", "orphan", "template")
# opt-in 검사 — 기본 실행에서 뺀다. 계약(`_Wiki/contracts.md` → Operational MOC 역방향)이
#   요구하지만 실측 누락 271/329(82%)이라 기본에 넣으면 리포트를 덮는다. 백필은 별건.
OPTIONAL_CHECKS = ("moc-backlink",)
ALL_CHECKS = CHECKS + OPTIONAL_CHECKS

MOC_DIR = "_Wiki/topics/"
TAG_RE = re.compile(r'#업무/([^/\s#`]+)')

# 링크 대상에서 떼어낼 것: `|별칭`, `#헤딩`, `^블록`
LINK_RE = re.compile(r'!?\[\[([^\]]+)\]\]')
FENCE_RE = re.compile(r'```.*?```', re.DOTALL)
INLINE_RE = re.compile(r'`[^`\n]*`')


def norm(s):
    return unicodedata.normalize("NFC", str(s).replace("\\", "/"))


def collect(root):
    """볼트 파일 인덱스.

    반환: (lint 대상 노트, 전체 노트, 전체 첨부).
    **해석용 인덱스는 제외 폴더까지 전부 담는다** — `90_Archive/`를 인덱스에서 빼면
    아카이브로 이관된 노트를 가리키는 정상 링크가 전부 deadlink 오탐이 된다
    (실측 2026-08-25: 284건 중 다수). 제외는 "무엇을 검사하는가"에만 적용한다.
    첨부까지 담는 이유는 첨부 링크를 deadlink로 오판하지 않기 위함.
    """
    lint_notes, all_notes, assets = [], [], []
    for r, dirs, files in os.walk(root):
        rel = norm(os.path.relpath(r, root))
        rel = "" if rel == "." else rel + "/"
        # `.trash/`는 Obsidian 휴지통이라 해석 인덱스에서도 뺀다 — 삭제된 사본이 남아
        # 살아 있는 노트와 이름이 겹치면 ambiguous 오탐이 된다.
        if any(s in "/" + rel for s in ("/.git/", "/.obsidian/", "/__pycache__/", "/.trash/")):
            dirs[:] = []
            continue
        for x in files:
            p = norm(rel + x)
            if not x.endswith(".md"):
                assets.append(p)
                continue
            all_notes.append(p)
            if not any(s in "/" + p for s in GLOBAL_SKIP):
                lint_notes.append(p)
    return lint_notes, all_notes, assets


def link_target(raw):
    """`[[폴더/노트#헤딩|별칭]]` → `폴더/노트`. 빈 링크는 None (템플릿 검사 소관)."""
    t = raw.split("|")[0].split("#")[0].split("^")[0].strip()
    return norm(t) or None


def build(root, paths):
    text = {}
    for p in paths:
        try:
            text[p] = (pathlib.Path(root) / p).read_text(encoding="utf-8")
        except Exception:
            text[p] = ""
    return text


def run(root, checks):
    note_paths, all_notes, asset_paths = collect(root)
    text = build(root, note_paths)

    by_stem = defaultdict(list)          # 노트 이름 → 경로들 (Obsidian 최단경로 해석)
    for p in all_notes:
        by_stem[pathlib.PurePosixPath(p).stem].append(p)
    asset_stem = defaultdict(list)
    for p in asset_paths:
        asset_stem[pathlib.PurePosixPath(p).stem].append(p)
        asset_stem[pathlib.PurePosixPath(p).name].append(p)
    note_set = set(all_notes)
    lint_set = set(note_paths)

    findings = []
    inbound = Counter({p: 0 for p in note_paths})
    outbound = defaultdict(set)          # 노트 → 해석된 링크 대상 경로들

    for p in note_paths:
        # 펜스는 **줄 수를 보존한 채** 지운다 — 통째로 지우면 이후 findings의 줄 번호가
        # 원본과 어긋난다 (실측 2026-08-25: 졸업-운영-MOC 보고 줄이 실제 링크 줄과 불일치).
        body = FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text[p])
        lines = body.splitlines()
        for ln, line in enumerate(lines, 1):
            line_nc = INLINE_RE.sub("", line)
            for raw in LINK_RE.findall(line_nc):
                tgt = link_target(raw)
                if not tgt or "{" in tgt:      # 템플릿 플레이스홀더는 링크가 아니다
                    continue
                qualified = "/" in tgt
                # 링크 대상에서는 `.md`만 뗀다. `PurePosixPath.stem`을 쓰면 노트 이름 안의
                # 괄호 확장자(`...불가(hg_3060404_b.xfdl)`)를 접미사로 오인해 잘라내고
                # 멀쩡한 링크가 deadlink로 잡힌다 (실측 2026-08-25).
                stem = (tgt[:-3] if tgt.endswith(".md") else tgt).rsplit("/", 1)[-1]
                # 1) 경로 지정 링크: 그대로 또는 .md 붙여 해석
                hits = [c for c in (tgt, tgt + ".md") if c in note_set]
                # 2) 이름만 있는 링크: 같은 이름의 노트 전부가 후보
                if not hits and not qualified:
                    hits = list(by_stem.get(stem, []))
                # 3) 경로 지정인데 못 찾으면 이름으로도 시도 (폴더 이동된 노트)
                if not hits and qualified:
                    hits = [q for q in by_stem.get(stem, [])]
                if not hits:
                    if asset_stem.get(tgt.rsplit("/", 1)[-1]) or asset_stem.get(stem):
                        continue          # 첨부 링크
                    if "deadlink" in checks:
                        findings.append(dict(check="deadlink", path=p, line=ln,
                                             detail=f"[[{raw.strip()}]] → 대상 없음"))
                    continue
                # 후보가 여럿이어도 lint 범위(= 현행 노트)에 정확히 1건이면 모호하지 않다.
                # Obsidian도 최단경로로 살아 있는 노트를 고르고, 아카이브 사본은 이관의
                # 정상 결과다. 현행 후보가 2건 이상일 때만 실제로 해석이 흔들린다.
                live = [h for h in hits if h in lint_set]
                if len(live) == 1:
                    hits = live
                for h in hits:
                    outbound[p].add(h)
                    if h != p:
                        inbound[h] += 1
                if len(hits) > 1 and not qualified and "ambiguous" in checks:
                    findings.append(dict(check="ambiguous", path=p, line=ln,
                                         detail=f"[[{raw.strip()}]] → {len(hits)}건 후보: "
                                                + ", ".join(sorted(hits)[:3])))

    if "orphan" in checks:
        for p in note_paths:
            if (inbound[p] == 0 and p.startswith(ORPHAN_SCOPE)
                    and not p.startswith(ORPHAN_EXCEPT)):
                findings.append(dict(check="orphan", path=p, line=0,
                                     detail="inbound 링크 0 — 인용·등록되지 않음"))

    if "moc-backlink" in checks:
        # `_Wiki/contracts.md` → Operational MOC 역방향: 도메인 MOC가 **있으면** 노트의
        # `## 관련 문서`에 `- 운영 MOC: [[{도메인}-운영-MOC]]`를 남긴다. MOC가 없으면
        # 추가하지 않는다(깨진 링크 금지) — 그래서 MOC 부재 도메인은 위반이 아니다.
        moc_by_domain = defaultdict(list)
        for q in all_notes:
            # **운영 MOC만** 대상이다. `홈페이지-MOC`·`기타-MOC` 같은 정적 topic MOC는
            # 다른 계약(Topic MOC)이라 업무노트 역링크를 요구하지 않는다.
            if not q.startswith(MOC_DIR) or not q.endswith("-운영-MOC.md"):
                continue
            stem = pathlib.PurePosixPath(q).stem
            moc_by_domain[stem.replace("-운영-MOC", "")].append(q)
        for p in note_paths:
            if not (p.startswith("10_Areas/") or p.startswith("14_Changes/")):
                continue
            fm = re.match(r'^---\s*\n(.*?)\n---', text[p], re.DOTALL)
            if not fm or not re.search(r'^type:\s*\S', fm.group(1), re.MULTILINE):
                continue                  # frontmatter 없는 건 template 검사 소관
            # 도메인: `#업무/` 첫 세그먼트가 1순위, 없으면 `10_Areas/{도메인}/` 폴더명
            tag = TAG_RE.search(text[p])
            dom = tag.group(1) if tag else (p.split("/")[1] if p.startswith("10_Areas/") else None)
            targets = moc_by_domain.get(dom or "", [])
            if not targets:
                continue
            if not (outbound[p] & set(targets)):
                findings.append(dict(check="moc-backlink", path=p, line=0,
                                     detail=f"운영 MOC 역링크 없음 — `## 관련 문서`에 "
                                            f"`[[{pathlib.PurePosixPath(targets[0]).stem}]]` 추가"))

    if "template" in checks:
        # 훅과 같은 규칙, 넓은 범위. `_Wiki/`·`_Sources/`는 note_rules의 NOTE_FOLDERS가
        # 아니므로 embed·빈 wikilink만 걸린다 — 문서 규격 검사는 contracts.md 기반으로 별도.
        lint_skip = tuple(s for s in note_rules.HOOK_SKIP
                          if s not in ("/_Wiki/", "/_Sources/"))
        for p in note_paths:
            for v in note_rules.check(p, text[p], skip=lint_skip):
                findings.append(dict(check="template", path=p, line=0, detail=v))

    findings.sort(key=lambda f: (ALL_CHECKS.index(f["check"]), f["path"], f["line"]))
    return findings, len(note_paths)


def render(findings, total, fmt, checks=CHECKS):
    counts = Counter(f["check"] for f in findings)
    if fmt == "json":
        return json.dumps(dict(notes=total, counts=dict(counts), findings=findings),
                          ensure_ascii=False, indent=1)
    out = []
    head = f"노트 {total}건 검사 · 발견 {len(findings)}건 (" + \
           ", ".join(f"{c} {counts.get(c, 0)}" for c in checks) + ")"
    out.append(f"# vault lint\n\n{head}" if fmt == "markdown" else head)
    for c in checks:
        rows = [f for f in findings if f["check"] == c]
        if not rows:
            continue
        out.append(f"\n## {c} ({len(rows)})" if fmt == "markdown" else f"\n[{c}] {len(rows)}건")
        for f in rows:
            loc = f"{f['path']}:{f['line']}" if f["line"] else f["path"]
            out.append(f"- `{loc}` — {f['detail']}" if fmt == "markdown" else f"  {loc}  {f['detail']}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="볼트 전수 lint (읽기 전용)")
    ap.add_argument("--vault", default=str(pathlib.Path(__file__).resolve().parents[2]))
    ap.add_argument("--check", action="append", choices=ALL_CHECKS,
                    help="검사 선택 (기본: %s · opt-in: %s)" % (", ".join(CHECKS), ", ".join(OPTIONAL_CHECKS)))
    ap.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    ap.add_argument("--strict", action="store_true", help="발견이 있으면 exit 1")
    a = ap.parse_args()
    checks = tuple(a.check) if a.check else CHECKS
    findings, total = run(a.vault, checks)
    sys.stdout.reconfigure(encoding="utf-8")
    print(render(findings, total, a.format, checks))
    sys.exit(1 if (a.strict and findings) else 0)


if __name__ == "__main__":
    main()
