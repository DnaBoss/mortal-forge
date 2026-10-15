"""Tests for the write_guard loop-size rule. Run: python3 -m unittest test_loop_size -v"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import write_guard as wg  # noqa: E402


def decide(payload, home):
    env = dict(os.environ, HOME=home)
    r = subprocess.run([sys.executable, str(HERE / "write_guard.py")], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=60)
    if not r.stdout.strip():
        return "allow", None
    spec = json.loads(r.stdout)["hookSpecificOutput"]
    return ("deny" if spec.get("permissionDecision") == "deny" else "warn"), spec.get("permissionDecisionReason")


class LoopSizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.loop = os.path.join(self.tmp.name, "task.loop.md")
        with open(self.loop, "w", encoding="utf-8") as fh:
            fh.write("# LOOP\n" + "狀態" * 1400)  # 2807 chars

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_over_limit_is_denied(self):
        verdict, reason = decide({"tool_name": "Write", "tool_input": {"file_path": self.loop, "content": "x" * 3001}}, self.tmp.name)
        self.assertEqual(verdict, "deny")
        self.assertIn("LOOP 檔上限", reason)

    def test_write_within_limit_is_allowed(self):
        verdict, _ = decide({"tool_name": "Write", "tool_input": {"file_path": self.loop, "content": "x" * 3000}}, self.tmp.name)
        self.assertEqual(verdict, "allow")

    def test_edit_that_crosses_limit_is_denied(self):
        verdict, _ = decide({"tool_name": "Edit", "tool_input": {"file_path": self.loop, "old_string": "# LOOP", "new_string": "# LOOP" + "y" * 300}}, self.tmp.name)
        self.assertEqual(verdict, "deny")

    def test_edit_that_shrinks_is_allowed(self):
        verdict, _ = decide({"tool_name": "Edit", "tool_input": {"file_path": self.loop, "old_string": "狀態" * 100, "new_string": ""}}, self.tmp.name)
        self.assertEqual(verdict, "allow")

    def test_other_markdown_is_not_limited(self):
        other = os.path.join(self.tmp.name, "notes.md")
        verdict, _ = decide({"tool_name": "Write", "tool_input": {"file_path": other, "content": "x" * 5000}}, self.tmp.name)
        self.assertEqual(verdict, "allow")

    def test_pure_function(self):
        self.assertEqual(wg.loop_over_limit({"file_path": "/x/a.loop.md", "content": "a" * 3001}), 3001)
        self.assertIsNone(wg.loop_over_limit({"file_path": "/x/a.loop.md", "content": "a" * 10}))


if __name__ == "__main__":
    unittest.main()
