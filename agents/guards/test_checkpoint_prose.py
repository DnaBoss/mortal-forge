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


    def test_new_observed_glyphs_in_all_prose_fields_denied(self):
        for glyph in ['\u4e24', '\u8f6e', '\u9759', '\u6765', '\u9605', '\u7ed3', '\u95f4']:
            for option in ['target','proven','not-proven','risk','next','reason','impact','source','check']:
                with self.subTest(glyph=ord(glyph), option=option):
                    self.assertEqual(self.rule('~/tools/cash-rule-checkpoint x.checkpoints.jsonl --'+option+' "'+glyph+'"'), 'checkpoint-prose')

    def test_new_glyphs_do_not_scan_paths_or_unrelated_tools(self):
        self.assertIsNone(self.rule('~/tools/cash-rule-checkpoint /\u8f6e/x.checkpoints.jsonl --target "\u5169\u8f2a\u975c\u4f86\u95b1\u7d50\u9593" --evidence file=/\u9759/result.json'))
        self.assertIsNone(self.rule('python3 unrelated.py --target "\u4e24\u8f6e"'))



    def test_mall_observed_glyphs_in_prose_denied(self):
        for glyph in ['\u590d','\u7ec8','\u9879','\u8fdb']:
            for option in ['target','proven','not-proven','risk','next','reason','impact','source','check']:
                with self.subTest(glyph=ord(glyph), option=option):
                    self.assertEqual(self.rule('~/tools/cash-rule-checkpoint x.checkpoints.jsonl --'+option+' "'+glyph+'"'), 'checkpoint-prose')

    def test_mall_traditional_and_technical_paths_allowed(self):
        self.assertIsNone(self.rule('~/tools/cash-rule-checkpoint /\u590d/x.checkpoints.jsonl --target "\u6062\u5fa9\u7d42\u7aef\u56db\u9805" --evidence file=/\u7ec8/result.json'))
        self.assertIsNone(self.rule('python3 unrelated.py --target "\u590d\u7ec8\u9879"'))

if __name__ == '__main__':
    unittest.main()

class StatisticalGlyphsTest(unittest.TestCase):
    def test_both_observed_glyphs_denied_in_prose(self):
        for glyph in ['\u7edf','\u8ba1']:
            for option in ['target','proven','not-proven','risk','next','reason','impact','source','check']:
                with self.subTest(glyph=ord(glyph),option=option):
                    payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --'+option+' "'+glyph+'"'}}
                    self.assertEqual(write_guard.verdict(payload)[0],'checkpoint-prose')
    def test_traditional_and_technical_paths_keep_original_boundary(self):
        payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint /\u7edf/x.checkpoints.jsonl --target "統計" --evidence file=/\u8ba1/result.json'}}
        self.assertIsNone(write_guard.verdict(payload)[0])

class ReadGlyphTest(unittest.TestCase):
    def test_observed_read_glyph_in_prose_is_denied(self):
        for option in ['target','proven','not-proven','risk','next','reason','impact','source','check']:
            with self.subTest(option=option):
                payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --'+option+' "\u8bfb"'}}
                self.assertEqual(write_guard.verdict(payload)[0],'checkpoint-prose')

class QueryObservedGlyphTest(unittest.TestCase):
    def test_both_observed_glyphs_denied_in_prose(self):
        for glyph in ['\u79bb','\u8054']:
            for option in ['target','proven','not-proven','risk','next','reason','impact','source','check']:
                with self.subTest(glyph=ord(glyph),option=option):
                    payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --'+option+' "'+glyph+'"'}}
                    self.assertEqual(write_guard.verdict(payload)[0],'checkpoint-prose')
    def test_traditional_and_path_boundaries_preserved(self):
        payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint /\u79bb/x.checkpoints.jsonl --target "離線聯驗" --evidence file=/\u8054/result.json'}}
        self.assertIsNone(write_guard.verdict(payload)[0])
        self.assertIsNone(write_guard.verdict({'tool_input':{'cmd':'python3 unrelated.py --target "\u79bb\u8054"'}})[0])


class HistoryObservedGlyphTest(unittest.TestCase):
    def test_observed_glyphs_denied_in_human_fields(self):
        for glyph in ['\u5f53', '\u5199']:
            for option in ['target','proven','not-proven','risk','next','reason','impact','source','check']:
                for suffix in [' "'+glyph+'"', '='+glyph]:
                    with self.subTest(glyph=ord(glyph), option=option, suffix=suffix):
                        payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --'+option+suffix}}
                        self.assertEqual(write_guard.verdict(payload)[0], 'checkpoint-prose')
    def test_traditional_paths_and_unrelated_commands_allowed(self):
        payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint /\u5f53/x.checkpoints.jsonl --target "當來源寫入" --evidence file=/\u5199/result.json'}}
        self.assertIsNone(write_guard.verdict(payload)[0])
        self.assertIsNone(write_guard.verdict({'tool_input':{'cmd':'python3 unrelated.py --target "\u5f53\u5199"'}})[0])


class NegativeControlProseTest(unittest.TestCase):
    def test_registered_bad_glyph_in_procedure_denied(self):
        payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --neg "\u9519字對照=>file=/tmp/result.json"'}}
        self.assertEqual(write_guard.verdict(payload)[0], 'checkpoint-prose')
    def test_negative_control_locator_keeps_literal_path(self):
        payload={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --neg "刻意失敗=>file=/\u9519/result.json"'}}
        self.assertIsNone(write_guard.verdict(payload)[0])

class PointGlyphTest(unittest.TestCase):
    def test_point_glyph(self):
        bad={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --target "\u70b9\u6578"'}}
        good={'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --target "\u9ede\u6578"'}}
        self.assertEqual(write_guard.verdict(bad)[0],'checkpoint-prose')
        self.assertIsNone(write_guard.verdict(good)[0])
