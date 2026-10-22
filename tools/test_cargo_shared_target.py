#!/usr/bin/env python3
"""Real cargo + git worktree checks for cargo_shared_target.py."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

WRAPPER = Path(__file__).resolve().parent / 'cargo_shared_target.py'
REAL = shutil.which('cargo', path=str(Path.home() / '.cargo/bin'))


def sh(*args, cwd, env=None, check=True):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=300, check=check)


class SharedTargetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='cargo-shared-'))
        self.bin = self.tmp / 'bin'
        self.bin.mkdir()
        (self.bin / 'cargo').symlink_to(WRAPPER)
        self.env = dict(os.environ, PATH=f'{self.bin}:{Path(REAL).parent}:/usr/bin:/bin')
        for key in ('CARGO_TARGET_DIR', 'CARGO_SHARED_TARGET', 'CARGO_ALLOW_SEPARATE_TARGET'):
            self.env.pop(key, None)
        self.main = self.tmp / 'repo'
        self.main.mkdir()
        sh('git', 'init', '-q', '-b', 'main', cwd=self.main)
        (self.main / 'Cargo.toml').write_text('[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n')
        (self.main / 'src').mkdir()
        (self.main / 'src/lib.rs').write_text('pub fn one() -> u8 { 1 }\n')
        (self.main / '.gitignore').write_text('/target\n')
        sh('git', 'add', '.', cwd=self.main)
        sh('git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init', cwd=self.main)
        self.wt = self.tmp / 'wt'
        sh('git', 'worktree', 'add', '-q', str(self.wt), '-b', 'side', cwd=self.main)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_worktree_build_uses_main_target(self):
        sh('cargo', 'build', '--offline', cwd=self.wt, env=self.env)
        self.assertFalse((self.wt / 'target').exists())
        self.assertTrue((self.main / 'target/debug').is_dir())

    def test_negative_control_real_cargo_makes_separate_target(self):
        sh(REAL, 'build', '--offline', cwd=self.wt, env=self.env)
        self.assertTrue((self.wt / 'target/debug').is_dir())

    def test_registered_keeper_wins(self):
        keeper = self.wt / 'target'
        keeper.mkdir()
        common = Path(sh('git', 'rev-parse', '--path-format=absolute', '--git-common-dir', cwd=self.main).stdout.strip())
        (common / 'cargo-cache.json').write_text('{"keeper": "%s"}' % keeper)
        sh('cargo', 'build', '--offline', cwd=self.main, env=self.env)
        self.assertTrue((keeper / 'debug').is_dir())
        self.assertFalse((self.main / 'target').exists())

    def test_separate_target_dir_refused(self):
        result = sh('cargo', 'build', '--offline', '--target-dir', str(self.tmp / 'other'),
                    cwd=self.wt, env=self.env, check=False)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.tmp / 'other').exists())

    def test_own_target_subdir_remapped(self):
        sh('cargo', 'build', '--offline', '--target-dir', 'target/ra', cwd=self.wt, env=self.env)
        self.assertFalse((self.wt / 'target').exists())
        self.assertTrue((self.main / 'target/ra/debug').is_dir())

    def test_subdir_workspace_shares_per_path(self):
        sub = self.main / 'server'
        sub.mkdir()
        (sub / 'Cargo.toml').write_text('[package]\nname = "srv"\nversion = "0.1.0"\nedition = "2021"\n[workspace]\n')
        (sub / 'src').mkdir()
        (sub / 'src/lib.rs').write_text('pub fn two() -> u8 { 2 }\n')
        sh('git', 'add', '.', cwd=self.main)
        sh('git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'srv', cwd=self.main)
        sh('git', 'merge', '-q', 'main', cwd=self.wt)
        sh('cargo', 'build', '--offline', cwd=self.wt / 'server', env=self.env)
        self.assertFalse((self.wt / 'server/target').exists())
        self.assertTrue((self.main / 'server/target/debug').is_dir())

    def test_outside_git_untouched(self):
        plain = self.tmp / 'plain'
        shutil.copytree(self.main, plain, ignore=shutil.ignore_patterns('.git', 'target'))
        sh('cargo', 'build', '--offline', cwd=plain, env=self.env)
        self.assertTrue((plain / 'target/debug').is_dir())


if __name__ == '__main__':
    unittest.main(verbosity=2)
