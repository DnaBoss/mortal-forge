"""Tests for lessons_context.select: 30-day window, guard filter, budget. Run: python3 -m unittest test_lessons_context -v"""
import datetime as dt
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lessons_context as lc  # noqa: E402

TODAY = dt.date(2026, 10, 15)


def entry(day, body="x", guarded=False):
    text = f"## {day} lesson {body}\n- 錯：{body}\n"
    if guarded:
        text += "- guard: write_guard.py some-rule\n"
    return text


class SelectTests(unittest.TestCase):
    def test_project_scope_and_common_lessons(self):
        text = ("# h\n\n" + entry("2026-10-12", "scoped")
                + '- projects: ["/tmp/project"]\n'
                + entry("2026-10-13", "common"))
        self.assertIn("lesson scoped", lc.select(text, today=TODAY, cwd="/tmp/project/src"))
        for cwd in [None, "/tmp/project-other", "/elsewhere"]:
            out = lc.select(text, today=TODAY, cwd=cwd)
            self.assertNotIn("lesson scoped", out)
            self.assertIn("lesson common", out)

    def test_invalid_scope_is_not_global(self):
        for scope in ['[]', '["relative"]', 'not-json', 'null']:
            text = entry("2026-10-12", "invalid") + f"- projects: {scope}\n"
            self.assertNotIn("lesson invalid", lc.select(text, today=TODAY, cwd="/tmp"))

    def test_project_alias_and_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "project").mkdir()
            (root / "alias").symlink_to(root / "project", target_is_directory=True)
            text = ("# h\n\n" + entry("2026-10-10", "scoped")
                    + f'- projects: ["{root / "project"}"]\n'
                    + entry("2026-10-13", "x" * 200))
            out = lc.select(text, budget=300, today=TODAY, cwd=str(root / "alias"))
            self.assertIn("lesson scoped", out)
            self.assertNotIn("x" * 200, out)

    def test_old_entries_are_dropped_and_counted(self):
        text = "# header\n\n" + entry("2026-08-01", "old") + entry("2026-10-10", "new")
        out = lc.select(text, budget=9000, today=TODAY)
        self.assertIn("lesson new", out)
        self.assertNotIn("lesson old", out)
        self.assertIn("1 條超過 30 天未載入", out)

    def test_boundary_30_days_is_kept(self):
        text = "# h\n\n" + entry("2026-09-15", "edge") + entry("2026-09-14", "beyond")
        out = lc.select(text, budget=9000, today=TODAY)
        self.assertIn("lesson edge", out)
        self.assertNotIn("lesson beyond", out)

    def test_guarded_recent_entry_is_not_injected(self):
        text = "# h\n\n" + entry("2026-10-10", "guarded", guarded=True) + entry("2026-10-11", "plain")
        out = lc.select(text, budget=9000, today=TODAY)
        self.assertNotIn("lesson guarded", out)
        self.assertIn("lesson plain", out)
        self.assertIn("1 條已由 guard 機械擋下", out)

    def test_undated_entries_count_as_old(self):
        text = "# h\n\n1. legacy numbered lesson\n" + entry("2026-10-12", "dated")
        out = lc.select(text, budget=9000, today=TODAY)
        self.assertNotIn("legacy numbered", out)
        self.assertIn("lesson dated", out)

    def test_budget_keeps_newest(self):
        text = "# h\n\n" + entry("2026-10-01", "a" * 3000) + entry("2026-10-12", "b" * 3000)  # each entry ~6,050 bytes
        out = lc.select(text, budget=7000, today=TODAY)
        self.assertIn("b" * 3000, out)
        self.assertNotIn("a" * 3000, out)


if __name__ == "__main__":
    unittest.main()
