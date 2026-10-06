#!/usr/bin/env python3
"""Regression tests for round_setup.py — generate/verify without Hancom COM.

Run directly: ``python3 .claude/skills/gwaeop-simui/tests/test_round_setup.py`` must exit 0.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPT = HERE.parent.parent / "scripts" / "round_setup.py"
spec = importlib.util.spec_from_file_location("round_setup", SCRIPT)
assert spec and spec.loader
rs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rs
spec.loader.exec_module(rs)

MEMBERS5 = [
    {"name": "김승현", "org": "정보전산원", "position": "정보전산원장"},
    {"name": "김승연", "org": "컴퓨터교육과", "position": "교수"},
    {"name": "김경미", "org": "충청북도교육청", "position": "과장", "consent": True},
    {"name": "김영우", "org": "충북대학교", "position": "정보화과장"},
    {"name": "정승원", "org": "교육부", "position": "", "consent": True},
]
PROJECTS = [
    {"id": "2026-035", "title": "수업 데이터 기반 플랫폼 구축 용역", "dept": "융합교육연구소", "period": True},
    {"id": "2026-036", "title": "AI 활용 <교과> 콘텐츠 개발 & 보급", "dept": "산학협력단", "period": False},
]


def write_round(d: Path, members=MEMBERS5, projects=PROJECTS, start="2026-10-08", end="2026-10-12", chair="김승현") -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "_round.json").write_text(json.dumps({
        "round": 10, "review_start": start, "review_end": end, "chair": chair,
        "members": members, "projects": projects}, ensure_ascii=False), encoding="utf-8")
    return d


def quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        rc = fn(*a)
    return rc, buf.getvalue()


class FormatTests(unittest.TestCase):
    def test_krange(self):
        d = dt.date
        self.assertEqual(rs.krange(d(2026, 6, 19), d(2026, 6, 22)), "2026년 6월 19일~22일")
        self.assertEqual(rs.krange(d(2026, 7, 7), d(2026, 7, 7)), "2026년 7월 7일")
        self.assertEqual(rs.krange(d(2026, 10, 30), d(2026, 11, 2)), "2026년 10월 30일~11월 2일")
        self.assertEqual(rs.krange(d(2026, 12, 30), d(2027, 1, 4)), "2026년 12월 30일~2027년 1월 4일")

    def test_spaced(self):
        self.assertEqual(rs.spaced("김승현"), "김 승 현")


class SignatureGridTests(unittest.TestCase):
    def test_one_member_matches_9th_round(self):
        self.assertEqual(rs.signature_grid(1)[:2], ["member", "chair"])

    def test_four_members_chair_bottom_right(self):
        self.assertEqual(rs.signature_grid(4), ["member"] * 4 + ["empty", "chair"])

    def test_every_size_has_k_members_and_one_chair_in_right_column(self):
        for k in range(1, 6):
            g = rs.signature_grid(k)
            self.assertEqual(g.count("member"), k)
            self.assertEqual(g.count("chair"), 1)
            self.assertEqual(g.index("chair") % 2, 1, k)


class PlanTests(unittest.TestCase):
    def test_counts_and_numbering(self):
        with tempfile.TemporaryDirectory() as td:
            r = rs.load_round(write_round(Path(td) / "r"))
            names = [d.filename for d in rs.plan(r)]
            # period: 5인 × 3 + 종합 2 = 17 / non-period: 5인 × 2 + 종합 1 = 11
            self.assertEqual(len(names), 28)
            self.assertIn("2026-035_4_과업내용 확정 종합 심의 결과서.hwpx", names)
            self.assertIn("2026-035_5_소프트웨어 개발사업의 적정 사업기간 종합 산정서.hwpx", names)
            self.assertIn("2026-036_3_과업내용 확정 종합 심의 결과서.hwpx", names)
            self.assertIn("2026-036_1_서약서_정승원.hwpx", names)

    def test_config_errors_exit(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit):
                rs.load_round(write_round(Path(td) / "a", chair="없는사람"))
            with self.assertRaises(SystemExit):
                rs.load_round(write_round(Path(td) / "b", start="2026-10-12", end="2026-10-08"))
            with self.assertRaises(SystemExit):
                rs.load_round(write_round(Path(td) / "c", members=MEMBERS5[:1]))


class GenerateVerifyTests(unittest.TestCase):
    def run_round(self, members):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        rd = write_round(Path(td.name) / "202610_제10차과업심의", members=members)
        rc, out = quiet(rs.main, ["generate", str(rd), "--no-validate"])
        self.assertEqual(rc, 0, out)
        return rd

    def test_five_member_round_verifies_clean(self):
        rd = self.run_round(MEMBERS5)
        rc, out = quiet(rs.main, ["verify", str(rd)])
        self.assertEqual(rc, 0, out)

    def test_two_member_round_verifies_clean(self):
        rd = self.run_round(MEMBERS5[:2])
        rc, out = quiet(rs.main, ["verify", str(rd)])
        self.assertEqual(rc, 0, out)

    def test_xml_special_chars_escaped(self):
        rd = self.run_round(MEMBERS5)
        f = rd / "2026-036" / "2026-036_3_과업내용 확정 종합 심의 결과서.hwpx"
        xml = zipfile.ZipFile(f).read("Contents/section0.xml").decode()
        self.assertIn("AI 활용 &lt;교과&gt; 콘텐츠 개발 &amp; 보급", xml)

    def test_summary_has_all_member_signature_slots(self):
        rd = self.run_round(MEMBERS5)
        texts = [t.strip() for t in rs.doc_texts(rd / "2026-035" / "2026-035_4_과업내용 확정 종합 심의 결과서.hwpx")]
        self.assertEqual(texts.count("위       원"), 4)
        self.assertEqual(texts.count("위   원   장"), 1)
        texts = [t.strip() for t in rs.doc_texts(rd / "2026-035" / "2026-035_5_소프트웨어 개발사업의 적정 사업기간 종합 산정서.hwpx")]
        self.assertEqual(sum(t.startswith("위원 ") and t.endswith("(서명)") for t in texts), 4)

    def test_existing_files_refused_without_force(self):
        rd = self.run_round(MEMBERS5)
        with self.assertRaises(SystemExit):
            quiet(rs.main, ["generate", str(rd), "--no-validate"])
        rc, _ = quiet(rs.main, ["generate", str(rd), "--no-validate", "--force"])
        self.assertEqual(rc, 0)

    def test_verify_catches_wrong_value_missing_and_extra(self):
        rd = self.run_round(MEMBERS5)
        f = rd / "2026-035" / "2026-035_1_서약서_김경미.hwpx"
        with zipfile.ZipFile(f) as z:
            entries = [(i, z.read(i)) for i in z.infolist()]
        with zipfile.ZipFile(f, "w") as z:
            for i, data in entries:
                if i.filename == "Contents/section0.xml":
                    data = data.decode().replace("충청북도교육청", "다른기관").encode()
                z.writestr(i, data, compress_type=i.compress_type)
        (rd / "2026-035" / "2026-035_2_과업내용 확정 위원별 심의 결과서_김영우.hwpx").unlink()
        (rd / "2026-035" / "2026-035_1_서약서_윤인자.hwpx").write_bytes(b"")
        rc, out = quiet(rs.main, ["verify", str(rd)])
        self.assertEqual(rc, 1)
        self.assertIn("FAIL 2026-035/2026-035_1_서약서_김경미.hwpx: 소속 충청북도교육청", out)
        self.assertIn("MISSING 2026-035/2026-035_2_과업내용 확정 위원별 심의 결과서_김영우.hwpx", out)
        self.assertIn("EXTRA 2026-035/2026-035_1_서약서_윤인자.hwpx", out)

    def test_blank_position_renders_empty(self):
        rd = self.run_round(MEMBERS5)
        xml = zipfile.ZipFile(rd / "2026-035" / "2026-035_1_서약서_정승원.hwpx").read("Contents/section0.xml").decode()
        self.assertNotIn("<hp:t></hp:t>", xml)
        self.assertNotIn("{{", xml)

    def test_mimetype_first_and_stored(self):
        rd = self.run_round(MEMBERS5[:2])
        with zipfile.ZipFile(rd / "2026-036" / "2026-036_1_서약서_김승현.hwpx") as z:
            first = z.infolist()[0]
        self.assertEqual(first.filename, "mimetype")
        self.assertEqual(first.compress_type, zipfile.ZIP_STORED)


if __name__ == "__main__":
    unittest.main()
