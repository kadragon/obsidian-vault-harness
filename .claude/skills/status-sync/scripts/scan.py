#!/usr/bin/env python3
"""Scan 10_Areas and 14_Changes for notes with frontmatter `status: open`
and classify completion.

The two folders use different templates:

  10_Areas  — 업무사안/개선 노트
              todo:    ## 할 일
              context: ## 현황
              result:  ## 처리 결과

  14_Changes — improvement/incident 기록
              todo:    ## 🏷 Todo
              context: ## 📡 수정 사유
              result:  ## 🛠 주요 코드    (code block filled ⇒ work done)

Default stdout (compact JSON, token-lean for the orchestrator):
{
  "auto_close": [ {path} ],
  "review":     [ {path, result_filled} ],
  "keep_open_count": N,
  "review_bundle": ".claude/.cache/status-sync-review.jsonl" | null
}

When the `review` bucket is non-empty, scan.py also writes a JSONL bundle
with context and todo excerpts for each review note, so the
status-judge sub-agent can judge the whole batch in one call without
Read-ing the source notes itself.

Flags:
  --full   include every field on every note (debug only; not token-lean)
"""
from __future__ import annotations
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

VAULT = Path(__file__).resolve().parents[4]

FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
STATUS_RE = re.compile(r"^status:\s*open\s*$", re.MULTILINE)
OPEN_BOX = re.compile(r"^\s*-\s*\[\s\]", re.MULTILINE)
DONE_BOX = re.compile(r"^\s*-\s*\[x\]", re.MULTILINE | re.IGNORECASE)

EXCERPT_CHARS = 800


def _section_re(heading: str) -> re.Pattern:
    # Match a level-2 heading whose trimmed text equals `heading` (ignoring
    # surrounding whitespace/emoji spacing), and capture until the next `## `
    # or EOF.
    esc = re.escape(heading).replace(r"\ ", r"\s+")
    return re.compile(
        rf"^##\s*{esc}\s*$(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )


@dataclass(frozen=True)
class Profile:
    name: str           # label in output (not used by orchestrator)
    root: Path          # folder to scan
    todo: re.Pattern    # todo section
    context: re.Pattern # context excerpt for judge (현황 / 수정 사유)
    result: re.Pattern  # result section (처리 결과 / 주요 코드)


PROFILES: list[Profile] = [
    Profile(
        name="areas",
        root=VAULT / "10_Areas",
        todo=_section_re("할 일"),
        context=_section_re("현황"),
        result=_section_re("처리 결과"),
    ),
    Profile(
        name="changes",
        root=VAULT / "14_Changes",
        todo=_section_re("🏷 Todo"),
        context=_section_re("📡 수정 사유"),
        result=_section_re("🛠 주요 코드"),
    ),
]


def _excerpt(section_re: re.Pattern, body: str) -> str:
    m = section_re.search(body)
    if not m:
        return ""
    text = m.group(1).strip()
    if len(text) > EXCERPT_CHARS:
        text = text[:EXCERPT_CHARS].rstrip() + " …"
    return text


def _result_filled(section_re: re.Pattern, body: str) -> bool:
    m = section_re.search(body)
    if not m:
        return False
    text = m.group(1)
    # Strip fenced code blocks of *only* whitespace; keep blocks with any
    # non-whitespace content. For 14_Changes "주요 코드", a filled fenced
    # block is the main signal that the work was done.
    meaningful: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s == "-":
            continue
        # Skip bare fence delimiters but count language-tagged ones as
        # signal only if other lines exist — they do, since the fenced
        # body lines also arrive here.
        if re.fullmatch(r"`{3,}[\w+-]*", s):
            continue
        meaningful.append(s)
    return bool(meaningful)


def classify(path: Path, profile: Profile) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = FM_RE.match(text)
    if not m or not STATUS_RE.search(m.group(1)):
        return None

    body = text[m.end():]
    todo_block = profile.todo.search(body)

    if todo_block:
        todo_text = todo_block.group(1)
        open_n = len(OPEN_BOX.findall(todo_text))
        done_n = len(DONE_BOX.findall(todo_text))
    else:
        open_n = done_n = 0

    return {
        "path": str(path.relative_to(VAULT)),
        "profile": profile.name,
        "todo_open": open_n,
        "todo_done": done_n,
        "result_filled": _result_filled(profile.result, body),
        "status_excerpt": _excerpt(profile.context, body),
        "todo_excerpt": _excerpt(profile.todo, body),
    }


def bucket(info: dict) -> str:
    if info["todo_open"] > 0:
        return "keep_open"
    all_done = info["todo_done"] > 0 and info["todo_open"] == 0
    if all_done and info["result_filled"]:
        return "auto_close"
    if all_done or info["result_filled"]:
        return "review"
    return "keep_open"


BUNDLE_PATH = VAULT / ".claude" / ".cache" / "status-sync-review.jsonl"


def main() -> int:
    full = "--full" in sys.argv[1:]
    out = {"auto_close": [], "review": [], "keep_open": []}
    for profile in PROFILES:
        if not profile.root.exists():
            continue
        for path in sorted(profile.root.rglob("*.md")):
            info = classify(path, profile)
            if info is None:
                continue
            out[bucket(info)].append(info)

    bundle_rel = None
    if out["review"]:
        BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with BUNDLE_PATH.open("w", encoding="utf-8") as f:
            for x in out["review"]:
                f.write(json.dumps({
                    "path": x["path"],
                    "profile": x["profile"],
                    "status_excerpt": x["status_excerpt"],
                    "todo_excerpt": x["todo_excerpt"],
                }, ensure_ascii=False) + "\n")
        bundle_rel = str(BUNDLE_PATH.relative_to(VAULT))
    elif BUNDLE_PATH.exists():
        BUNDLE_PATH.unlink()

    if not full:
        compact = {
            "auto_close": [{"path": x["path"]} for x in out["auto_close"]],
            "review": [
                {"path": x["path"], "result_filled": x["result_filled"]}
                for x in out["review"]
            ],
            "keep_open_count": len(out["keep_open"]),
            "review_bundle": bundle_rel,
        }
        json.dump(compact, sys.stdout, ensure_ascii=False, indent=2)
    else:
        full_out = {**out, "review_bundle": bundle_rel}
        json.dump(full_out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
