import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import write_guard


class GitSourcePathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        def git(*args):
            subprocess.run(['git', *args], cwd=self.repo, env=env,
                           check=True, capture_output=True)
        git('init')
        (self.repo / 'known file.txt').write_text('fixture')
        git('add', '.')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
            'commit', '-m', 'fixture')

    def tearDown(self):
        self.temp.cleanup()

    def verdict(self, args, **extra):
        return write_guard.verdict({'tool_input': {
            'cmd': shlex.join(['git', *args]), 'workdir': str(self.repo), **extra}})[0]

    def test_missing_denied(self):
        self.assertEqual(self.verdict(['show', 'HEAD:absent.rs']), 'git-source-path')

    def test_existing_quoted_space_allowed(self):
        self.assertIsNone(self.verdict(['show', 'HEAD:known file.txt']))

    def test_stat_allowed(self):
        self.assertIsNone(self.verdict(['show', '--stat', 'HEAD']))

    def test_unknown_revision_allowed(self):
        self.assertIsNone(self.verdict(['show', 'unknown:absent.rs']))

    def test_wrong_repository_fixed_revision_denied(self):
        self.assertEqual(self.verdict(['ls-tree', '-r', 'a' * 40]), 'git-source-revision')

    def test_dynamic_allowed(self):
        self.assertIsNone(self.verdict(['show', 'HEAD:$PATH']))

    def test_explicit_c_allowed(self):
        self.assertIsNone(self.verdict(['-C', str(self.repo), 'show', 'HEAD:known file.txt'], workdir='/tmp'))

    def test_workdir_overrides_payload_cwd(self):
        payload = {'cwd': '/tmp', 'tool_input': {'cmd': 'git show HEAD:absent.rs', 'workdir': str(self.repo)}}
        self.assertEqual(write_guard.verdict(payload)[0], 'git-source-path')

    def test_parent_git_environment_isolated(self):
        with patch.dict(os.environ, {'GIT_DIR': '/nonexistent/fixture', 'GIT_WORK_TREE': '/nonexistent/fixture'}):
            self.assertEqual(self.verdict(['show', 'HEAD:absent.rs']), 'git-source-path')


if __name__ == '__main__':
    unittest.main()
