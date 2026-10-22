"""Integrity and path-boundary controls using isolated repositories."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("ecc_load", Path(__file__).with_name("load.py"))
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c",
                        "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], check=True)
        self.sha = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        (self.root / "ref.md").write_text("reference")
        self.manifest = {"source_root": str(self.root), "commit": self.sha,
                         "groups": {"test": ["ref.md"]},
                         "files": {"ref.md": hashlib.sha256(b"reference").hexdigest()}}

    def test_valid_reference(self):
        self.assertEqual(loader.verified(self.manifest, "test"), [("ref.md", "reference")])

    def test_tamper_rejected(self):
        (self.root / "ref.md").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            loader.verified(self.manifest, "test")

    def test_wrong_version_rejected(self):
        self.manifest["commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "version"):
            loader.verified(self.manifest, "test")

    def test_missing_reference_rejected(self):
        self.manifest["groups"]["test"] = ["missing.md"]
        with self.assertRaises(FileNotFoundError):
            loader.verified(self.manifest, "test")

    def test_escape_rejected(self):
        self.manifest["groups"]["test"] = ["../outside.md"]
        with self.assertRaisesRegex(ValueError, "escapes"):
            loader.verified(self.manifest, "test")


if __name__ == "__main__":
    unittest.main()
