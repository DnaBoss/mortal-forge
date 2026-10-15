import subprocess
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cargo_cache as cc


class CargoCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.env = patch.dict(os.environ, {'HOME': self.tmp.name})
        self.env.start()
        self.repo = Path(self.tmp.name) / 'main'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')
        (self.repo / 'Cargo.toml').write_text('[package]\nname="test"\nversion="0.1.0"\n')
        (self.repo / '.gitignore').write_text('target/\n')
        self.git('add', '.')
        self.git('commit', '-m', 'initial')
        self.wt = Path(self.tmp.name) / 'wt'
        self.git('worktree', 'add', '-b', 'feature/x', str(self.wt))
        for root in (self.repo, self.wt):
            (root / 'target/debug').mkdir(parents=True)
            (root / 'target/.rustc_info.json').write_text('{}')
            (root / 'target/debug/dummy').write_text('keep')
        self.keeper = self.repo / 'target'

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True,
                              capture_output=True, text=True)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    @patch('cargo_cache.in_use', return_value=set())
    def test_idle_duplicate_replaced_by_link(self, _):
        result = cc.adopt(self.repo, self.keeper)
        self.assertEqual(result['skipped'], [])
        self.assertTrue((self.wt / 'target').is_symlink())
        self.assertEqual((self.wt / 'target').resolve(), self.keeper)
        self.assertEqual((self.keeper / 'debug/dummy').read_text(), 'keep')
        self.assertEqual(self.git('-C', str(self.wt), 'status', '--porcelain').stdout, '')

    def test_busy_duplicate_is_preserved(self):
        with patch('cargo_cache.in_use', return_value={str(self.wt / 'target/debug/dummy')}):
            result = cc.adopt(self.repo, self.keeper)
        self.assertTrue((self.wt / 'target/debug/dummy').is_file())
        self.assertFalse((self.wt / 'target').is_symlink())
        self.assertIn(str(self.wt / 'target'), result['skipped'])

    @patch('cargo_cache.in_use', return_value=set())
    def test_external_keeper_is_rejected(self, _):
        with self.assertRaises(ValueError):
            cc.adopt(self.repo, Path(self.tmp.name) / 'outside')
        self.assertTrue((self.wt / 'target/debug/dummy').is_file())

    @patch('cargo_cache.in_use', return_value=set())
    def test_unknown_content_rejected_before_any_deletion(self, _):
        (self.wt / 'target/user-data').write_text('important')
        with self.assertRaises(ValueError):
            cc.adopt(self.repo, self.keeper)
        self.assertTrue((self.wt / 'target/user-data').is_file())

    @patch('cargo_cache.in_use', return_value=set())
    def test_audit_reports_before_and_after(self, _):
        self.assertTrue(cc.audit(self.repo)['duplicates'])
        cc.adopt(self.repo, self.keeper)
        self.assertEqual(cc.audit(self.repo)['duplicates'], [])

    def test_proc_failure_prevents_deletion(self):
        with patch('cargo_cache.in_use', side_effect=RuntimeError('cannot inspect')):
            with self.assertRaises(RuntimeError):
                cc.adopt(self.repo, self.keeper)
        self.assertTrue((self.wt / 'target/debug/dummy').is_file())

    def test_session_end_does_not_delete_unmanaged_cache(self):
        cc.hook({'hook_event_name': 'SessionEnd', 'cwd': str(self.repo)})
        self.assertTrue((self.wt / 'target/debug/dummy').is_file())

    def test_stop_blocks_new_duplicate(self):
        result = cc.hook({'hook_event_name': 'Stop', 'cwd': str(self.repo)})
        self.assertEqual(result.get('decision'), 'block')

    @patch('cargo_cache.in_use', return_value=set())
    def test_new_worktree_is_linked_before_build(self, _):
        cc.adopt(self.repo, self.keeper)
        extra = Path(self.tmp.name) / 'new'
        self.git('worktree', 'add', '-b', 'feature/new', str(extra))
        result = cc.hook({'hook_event_name': 'PreToolUse', 'cwd': str(extra),
                          'tool_input': {'cmd': 'cargo build'}})
        self.assertEqual(result, {})
        self.assertEqual((extra / 'target').resolve(), self.keeper)

    @patch('cargo_cache.in_use', return_value=set())
    def test_separate_target_override_is_denied(self, _):
        cc.adopt(self.repo, self.keeper)
        for command in ('cargo build --target-dir /tmp/other',
                        'CARGO_TARGET_DIR=/tmp/other cargo test'):
            result = cc.hook({'hook_event_name': 'PreToolUse', 'cwd': str(self.wt),
                              'tool_input': {'command': command}})
            self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_retained_busy_cache_build_requires_shared_override(self):
        with patch('cargo_cache.in_use', return_value={str(self.wt / 'target/debug/dummy')}):
            cc.adopt(self.repo, self.keeper)
        result = cc.hook({'hook_event_name': 'PreToolUse', 'cwd': str(self.wt),
                          'tool_input': {'command': 'cargo test'}})
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    @patch('cargo_cache.in_use', return_value=set())
    def test_keeper_removal_is_detected(self, _):
        cc.adopt(self.repo, self.keeper)
        import shutil
        shutil.rmtree(self.keeper)
        result = cc.hook({'hook_event_name': 'PreToolUse', 'cwd': str(self.repo),
                          'tool_input': {'command': 'cargo test'}})
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    @patch('cargo_cache.in_use', return_value=set())
    def test_external_symlink_is_never_followed(self, _):
        import shutil
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        (outside / 'important').write_text('keep')
        shutil.rmtree(self.wt / 'target')
        (self.wt / 'target').symlink_to(outside)
        with self.assertRaises(ValueError):
            cc.adopt(self.repo, self.keeper)
        self.assertEqual((outside / 'important').read_text(), 'keep')

    def test_session_end_launches_no_worker_without_opt_in(self):
        with patch('cargo_cache.spawn_cleanup') as spawn:
            cc.hook({'hook_event_name': 'SessionEnd', 'cwd': str(self.repo)})
            spawn.assert_not_called()

    def test_install_is_idempotent_and_preserves_existing_hooks(self):
        import json
        location = Path(self.tmp.name) / '.codex/hooks.json'
        location.parent.mkdir()
        original = {'hooks': {'Stop': [{'hooks': [{'command': 'existing'}]}]}, 'extra': 123}
        location.write_text(json.dumps(original))
        guard = Path('/test/cargo_cache_guard.py')
        cc.install_hooks(Path(self.tmp.name), guard)
        data = json.loads(location.read_text())
        self.assertEqual(data['extra'], 123)
        self.assertEqual(data['hooks']['Stop'][0], original['hooks']['Stop'][0])
        self.assertEqual(cc.install_hooks(Path(self.tmp.name), guard)['updated'], [])

    def test_registered_cleanup_does_not_delete_unapproved_duplicate(self):
        with patch('cargo_cache.in_use', return_value={str(self.wt / 'target/debug/dummy')}):
            cc.adopt(self.repo, self.keeper, auto_cleanup=True)
        extra = Path(self.tmp.name) / 'unapproved'
        self.git('worktree', 'add', '-b', 'feature/unapproved', str(extra))
        (extra / 'target/debug').mkdir(parents=True)
        (extra / 'target/.rustc_info.json').write_text('{}')
        (extra / 'target/debug/keep').write_text('keep')
        with patch('cargo_cache.in_use', return_value=set()):
            cc.adopt(self.repo, self.keeper, allowed={str(self.wt / 'target')}, auto_cleanup=True)
        self.assertEqual((extra / 'target/debug/keep').read_text(), 'keep')
        self.assertTrue((self.wt / 'target').is_symlink())


if __name__ == '__main__':
    unittest.main()
