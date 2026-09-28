#!/usr/bin/env python3
"""Regression tests for legacy .hwp text extraction in extract_bundle.py.

Run directly (tests below ``.claude/`` are not pytest collection targets):
``python3 .claude/skills/gwaeop-simui/tests/test_extract_hwp.py`` must exit 0.
"""
from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPT = HERE.parent.parent / "scripts" / "extract_bundle.py"
spec = importlib.util.spec_from_file_location("extract_bundle", SCRIPT)
assert spec and spec.loader
extract_bundle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = extract_bundle
spec.loader.exec_module(extract_bundle)

PARA_TEXT = 67
PARA_HEADER = 66


def record(tag: int, body: bytes) -> bytes:
    size = len(body)
    if size >= 0xFFF:
        return struct.pack("<II", tag | (0xFFF << 20), size) + body
    return struct.pack("<I", tag | (size << 20)) + body


def wchars(text: str) -> bytes:
    return text.encode("utf-16-le")


class HwpSectionTextTests(unittest.TestCase):
    def test_reads_para_text_and_ignores_other_records(self):
        data = record(PARA_HEADER, b"\x00" * 22) + record(PARA_TEXT, wchars("과업심의위원회"))
        self.assertEqual(extract_bundle.hwp_section_text(data), "과업심의위원회")

    def test_skips_extended_control_payload(self):
        # char 11 (table/drawing object) occupies 8 wchars; its payload must not leak as text.
        ctrl = struct.pack("<H", 11) + b"tbl " + b"\x00" * 8 + struct.pack("<H", 11)
        data = record(PARA_TEXT, wchars("앞") + ctrl + wchars("뒤"))
        self.assertEqual(extract_bundle.hwp_section_text(data), "앞뒤")

    def test_tab_and_line_break(self):
        tab = struct.pack("<H", 9) + b"\x00" * 12 + struct.pack("<H", 9)
        data = record(PARA_TEXT, wchars("가") + tab + wchars("나") + struct.pack("<H", 10) + wchars("다"))
        self.assertEqual(extract_bundle.hwp_section_text(data), "가\t나\n다")

    def test_extended_record_size(self):
        long_text = "가" * 3000  # 6000 bytes > 0xFFF
        data = record(PARA_TEXT, wchars(long_text)) + record(PARA_TEXT, wchars("끝"))
        self.assertEqual(extract_bundle.hwp_section_text(data), long_text + "\n끝")

    def test_non_ole_file_reports_error_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "broken.hwp"
            src.write_bytes(b"not an ole file")
            status = extract_bundle.extract_hwp(str(src), str(Path(tmp) / "out.txt"))
        self.assertTrue(status.startswith(("ERROR", "NEEDS_HWPX")), status)


class XlsxTextTests(unittest.TestCase):
    def test_extracts_cell_values_per_sheet(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl 미설치")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "산출내역서.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "개발비"
            ws.append(["항목", "단가", "수량", "금액"])
            ws.append(["분석설계", 1000000, 2, "=B2*C2"])
            wb.save(src)
            dst = Path(tmp) / "out.txt"
            status = extract_bundle.extract_xlsx(str(src), str(dst))
            text = dst.read_text(encoding="utf-8")
        self.assertTrue(status.startswith("OK"), status)
        self.assertIn("개발비", text)
        self.assertIn("분석설계 | 1000000 | 2", text)


if __name__ == "__main__":
    unittest.main()
