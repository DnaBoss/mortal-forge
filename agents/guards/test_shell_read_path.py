import tempfile
from pathlib import Path
import unittest
import write_guard


class ShellReadPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'known.rs').write_text('fixture')
        (self.root / 'known file.md').write_text('fixture')

    def tearDown(self):
        self.temp.cleanup()

    def rule(self, command):
        return write_guard.verdict({'tool_input': {'cmd': command, 'workdir': str(self.root)}})[0]

    def test_missing_alternation_pattern_denied(self):
        self.assertEqual(self.rule("rg -n 'turn_label|size_flags' absent.gd"), 'shell-read-path')

    def test_missing_piped_read_denied(self):
        self.assertEqual(self.rule("rg -n 'a|b' absent.gd | head -25"), 'shell-read-path')

    def test_missing_second_input_with_inventory_denied(self):
        self.assertEqual(self.rule("cat known.rs absent.md; rg --files . | head -25"), 'shell-read-path')

    def test_missing_after_known_read_denied(self):
        self.assertEqual(self.rule("cat known.rs; rg -n pattern absent.rs"), 'shell-read-path')

    def test_existing_pipeline_allowed(self):
        self.assertIsNone(self.rule("rg -n 'a|b' known.rs | head -25"))

    def test_create_then_piped_read_allowed(self):
        self.assertIsNone(self.rule("touch absent.md; cat absent.md | head -25"))

    def test_quoted_operator_path_allowed(self):
        (self.root / 'known|file.md').write_text('fixture')
        self.assertIsNone(self.rule("cat 'known|file.md'"))

    def test_pipeline_write_allowed(self):
        self.assertIsNone(self.rule("cat absent.md | tee created.md"))

    def test_missing_rg_denied(self):
        self.assertEqual(self.rule('rg -n pattern absent.rs'), 'shell-read-path')

    def test_missing_sed_denied(self):
        self.assertEqual(self.rule("sed -n '1,20p' absent.md"), 'shell-read-path')

    def test_missing_absolute_cat_denied(self):
        self.assertEqual(self.rule('cat ' + str(self.root / 'absent.md')), 'shell-read-path')

    def test_missing_tail_denied(self):
        self.assertEqual(self.rule('tail -n 5 absent.log'), 'shell-read-path')

    def test_missing_head_denied(self):
        self.assertEqual(self.rule('head -n 5 absent.log'), 'shell-read-path')

    def test_existing_rg_allowed(self):
        self.assertIsNone(self.rule('rg -n pattern known.rs'))

    def test_existing_sed_allowed(self):
        self.assertIsNone(self.rule("sed -n '1,20p' known.rs"))

    def test_quoted_existing_allowed(self):
        self.assertIsNone(self.rule("cat 'known file.md'"))

    def test_directory_search_allowed(self):
        self.assertIsNone(self.rule("rg -n pattern . -g '*.rs'"))

    def test_inventory_allowed(self):
        self.assertIsNone(self.rule("rg --files . -g '*missing*'"))

    def test_regex_paths_are_patterns(self):
        self.assertIsNone(self.rule("rg -n 'missing/path.rs' known.rs"))

    def test_dynamic_allowed(self):
        self.assertIsNone(self.rule('cat $TARGET'))

    def test_new_write_allowed(self):
        self.assertIsNone(self.rule('cat > absent.md'))

    def test_create_then_read_allowed(self):
        self.assertIsNone(self.rule('touch absent.md\ncat absent.md'))

    def test_heredoc_allowed(self):
        self.assertIsNone(self.rule("python3 - <<'PY'\nprint('cat absent.md')\nPY"))

    def test_explicit_regexp_allowed(self):
        self.assertIsNone(self.rule("rg -n -e missing/path.rs known.rs"))

    def test_missing_numbered_cat_denied(self):
        self.assertEqual(self.rule('cat -n absent.rs'), 'shell-read-path')

    def test_missing_counted_rg_denied(self):
        self.assertEqual(self.rule('rg -c pattern absent.rs'), 'shell-read-path')

    def test_missing_extensionless_file_denied(self):
        self.assertEqual(self.rule('cat README'), 'shell-read-path')

    def test_existing_numbered_cat_allowed(self):
        self.assertIsNone(self.rule('cat -n known.rs'))

    def test_existing_extensionless_file_allowed(self):
        (self.root / 'README').write_text('fixture')
        self.assertIsNone(self.rule('cat README'))


if __name__ == '__main__':
    unittest.main()
