#!/usr/bin/env python3
"""Regression tests for read-only lint baseline comparisons."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "vault_lint.py"


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "vault"
        self.root.mkdir()
        self.note = self.root / "일반.md"
        self.note.write_text("[[없는 문서]]\n", encoding="utf-8")
        self.baseline = Path(self.tmp.name) / "baseline.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, check="deadlink", fmt="json"):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", str(self.root),
             "--check", check, "--format", fmt, *args],
            capture_output=True, text=True, encoding="utf-8", timeout=30)

    def snapshot(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.baseline.write_text(r.stdout, encoding="utf-8")
        return json.loads(r.stdout)

    def compare(self, *args, **kwargs):
        return self.run_cli("--baseline", str(self.baseline), "--strict", *args, **kwargs)

    def test_existing_findings_and_line_shifts_pass(self):
        self.snapshot()
        self.note.write_text("\n\n[[없는 문서]]\n", encoding="utf-8")
        r = self.compare()
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["baseline"]["existing"], 1)

    def test_new_and_duplicate_findings_fail(self):
        self.snapshot()
        self.note.write_text("[[없는 문서]]\n[[없는 문서]]\n[[새 문서]]\n", encoding="utf-8")
        r = self.compare()
        self.assertEqual(r.returncode, 1, r.stderr)
        report = json.loads(r.stdout)
        self.assertEqual(len(report["findings"]), 2)
        self.assertEqual(report["baseline"]["existing"], 1)

    def test_resolved_findings_and_text_formats(self):
        self.snapshot()
        self.note.write_text("", encoding="utf-8")
        for fmt in ("json", "text", "markdown"):
            with self.subTest(fmt=fmt):
                r = self.compare(fmt=fmt)
                self.assertEqual(r.returncode, 0, r.stderr)
                if fmt == "json":
                    self.assertEqual(json.loads(r.stdout)["baseline"]["resolved"], 1)
                else:
                    self.assertIn("baseline", r.stdout)

    def test_changed_path_or_detail_is_new(self):
        self.snapshot()
        self.note.rename(self.root / "다른.md")
        r = self.compare()
        self.assertEqual(r.returncode, 1)
        (self.root / "다른.md").rename(self.note)
        self.note.write_text("[[다른 대상]]\n", encoding="utf-8")
        self.assertEqual(self.compare().returncode, 1)

    def test_missing_corrupt_and_invalid_baselines_fail_closed(self):
        self.assertEqual(self.compare().returncode, 2)
        for content in ("{", "[]", "{}"):
            with self.subTest(content=content):
                self.baseline.write_text(content, encoding="utf-8")
                r = self.compare()
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_incompatible_checks_and_malformed_findings_rejected(self):
        report = self.snapshot()
        self.assertEqual(self.compare(check="orphan").returncode, 2)
        for field, value in (("path", None), ("line", "2"), ("check", "orphan")):
            with self.subTest(field=field):
                bad = json.loads(json.dumps(report))
                bad["findings"][0][field] = value
                self.baseline.write_text(json.dumps(bad), encoding="utf-8")
                self.assertEqual(self.compare().returncode, 2)

    def test_comparison_report_cannot_be_reused_as_full_baseline(self):
        self.snapshot()
        r = self.compare()
        self.baseline.write_text(r.stdout, encoding="utf-8")
        self.assertEqual(self.compare().returncode, 2)

    def test_without_baseline_strict_still_fails(self):
        self.assertEqual(self.run_cli("--strict").returncode, 1)

    def test_rules_digest_and_counts_mismatch_rejected(self):
        report = self.snapshot()
        for field, value in (("rules_digest", "old-rules"), ("counts", {})):
            with self.subTest(field=field):
                bad = dict(report, **{field: value})
                self.baseline.write_text(json.dumps(bad), encoding="utf-8")
                self.assertEqual(self.compare().returncode, 2)

    def test_unicode_normalization_and_non_strict_reporting(self):
        import unicodedata
        report = self.snapshot()
        report["findings"][0]["path"] = unicodedata.normalize("NFD", self.note.name)
        self.baseline.write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual(self.compare().returncode, 0)
        self.note.write_text("[[새 문서]]", encoding="utf-8")
        r = self.run_cli("--baseline", str(self.baseline))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(json.loads(r.stdout)["findings"]), 1)


if __name__ == "__main__":
    unittest.main()
