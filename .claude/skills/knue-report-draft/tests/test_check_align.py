"""Alignment gate contracts using minimal XML packages."""
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[1] / 'scripts' / 'check_align.py'


class AlignmentTests(unittest.TestCase):
    def run_check(self, header, section=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.hwpx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Contents/header.xml', header)
                if section is not None:
                    archive.writestr('Contents/section0.xml', section)
            return subprocess.run([sys.executable, str(CHECKER), str(path)], capture_output=True, text=True)

    def test_left_and_justify(self):
        for align, expected in [('LEFT', 1), ('JUSTIFY', 0)]:
            with self.subTest(align=align):
                header = f'<h:head xmlns:h="urn:head"><h:paraPr other="x" id="1"><h:align vertical="BASELINE" horizontal="{align}"/></h:paraPr></h:head>'
                section = '<p:sec xmlns:p="urn:para"><p:p paraPrIDRef="1"><p:run><p:t style="x">Body</p:t></p:run></p:p></p:sec>'
                result = self.run_check(header, section)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def test_empty_or_malformed_document_is_unreadable(self):
        self.assertEqual(self.run_check('<head/>').returncode, 2)
        self.assertEqual(self.run_check('<broken', '<sec/>').returncode, 2)
        self.assertEqual(self.run_check('<head/>', '<broken').returncode, 2)

    def test_parent_text_is_checked_without_misattributing_nested_text(self):
        header = '<head><paraPr id="1"><align horizontal="LEFT"/></paraPr><paraPr id="2"><align horizontal="JUSTIFY"/></paraPr></head>'
        nested = '<p paraPrIDRef="2"><run><t>Nested</t></run></p>'
        result = self.run_check(header, '<sec><p paraPrIDRef="1"><run><t>Outer</t><tbl>' + nested + '</tbl></run></p></sec>')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Outer', result.stdout)
        result = self.run_check(header, '<sec><p paraPrIDRef="1"><run><tbl>' + nested + '</tbl></run></p></sec>')
        self.assertEqual(result.returncode, 0)


    def test_table_cell_alignment_is_not_a_body_rule(self):
        header = '<head><paraPr id="1"><align horizontal="LEFT"/></paraPr></head>'
        section = '<sec><p paraPrIDRef="1"><run><tbl><tr><tc><p paraPrIDRef="1"><run><t>Table label</t></run></p></tc></tr></tbl></run></p></sec>'
        self.assertEqual(self.run_check(header, section).returncode, 0)

    def test_headers_footers_and_text_boxes_are_not_body_paragraphs(self):
        header = '<head><paraPr id="1"><align horizontal="LEFT"/></paraPr></head>'
        text = '<p paraPrIDRef="1"><run><t>Page label</t></run></p>'
        for container in ('header', 'footer', 'subList', 'drawText'):
            with self.subTest(container=container):
                section = f'<sec><p paraPrIDRef="1"><run><{container}>{text}</{container}></run></p></sec>'
                self.assertEqual(self.run_check(header, section).returncode, 0)


if __name__ == '__main__':
    unittest.main()
