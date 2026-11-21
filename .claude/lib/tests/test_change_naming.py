#!/usr/bin/env python3
"""change_naming 규칙과 그것을 쓰는 세 곳(생성 스크립트·Rule 4 훅·note_rules Check 6)의 회귀 테스트."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
ROOT = LIB.parents[1]
sys.path.insert(0, str(LIB))
import change_naming as cn  # noqa: E402
import note_rules  # noqa: E402

HOOK = ROOT / ".claude" / "hooks" / "check-folder-rules.py"
GEN = {k: ROOT / ".claude" / "agents" / "workflows" / w / "scripts" / f"new_{k}_path.py"
       for k, w in (("incident", "incident-analyze"), ("improvement", "improvement-plan"))}


def parsed(stem):
    p = cn.parse_name(stem)
    assert p is not None, stem
    return p


def fm(**kv):
    base = {"type": "change", "change_type": "incident", "status": "open"}
    base.update(kv)
    body = "\n".join(f"{k}: {v}" for k, v in base.items() if v is not None)
    return f"---\n{body}\n---\n\n## 관련\n\n- #업무/수업성적\n"


class NameRule(unittest.TestCase):
    def test_parse_with_and_without_screen_id(self):
        p = parsed("2026-11-19 PATIS hl_3020701_u 전자출석부 강의일자 기본값 개선")
        self.assertEqual((p["date"], p["system"], p["screen_id"], p["summary"]),
                         ("2026-11-19", "PATIS", "hl_3020701_u", "전자출석부 강의일자 기본값 개선"))
        p = parsed("2026-10-23 홈페이지 게시글 대표 URL canonical 적용")
        self.assertEqual((p["system"], p["screen_id"]), ("홈페이지", ""))

    def test_parse_strips_folder_note_prefix_and_dup_suffix(self):
        p = parsed("_2024-01-26 PATIS 접근권한 및 보안관리 현황 점검")
        self.assertEqual(p["summary"], "접근권한 및 보안관리 현황 점검")
        p = parsed("2026-11-19 PATIS 저장 오류 (2)")
        self.assertEqual((p["summary"], p["dup"]), ("저장 오류", "2"))

    def test_parse_rejects_legacy_and_unknown_vocab(self):
        for stem in ("통합학사시스템 오류 처리 2026-04-10_1", "2026-11-19 포털 식단 연동 실패",
                     "2026-13-40 PATIS 날짜 오류", "hl_3020701_u 상벌 테이블 인덱스 개선"):
            self.assertIsNone(cn.parse_name(stem), stem)

    def test_build_normalizes_screen_id_and_rejects_bad_summary(self):
        self.assertEqual(cn.build_name("2026-06-25", "PATIS", "hl-3020906-v", "성적입력현황 성능 개선"),
                         "2026-06-25 PATIS hl_3020906_v 성적입력현황 성능 개선")
        for bad in ("a/b", "x" * 46, "부연 — 설명", "", "[링크]", "줄\n바꿈", "탭\t문자"):
            with self.assertRaises(ValueError):
                cn.build_name("2026-06-25", "PATIS", "", bad)
        with self.assertRaises(ValueError):
            cn.build_name("2026-06-25", "PATIS", "hl09", "약칭은 화면ID가 아님")

    def test_build_accepts_only_dashed_iso_date(self):
        for bad in ("20260625", "2026-W26-4", "2026-6-25", "2026-02-30"):
            with self.assertRaises(ValueError, msg=bad):
                cn.build_name(bad, "PATIS", "", "저장 오류")

    def test_build_rejects_summary_starting_with_screen_id_when_screen_id_empty(self):
        with self.assertRaises(ValueError):
            cn.build_name("2026-06-25", "PATIS", "", "hl_3020701_u 외 2개 화면 조회 개선")
        self.assertIsNotNone(cn.build_name("2026-06-25", "PATIS", "hl_3020701_u", "hl_3020702_u 연계 조회 개선"))

    def test_compute_path_half_year_and_collision_across_kinds(self):
        with tempfile.TemporaryDirectory() as d:
            v = pathlib.Path(d)
            p = cn.compute_path(v, "incident", "2026-07-01", "PATIS", "", "저장 오류")
            self.assertEqual(p.relative_to(v).as_posix(), "14_Changes/incident/2026/하반기/2026-07-01 PATIS 저장 오류.md")
            other = v / "14_Changes/improvement/2026/상반기"
            other.mkdir(parents=True)
            (other / "2026-07-01 PATIS 저장 오류.md").write_text("x", encoding="utf-8")
            p = cn.compute_path(v, "incident", "2026-07-01", "PATIS", "", "저장 오류")
            self.assertEqual(p.name, "2026-07-01 PATIS 저장 오류 (2).md")

    def test_compute_path_collision_ignores_case(self):
        with tempfile.TemporaryDirectory() as d:
            v = pathlib.Path(d)
            folder = v / "14_Changes/incident/2026/하반기"
            folder.mkdir(parents=True)
            (folder / "2026-07-01 PATIS API 저장 오류.md").write_text("x", encoding="utf-8")
            p = cn.compute_path(v, "incident", "2026-07-01", "PATIS", "", "api 저장 오류")
            self.assertEqual(p.name, "2026-07-01 PATIS api 저장 오류 (2).md")


class Generators(unittest.TestCase):
    def run_gen(self, kind, *args):
        with tempfile.TemporaryDirectory() as d:
            return subprocess.run([sys.executable, str(GEN[kind]), "--vault", d, *args],
                                  capture_output=True, text=True, encoding="utf-8",
                                  env={**os.environ, "PYTHONIOENCODING": "utf-8"})

    def test_incident_generator_prints_path(self):
        r = self.run_gen("incident", "--date", "2026-04-10", "--system", "PATIS",
                         "--screen-id", "hl_3020303_u", "--summary", "담당교수관리 PK 중복 오류")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().replace("\\", "/").endswith(
            "14_Changes/incident/2026/상반기/2026-04-10 PATIS hl_3020303_u 담당교수관리 PK 중복 오류.md"))

    def test_improvement_generator_rejects_unknown_system(self):
        r = self.run_gen("improvement", "--date", "2026-04-10", "--system", "코러스", "--summary", "연계")
        self.assertEqual(r.returncode, 2)
        self.assertIn("system", r.stderr)


class FolderHookRule4(unittest.TestCase):
    def hook(self, path):
        r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_input": {"file_path": path}}),
                           capture_output=True, text=True, encoding="utf-8")
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""

    def test_legacy_incident_name_warns(self):
        self.assertIn("파일명 규칙 위반", self.hook("C:/V/14_Changes/incident/2026/하반기/통합학사시스템 오류 처리 2026-11-20_1.md"))

    def test_legacy_free_improvement_name_warns(self):
        self.assertIn("파일명 규칙 위반", self.hook("C:/V/14_Changes/improvement/2026/하반기/수강신청 로그 개선.md"))

    def test_hook_delegates_to_change_naming_without_own_filename_regex(self):
        src = HOOK.read_text(encoding="utf-8")
        self.assertIn("change_naming.parse_name(", src)
        self.assertNotIn("오류 처리", src)
        self.assertNotIn(r"\d{4}-\d{2}-\d{2}", src)

    def test_new_names_pass_including_folder_note(self):
        self.assertEqual(self.hook("C:/V/14_Changes/incident/2026/하반기/2026-11-20 PATIS hl_3020701_u 저장 오류.md"), "")
        self.assertEqual(self.hook("C:/V/14_Changes/improvement/2024/상반기/2024-01-26 PATIS 점검/_2024-01-26 PATIS 점검.md"), "")


class NoteRulesCheck6(unittest.TestCase):
    P = "/v/14_Changes/incident/2026/하반기/2026-11-19 PATIS hl_3020701_u 저장 오류.md"

    def test_consistent_note_passes(self):
        self.assertEqual(note_rules.check(self.P, fm(system="PATIS", screen_id="hl_3020701_u", date="2026-11-19")), [])

    def test_missing_fields_reported(self):
        v = note_rules.check(self.P, fm())
        self.assertTrue(any("system: 없음" in x for x in v))
        self.assertTrue(any("date: 없음" in x for x in v))

    def test_filename_frontmatter_mismatch_reported(self):
        v = note_rules.check(self.P, fm(system="sugang", date="2026-11-18"))
        self.assertTrue(any("system 불일치" in x for x in v))
        self.assertTrue(any("date 불일치" in x for x in v))
        self.assertTrue(any("screen_id 불일치" in x for x in v))

    def test_bad_vocab_and_screen_format(self):
        v = note_rules.check("/v/14_Changes/improvement/2026/하반기/x.md",
                             fm(change_type="improvement", system="포털", date="2026.11.19", screen_id="HL0602"))
        self.assertTrue(any("비표준 system" in x for x in v))
        self.assertTrue(any("date 형식" in x for x in v))
        self.assertTrue(any("screen_id 형식" in x for x in v))

    def test_inline_yaml_comments_are_not_values(self):
        text = fm(system="PATIS\t# 시스템", screen_id="# 여러 화면", date="2026-11-18 # 발생일")
        v = note_rules.check("/v/14_Changes/incident/2026/하반기/2026-11-18 PATIS 저장 오류.md", text)
        self.assertEqual(v, [])

    def test_index_note_exempt(self):
        self.assertEqual([x for x in note_rules.check("/v/14_Changes/incident/_Changes.md",
                         "---\ntype: index\nstatus: active\n---\n") if "system" in x], [])


if __name__ == "__main__":
    unittest.main()
