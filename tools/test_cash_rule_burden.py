"""Fixture tests for cash_rule_burden metric functions (no real data read)."""
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/home/cash/tools")
import cash_rule_burden as b  # noqa: E402

T0 = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
SINCE = T0 - timedelta(days=1)


def ck(task, i, hours, task_state, step, step_state):
    return ({"task_id": task, "iteration": i, "recorded_at": (T0 + timedelta(hours=hours)).isoformat(),
             "task_state": task_state, "step_id": step, "step_state": step_state,
             "usage": {"input_tokens": {"status": "exact" if i == 1 else "unavailable"}}}, "/x/a.checkpoints.jsonl", 100)


class CheckpointTests(unittest.TestCase):
    def test_counts_repeats_waiting_and_long_tasks(self):
        recs = [ck("t1", 1, 0, "RUNNING", "S1", "RUNNING"), ck("t1", 2, 1, "RUNNING", "S1", "RUNNING"),  # repeat
                ck("t1", 3, 2, "WAITING", "S1", "RUNNING"), ck("t1", 4, 5, "RUNNING", "S2", "RUNNING"),  # 3 h waiting
                ck("t2", 1, 0, "PLANNED", "S1", "READY"), ck("t2", 2, 0.5, "COMPLETE", "S1", "DONE"),
                (None, "/x/a.checkpoints.jsonl", 10)]
        m, rows = b.checkpoint_metrics(recs, SINCE)
        self.assertEqual(m["tasks"], 2)
        self.assertEqual(m["records"], 6)
        self.assertEqual(m["bad_lines"], 1)
        self.assertEqual(m["repeat_records"], 1)
        self.assertEqual(m["waiting_records"], 1)
        self.assertAlmostEqual(m["waiting_hours"], 3.0)
        self.assertEqual(m["tasks_ge_4h"], 1)
        self.assertEqual(m["records_in_tasks_ge_4h"], 4)
        self.assertAlmostEqual(m["records_per_hour_in_tasks_ge_4h"], 0.8)
        self.assertEqual(m["usage_exact_records"], 2)
        self.assertEqual(m["final_state"], {"RUNNING": 1, "COMPLETE": 1})
        self.assertEqual(m["bytes_total"], 600)

    def test_records_before_window_are_ignored(self):
        old = ck("t1", 1, -72, "RUNNING", "S1", "RUNNING")
        m, _ = b.checkpoint_metrics([old], SINCE)
        self.assertEqual(m["records"], 0)
        self.assertEqual(m["tasks"], 0)


class ClaudeTests(unittest.TestCase):
    def rec(self, typ, content, **extra):
        r = {"type": typ, "timestamp": T0.isoformat(), "message": {"content": content}}
        r.update(extra)
        return r

    def test_text_tokens_and_dedupe(self):
        usage = {"input_tokens": 10, "cache_read_input_tokens": 90, "cache_creation_input_tokens": 0, "output_tokens": 7}
        recs = [("s1", self.rec("user", "問題")),
                ("s1", self.rec("assistant", [{"type": "thinking", "thinking": "x"}], message={"id": "m1", "usage": usage, "content": [{"type": "thinking"}]})),
                ("s1", self.rec("assistant", None, message={"id": "m1", "usage": usage, "content": [{"type": "text", "text": "回答十個字元在這裡。"}]})),
                ("s1", self.rec("assistant", None, message={"id": "m1", "usage": usage, "content": [{"type": "tool_use", "name": "Bash"}]})),
                ("s1", self.rec("user", [{"type": "tool_result", "content": "big output"}])),
                ("s1", self.rec("user", "長長的壓縮摘要" * 50, isCompactSummary=True)),
                ("s2", self.rec("user", "另一個", isSidechain=True))]
        m = b.claude_metrics(recs, SINCE)
        self.assertEqual(m["sessions"], 2)
        self.assertEqual(m["human_prompts"], 1)
        self.assertEqual(m["human_chars"], 2)
        self.assertEqual(m["api_calls"], 1)  # three blocks of one message count once
        self.assertEqual(m["context_tokens_per_call"]["median"], 100)
        self.assertEqual(m["assistant_text_messages"], 1)
        self.assertEqual(m["assistant_text_chars"], 10)
        self.assertEqual(m["tool_uses"], 1)
        self.assertEqual(m["compactions"], 1)
        self.assertEqual(m["sidechain_records"], 1)
        self.assertEqual(m["ai_chars_per_human_char"], 5.0)


class CodexTests(unittest.TestCase):
    def test_skips_injected_blocks_and_uses_input_tokens(self):
        def msg(role, text):
            return ("c1", {"type": "response_item", "timestamp": T0.isoformat(), "payload": {"type": "message", "role": role, "content": [{"type": "input_text", "text": text}]}})
        recs = [msg("user", "<environment_context>...</environment_context>"), msg("user", "做這件事"), msg("developer", "# AGENTS"),
                msg("assistant", "好的，做完了。"),
                ("c1", {"type": "event_msg", "timestamp": T0.isoformat(), "payload": {"type": "token_count", "info": {"last_token_usage": {"input_tokens": 35509, "cached_input_tokens": 12928}}}})]
        m = b.codex_metrics(recs, SINCE)
        self.assertEqual(m["user_messages"], 1)
        self.assertEqual(m["user_chars"], 4)
        self.assertEqual(m["assistant_chars"], 7)
        self.assertEqual(m["context_tokens_per_turn"]["median"], 35509)


class GuardTests(unittest.TestCase):
    def test_window_and_deny_rules(self):
        inside = (T0.isoformat())
        outside = (T0 - timedelta(days=30)).isoformat()
        lines = {"write_guard": [{"at": inside, "verdict": "deny", "rule": "pkill-full"}, {"at": inside, "verdict": "allow"},
                                 {"at": outside, "verdict": "deny", "rule": "old"}, None],
                 "finish_check": [{"at": inside, "blocked": True}, {"at": inside, "blocked": False}]}
        m = b.guard_metrics(lines, SINCE)
        self.assertEqual(m["write_guard"]["events"], 2)
        self.assertEqual(m["write_guard"]["deny"], 1)
        self.assertEqual(m["write_guard"]["top_deny_rules"], [("pkill-full", 1)])
        self.assertEqual(m["finish_check"]["blocked"], 1)


class LoopTests(unittest.TestCase):
    def test_sizes(self):
        m = b.loop_metrics([100, 300, 200])
        self.assertEqual(m["files"], 3)
        self.assertEqual(m["chars_total"], 600)
        self.assertEqual(m["chars_median"], 200)


if __name__ == "__main__":
    unittest.main()
