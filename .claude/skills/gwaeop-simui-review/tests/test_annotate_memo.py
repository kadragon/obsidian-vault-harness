#!/usr/bin/env python3
"""Regression tests for annotate_memo.py.

Run directly: ``python3 .claude/skills/gwaeop-simui-review/tests/test_annotate_memo.py`` must exit 0.
Fixtures are synthetic minimal OWPML; Hancom load is checked separately with verify_hancom.ps1.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPT = HERE.parent.parent / "scripts" / "annotate_memo.py"
spec = importlib.util.spec_from_file_location("annotate_memo", SCRIPT)
assert spec and spec.loader
am = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = am
spec.loader.exec_module(am)

HEADER = ('<hh:head><hh:refList><hh:styles itemCnt="1">'
          '<hh:style id="13" type="PARA" name="메모" engName="Memo" paraPrIDRef="0" charPrIDRef="4" '
          'nextStyleIDRef="13" langID="1042" lockForm="0"/></hh:styles></hh:refList></hh:head>')


def para(runs: str, segs: list[int]) -> str:
    lines = ''.join(f'<hp:lineseg textpos="{t}" vertpos="0"/>' for t in segs)
    return f'<hp:p id="0" paraPrIDRef="0" styleIDRef="0">{runs}<hp:linesegarray>{lines}</hp:linesegarray></hp:p>'


def section(*paras: str) -> str:
    return ('<hs:sec><hp:p id="0"><hp:run><hp:secPr memoShapeIDRef="0"/></hp:run>'
            '<hp:linesegarray><hp:lineseg textpos="0"/></hp:linesegarray></hp:p>' + ''.join(paras) + '</hs:sec>')


def textpos_after(xml: str, anchor: str) -> list[int]:
    i = xml.find(anchor)
    return [int(x) for x in re.findall(r'textpos="(\d+)"', xml[i:xml.find('</hp:p>', i)])]


class AnnotateMemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def build(self, sec: str, header: str = HEADER) -> Path:
        src = self.tmp / "src.hwpx"
        with zipfile.ZipFile(src, 'w') as z:
            z.writestr('mimetype', 'application/hwp+zip', compress_type=zipfile.ZIP_STORED)
            z.writestr('Contents/header.xml', header)
            z.writestr('Contents/section0.xml', sec)
        return src

    def run_cli(self, src: Path, memos: list[dict], out_name: str = "out.hwpx") -> tuple[int, Path]:
        mf = self.tmp / "memos.json"
        mf.write_text(json.dumps(memos, ensure_ascii=False), encoding='utf-8')
        out = self.tmp / out_name
        return am.main([str(src), str(out), str(mf)]), out

    def read(self, out: Path, name: str = 'Contents/section0.xml') -> str:
        return zipfile.ZipFile(out).read(name).decode('utf-8')

    def test_wraps_anchor_with_memo_field_and_body(self) -> None:
        src = self.build(section(para('<hp:run><hp:t> 보안관리: 수행자는</hp:t></hp:run>', [0])))
        rc, out = self.run_cli(src, [{"anchor": "보안관리", "text": "확인 1\n근거 & <지침>"}])
        self.assertEqual(rc, 0)
        xml = self.read(out)
        self.assertRegex(xml, r'<hp:t> </hp:t><hp:ctrl><hp:fieldBegin [^>]*type="MEMO".*?</hp:ctrl>'
                              r'<hp:t>보안관리</hp:t><hp:ctrl><hp:fieldEnd [^>]*/></hp:ctrl><hp:t>: 수행자는</hp:t>')
        self.assertIn('<hp:t>확인 1</hp:t>', xml)
        self.assertIn('<hp:t>근거 &amp; &lt;지침&gt;</hp:t>', xml)  # escaped, one paragraph per line
        self.assertIn('styleIDRef="13"', xml)  # document's own 메모 style
        begin = re.search(r'fieldBegin id="(\d+)"', xml)
        assert begin
        self.assertIn(f'beginIDRef="{begin.group(1)}"', xml)

    def test_adds_memo_properties_and_links_secpr(self) -> None:
        src = self.build(section(para('<hp:run><hp:t>보안관리</hp:t></hp:run>', [0])))
        _, out = self.run_cli(src, [{"anchor": "보안관리", "text": "x"}])
        self.assertIn('<hh:memoPr id="1"', self.read(out, 'Contents/header.xml'))
        self.assertIn('memoShapeIDRef="1"', self.read(out))

    def test_reuses_existing_memo_properties(self) -> None:
        header = HEADER.replace('</hh:refList>', '<hh:memoProperties itemCnt="1"><hh:memoPr id="3" width="1"/>'
                                                 '</hh:memoProperties></hh:refList>')
        src = self.build(section(para('<hp:run><hp:t>보안관리</hp:t></hp:run>', [0])), header)
        _, out = self.run_cli(src, [{"anchor": "보안관리", "text": "x"}])
        self.assertEqual(self.read(out, 'Contents/header.xml').count('<hh:memoPr '), 1)
        self.assertIn('memoShapeIDRef="3"', self.read(out))

    def test_shifts_later_lines_by_8_per_control(self) -> None:
        # anchor spans chars 21..29; second line starts at 27 -> only fieldBegin precedes it
        text = '서비스 구조, 계정·권한, 데이터 관리, 영상 정보 보호·보안 그리고 더 많은 내용'
        src = self.build(section(para(f'<hp:run><hp:t>{text}</hp:t></hp:run>', [0, 27, 40])))
        _, out = self.run_cli(src, [{"anchor": "영상 정보 보호", "text": "x"}])
        self.assertEqual(textpos_after(self.read(out), '<hp:t>·보안'), [0, 35, 56])

    def test_offset_counts_earlier_runs_in_paragraph(self) -> None:
        runs = '<hp:run><hp:t> 3.</hp:t></hp:run><hp:run><hp:t> 보안관리: 끝</hp:t></hp:run>'
        src = self.build(section(para(runs, [0, 2, 10])))
        _, out = self.run_cli(src, [{"anchor": "보안관리", "text": "x"}])
        # anchor occupies chars 4..8 -> 2 unchanged, 10 moved by both controls
        self.assertEqual(textpos_after(self.read(out), '<hp:t>: 끝'), [0, 2, 26])

    def test_unsafe_when_non_text_precedes_anchor_in_multiline_paragraph(self) -> None:
        runs = '<hp:run><hp:t>앞</hp:t><hp:tab/><hp:t>보안관리 뒤</hp:t></hp:run>'
        src = self.build(section(para(runs, [0, 5])))
        rc, out = self.run_cli(src, [{"anchor": "보안관리", "text": "x"}])
        self.assertEqual(rc, 1)
        self.assertNotIn('type="MEMO"', self.read(out))
        self.assertIn('memoShapeIDRef="0"', self.read(out))  # nothing placed -> untouched

    def test_single_line_paragraph_with_non_text_prefix_is_ok(self) -> None:
        runs = '<hp:run><hp:t>앞</hp:t><hp:tab/><hp:t>보안관리 뒤</hp:t></hp:run>'
        src = self.build(section(para(runs, [0])))
        rc, out = self.run_cli(src, [{"anchor": "보안관리", "text": "x"}])
        self.assertEqual(rc, 0)
        self.assertIn('type="MEMO"', self.read(out))

    def test_innermost_paragraph_in_table_cell(self) -> None:
        cell = para('<hp:run><hp:t>셀 앞부분 보안 문구</hp:t></hp:run>', [0, 7])  # break inside anchor (6..8)
        outer = ('<hp:p id="0" paraPrIDRef="0" styleIDRef="0"><hp:run><hp:tbl><hp:tc><hp:subList>'
                 f'{cell}</hp:subList></hp:tc></hp:tbl></hp:run>'
                 '<hp:linesegarray><hp:lineseg textpos="0"/></hp:linesegarray></hp:p>')
        src = self.build(section(outer))
        rc, out = self.run_cli(src, [{"anchor": "보안", "text": "x"}])
        self.assertEqual(rc, 0)
        xml = self.read(out)
        self.assertEqual(textpos_after(xml, '<hp:t> 문구'), [0, 15])  # cell's own lines shifted
        self.assertIn('</hp:tbl></hp:run><hp:linesegarray><hp:lineseg textpos="0"/>', xml)  # outer untouched

    def test_occurrence_selects_nth_match(self) -> None:
        src = self.build(section(para('<hp:run><hp:t>보안 A</hp:t></hp:run>', [0]),
                                 para('<hp:run><hp:t>보안 B</hp:t></hp:run>', [0])))
        _, out = self.run_cli(src, [{"anchor": "보안", "text": "x", "occurrence": 2}])
        xml = self.read(out)
        self.assertIn('<hp:t>보안 A</hp:t>', xml)
        self.assertIn('<hp:t>보안</hp:t><hp:ctrl><hp:fieldEnd', xml)

    def test_second_memo_does_not_match_text_inside_first_memo(self) -> None:
        src = self.build(section(para('<hp:run><hp:t>보안관리 조항</hp:t></hp:run>', [0])))
        rc, out = self.run_cli(src, [{"anchor": "보안관리", "text": "조항 확인"},
                                     {"anchor": "조항", "text": "y"}])
        self.assertEqual(rc, 0)
        xml = self.read(out)
        self.assertIn('<hp:t>조항 확인</hp:t>', xml)  # memo body intact
        self.assertRegex(xml, r'<hp:t>조항</hp:t><hp:ctrl><hp:fieldEnd')

    def test_not_found_returns_1_and_reports(self) -> None:
        src = self.build(section(para('<hp:run><hp:t>본문</hp:t></hp:run>', [0])))
        rc, _ = self.run_cli(src, [{"anchor": "없는 문구", "text": "x"}])
        self.assertEqual(rc, 1)

    def test_refuses_to_overwrite_source_or_existing_output(self) -> None:
        src = self.build(section(para('<hp:run><hp:t>보안</hp:t></hp:run>', [0])))
        before = src.read_bytes()
        mf = self.tmp / "m.json"
        mf.write_text('[{"anchor": "보안", "text": "x"}]', encoding='utf-8')
        self.assertEqual(am.main([str(src), str(src), str(mf)]), 2)
        self.assertEqual(src.read_bytes(), before)
        existing = self.tmp / "exists.hwpx"
        existing.write_bytes(b'keep')
        self.assertEqual(am.main([str(src), str(existing), str(mf)]), 2)
        self.assertEqual(existing.read_bytes(), b'keep')

    def test_mimetype_first_and_stored(self) -> None:
        src = self.build(section(para('<hp:run><hp:t>보안</hp:t></hp:run>', [0])))
        _, out = self.run_cli(src, [{"anchor": "보안", "text": "x"}])
        first = zipfile.ZipFile(out).infolist()[0]
        self.assertEqual((first.filename, first.compress_type), ('mimetype', zipfile.ZIP_STORED))


if __name__ == '__main__':
    unittest.main()
