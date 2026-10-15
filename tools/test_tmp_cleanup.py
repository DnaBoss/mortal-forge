import os
import tempfile
import time
import unittest
from pathlib import Path

import tmp_cleanup as tc

H = 3600


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000.0

    def run_one(self, entry, in_use=(), live=()):
        [d] = tc.decide([entry], set(in_use), set(live), self.now, 6 * H)
        return d

    def test_stale_unused_is_deleted(self):
        d = self.run_one(tc.Entry("/tmp/a", self.now - 7 * H, 10))
        self.assertEqual((d.action, d.reason, d.size), ("delete", "stale", 10))

    def test_recent_is_kept(self):
        d = self.run_one(tc.Entry("/tmp/a", self.now - 5 * H, 10))
        self.assertEqual((d.action, d.reason), ("keep", "recent"))

    def test_open_file_inside_keeps_dir(self):
        d = self.run_one(tc.Entry("/tmp/a", 0, 10), in_use=["/tmp/a/x/y.log"])
        self.assertEqual((d.action, d.reason), ("keep", "in_use"))

    def test_sibling_prefix_is_not_in_use(self):
        d = self.run_one(tc.Entry("/tmp/a", 0, 10), in_use=["/tmp/ab/file"])
        self.assertEqual(d.action, "delete")

    def test_live_session_is_kept(self):
        d = self.run_one(tc.Entry("/tmp/c/-p/s1", 0, 10, "s1"), live=["s1"])
        self.assertEqual((d.action, d.reason), ("keep", "live_session"))

    def test_truncated_walk_counts_as_recent(self):
        d = self.run_one(tc.Entry("/tmp/a", float("inf"), 10))
        self.assertEqual(d.action, "keep")


class EndToEndTest(unittest.TestCase):
    def test_apply_deletes_only_stale_entry(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            old, new = root / "old", root / "new"
            for d in (old, new):
                d.mkdir()
                (d / "f").write_text("x")
            past = time.time() - 10 * H
            for p in (old / "f", old):
                os.utime(p, (past, past))
            tc.TMP, tc.LOG = root, root / "log.jsonl"
            tc.live_session_ids = lambda: set()
            self.assertEqual(tc.main(["--apply"]), 0)
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())
            self.assertTrue(tc.LOG.read_text().strip())

    def test_dir_holding_socket_counts_as_recent(self):
        import socket
        with tempfile.TemporaryDirectory(dir="/tmp") as root:
            d = Path(root) / "srv"
            d.mkdir()
            sock = socket.socket(socket.AF_UNIX)
            sock.bind(str(d / "s.sock"))
            sock.close()
            past = time.time() - 10 * H
            os.utime(d / "s.sock", (past, past), follow_symlinks=False)
            os.utime(d, (past, past))
            newest, _ = tc.measure(str(d))
            self.assertEqual(newest, float("inf"))


if __name__ == "__main__":
    unittest.main()
