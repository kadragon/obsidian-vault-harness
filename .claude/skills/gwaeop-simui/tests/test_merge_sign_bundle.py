#!/usr/bin/env python3
"""Regression tests for merge_sign_bundle.py (pure functions only — no Hancom COM).

Run directly: ``python3 .claude/skills/gwaeop-simui/tests/test_merge_sign_bundle.py`` must exit 0.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPT = HERE.parent.parent / "scripts" / "merge_sign_bundle.py"
spec = importlib.util.spec_from_file_location("merge_sign_bundle", SCRIPT)
assert spec and spec.loader
msb = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = msb
spec.loader.exec_module(msb)


def p(pid: str, text: str = "") -> str:
    return f'<hp:p id="{pid}" paraPrIDRef="0"><hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run></hp:p>'


def ids(sections: list[str]) -> list[str]:
    return [m for s in sections for m in re.findall(r'<hp:p id="(\d+)"', s)]


class DedupeTests(unittest.TestCase):
    def test_cross_section_duplicate_renumbered(self):
        # 같은 서식 2건을 합친 모양: 033·034 결과서가 같은 id를 가진다
        secs = [p("3121190098") + p("5"), p("3121190098") + p("5")]
        out, n = msb.dedupe_para_ids(secs)
        self.assertEqual(n, 2)
        got = ids(out)
        self.assertEqual(len(got), len(set(got)))
        self.assertEqual(got[:2], ["3121190098", "5"])  # 첫 등장은 유지

    def test_placeholder_id_left_alone(self):
        secs = [p(msb.PLACEHOLDER_ID) + p(msb.PLACEHOLDER_ID), p(msb.PLACEHOLDER_ID)]
        out, n = msb.dedupe_para_ids(secs)
        self.assertEqual(n, 0)
        self.assertEqual(out, secs)

    def test_new_ids_avoid_existing(self):
        secs = [p("1") + p("1") + p("2")]
        out, _ = msb.dedupe_para_ids(secs)
        self.assertEqual(ids(out), ["1", "3", "2"])

    def test_no_duplicates_is_noop(self):
        secs = [p("1") + p("2"), p("3")]
        out, n = msb.dedupe_para_ids(secs)
        self.assertEqual((out, n), (secs, 0))


class ReplaceTests(unittest.TestCase):
    def test_substring_inside_text_node(self):
        secs = [p("1", "본인은 2026년도 제8회 한국교원대학교"), p("2", "하 진 석")]
        out = msb.apply_replacements(secs, [("제8회", "제9회"), ("하 진 석", "윤 인 자")])
        self.assertIn("<hp:t>본인은 2026년도 제9회 한국교원대학교</hp:t>", out[0])
        self.assertIn("<hp:t>윤 인 자</hp:t>", out[1])

    def test_missing_or_ambiguous_exits(self):
        secs = [p("1", "2026년 8월 21일"), p("2", "2026년 8월 21일")]
        with self.assertRaises(SystemExit):
            msb.apply_replacements(secs, [("2026년 8월 21일", "x")])  # 2회
        with self.assertRaises(SystemExit):
            msb.apply_replacements(secs, [("없는 값", "x")])  # 0회

    def test_attribute_text_not_touched(self):
        secs = ['<hp:p id="8"><hp:run><hp:t>8</hp:t></hp:run></hp:p>']
        out = msb.apply_replacements(secs, [("8", "9")])
        self.assertEqual(out[0], '<hp:p id="8"><hp:run><hp:t>9</hp:t></hp:run></hp:p>')


if __name__ == "__main__":
    unittest.main()
