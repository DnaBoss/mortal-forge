import tempfile
from pathlib import Path
import unittest
import write_guard


class DocsPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'docs').mkdir()
        (self.root / 'docs/known.md').write_text('fixture')

    def tearDown(self):
        self.tmp.cleanup()

    def rule(self, body, **extra):
        return write_guard.verdict({'cwd': '/nonexistent', 'tool_input': {
            'cmd': "python3 - <<'PY'\n" + body + '\nPY',
            'workdir': str(self.root), **extra}})[0]

    def test_missing_direct_denied(self):
        self.assertEqual(self.rule("value = Path('docs/missing.md').read_text()"), 'docs-read-path')

    def test_missing_assigned_denied(self):
        self.assertEqual(self.rule("p = Path('docs/missing.md'); s = p.read_text()"), 'docs-read-path')

    def test_existing_allowed(self):
        self.assertIsNone(self.rule("p = Path('docs/known.md'); s = p.read_text()"))

    def test_new_write_allowed(self):
        self.assertIsNone(self.rule("p = Path('docs/new.md'); p.write_text('new')"))

    def test_create_then_read_allowed(self):
        self.assertIsNone(self.rule("p = Path('docs/new.md'); p.write_text('new'); value = p.read_text()"))

    def test_direct_create_then_read_allowed(self):
        self.assertIsNone(self.rule("Path('docs/new.md').write_text('new'); value = Path('docs/new.md').read_text()"))

    def test_absolute_allowed(self):
        self.assertIsNone(self.rule("Path('/nonexistent/docs/new.md').read_text()"))

    def test_dynamic_allowed(self):
        self.assertIsNone(self.rule("Path(value).read_text()"))

    def test_unrelated_path_allowed(self):
        self.assertIsNone(self.rule("Path('cache/new.json').read_text()"))

    def test_reassigned_allowed(self):
        self.assertIsNone(self.rule("p = Path('docs/missing.md'); p = other; p.read_text()"))

    def test_changed_cwd_allowed(self):
        self.assertIsNone(self.rule("os.chdir(other); Path('docs/missing.md').read_text()"))

    def test_invalid_python_allowed(self):
        self.assertIsNone(self.rule("Path('docs/missing.md').read_text(??)"))

    def test_workdir_precedence(self):
        self.assertIsNone(self.rule("Path('docs/known.md').read_text()"))

    def test_not_python_allowed(self):
        payload = {'tool_input': {'cmd': "cat <<'PY'\nPath('docs/missing.md').read_text()\nPY", 'workdir': str(self.root)}}
        self.assertIsNone(write_guard.verdict(payload)[0])


if __name__ == '__main__':
    unittest.main()
