"""Synthetic PDFs verify page selection, preservation, and non-overwriting writes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

SPEC = importlib.util.spec_from_file_location(
    "round_pdf_pages", Path(__file__).resolve().parents[1] / "scripts" / "pdf_pages.py"
)
pdf_pages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pdf_pages)


def make_pdf(path: Path, labels: list[str]) -> None:
    writer = PdfWriter()
    for label in labels:
        page = writer.add_blank_page(200, 100)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        })
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 50 Td ({label}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = stream
    with path.open("wb") as output:
        writer.write(output)


def manifest(tmp_path: Path, config=None) -> tuple[Path, Path]:
    make_pdf(tmp_path / "a.pdf", ["A1", "A2", "A3"])
    make_pdf(tmp_path / "b.pdf", ["B1", "B2"])
    config = config or {
        "version": 1,
        "sources": {"a": "a.pdf", "b": "b.pdf"},
        "outputs": [
            {"path": "결과/01-merged.pdf", "parts": [
                {"source": "a", "pages": [[3, 3], [1, 1]]},
                {"source": "b", "pages": [[2, 2]]},
            ]},
            {"path": "결과/02-rest.pdf", "parts": [
                {"source": "a", "pages": [[2, 2]]},
                {"source": "b", "pages": [[1, 1]]},
            ]},
        ],
    }
    path = tmp_path / "pages.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, tmp_path / "output"


def rewrite(path, edit):
    config = json.loads(path.read_text())
    edit(config)
    path.write_text(json.dumps(config))


def texts(path):
    return [page.extract_text().strip() for page in PdfReader(path).pages]


def test_dry_run_creates_nothing_and_apply_preserves_order_text_and_sources(tmp_path):
    path, out = manifest(tmp_path)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.glob("*.pdf")}
    plan = pdf_pages.execute(path, out)
    assert plan["ok"] and plan["created"] == []
    assert not out.exists()
    assert plan["outputs"][0]["page_order"] == [["a", 3], ["a", 1], ["b", 2]]
    result = pdf_pages.execute(path, out, apply=True)
    assert result["ok"]
    assert [item["page_count"] for item in result["created"]] == [3, 2]
    assert texts(out / "결과/01-merged.pdf") == ["A3", "A1", "B2"]
    assert texts(out / "결과/02-rest.pdf") == ["A2", "B1"]
    assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.glob("*.pdf")}
    before = (out / "결과/01-merged.pdf").read_bytes()
    assert not pdf_pages.execute(path, out, apply=True)["ok"]
    assert (out / "결과/01-merged.pdf").read_bytes() == before


@pytest.mark.parametrize("bad_path", ["../bad.pdf", "/bad.pdf", "x\\bad.pdf", "NUL.pdf", "a:bad.pdf", "folder./a.pdf", "bad.txt", "./a.pdf"])
def test_rejects_unsafe_names_before_any_output(tmp_path, bad_path):
    path, out = manifest(tmp_path)
    rewrite(path, lambda cfg: cfg["outputs"][1].update(path=bad_path))
    assert not pdf_pages.execute(path, out, apply=True)["ok"]
    assert not out.exists()


@pytest.mark.parametrize("pages", [[], [[0, 1]], [[1, 4]], [[2, 1]], [[True, 2]], [[1]], [[1, 2], [2, 3]]])
def test_invalid_or_overlapping_ranges_fail_whole_plan(tmp_path, pages):
    path, out = manifest(tmp_path)
    rewrite(path, lambda cfg: cfg["outputs"][1]["parts"][0].update(pages=pages))
    assert not pdf_pages.execute(path, out, apply=True)["ok"]
    assert not out.exists()


def test_omission_and_cross_output_reuse_need_explicit_opt_in(tmp_path):
    path, out = manifest(tmp_path)
    rewrite(path, lambda cfg: cfg["outputs"].pop())
    assert not pdf_pages.execute(path, out)["ok"]
    rewrite(path, lambda cfg: cfg.update(allow_unused_pages=True))
    result = pdf_pages.execute(path, out)
    assert result["ok"] and result["sources"]["a"]["unused_pages"] == [2]
    rewrite(path, lambda cfg: cfg["outputs"].append({
        "path": "another.pdf", "parts": [{"source": "a", "pages": [[1, 1]]}],
    }))
    assert not pdf_pages.execute(path, out)["ok"]
    rewrite(path, lambda cfg: cfg.update(allow_reuse=True))
    assert pdf_pages.execute(path, out)["reused_pages"] == ["a:1"]


def test_missing_empty_sources_and_outputs_are_rejected(tmp_path):
    path, out = manifest(tmp_path)
    (tmp_path / "b.pdf").unlink()
    assert not pdf_pages.execute(path, out, apply=True)["ok"]
    assert not out.exists()
    make_pdf(tmp_path / "b.pdf", [])
    assert not pdf_pages.execute(path, out)["ok"]
    make_pdf(tmp_path / "b.pdf", ["B1", "B2"])
    rewrite(path, lambda cfg: cfg.update(outputs=[]))
    assert not pdf_pages.execute(path, out)["ok"]


def test_duplicate_names_and_symlink_escape_are_rejected(tmp_path):
    path, out = manifest(tmp_path)
    rewrite(path, lambda cfg: cfg["outputs"][1].update(path=cfg["outputs"][0]["path"].upper()))
    assert not pdf_pages.execute(path, out)["ok"]
    path, out = manifest(tmp_path)
    out.mkdir()
    (out / "결과").symlink_to(tmp_path, target_is_directory=True)
    assert not pdf_pages.execute(path, out, apply=True)["ok"]
    assert not (tmp_path / "01-merged.pdf").exists()


def test_failure_reports_completed_unverified_and_unattempted_outputs(tmp_path, monkeypatch):
    path, out = manifest(tmp_path)
    def split_last_output(cfg):
        last_part = cfg["outputs"][1]["parts"].pop()
        cfg["outputs"].append({"path": "third.pdf", "parts": [last_part]})
    rewrite(path, split_last_output)
    original = pdf_pages.PdfWriter.write
    calls = 0
    def fail_second(self, stream):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic write failure")
        return original(self, stream)
    monkeypatch.setattr(pdf_pages.PdfWriter, "write", fail_second)
    result = pdf_pages.execute(path, out, apply=True)
    assert not result["ok"]
    assert result["created"] == [{"path": "결과/01-merged.pdf", "page_count": 3}]
    assert result["failed"][0]["created_unverified"] is True
    assert result["not_written"] == ["third.pdf"]
    assert not (out / "third.pdf").exists()
    assert texts(out / "결과/01-merged.pdf") == ["A3", "A1", "B2"]
    assert texts(tmp_path / "a.pdf") == ["A1", "A2", "A3"]


def test_cli_is_dry_run_by_default(tmp_path, capsys):
    path, out = manifest(tmp_path)
    assert pdf_pages.main([str(path), "--output-root", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "dry-run"
    assert not out.exists()


def test_existing_source_cannot_be_used_as_output(tmp_path):
    path, _ = manifest(tmp_path)
    before = (tmp_path / "a.pdf").read_bytes()
    rewrite(path, lambda cfg: cfg["outputs"][0].update(path="a.pdf"))
    assert not pdf_pages.execute(path, tmp_path, apply=True)["ok"]
    assert (tmp_path / "a.pdf").read_bytes() == before
    assert not (tmp_path / "결과").exists()


def test_page_count_readback_mismatch_is_reported(tmp_path, monkeypatch):
    path, out = manifest(tmp_path)
    original = pdf_pages.PdfWriter.write
    def omit_last_page(self, stream):
        del self.pages[-1]
        return original(self, stream)
    monkeypatch.setattr(pdf_pages.PdfWriter, "write", omit_last_page)
    result = pdf_pages.execute(path, out, apply=True)
    assert not result["ok"]
    assert result["created"] == []
    assert "page count mismatch" in result["failed"][0]["error"]
    assert result["not_written"] == ["결과/02-rest.pdf"]


def test_encrypted_source_is_rejected_before_outputs(tmp_path):
    path, out = manifest(tmp_path)
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.encrypt("test-only-password")
    with (tmp_path / "b.pdf").open("wb") as stream:
        writer.write(stream)
    result = pdf_pages.execute(path, out, apply=True)
    assert not result["ok"] and "encrypted" in result["errors"][0]
    assert not out.exists()
