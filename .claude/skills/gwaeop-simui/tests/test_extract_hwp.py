#!/usr/bin/env python3
"""Regression tests for legacy .hwp text extraction in extract_bundle.py.

Run directly (tests below ``.claude/`` are not pytest collection targets):
``python3 .claude/skills/gwaeop-simui/tests/test_extract_hwp.py`` must exit 0.
"""
from __future__ import annotations

import importlib.util
import os
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

    def test_unpaired_surrogate_is_written_not_raised(self):
        # A lone UTF-16 surrogate wchar (0xD800) becomes an unpaired surrogate in str;
        # writing it as utf-8 used to raise UnicodeEncodeError.
        section = record(PARA_TEXT, wchars("앞") + struct.pack("<H", 0xD800) + wchars("뒤"))

        class FakeOle:
            def __init__(self, _src):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def openstream(self, name):
                import io
                if name == "FileHeader":
                    return io.BytesIO(b"\x00" * 40)  # props at offset 36 = 0: uncompressed, no password
                return io.BytesIO(section)

            def listdir(self):
                return [["BodyText", "Section0"]]

        fake = type(sys)("olefile")
        fake.isOleFile = lambda _src: True
        fake.OleFileIO = FakeOle
        saved = sys.modules.get("olefile")
        sys.modules["olefile"] = fake
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dst = Path(tmp) / "out.txt"
                status = extract_bundle.extract_hwp(str(Path(tmp) / "x.hwp"), str(dst))
                text = dst.read_text(encoding="utf-8")
        finally:
            if saved is None:
                sys.modules.pop("olefile", None)
            else:
                sys.modules["olefile"] = saved
        self.assertTrue(status.startswith("OK"), status)
        self.assertIn("앞", text)
        self.assertIn("뒤", text)


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


FIXTURES = HERE.parent / "fixtures"


class XlsTextTests(unittest.TestCase):
    """fixtures/cost_sheet.xls 는 xlwt 로 만든 BIFF8 — 날짜·불리언·오류 셀과 0.1+0.2 부동소수 노이즈를 담는다."""

    def _walk(self, name: str, data: bytes):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "bundle" / name
            src.parent.mkdir()
            src.write_bytes(data)
            out = Path(tmp) / "out"
            rows = extract_bundle.walk(str(src.parent), str(out), None)
            txt = out / (name + ".txt")
            return rows[0][2], txt.read_text(encoding="utf-8") if txt.exists() else ""

    def test_xls_cells_are_rendered_by_type(self):
        try:
            import xlrd  # noqa: F401
        except ImportError:
            self.skipTest("xlrd 미설치")
        status, text = self._walk("산출내역서.xls", (FIXTURES / "cost_sheet.xls").read_bytes())
        self.assertTrue(status.startswith("OK"), status)
        self.assertIn("===SHEET 개발비===", text)
        self.assertIn("분석설계 | 1000000 | 2 | 1100000 | 2026-11-02 | TRUE", text)
        self.assertIn("VAT | 0.3 |  | #DIV/0!", text)

    def test_xls_named_ooxml_is_read_as_xlsx(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl 미설치")
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.xlsx"
            wb = openpyxl.Workbook()
            wb.active.append(["항목", "금액"])
            wb.save(real)
            data = real.read_bytes()
        status, text = self._walk("산출내역서.xls", data)
        self.assertTrue(status.startswith("OK"), status)
        self.assertIn("항목 | 금액", text)

    def test_xls_named_html_is_copied_as_text(self):
        status, text = self._walk("산출내역서.xls", "<html><table><tr><td>금액</td></tr></table></html>".encode())
        self.assertTrue(status.startswith("OK"), status)
        self.assertIn("<td>금액</td>", text)


class HwpxToolPathTests(unittest.TestCase):
    """prod:hwpx text.py 해석 순서를 고정한다 — marketplaces 우선, 없으면 cache 최신 버전, 둘 다 없으면 None."""

    MARKET = ".claude/plugins/marketplaces/kadragon/prod/skills/hwpx/scripts/text.py"
    CACHE = ".claude/plugins/cache/kadragon/prod/{ver}/skills/hwpx/scripts/text.py"

    def _resolve(self, home: Path, rels: list[str]) -> str | None:
        for rel in rels:
            p = home / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")
        saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)
        try:
            # 경로를 import 시점에 펼치는 구현도 잡도록 모듈을 새로 로드한다.
            fresh_spec = importlib.util.spec_from_file_location("extract_bundle_fresh", SCRIPT)
            fresh = importlib.util.module_from_spec(fresh_spec)
            fresh_spec.loader.exec_module(fresh)
            return fresh.find_hwpx_text_py()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_marketplaces_wins_over_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = self._resolve(Path(tmp), [self.MARKET, self.CACHE.format(ver="0.9.0")])
            self.assertEqual(Path(got), Path(tmp) / self.MARKET)

    def test_cache_fallback_picks_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = self._resolve(Path(tmp), [self.CACHE.format(ver="0.8.0"), self.CACHE.format(ver="0.9.0")])
            self.assertEqual(Path(got), Path(tmp) / self.CACHE.format(ver="0.9.0"))

    def test_missing_tool_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self._resolve(Path(tmp), []))

    def test_missing_tool_status_without_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(extract_bundle.extract_hwpx("x.hwpx", str(Path(tmp) / "o.txt"), None), "NO_HWPX_TOOL")


if __name__ == "__main__":
    unittest.main()
