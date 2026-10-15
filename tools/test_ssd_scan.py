import fcntl
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import ssd_scan as scan


class ScannerTests(unittest.TestCase):
    def test_unknown_and_first_measurement_are_not_zero_growth(self):
        self.assertIsNone(scan.compare({'path':'a','bytes':4}, {})['delta_bytes'])
        self.assertIsNone(scan.compare({'path':'a','bytes':None}, {'a':{'bytes':4}})['delta_bytes'])
        self.assertEqual(scan.compare({'path':'a','bytes':7}, {'a':{'bytes':4}})['delta_bytes'], 3)

    def test_missing_process_evidence_never_marks_safe(self):
        self.assertEqual(scan.classify(Path('/home/test/target'), set(), False)[0], 'unknown')
        self.assertEqual(scan.classify(Path('/home/test/target'), {'/home/test/target/run'}, True)[0], 'busy')

    def test_model_database_and_installed_tools_protected(self):
        for path in ['/home/test/models/model.pth', '/home/test/data.sqlite', '/home/test/.npm/_npx/node_modules', '/home/test/repo/.git']:
            self.assertEqual(scan.classify(Path(path), set(), True)[0], 'protected')

    def test_build_is_review_only(self):
        self.assertEqual(scan.classify(Path('/home/test/repo/target'), set(), True)[0], 'review')

    def test_timeout_never_returns_complete_size(self):
        with patch.object(scan.subprocess, 'run', side_effect=subprocess.TimeoutExpired('du',1)):
            size, error, modified = scan.measure(Path('/home/test'))
        self.assertIsNone(size)
        self.assertIsNotNone(error)
        self.assertIsNone(modified)

    def test_hardlinks_count_once_and_scan_does_not_change_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td);p=root/'one';p.write_bytes(b'x' * 8192);os.link(p,root/'two')
            before=p.read_bytes();size,error,modified=scan.measure(root)
            self.assertIsNone(error)
            self.assertEqual(size, root.stat().st_blocks * 512 + p.stat().st_blocks * 512)
            self.assertEqual(p.read_bytes(),before)
            self.assertIsNotNone(modified)

    def test_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'link').symlink_to('/usr')
            self.assertIsNone(scan.measure(root/'link')[0])
            found,large,errors,complete,count=scan.discover(root,time.monotonic()+1)
            self.assertEqual(found,[])

    def test_limits_report_incomplete_and_forbidden_directory_not_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'aletheia-hotfix').mkdir();(root/'aletheia-hotfix'/'target').mkdir()
            self.assertEqual(scan.discover(root,time.monotonic()+1)[0],[])
            self.assertFalse(scan.discover(root,time.monotonic()+1,max_entries=0)[3])

    def test_docker_report_drops_commands_and_labels(self):
        data = {'Containers':[{'Names':'example','Size':'1MB','Command':'secret','Labels':'secret'}]}
        self.assertEqual(scan.sanitize_docker(data)['Containers'], [{'Names':'example','Size':'1MB'}])

    def test_running_scan_cannot_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td)
            with (state/'lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertEqual(scan.run(state,state)['status'],'running')


if __name__ == '__main__':
    unittest.main()
