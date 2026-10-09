#!/usr/bin/env python3
"""Tests for change-log scripts/collect_weekly_notes.py.

Run:  python3 -m pytest .claude/skills/change-log/tests/ -q

NOTE: SKILL.md Step 2 수집 제외 기준 중 기술 용어 제거 규칙은
스크립트에 구현되어 있지 않다 — 서술 다듬기라 수동 판정이다.
자동 제외(`weekly_exclude: true` 플래그)는 스크립트 `is_excluded()`가
수행하며, 본 파일이 회귀 테스트한다. 실파일 대신
인메모리 문자열과 tmp_path만 쓴다.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPTS = HERE.parents[1] / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cw = _load("cw_collect", SCRIPTS / "collect_weekly_notes.py")


def test_parse_date_value_valid_and_invalid():
    assert cw.parse_date_value("2026-09-30") == date(2026, 9, 30)
    assert cw.parse_date_value("2026-09-30 12:00:00") == date(2026, 9, 30)
    assert cw.parse_date_value("not-a-date") is None
    assert cw.parse_date_value("") is None


def test_prev_week_range_is_mon_to_sun():
    mon, sun = cw.prev_week_range(date(2026, 10, 9))  # a Friday
    assert mon.weekday() == 0 and sun.weekday() == 6
    assert (sun - mon).days == 6
    assert (mon, sun) == (date(2026, 9, 28), date(2026, 10, 4))


def test_matched_date_inside_week_included():
    text = "---\ntype: work\n---\n# 성적 오류 수정\n- [x] 반영 ✅ 2026-09-30\n"
    assert cw.matched_date_in_range(text, date(2026, 9, 28), date(2026, 10, 4)) == "2026-09-30"


def test_matched_date_outside_week_excluded():
    text = "---\ntype: work\n---\n# 지난주 건\n- [x] 반영 ✅ 2026-09-20\n"
    assert cw.matched_date_in_range(text, date(2026, 9, 28), date(2026, 10, 4)) is None


def test_find_completed_todo_dates_checked_box_fallback():
    text = "- [x] 반영 📅 2026-09-29\n"
    assert cw.find_completed_todo_dates(text) == [date(2026, 9, 29)]
    assert cw.find_completed_todo_dates("- [ ] 미완료 📅 2026-09-29\n") == []


def test_category_map_known_areas():
    assert cw.CATEGORY_MAP["수업성적"] == "학사"
    assert cw.CATEGORY_MAP["교수업적"] == "행정"
    assert cw.CATEGORY_MAP["AI플랫폼"] == "공통"


def test_infer_area_from_tag_alias_and_two_level():
    assert cw.infer_area_from_tag("#업무/수업/성적관리") == "수업성적"
    assert cw.infer_area_from_tag("#업무/학사/수업성적/성적관리") == "수업성적"
    assert cw.infer_area_from_tag("태그 없음") is None


def test_collect_10areas_tmp_path_week_filter(tmp_path):
    area = tmp_path / "10_Areas" / "수업성적"
    area.mkdir(parents=True)
    (area / "in.md").write_text(
        "---\ntype: work\n---\n# 주내 완료\n- [x] 반영 ✅ 2026-09-30\n#업무/수업성적/성적관리\n",
        encoding="utf-8",
    )
    (area / "out.md").write_text(
        "---\ntype: work\n---\n# 범위 밖\n- [x] 반영 ✅ 2026-09-20\n#업무/수업성적/성적관리\n",
        encoding="utf-8",
    )
    got, excluded = cw.collect_10areas(tmp_path, date(2026, 9, 28), date(2026, 10, 4))
    titles = [n["title"] for n in got]
    assert "주내 완료" in titles and "범위 밖" not in titles
    assert excluded == 0
    assert got[0]["category"] == "학사"


def test_is_excluded_flag_variants():
    assert cw.is_excluded("---\nweekly_exclude: true\n---\n# t\n") is True
    assert cw.is_excluded("---\nweekly_exclude: yes\n---\n# t\n") is True
    assert cw.is_excluded("---\nweekly_exclude: True\n---\n# t\n") is True
    assert cw.is_excluded("---\ntype: work\n---\n# t\n") is False
    assert cw.is_excluded("---\nweekly_exclude: false\n---\n# t\n") is False


def test_collect_10areas_skips_flagged_and_counts(tmp_path):
    area = tmp_path / "10_Areas" / "수업성적"
    area.mkdir(parents=True)
    (area / "in.md").write_text(
        "---\ntype: work\n---\n# 주내 완료\n- [x] 반영 ✅ 2026-09-30\n#업무/수업성적/성적관리\n",
        encoding="utf-8",
    )
    (area / "skip.md").write_text(
        "---\ntype: work\nweekly_exclude: true\n---\n# 1회성 처리\n- [x] 반영 ✅ 2026-09-30\n#업무/수업성적/성적관리\n",
        encoding="utf-8",
    )
    got, excluded = cw.collect_10areas(tmp_path, date(2026, 9, 28), date(2026, 10, 4))
    titles = [n["title"] for n in got]
    assert "주내 완료" in titles and "1회성 처리" not in titles
    assert excluded == 1


def test_collect_14changes_skips_flagged(tmp_path):
    sub = tmp_path / "14_Changes" / "improvement" / "2026"
    sub.mkdir(parents=True)
    (sub / "skip.md").write_text(
        "---\ntype: improvement\nweekly_exclude: true\n---\n# 미완료 개발\n- [x] 반영 ✅ 2026-09-30\n#업무/수업성적/성적관리\n",
        encoding="utf-8",
    )
    got, excluded = cw.collect_14changes(tmp_path, date(2026, 9, 28), date(2026, 10, 4))
    assert got == [] and excluded == 1
