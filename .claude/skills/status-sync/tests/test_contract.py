#!/usr/bin/env python3
"""Contract test: status-sync must parse BOTH legacy plain notes and the new
callout-styled notes from 99_Template/ identically.

Run:  python3 .claude/skills/status-sync/tests/test_contract.py
Exit 0 = contract holds.  Any AssertionError = a parser drifted from a template.

Covers:
  - checkbox counting works with and without a `> ` callout prefix
  - `_result_filled` treats an empty `> [!success]-` callout as NOT filled
  - bucket() classifies empty / in-progress / done-and-filled notes correctly
  - apply.add_todo inserts a `> - [ ]` line when the 할 일 section is a callout
  - every shipped template still carries its required `## ` headings
"""
from __future__ import annotations
import importlib.util
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPTS = HERE.parents[1] / "scripts"
VAULT = HERE.parents[4]
TEMPLATES = VAULT / "99_Template"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclass type resolution needs the module registered
    spec.loader.exec_module(mod)
    return mod


scan = _load("ss_scan", SCRIPTS / "scan.py")
apply = _load("ss_apply", SCRIPTS / "apply.py")

AREAS = next(p for p in scan.PROFILES if p.name == "areas")
CHANGES = next(p for p in scan.PROFILES if p.name == "changes")

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)


def classify_body(body: str, profile=AREAS) -> dict:
    todo = profile.todo.search(body)
    if todo:
        t = todo.group(1)
        open_n = len(scan.OPEN_BOX.findall(t))
        done_n = len(scan.DONE_BOX.findall(t))
    else:
        open_n = done_n = 0
    info = {
        "todo_open": open_n,
        "todo_done": done_n,
        "result_filled": scan._result_filled(profile.result, body),
    }
    info["bucket"] = scan.bucket(info)
    return info


# ── legacy plain format (existing 10_Areas notes) ──────────────────────────
LEGACY_EMPTY = """
## 현황

-

## 할 일

- [ ] 📅 2026-07-01

## 처리 결과

-
"""
LEGACY_DONE = """
## 현황

- 처리 완료

## 할 일

- [x] 반영함

## 처리 결과

- 운영 반영 완료
"""

# ── new callout format (from redesigned templates) ─────────────────────────
NEW_EMPTY = """
## 현황

> [!info]+ 현황
> -

## 할 일

> [!todo]+ 할 일
> - [ ] 📅 2026-07-01

## 처리 결과

> [!success]- 처리 결과
> -
"""
NEW_INPROGRESS = """
## 할 일

> [!todo]+ 할 일
> - [x] 1차 반영
> - [ ] 검증 남음

## 처리 결과

> [!success]- 처리 결과
> -
"""
NEW_DONE = """
## 할 일

> [!todo]+ 할 일
> - [x] 반영함

## 처리 결과

> [!success]- 처리 결과
> - 운영 반영 완료
"""

# legacy still works
li = classify_body(LEGACY_EMPTY)
check(li["todo_open"] == 1 and li["bucket"] == "keep_open", f"legacy empty → {li}")
ld = classify_body(LEGACY_DONE)
check(ld["todo_done"] == 1 and ld["result_filled"] and ld["bucket"] == "auto_close",
      f"legacy done → {ld}")

# new callout format
ne = classify_body(NEW_EMPTY)
check(ne["todo_open"] == 1, f"new empty: open box not counted under callout → {ne}")
check(ne["result_filled"] is False,
      f"new empty: empty success-callout wrongly read as filled → {ne}")
check(ne["bucket"] == "keep_open", f"new empty bucket → {ne}")

ni = classify_body(NEW_INPROGRESS)
check(ni["todo_open"] == 1 and ni["todo_done"] == 1, f"new in-progress counts → {ni}")
check(ni["bucket"] == "keep_open", f"new in-progress bucket → {ni}")

nd = classify_body(NEW_DONE)
check(nd["todo_done"] == 1 and nd["todo_open"] == 0, f"new done counts → {nd}")
check(nd["result_filled"] is True, f"new done: filled callout not detected → {nd}")
check(nd["bucket"] == "auto_close", f"new done bucket → {nd}")

