import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from turn_context import SKILL, context


class TurnContextTests(unittest.TestCase):
    def test_every_prompt_is_injected_without_classifying_user_text(self):
        expected = SKILL.read_text(encoding="utf-8").split("---", 2)[2].strip()
        for prompt in ["Open LINE", "Fix the API", "Continue", "Open LINE"]:
            with self.subTest(prompt=prompt):
                result = context({"hook_event_name": "UserPromptSubmit", "prompt": prompt})
                self.assertEqual(result["hookSpecificOutput"]["additionalContext"], expected)
                self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")

    def test_session_start_including_compaction(self):
        for source in ["startup", "resume", "compact"]:
            self.assertIn("hookSpecificOutput", context({"hook_event_name": "SessionStart", "source": source}))

    def test_unrelated_events_have_no_effect(self):
        for event in ["Stop", "PreToolUse", "PostToolUse", None]:
            self.assertEqual(context({"hook_event_name": event}), {})

    def test_missing_or_empty_skill_is_not_reported_as_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            with self.assertRaises(OSError):
                context({"hook_event_name": "UserPromptSubmit"}, path)
            path.write_text("---\nname: empty\n---\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                context({"hook_event_name": "UserPromptSubmit"}, path)

    def test_cli_returns_json_and_does_not_echo_prompt(self):
        command = [sys.executable, str(Path(__file__).with_name("turn_context.py"))]
        result = subprocess.run(command, input=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "PRIVATE_SENTINEL"}), text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn("hookSpecificOutput", json.loads(result.stdout))
        self.assertNotIn("PRIVATE_SENTINEL", result.stdout + result.stderr)

    def test_invalid_input_fails_without_echoing_content(self):
        command = [sys.executable, str(Path(__file__).with_name("turn_context.py"))]
        for value in ["PRIVATE_SENTINEL", "[]", "null"]:
            result = subprocess.run(command, input=value, text=True, capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn(value, result.stderr)


if __name__ == "__main__":
    unittest.main()
