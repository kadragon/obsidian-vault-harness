"""Exercise the public shell entry point against temporary vaults."""
from pathlib import Path
import json
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect_active_notes.sh"


def run(vault):
    return subprocess.run(["bash", str(SCRIPT), str(vault)], capture_output=True, text=True)


def setup(vault):
    for area in ("12_Projects", "10_Areas", "14_Changes"):
        (vault / area).mkdir()


def test_frontmatter_only_and_markdown_only(tmp_path):
    setup(tmp_path)
    cases = {
        "plain.md": "---\nstatus: open\n---\n",
        "single.md": "---\nstatus: 'open' # comment\n---\n",
        "double.md": '---\nstatus: "active"\n---\n',
        "closed.md": "---\nstatus: closed\n---\n```yaml\nstatus: open\n```\n",
        "body.md": "# Text\nstatus: open\n",
        "prefix.md": "---\nstatus: opened\n---\n",
        "invalid.md": "---\nstatus: 'open\n---\n",
        "attachment.txt": "---\nstatus: open\n---\n",
    }
    for name, text in cases.items():
        (tmp_path / "10_Areas" / name).write_text(text, encoding="utf-8")
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    paths = {Path(line).name for line in result.stdout.splitlines() if not line.startswith("===")}
    assert paths == {"plain.md", "single.md", "double.md"}
    assert not result.stderr


def test_generated_projects_excluded_with_crlf_and_unicode_paths(tmp_path):
    setup(tmp_path)
    project = tmp_path / "12_Projects" / "사업 폴더"
    project.mkdir()
    for ending in ("\n", "\r\n"):
        path = project / ("generated-lf.md" if ending == "\n" else "generated-crlf.md")
        path.write_bytes(ending.join([
            "---", "status: active", "---", "<!-- homepage-collect:begin v1 -->", "",
        ]).encode("utf-8"))
    manual = project / "일반 업무.md"
    manual.write_bytes(b"\xef\xbb\xbf---\r\nstatus: 'active'\r\n---\r\n")
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert str(manual) in result.stdout
    assert "generated-" not in result.stdout


def test_empty_vault_succeeds(tmp_path):
    setup(tmp_path)
    result = run(tmp_path)
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["=== 12_Projects ===", "=== 10_Areas ===", "=== 14_Changes ==="]
    assert not result.stderr


def test_missing_area_warns_but_existing_notes_are_collected(tmp_path):
    (tmp_path / "10_Areas").mkdir()
    note = tmp_path / "10_Areas" / "task.md"
    note.write_text("---\nstatus: open\n---\n", encoding="utf-8")
    result = run(tmp_path)
    assert result.returncode == 0
    assert str(note) in result.stdout
    assert "WARNING:" in result.stderr and "12_Projects" in result.stderr
    assert "14_Changes" in result.stderr


def test_invalid_vault_is_error(tmp_path):
    result = run(tmp_path / "missing")
    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert not result.stdout


def test_read_failure_is_not_reported_as_no_matches(tmp_path):
    setup(tmp_path)
    (tmp_path / "10_Areas" / "bad.md").write_bytes(b"\xff")
    result = run(tmp_path)
    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert not result.stdout


def test_area_file_is_error(tmp_path):
    (tmp_path / "12_Projects").write_text("not a directory", encoding="utf-8")
    result = run(tmp_path)
    assert result.returncode == 1
    assert "Expected directory" in result.stderr


def test_json_period_tasks_context_and_source_lines(tmp_path):
    setup(tmp_path)
    project = tmp_path / "12_Projects" / "2026" / "새 사업"
    project.mkdir(parents=True)
    note = project / "_새 사업.md"
    lines = [
        "---", "status: active", "---", "# 사업 제목", "- #부서/학사관리과/학적팀",
        "## 현황", "> [!info]+ 현황", "> - 2026. 12. 31. 협의 예정", "## 주요 일정",
        "- [ ] 나중 마감 📅 2027-01-05", "> - [ ] 이번 주 📅 2026-12-30",
        "- [ ] 지난 마감 📅 2026-12-20", "- [ ] 날짜 없는 업무", "- [ ] 잘못된 날짜 📅 2026-02-30",
        "- [x] 완료 업무 📅 2026-12-29", "```markdown", "- [ ] 코드 안 업무 📅 2026-12-30", "```",
        "> ~~~text", "> - [ ] 코드 안 인용", "> ~~~", "## 기타", "- [ ] 분류 확인할 업무",
    ]
    note.write_text("\n".join(lines), encoding="utf-8")
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path), "--json", "--date", "2026-12-31", "--weeks", "2"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["period"]["start"] == {"date": "2026-12-28", "weekday": "월", "display": "12. 28.(월)"}
    assert data["period"]["end"]["date"] == "2027-01-10"
    assert data["period"]["end"]["weekday"] == "일"
    assert len(data["notes"]) == 1
    got = data["notes"][0]
    assert got["title"] == "사업 제목" and got["project_name"] == "새 사업"
    assert got["departments"] == [{"name": "학사관리과", "line": 5, "raw": lines[4]}]
    assert got["completed_task_count"] == 1
    assert len(got["tasks"]) == 6
    assert [t["due"]["date"] for t in got["tasks"][:3]] == ["2026-12-20", "2026-12-30", "2027-01-05"]
    assert got["tasks"][0]["candidate_reason"] == "overdue"
    assert got["tasks"][1]["due"]["weekday"] == "수"
    for task in got["tasks"]:
        assert lines[task["line"] - 1] == task["raw"]
    assert set(got["review_required"]) == {"overdue", "no_due_date", "invalid_due_date", "outside_task_section"}
    event = next(c for c in got["context"] if c["dates"])
    assert event["dates"][0]["date"] == "2026-12-31" and event["event_in_period"]
    assert event["line"] == 8
    assert "context_event_in_period" in got["candidate_reasons"]


def test_json_retains_future_and_undated_tasks_with_one_week_default(tmp_path):
    setup(tmp_path)
    note = tmp_path / "10_Areas" / "work.md"
    note.write_text(
        "---\nstatus: open\ntags: ['#부서/정보전산원']\n---\n# 작업\n## 할 일\n"
        "> - [ ] 다음 달 📅 2026-11-30\n- [ ] 계속 작업\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path), "--json", "--date", "2026-11-01"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    assert data["weeks"] == 1
    assert data["period"]["start"]["date"] == "2026-10-26"
    assert data["period"]["end"]["date"] == "2026-11-01"
    got = data["notes"][0]
    assert len(got["tasks"]) == 2
    assert set(got["candidate_reasons"]) == {"due_after_period", "no_due_date"}
    assert got["departments"][0]["name"] == "정보전산원"
    assert got["departments"][0]["line"] == 3


def test_json_keeps_no_open_tasks_for_review(tmp_path):
    setup(tmp_path)
    (tmp_path / "14_Changes" / "change.md").write_text(
        "---\nstatus: open\n---\n## 🏷 Todo\n- [x] Done\n", encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path), "--json", "--date", "2026-11-01"],
        capture_output=True, text=True, check=True,
    )
    got = json.loads(result.stdout)["notes"][0]
    assert got["tasks"] == [] and got["completed_task_count"] == 1
    assert got["review_required"] == ["no_open_tasks"]


def test_json_rejects_invalid_period_arguments(tmp_path):
    for args in (["--weeks", "3"], ["--date", "2026-02-30"]):
        result = subprocess.run(["bash", str(SCRIPT), str(tmp_path), "--json", *args], capture_output=True, text=True)
        assert result.returncode == 2 and not result.stdout
