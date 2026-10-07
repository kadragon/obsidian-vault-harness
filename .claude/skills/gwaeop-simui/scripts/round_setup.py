#!/usr/bin/env python3
"""과업심의 회차 서류 자동화 (과업심의_프로세스 Step 6·7-2·9).

회차 폴더의 `_round.json` 하나로 서류를 만들고 검증한다. 판단이 필요한 일
(심의자료 파일명, 번호 부여, 산정서 대상, 위원 구성, 검토의견)은 하지 않는다.

  generate   서약서·위원별 결과서·위원별 산정서·종합 결과서·종합 산정서 생성 (Step 6)
  verify     생성된 서류를 _round.json 값과 대조 (Step 9) — 생성 코드와 별개 경로로 텍스트를 읽는다
  bundle     위원별 전자서명 통합본 생성 (Step 7-2, 한글·pywin32 필요)
  diff-final 발주부서가 준 최종본 폴더와 심의자료/ 대조 (hwp는 한글로 hwpx 변환 후 텍스트 비교)

예:
  python3 round_setup.py generate "10_Areas/과업심의/202610_제10차과업심의"
  python3 round_setup.py verify   "10_Areas/과업심의/202610_제10차과업심의"
  python3 round_setup.py bundle   "10_Areas/과업심의/202610_제10차과업심의"
  python3 round_setup.py diff-final "…/2026-038/공문원본" "…/2026-038/심의자료"

_round.json 형식은 references/round-config.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import glob
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORMS = HERE.parent / "assets" / "forms"
MERGE = HERE / "merge_sign_bundle.py"
HWPX_GLOBS = [
    os.path.expanduser("~/.claude/plugins/marketplaces/*/prod/skills/hwpx/scripts"),
    os.path.expanduser("~/.claude/plugins/cache/*/prod/*/skills/hwpx/scripts"),
]
PLACEHOLDER_ID = "2147483648"

DOC_PLEDGE = "서약서"
DOC_MEMBER_RESULT = "과업내용 확정 위원별 심의 결과서"
DOC_MEMBER_PERIOD = "소프트웨어 개발사업의 적정 사업기간 위원별 산정서"
DOC_SUMMARY_RESULT = "과업내용 확정 종합 심의 결과서"
DOC_SUMMARY_PERIOD = "소프트웨어 개발사업의 적정 사업기간 종합 산정서"
FORM_OF = {
    DOC_PLEDGE: "pledge", DOC_MEMBER_RESULT: "member-result", DOC_MEMBER_PERIOD: "member-period",
    DOC_SUMMARY_RESULT: "summary-result", DOC_SUMMARY_PERIOD: "summary-period",
}


# ---- config ---------------------------------------------------------------
@dataclass(frozen=True)
class Member:
    name: str
    org: str
    position: str
    consent: bool


@dataclass(frozen=True)
class Project:
    id: str
    title: str
    dept: str
    period: bool


@dataclass(frozen=True)
class Round:
    dir: Path
    number: int
    start: dt.date
    end: dt.date
    chair: str
    members: tuple[Member, ...]
    projects: tuple[Project, ...]


def load_round(round_dir: Path) -> Round:
    cfg_path = round_dir / "_round.json"
    if not cfg_path.is_file():
        sys.exit(f"_round.json 없음: {cfg_path}")
    c = json.loads(cfg_path.read_text(encoding="utf-8"))
    errs = []
    flags = [(f"members[{m['name']}].consent", m.get("consent", False)) for m in c["members"]]
    flags += [(f"projects[{p['id']}].period", p["period"]) for p in c["projects"]]
    errs += [f"{k}는 true/false여야 함: {v!r}" for k, v in flags if not isinstance(v, bool)]
    members = tuple(Member(m["name"], m["org"], m.get("position", ""), m.get("consent", False)) for m in c["members"])
    projects = tuple(Project(p["id"], p["title"], p["dept"], p["period"]) for p in c["projects"])
    r = Round(round_dir, int(c["round"]), dt.date.fromisoformat(c["review_start"]),
              dt.date.fromisoformat(c["review_end"]), c["chair"], members, projects)
    names = [m.name for m in members]
    if len(set(names)) != len(names):
        errs.append("members.name 중복")
    if r.chair not in names:
        errs.append(f"chair '{r.chair}'가 members에 없음")
    if not 1 <= len(members) - 1 <= 5:
        errs.append(f"위원(위원장 제외) {len(members) - 1}명 — 종합 서명란은 1~5명만 지원")
    if r.end < r.start:
        errs.append("review_end < review_start")
    ids = [p.id for p in projects]
    if len(set(ids)) != len(ids):
        errs.append("projects.id 중복")
    for p in projects:
        if not re.fullmatch(r"\d{4}-\d{3}", p.id):
            errs.append(f"projects.id 형식 오류: {p.id}")
    if errs:
        sys.exit("_round.json 오류:\n  " + "\n  ".join(errs))
    return r


# ---- formatting -----------------------------------------------------------
def kdate(d: dt.date) -> str:
    return f"{d.year}년 {d.month}월 {d.day}일"


def krange(a: dt.date, b: dt.date) -> str:
    """심의기간 표기 — 선례 `2026년 6월 19일~22일`."""
    if a == b:
        return kdate(a)
    if a.year != b.year:
        return f"{kdate(a)}~{kdate(b)}"
    if a.month != b.month:
        return f"{kdate(a)}~{b.month}월 {b.day}일"
    return f"{kdate(a)}~{b.day}일"


def spaced(name: str) -> str:
    return " ".join(name)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---- plan: which files a round must contain --------------------------------
@dataclass(frozen=True)
class Doc:
    project: Project
    seq: int
    kind: str
    member: Member | None

    @property
    def filename(self) -> str:
        tail = f"_{self.member.name}" if self.member else ""
        return f"{self.project.id}_{self.seq}_{self.kind}{tail}.hwpx"


def plan(r: Round) -> list[Doc]:
    docs = []
    for p in r.projects:
        for m in r.members:
            docs.append(Doc(p, 1, DOC_PLEDGE, m))
            docs.append(Doc(p, 2, DOC_MEMBER_RESULT, m))
            if p.period:
                docs.append(Doc(p, 3, DOC_MEMBER_PERIOD, m))
        docs.append(Doc(p, 4 if p.period else 3, DOC_SUMMARY_RESULT, None))
        if p.period:
            docs.append(Doc(p, 5, DOC_SUMMARY_PERIOD, None))
    return docs


def values(r: Round, d: Doc) -> dict[str, str]:
    v = {
        "사업명": d.project.title, "발주부서": d.project.dept, "번호": d.project.id,
        "시작일": kdate(r.start), "종료일": kdate(r.end), "심의기간": krange(r.start, r.end),
        "위원장_띄움": spaced(r.chair), "회차": str(r.number),
    }
    if d.member:
        v.update({"성명": d.member.name, "성명_띄움": spaced(d.member.name),
                  "소속": d.member.org, "직위": d.member.position})
    return v


# ---- XML helpers -----------------------------------------------------------
TC_RE = re.compile(r"<hp:tc [^>]*>.*?</hp:tc>", re.S)
SUB_RE = re.compile(r"(<hp:subList[^>]*>)(.*)(</hp:subList>)", re.S)
TOKEN_RE = re.compile(r"\{\{([^}]+)\}\}")


def _tc(s: str, col: int, row: int) -> re.Match:
    hits = [m for m in TC_RE.finditer(s) if f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>' in m.group(0)]
    if len(hits) != 1:
        raise ValueError(f"cell {col},{row}: {len(hits)} hits")
    return hits[0]


def get_inner(s: str, col: int, row: int) -> str:
    inner = SUB_RE.search(_tc(s, col, row).group(0)).group(2)
    return re.sub(r'<hp:p id="\d+"', f'<hp:p id="{PLACEHOLDER_ID}"', inner)


def set_inner(s: str, col: int, row: int, inner: str) -> str:
    m = _tc(s, col, row)
    tc = SUB_RE.sub(lambda mm: mm.group(1) + inner + mm.group(3), m.group(0), count=1)
    return s[: m.start()] + tc + s[m.end():]


def chair_slot(k: int) -> int:
    """위원 k명일 때 위원장 칸 번호. 칸은 2열 행 우선(0=1행 왼쪽, 1=1행 오른쪽 …)이고 위원장은 늘 오른쪽 열."""
    return k if k % 2 == 1 else k + 1


def signature_grid(k: int) -> list[str]:
    """칸 6개의 역할 — 'member' | 'chair' | 'empty'. 위원 1명이면 9차와 같은 `위원|위원장`."""
    cs = chair_slot(k)
    return ["member" if i < k else "chair" if i == cs else "empty" for i in range(6)]


def layout_summary_result(s: str, k: int) -> str:
    """종합 결과서(서식 11~13행, 칸마다 이름표·이름·서명 3셀) — 위에서부터 채운다."""
    left, right = (0, 2, 5), (6, 8, 10)
    proto = {
        "member": [get_inner(s, c, 11) for c in left],
        "chair": [get_inner(s, c, 11) for c in right],
        "empty": {cols: [get_inner(s, c, 13) for c in cols] for cols in (left, right)},
    }
    for i, role in enumerate(signature_grid(k)):
        row, cols = 11 + i // 2, (left if i % 2 == 0 else right)
        cells = proto["empty"][cols] if role == "empty" else proto[role]
        for c, inner in zip(cols, cells):
            s = set_inner(s, c, row, inner)
    return s


def layout_summary_period(s: str, k: int) -> str:
    """종합 산정서(서식 13~15행, 칸마다 셀 1개) — 아래쪽에 붙인다(6차 선례: 서명이 표 맨 아래)."""
    proto = {"member": get_inner(s, 0, 15), "chair": get_inner(s, 2, 15),
             "empty": {0: get_inner(s, 0, 12), 2: get_inner(s, 2, 12)}}
    grid = signature_grid(k)
    rows = chair_slot(k) // 2 + 1
    first = 16 - rows
    for row in range(13, first):
        for c in (0, 2):
            s = set_inner(s, c, row, proto["empty"][c])
    for i in range(rows * 2):
        row, c = first + i // 2, (0 if i % 2 == 0 else 2)
        s = set_inner(s, c, row, proto["empty"][c] if grid[i] == "empty" else proto[grid[i]])
    return s


def fill_tokens(s: str, v: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        if m.group(1) not in v:
            raise KeyError(f"값 없는 토큰: {m.group(0)}")
        return esc(v[m.group(1)])
    s = TOKEN_RE.sub(repl, s)
    return s.replace("<hp:t></hp:t>", "<hp:t/>")


def render(form: str, v: dict[str, str], k: int) -> bytes:
    """서식 hwpx → 값이 채워진 hwpx 바이트. 엔트리 순서·압축 방식은 서식 그대로(mimetype 첫 엔트리·STORED 유지)."""
    src = FORMS / f"{form}.hwpx"
    out = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info)
            if info.filename == "Contents/section0.xml":
                s = data.decode("utf-8")
                if form == "summary-result":
                    s = layout_summary_result(s, k)
                elif form == "summary-period":
                    s = layout_summary_period(s, k)
                s = fill_tokens(s, v)
                s = re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", s, flags=re.S)
                data = s.encode("utf-8")
            zout.writestr(info, data, compress_type=info.compress_type)
    return out.getvalue()


def find_hwpx_scripts() -> Path:
    for pattern in HWPX_GLOBS:
        hits = sorted(glob.glob(pattern))
        if hits:
            return Path(hits[-1])
    sys.exit("prod:hwpx 플러그인 scripts 폴더를 찾지 못함")


def run_py(script: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


# ---- generate ---------------------------------------------------------------
def cmd_generate(a) -> int:
    r = load_round(a.round_dir)
    out_root = a.out or r.dir
    k = len(r.members) - 1
    docs = plan(r)
    targets = [(d, out_root / d.project.id / d.filename) for d in docs]
    existing = [t for _, t in targets if t.exists()]
    if existing and not a.force:
        sys.exit(f"이미 있는 파일 {len(existing)}건 (예: {existing[0].name}) — 덮어쓰려면 --force")
    hx = None if a.no_validate else find_hwpx_scripts()
    fails = 0
    for d, t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_bytes(render(FORM_OF[d.kind], values(r, d), k))
        if hx:
            res = run_py(hx / "validate.py", "validate", t, "--baseline", FORMS / f"{FORM_OF[d.kind]}.hwpx")
            if res.returncode:
                fails += 1
                t.unlink()  # INVALID 파일을 남기면 텍스트 기반 verify가 통과시킨다
                print(f"INVALID {t.name} (삭제)\n{res.stdout}{res.stderr}")
    print(f"generate: {len(targets)}건 → {out_root}" + ("" if hx else " (validate 생략)") + (f", INVALID {fails}건" if fails else ""))
    return 1 if fails else 0


# ---- verify -----------------------------------------------------------------
def doc_texts(path: Path) -> list[str]:
    """section0.xml의 문단별 텍스트 (generate와 독립된 읽기 경로)."""
    with zipfile.ZipFile(path) as z:
        s = z.read("Contents/section0.xml").decode("utf-8")
    paras = re.findall(r"<hp:p [^>]*>(.*?)</hp:p>", s, flags=re.S)
    return [html.unescape("".join(re.findall(r"<hp:t>([^<]*)</hp:t>", p))) for p in paras]


def check_doc(r: Round, d: Doc, texts: list[str]) -> list[str]:
    full = "\n".join(texts)
    stripped = [t.strip() for t in texts]
    errs = []

    def need(label, cond):
        if not cond:
            errs.append(label)

    need("토큰 잔존", "{{" not in full)
    p, m = d.project, d.member
    k = len(r.members) - 1
    if d.kind == DOC_PLEDGE:
        need(f"사업명 ｢{p.title}｣", f"｢{p.title}｣" in full)
        need(f"날짜 {kdate(r.start)}", kdate(r.start) in stripped)
        need(f"소속 {m.org}", m.org in stripped)
        if m.position:
            need(f"직위 {m.position}", m.position in stripped)
        else:
            after = [t for t in stripped[stripped.index("직 위 :") + 1:] if t] if "직 위 :" in stripped else []
            need("직위 공란", bool(after) and after[0] == "성 명 :")
        need(f"성명 {m.name}", m.name in stripped)
    elif d.kind == DOC_MEMBER_RESULT:
        need(f"사업명 {p.title}", p.title in stripped)
        need("제목", f"{p.title} 과업 확정 심의" in stripped)
        need(f"발주부서 {p.dept}", p.dept in stripped)
        need(f"번호 {p.id}", p.id in stripped)
        need(f"심의기간·하단 날짜 {kdate(r.start)} ×2", stripped.count(kdate(r.start)) == 2)
        need("승인 미체크", "[  ] 승인        [  ] 불가        [  ] 조건부 승인" in stripped)
        need(f"성명 {m.name}", m.name in stripped)
    elif d.kind == DOC_MEMBER_PERIOD:
        need(f"사업명 {p.title}", p.title in stripped)
        need(f"날짜 {kdate(r.start)}", kdate(r.start) in stripped)
        need(f"서명란 {spaced(m.name)}", any(t.startswith("위    원") and spaced(m.name) in t for t in stripped))
        need("개월 공란 ×5", stripped.count("개월") == 5)
    elif d.kind == DOC_SUMMARY_RESULT:
        need(f"사업명 {p.title}", p.title in stripped)
        need("제목", f"{p.title} 과업 확정 심의" in stripped)
        need(f"발주부서 {p.dept}", p.dept in stripped)
        need(f"번호 {p.id}", p.id in stripped)
        need(f"심의기간 {krange(r.start, r.end)}", krange(r.start, r.end) in stripped)
        # 당일 심의면 심의기간 문단도 kdate(r.end)라 개수로 하단 날짜를 따로 확인
        need(f"하단 날짜 {kdate(r.end)}", stripped.count(kdate(r.end)) == (2 if r.start == r.end else 1))
        need("승인 미체크", "[  ] 승인        [  ] 불가        [  ] 조건부 승인" in stripped)
        i = stripped.index("[검토의견]") + 1 if "[검토의견]" in stripped else len(stripped)
        need("검토의견 공란", i < len(stripped) and stripped[i] == "")
        need(f"위원 서명란 {k}칸", stripped.count("위       원") == k)
        need("위원장 서명란 1칸", stripped.count("위   원   장") == 1)
        need(f"위원장 {spaced(r.chair)}", spaced(r.chair) in stripped)
    elif d.kind == DOC_SUMMARY_PERIOD:
        need(f"사업명 {p.title}", p.title in stripped)
        need(f"날짜 {kdate(r.end)}", kdate(r.end) in stripped)
        need("개월 공란 ×5", stripped.count("개월") == 5)
        need(f"위원 서명란 {k}칸", sum(t.startswith("위원 ") and t.endswith("(서명)") and not t.startswith("위원장") for t in stripped) == k)
        need(f"위원장 {spaced(r.chair)}", any(t.startswith("위원장") and spaced(r.chair) in t for t in stripped))
    return errs


def cmd_verify(a) -> int:
    r = load_round(a.round_dir)
    root = a.out or r.dir
    docs = plan(r)
    expected = {(d.project.id, d.filename) for d in docs}
    problems = []
    for d in docs:
        f = root / d.project.id / d.filename
        if not f.exists():
            problems.append(f"MISSING {d.project.id}/{d.filename}")
            continue
        for e in check_doc(r, d, doc_texts(f)):
            problems.append(f"FAIL {d.project.id}/{d.filename}: {e}")
    pat = re.compile(r"^\d{4}-\d{3}_\d_.+\.hwpx$")
    for p in r.projects:
        pdir = root / p.id
        if pdir.is_dir():
            for f in sorted(pdir.iterdir()):
                if pat.match(f.name) and (p.id, f.name) not in expected:
                    problems.append(f"EXTRA {p.id}/{f.name}")
    for line in problems:
        print(line)
    print(f"verify: {len(docs)}건 대조, 문제 {len(problems)}건")
    return 1 if problems else 0


# ---- bundle -----------------------------------------------------------------
def bundle_parts(r: Round, m: Member) -> list[Doc]:
    return [d for d in plan(r) if d.member == m]


def cmd_bundle(a) -> int:
    r = load_round(a.round_dir)
    who = [m for m in r.members if not a.member or m.name in a.member]
    unknown = set(a.member or ()) - {m.name for m in r.members}
    if unknown:
        sys.exit(f"members에 없는 이름: {unknown}")
    rc = 0
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        for m in who:
            parts: list[Path] = []
            if m.consent:
                c = Path(td) / f"consent_{m.name}.hwpx"
                c.write_bytes(render("consent", {"회차": str(r.number), "시작일": kdate(r.start), "성명_띄움": spaced(m.name)}, 0))
                parts.append(c)
            parts += [(a.src or r.dir) / d.project.id / d.filename for d in bundle_parts(r, m)]
            missing = [p for p in parts if not p.exists()]
            if missing:
                sys.exit(f"{m.name}: 없는 파일 {missing[0]} — generate 먼저")
            out = (a.out or r.dir) / f"{r.dir.name}_{m.name}.hwpx"
            args = ["-o", out, "--expect-pages", len(parts)]
            if a.pdf_dir:
                a.pdf_dir.mkdir(parents=True, exist_ok=True)
                args += ["--pdf", a.pdf_dir / f"{m.name}.pdf"]
            res = run_py(MERGE, *args, *parts)
            ok = res.returncode == 0
            rc |= 0 if ok else 1
            print(f"{'OK  ' if ok else 'FAIL'} {out.name} ({len(parts)}쪽{', 동의서 포함' if m.consent else ''})")
            if not ok:
                print(res.stdout[-2000:], res.stderr[-2000:])
    return rc


# ---- diff-final --------------------------------------------------------------
def _zip_name(info: zipfile.ZipInfo) -> str:
    n = info.filename
    if not info.flag_bits & 0x800:
        try:
            n = n.encode("cp437").decode("cp949")
        except UnicodeError:
            pass
    return Path(n).name


def expand(src: Path, work: Path) -> list[Path]:
    """폴더 → 비교 대상 파일 목록. zip은 풀고, .hwp는 한글로 .hwpx 변환(사본에서). 메일(.htm/.html)은 제외."""
    work.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(src.iterdir()):
        if f.is_dir() or f.suffix.lower() in (".htm", ".html"):
            continue
        if f.suffix.lower() == ".zip":
            with zipfile.ZipFile(f) as z:
                for i, info in enumerate(z.infolist(), 1):
                    if not info.is_dir():
                        t = work / f"{f.stem}_{i:02d}_{_zip_name(info)}"
                        t.write_bytes(z.read(info))
                        files.append(t)
            continue
        t = work / f.name
        shutil.copy2(f, t)
        files.append(t)
    out = []
    for f in files:
        if f.suffix.lower() == ".hwp":
            # 별도 폴더에서 변환 — 같은 이름 .hwpx가 옆에 있으면 convert_hwp.ps1이 덮어쓰기를 거부한다
            iso = work / "_hwp" / f.name
            iso.parent.mkdir(exist_ok=True)
            f.replace(iso)
            conv = find_hwpx_scripts() / "convert_hwp.ps1"
            res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(conv), "-Path", str(iso)],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            h = iso.with_suffix(".hwpx")
            if res.returncode or not h.exists():
                sys.exit(f"hwp 변환 실패: {f.name}\n{res.stderr}")
            out.append(h)
        else:
            out.append(f)
    return out


def comparable_text(f: Path) -> list[str] | None:
    """비교용 줄 목록. 추출 실패·빈 추출은 None — 빈 목록끼리 SAME(text)로 판정되지 않게."""
    s = f.suffix.lower()
    lines: list[str] = []
    if s == ".hwpx":
        res = run_py(find_hwpx_scripts() / "text.py", "extract", f, "--include-tables")
        if res.returncode:
            return None
        lines = [l.rstrip() for l in res.stdout.splitlines() if l.strip()]
    elif s == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return None
        d = f.read_bytes()
        start, end = d.find(b"%PDF"), d.rfind(b"%%EOF")
        if start != -1 and end != -1:
            d = d[start: end + 5]  # 핸디소프트 결재 컨테이너 대응
        try:
            lines = [l for pg in PdfReader(io.BytesIO(d)).pages for l in (pg.extract_text() or "").splitlines() if l.strip()]
        except Exception:  # 손상·암호화 PDF — 바이트 비교만
            return None
    return lines or None


def sha(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


def cmd_diff_final(a) -> int:
    with tempfile.TemporaryDirectory() as td:
        fin = expand(a.final_dir, Path(td) / "final")
        cur = expand(a.current_dir, Path(td) / "current")
        ftext = {f: comparable_text(f) for f in fin}
        ctext = {c: comparable_text(c) for c in cur}
        unmatched_c = list(cur)
        changed = []
        report = []
        for f in fin:
            hit = next((c for c in unmatched_c if sha(c) == sha(f)), None)
            kind = "SAME(bytes)"
            if not hit and ftext[f] is not None:
                hit = next((c for c in unmatched_c if c.suffix.lower() == f.suffix.lower() and ctext[c] == ftext[f]), None)
                kind = "SAME(text)"
            if hit:
                unmatched_c.remove(hit)
                report.append(f"{kind:12} {f.name}  =  {hit.name}")
            else:
                changed.append(f)
        for f in changed:  # 내용이 바뀐 파일 — 가장 비슷한 현재 파일과 짝지어 diff
            cands = [c for c in unmatched_c if c.suffix.lower() == f.suffix.lower() and ctext[c] is not None and ftext[f] is not None]
            best = max(cands, key=lambda c: difflib.SequenceMatcher(None, ctext[c], ftext[f]).ratio(), default=None)
            if best and difflib.SequenceMatcher(None, ctext[best], ftext[f]).ratio() >= 0.5:
                unmatched_c.remove(best)
                report.append(f"{'CHANGED':12} {f.name}  ≠  {best.name}")
                diff = difflib.unified_diff(ctext[best], ftext[f], "현재", "최종", n=0, lineterm="")
                report += ["    " + (l if len(l) <= 300 else l[:300] + " …") for l in diff][: a.max_lines]
            else:
                report.append(f"{'ONLY-FINAL':12} {f.name}")
        report += [f"{'ONLY-CURRENT':12} {c.name}" for c in unmatched_c]
    print("\n".join(report))
    n_bad = sum(1 for l in report if l.split()[0] in ("CHANGED", "ONLY-FINAL", "ONLY-CURRENT"))
    print(f"diff-final: 최종 {len(fin)}건 · 현재 {len(cur)}건 · 불일치 {n_bad}건")
    return 1 if n_bad else 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="회차 서류 생성")
    g.add_argument("round_dir", type=Path)
    g.add_argument("--out", type=Path, help="다른 폴더에 생성 (기본: round_dir — 회귀 확인용)")
    g.add_argument("--force", action="store_true", help="이미 있는 파일 덮어쓰기")
    g.add_argument("--no-validate", action="store_true", help="validate.py 호출 생략")
    v = sub.add_parser("verify", help="생성 서류를 _round.json과 대조")
    v.add_argument("round_dir", type=Path)
    v.add_argument("--out", type=Path, help="generate --out으로 만든 폴더를 검증")
    b = sub.add_parser("bundle", help="위원별 전자서명 통합본 (한글 필요)")
    b.add_argument("round_dir", type=Path)
    b.add_argument("--member", action="append", help="이 위원만 (반복 가능)")
    b.add_argument("--out", type=Path, help="통합본 저장 폴더 (기본: round_dir)")
    b.add_argument("--src", type=Path, help="generate --out으로 만든 폴더에서 서류를 읽음 (기본: round_dir)")
    b.add_argument("--pdf-dir", type=Path, help="쪽 순서 확인용 PDF 저장 폴더")
    f = sub.add_parser("diff-final", help="최종본 폴더 ↔ 심의자료 대조 (hwp 변환에 한글 필요)")
    f.add_argument("final_dir", type=Path)
    f.add_argument("current_dir", type=Path)
    f.add_argument("--max-lines", type=int, default=60, help="파일당 diff 최대 줄 수")
    a = ap.parse_args(argv)
    return {"generate": cmd_generate, "verify": cmd_verify, "bundle": cmd_bundle, "diff-final": cmd_diff_final}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