# ── 14_Changes "changes" profile: legacy emoji + new plain, both note kinds ──
# legacy improvement (emoji headings + filled code block ⇒ done)
LEGACY_IMPROVE_DONE = """
## 🏷 Todo

- [x] 반영

## 🛠 주요 코드

```sql
UPDATE t SET x = 1;
```
"""
ci = classify_body(LEGACY_IMPROVE_DONE, CHANGES)
check(ci["todo_done"] == 1 and ci["result_filled"] and ci["bucket"] == "auto_close",
      f"legacy emoji improvement → {ci}")

# legacy incident (할 일 + 처리 방안)
LEGACY_INCIDENT_DONE = """
## 할 일

- [x] 처리

## 처리 방안

- 파라미터 보정 후 재실행
"""
cinc = classify_body(LEGACY_INCIDENT_DONE, CHANGES)
check(cinc["result_filled"] and cinc["bucket"] == "auto_close",
      f"legacy incident (처리 방안) → {cinc}")

# new improvement from current _개선 template (callout sections)
NEW_IMPROVE_EMPTY = """
## 수정 사유

> [!question]+ 수정 사유
> -

## 할 일

> [!todo]+ 할 일
> - [ ] 📅 2026-07-01

## 처리 결과

> [!success]- 처리 결과
> -
"""
cne = classify_body(NEW_IMPROVE_EMPTY, CHANGES)
check(cne["todo_open"] == 1 and not cne["result_filled"]
      and cne["bucket"] == "keep_open", f"new improvement empty → {cne}")

NEW_IMPROVE_DONE = """
## 할 일

> [!todo]+ 할 일
> - [x] 반영

## 처리 결과

> [!success]- 처리 결과
> - 운영 반영 완료
"""
cnd = classify_body(NEW_IMPROVE_DONE, CHANGES)
check(cnd["todo_done"] == 1 and cnd["result_filled"]
      and cnd["bucket"] == "auto_close", f"new improvement done → {cnd}")

# ── apply.add_todo into a callout 할 일 section ─────────────────────────────
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "n.md"
    f.write_text(
        "---\ntype: work\nstatus: open\ndate modified: 2026-01-01 00:00:00\n---\n"
        "# T\n\n## 할 일\n\n> [!todo]+ 할 일\n> - [ ] 기존\n\n## 처리 결과\n\n- \n",
        encoding="utf-8",
    )
    ok, msg = apply.add_todo(f, "신규 작업")
    out = f.read_text(encoding="utf-8")
    check(ok, f"add_todo failed: {msg}")
    check("> - [ ] 신규 작업" in out,
          f"add_todo did not insert callout-prefixed line:\n{out}")
    # new line must stay inside the callout, before the next section
    todo_sec = AREAS.todo.search(out[out.index("# T"):])
    check(todo_sec is not None and "신규 작업" in todo_sec.group(1),
          "new todo escaped the 할 일 section")

# ── every shipped template keeps its required headings ─────────────────────
REQUIRED = {
    "_업무사안.md": ["## 현황", "## 할 일", "## 처리 결과"],
    "_개선.md": ["## 수정 사유", "## 할 일", "## 처리 결과"],
    "_인시던트.md": ["## 발생 정보", "## 프로시저", "## 메뉴 위치",
                   "## 오류 구분", "## 할 일", "## 처리 결과"],
    "_교육.md": ["## 핵심 내용", "## 핵심 정리"],
    "_프로젝트.md": ["## 목표", "## 범위"],
    "_루틴.md": ["## 절차", "## 작업 이력"],
}
for fname, heads in REQUIRED.items():
    p = TEMPLATES / fname
    check(p.exists(), f"missing template {fname}")
    if not p.exists():
        continue
    txt = p.read_text(encoding="utf-8")
    check("![[" not in txt, f"{fname}: forbidden ![[embed]] present")
    fm = re.match(r"^---\s*\n(.*?)\n---", txt, re.DOTALL)
    check(bool(fm), f"{fname}: no frontmatter")
    if fm:
        sm = re.search(r"^status:\s*(\S+)", fm.group(1), re.MULTILINE)
        check(bool(sm) and sm.group(1) in
              {"open", "in-progress", "hold", "closed", "active"},
              f"{fname}: status not enum-valid")
    for h in heads:
        check(re.search(rf"^{re.escape(h)}\s*$", txt, re.MULTILINE) is not None,
              f"{fname}: missing heading {h!r}")

if FAILURES:
    print(f"FAIL ({len(FAILURES)})")
    for x in FAILURES:
        print("  -", x)
    sys.exit(1)
print("OK — status-sync contract holds for legacy + callout templates")
