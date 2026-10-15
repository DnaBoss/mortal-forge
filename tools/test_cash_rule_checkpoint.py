"""Tests for the burden-cut gates of cash_rule_checkpoint.py (heartbeat rejection, wait bar, no usage).

Run: python3 -I ~/tools/test_cash_rule_checkpoint.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

TOOL = pathlib.Path.home() / "tools/cash-rule-checkpoint"


def run(file, *extra):
    base = [str(TOOL), str(file), "--task", "t-test", "--executor", "codex"]
    return subprocess.run(base + list(extra), capture_output=True, text=True, timeout=120)


class CheckpointGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = pathlib.Path(self.tmp.name) / "t.checkpoints.jsonl"
        r = run(self.file, "--step", "S01", "--task-state", "PLANNED", "--step-state", "READY", "--target", "plan",
                "--evidence", "file=/tmp/a")
        self.assertEqual(r.returncode, 0, r.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def records(self):
        return [json.loads(l) for l in self.file.read_text().splitlines() if l.strip()]

    def test_no_usage_fields_written(self):
        rec = self.records()[0]
        self.assertNotIn("usage", rec)
        self.assertNotIn("telemetry_mode", rec)

    def test_identical_repeat_is_rejected(self):
        r = run(self.file, "--step", "S01", "--task-state", "PLANNED", "--step-state", "READY", "--target", "plan again",
                "--evidence", "file=/tmp/a")
        self.assertEqual(r.returncode, 1)
        self.assertIn("無狀態變化", r.stderr)
        self.assertEqual(len(self.records()), 1)

    def test_repeat_with_new_evidence_is_accepted(self):
        r = run(self.file, "--step", "S01", "--task-state", "PLANNED", "--step-state", "READY", "--target", "plan again",
                "--evidence", "file=/tmp/b")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.records()), 2)

    def test_state_change_is_accepted_without_new_evidence(self):
        r = run(self.file, "--step", "S01", "--task-state", "RUNNING", "--step-state", "RUNNING", "--target", "go",
                "--evidence", "file=/tmp/a", "--acceptance", "A1")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_wait_without_alternatives_is_rejected(self):
        r = run(self.file, "--step", "S01", "--task-state", "WAITING", "--step-state", "READY", "--target", "wait",
                "--decision", "wait")
        self.assertEqual(r.returncode, 1)
        self.assertIn("等人門檻", r.stderr)

    def test_wait_with_alternatives_is_recorded(self):
        r = run(self.file, "--step", "S01", "--task-state", "WAITING", "--step-state", "READY", "--target", "wait",
                "--decision", "wait", "--wait-on", "cash: 核准花費", "--wait-tried", "web=>無免費替代",
                "--wait-tried", "other-ai=>同意需人核准")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.records()[-1]
        self.assertEqual(rec["blockers"][0], "wait_on: cash: 核准花費")
        self.assertEqual(len(rec["blockers"]), 3)


if __name__ == "__main__":
    unittest.main()
