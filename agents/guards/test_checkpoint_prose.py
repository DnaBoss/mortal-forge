"""Checkpoint prose guard regressions without creating a Git repository."""
import unittest
import write_guard


class CheckpointProseTest(unittest.TestCase):
    def rule(self, cmd):
        return write_guard.verdict({'tool_input': {'cmd': cmd}})[0]

    def test_simplified_human_fields_denied(self):
        for option in ['target', 'proven', 'not-proven', 'risk', 'next', 'reason', 'impact', 'source', 'check']:
            for value in [f'--{option} "\u65f6\u6548"', f'--{option}=\u9a8c\u8bc1']:
                with self.subTest(value=value):
                    self.assertEqual(self.rule('~/tools/cash-rule-checkpoint x.checkpoints.jsonl ' + value), 'checkpoint-prose')

    def test_traditional_and_paths_allowed(self):
        self.assertIsNone(self.rule('~/tools/cash-rule-checkpoint /\u65f6/x.checkpoints.jsonl --target "\u6642\u6548\u9a57\u8b49" --evidence file=/\u9a8c/result.json'))

    def test_unrelated_commands_allowed(self):
        self.assertIsNone(self.rule('echo "cash-rule-checkpoint --target \u65f6\u6548"'))
        self.assertIsNone(self.rule('python3 unrelated.py --target "\u65f6\u6548"'))

    def test_wrapped_and_multiline_commands(self):
        self.assertEqual(self.rule('env FOO=1 ~/tools/cash-rule-checkpoint x.checkpoints.jsonl --target "\u65f6\u6548"'), 'checkpoint-prose')
        self.assertEqual(self.rule('date\npython3 /tmp/cash_rule_checkpoint.py x.checkpoints.jsonl --target "\u65f6\u6548"'), 'checkpoint-prose')
        self.assertEqual(self.rule('date; ~/tools/cash-rule-checkpoint x.checkpoints.jsonl --target "A;\u65f6\u6548"'), 'checkpoint-prose')

    def test_other_command_fields_not_scanned(self):
        self.assertIsNone(self.rule('~/tools/cash-rule-checkpoint x.checkpoints.jsonl --target "ASCII"; echo --target "\u65f6\u6548"'))

    def test_malformed_text_fails_open(self):
        self.assertIsNone(self.rule('~/tools/cash-rule-checkpoint --target "unterminated'))


if __name__ == '__main__':
    unittest.main()
