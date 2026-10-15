"""Clear only fixed regenerable caches; uncertainty and active use must preserve data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import fcntl
import json
import os
import subprocess
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('disk_cache_cleanup', Path(__file__).with_name('disk_cache_cleanup.py'))
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class CacheCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / '.cache/pip/http-v2'
        self.root.mkdir(parents=True)
        (self.root / 'download').write_bytes(b'package-cache')

    def test_dry_run_does_not_delete(self):
        result = cache.clean('pip-http', False, self.home, set(), set())
        self.assertEqual(result['status'], 'candidate')
        self.assertTrue((self.root / 'download').exists())

    def test_installed_npx_runtimes_are_never_a_cleanup_profile(self):
        with self.assertRaises(ValueError):
            cache.clean('npm-executables', True, self.home, set(), set())
        self.assertFalse(any(suffix == '.npm/_npx' for suffix, family in cache.PROFILES.values()))

    def test_cached_interpreted_program_is_busy_even_if_it_closed_all_files(self):
        words = ['python3', str(self.home / '.cache/uv/archive-v0/tool/main.py')]
        self.assertIn('python', cache.process_families(words, self.home))

    def test_apply_clears_cache_and_preserves_models_and_root(self):
        model = self.home / 'models/keep.bin'
        model.parent.mkdir()
        model.write_bytes(b'important')
        self.assertEqual(cache.clean('pip-http', True, self.home, set(), set())['status'], 'cleaned')
        self.assertTrue(self.root.is_dir())
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(model.read_bytes(), b'important')

    def test_open_file_and_installer_each_block_cleanup(self):
        for refs, families in [({str(self.root / 'download')}, set()), (set(), {'python'})]:
            with self.subTest(refs=refs, families=families):
                self.assertEqual(cache.clean('pip-http', True, self.home, refs, families)['status'], 'skipped')
                self.assertTrue((self.root / 'download').exists())

    def test_symlink_root_is_rejected_without_touching_destination(self):
        other = self.home / 'database'
        other.mkdir()
        (other / 'rows').write_bytes(b'keep')
        self.root.rename(self.root.with_name('old'))
        self.root.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError):
            cache.clean('pip-http', True, self.home, set(), set())
        self.assertEqual((other / 'rows').read_bytes(), b'keep')

    def test_nested_symlink_never_follows_destination(self):
        other = self.home / 'keep'
        other.write_bytes(b'keep')
        (self.root / 'link').symlink_to(other)
        cache.clean('pip-http', True, self.home, set(), set())
        self.assertEqual(other.read_bytes(), b'keep')

    def test_process_scan_failure_cannot_turn_into_permission_to_delete(self):
        with patch.object(cache, 'in_use', side_effect=RuntimeError('unreadable')):
            with self.assertRaises(RuntimeError):
                cache.snapshot()
        self.assertTrue((self.root / 'download').exists())

    def test_new_process_before_apply_preserves_cache(self):
        refresh = lambda: ({str(self.root / 'download')}, set())
        result = cache.clean('pip-http', True, self.home, set(), set(), refresh=refresh)
        self.assertEqual(result['status'], 'skipped')
        self.assertTrue((self.root / 'download').exists())

    def test_root_replaced_after_inspection_cannot_redirect_deletion(self):
        other = self.home / 'database'
        other.mkdir()
        (other / 'rows').write_bytes(b'keep')
        def replace_root():
            self.root.rename(self.root.with_name('saved'))
            self.root.symlink_to(other, target_is_directory=True)
            return set(), set()
        with self.assertRaises((OSError, ValueError)):
            cache.clean('pip-http', True, self.home, set(), set(), refresh=replace_root)
        self.assertEqual((other / 'rows').read_bytes(), b'keep')

    def test_unknown_profile_and_entry_limit_reject_mutation(self):
        with self.assertRaises(ValueError):
            cache.clean('database', True, self.home, set(), set())
        with patch.object(cache, 'MAX_ENTRIES', 1), self.assertRaises(RuntimeError):
            cache.clean('pip-http', True, self.home, set(), set())
        self.assertTrue((self.root / 'download').exists())


class CleanupShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, XDG_STATE_HOME=str(self.state), PATH=str(self.bin) + ':' + os.environ['PATH'])
        self.script = Path(__file__).with_name('disk-cleanup.sh')

    def timeout_stub(self, result):
        path = self.bin / 'timeout'
        path.write_text('#!/bin/sh\nexit ' + str(result) + '\n')
        path.chmod(0o755)

    def test_timeout_is_failure_and_is_recorded_without_running_real_cleanup(self):
        self.timeout_stub(124)
        done = subprocess.run(['bash', str(self.script), '--apply'], env=self.env, capture_output=True, timeout=5)
        self.assertEqual(done.returncode, 1)
        record = json.loads((self.state / 'disk-cleanup/log.jsonl').read_text().splitlines()[-1])
        self.assertIn('regenerable-caches', record['failed'])

    def test_existing_lock_skips_without_starting_any_action(self):
        self.timeout_stub(99)
        folder = self.state / 'disk-cleanup'
        folder.mkdir(parents=True)
        with (folder / 'lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            done = subprocess.run(['bash', str(self.script), '--apply'], env=self.env, capture_output=True, timeout=5)
        self.assertEqual(done.returncode, 0)
        self.assertFalse((folder / 'log.jsonl').exists())

    def test_default_is_preview_and_unknown_flags_are_rejected(self):
        self.timeout_stub(0)
        done = subprocess.run(['bash', str(self.script)], env=self.env, capture_output=True, timeout=5)
        self.assertEqual(done.returncode, 0)
        record = json.loads((self.state / 'disk-cleanup/log.jsonl').read_text().splitlines()[-1])
        self.assertFalse(record['apply'])
        bad = subprocess.run(['bash', str(self.script), '--anything'], env=self.env, capture_output=True, timeout=5)
        self.assertEqual(bad.returncode, 2)


if __name__ == '__main__':
    unittest.main()
