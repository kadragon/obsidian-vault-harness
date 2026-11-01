"""Recovery reports survive partial closure and never overwrite prior evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "status_apply_recovery", Path(__file__).resolve().parents[1] / "scripts" / "apply.py"
)
apply = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apply)


def note(vault: Path, name: str, status: str = "open") -> Path:
    path = vault / "10_Areas" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nstatus: {status}\ndate modified: 2026-01-01\n---\n# Work\n")
    return path


def records(report: Path) -> list[dict]:
    return [json.loads(line) for line in report.read_text().splitlines()]


def test_report_retains_successes_when_other_targets_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(apply, "VAULT", tmp_path)
    first = note(tmp_path, "first.md")
    already = note(tmp_path, "already.md", "closed")
    report = tmp_path / "reports" / "close.jsonl"
    assert apply.cmd_close([
        "10_Areas/first.md", "10_Areas/already.md", "10_Areas/missing.md",
        "--report", str(report),
    ]) == 1
    rows = records(report)
    assert [r["event"] for r in rows] == ["planned", "closed", "failed", "failed"]
    assert rows[1]["path"] == "10_Areas/first.md"
    assert rows[1]["recorded_at"][:10]
    assert "status: closed" in first.read_text()
    assert "2026-01-01" in already.read_text()
    assert not (tmp_path / "_Wiki").exists()


def test_existing_report_prevents_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(apply, "VAULT", tmp_path)
    target = note(tmp_path, "first.md")
    report = tmp_path / "close.jsonl"
    report.write_text("prior recovery evidence\n")
    assert apply.cmd_close(["10_Areas/first.md", "--report", str(report)]) == 1
    assert "status: open" in target.read_text()
    assert report.read_text() == "prior recovery evidence\n"


def test_report_failure_stops_before_closing_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(apply, "VAULT", tmp_path)
    target = note(tmp_path, "first.md")
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(apply, "_record", fail)
    assert apply.cmd_close(["10_Areas/first.md", "--report", str(tmp_path / "close.jsonl")]) == 1
    assert "status: open" in target.read_text()


def test_interrupted_result_write_retains_plan_and_stops_next_note(tmp_path, monkeypatch):
    monkeypatch.setattr(apply, "VAULT", tmp_path)
    first = note(tmp_path, "first.md")
    second = note(tmp_path, "second.md")
    report = tmp_path / "close.jsonl"
    original = apply._record
    def fail_after_plan(stream, entry):
        if entry["event"] != "planned":
            raise OSError("disk unavailable")
        original(stream, entry)
    monkeypatch.setattr(apply, "_record", fail_after_plan)
    assert apply.cmd_close([
        "10_Areas/first.md", "10_Areas/second.md", "--report", str(report),
    ]) == 1
    assert records(report)[0]["paths"] == ["10_Areas/first.md", "10_Areas/second.md"]
    assert "status: closed" in first.read_text()
    assert "status: open" in second.read_text()


def test_legacy_close_output_is_preserved(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(apply, "VAULT", tmp_path)
    note(tmp_path, "first.md")
    assert apply.cmd_close(["10_Areas/first.md"]) == 0
    assert capsys.readouterr().out == "OK  close 10_Areas/first.md  — ok\n"
