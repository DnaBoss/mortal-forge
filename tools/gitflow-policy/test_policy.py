"""Exercise actual Git hooks against disposable repositories and a local bare remote."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent


class HooksTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.run_git("init", "-b", "develop")
        self.run_git("config", "user.email", "tests@example.invalid")
        self.run_git("config", "user.name", "Policy Test")
        self.write("README.md", "baseline\n")
        self.run_git("add", "README.md")
        self.run_git("commit", "-m", "baseline history")
        self.baseline = self.run_git("rev-parse", "HEAD").stdout.strip()
        self.run_git("update-ref", "refs/remotes/origin/develop", self.baseline)
        self.source = self.root / "source"
        shutil.copytree(SOURCE, self.source)
        self.config = {"baseline": self.baseline, "legacy_branches": ["feat/old"], "checks": [], "deployment_branches": ["main"], "default_branch": "main"}
        self.set_config()
        self.install()
        self.run_git("switch", "-c", "feature/example")

    def tearDown(self):
        self.directory.cleanup()

    def run_git(self, *args, ok=True):
        result = subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def write(self, name, content):
        (self.repo / name).write_text(content)

    def set_config(self):
        (self.source / "config.json").write_text(json.dumps(self.config))

    def install(self):
        result = subprocess.run(["python3", str(SOURCE / "install.py"), "--repo", str(self.repo), "--source", str(self.source)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.state = json.loads(result.stdout)

    def candidate(self, message="feat: add example"):
        self.write("README.md", "example\n")
        self.run_git("add", "README.md")
        return self.run_git("commit", "-m", message, ok=False)

    def push_hook(self, target="refs/heads/feature/example", old=None, oid=None):
        new = oid or self.run_git("rev-parse", "HEAD").stdout.strip()
        payload = f"refs/heads/feature/example {new} {target} {old or '0'*40}\n"
        return subprocess.run([str(Path(self.state["installed_hooks_path"]) / "pre-push"), "origin", "local-test"], cwd=self.repo, input=payload, capture_output=True, text=True)

    def test_valid_commit_and_local_push(self):
        self.assertEqual(self.candidate().returncode, 0)
        bare = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        self.run_git("remote", "add", "target", str(bare))
        self.run_git("push", "target", "HEAD:refs/heads/feature/example")

    def test_direct_develop_commit_is_rejected_and_index_preserved(self):
        self.run_git("switch", "develop")
        result = self.candidate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Direct commits", result.stderr)
        self.assertIn("README.md", self.run_git("diff", "--cached", "--name-only").stdout)

    def test_invalid_branch_is_rejected(self):
        self.run_git("switch", "-c", "random-name")
        self.assertIn("Invalid branch", self.candidate().stderr)

    def test_bad_commit_message_is_rejected(self):
        self.assertIn("Conventional Commits", self.candidate("update files").stderr)

    def test_legacy_branch_is_retained(self):
        self.run_git("switch", "-c", "feat/old")
        self.assertEqual(self.candidate("fix: maintain existing work").returncode, 0)

    def test_secret_path_is_rejected_without_printing_content(self):
        self.write(".env", "PASSWORD=private-value\n")
        self.run_git("add", ".env")
        result = self.run_git("commit", "-m", "chore: local settings", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("private-value", result.stderr)

    def test_staged_python_syntax_is_checked(self):
        self.write("sample.py", "def broken(\n")
        self.run_git("add", "sample.py")
        self.assertIn("Syntax check failed", self.candidate().stderr)

    def test_dirty_push_and_deployment_are_rejected(self):
        self.assertEqual(self.candidate().returncode, 0)
        self.write("README.md", "not committed\n")
        self.assertIn("Uncommitted tracked", self.push_hook().stderr)
        self.assertIn("triggers deployment", self.push_hook(target="refs/heads/main").stderr)

    def test_force_and_protected_deletion_are_rejected(self):
        self.assertEqual(self.candidate().returncode, 0)
        latest = self.run_git("rev-parse", "HEAD").stdout.strip()
        self.assertIn("Non-fast-forward", self.push_hook(old=latest, oid=self.baseline).stderr)
        self.assertIn("Cannot delete", self.push_hook(target="refs/heads/develop", old=latest, oid="0"*40).stderr)

    def test_unmerged_deletion_is_rejected(self):
        self.assertEqual(self.candidate().returncode, 0)
        latest = self.run_git("rev-parse", "HEAD").stdout.strip()
        self.assertIn("Deletion requires", self.push_hook(old=latest, oid="0"*40).stderr)

    def test_release_tag_cannot_be_deleted(self):
        self.assertIn("must not be deleted", self.push_hook(target="refs/tags/v1.2.3", old=self.baseline, oid="0"*40).stderr)

    def test_missing_required_gate_cannot_be_skipped(self):
        installed = Path(self.state["installed_hooks_path"]) / "config.json"
        self.config["checks"] = [{"pattern": "README", "requires": "missing.toml", "pre_push": ["python3", "-c", "pass"]}]
        installed.write_text(json.dumps(self.config))
        self.assertEqual(self.candidate().returncode, 0)
        self.assertIn("Required check prerequisite", self.push_hook().stderr)

    def test_staged_manifest_deletion_cannot_disable_gate(self):
        self.write("package.json", "{}\n")
        self.run_git("add", "package.json")
        self.run_git("commit", "-m", "build: add manifest")
        installed = Path(self.state["installed_hooks_path"]) / "config.json"
        self.config["checks"] = [{"pattern": "package.json", "requires": "package.json", "pre_commit": ["python3", "-c", "pass"]}]
        installed.write_text(json.dumps(self.config))
        self.run_git("rm", "package.json")
        result = self.run_git("commit", "-m", "build: remove manifest", ok=False)
        self.assertIn("Required check prerequisite", result.stderr)

    def test_existing_hook_failure_and_restore(self):
        hook = self.repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\necho original-gate >&2\nexit 19\n")
        hook.chmod(0o755)
        result = self.candidate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("original-gate", result.stderr)
        subprocess.run(["python3", str(SOURCE / "install.py"), "--repo", str(self.repo), "--restore", str(Path(self.state["installed_hooks_path"]) / "installation.json")], check=True)
        self.assertEqual(self.run_git("config", "--get", "core.hooksPath", ok=False).returncode, 1)
        self.assertIn("original-gate", self.candidate().stderr)

    def test_failed_project_check_blocks_push(self):
        installed = Path(self.state["installed_hooks_path"]) / "config.json"
        self.config["checks"] = [{"pattern": "README", "pre_push": ["python3", "-c", "raise SystemExit(7)"]}]
        installed.write_text(json.dumps(self.config))
        self.assertEqual(self.candidate().returncode, 0)
        self.assertIn("Project check failed", self.push_hook().stderr)

    def test_release_name_and_merge_to_develop(self):
        self.run_git("switch", "-c", "release/1.2.3")
        self.assertEqual(self.candidate("chore(release): prepare 1.2.3").returncode, 0)
        self.run_git("switch", "develop")
        self.run_git("merge", "--no-ff", "release/1.2.3")

    def test_untracked_file_cannot_contaminate_push_gate(self):
        self.assertEqual(self.candidate().returncode, 0)
        self.write("unchecked.txt", "green\n")
        self.assertIn("Untracked files", self.push_hook().stderr)

    def test_other_unstaged_file_cannot_contaminate_commit_gate(self):
        self.write("other.txt", "committed\n")
        self.run_git("add", "other.txt")
        self.run_git("commit", "-m", "test: add fixture")
        self.write("other.txt", "not staged\n")
        installed = Path(self.state["installed_hooks_path"]) / "config.json"
        self.config["checks"] = [{"pattern": "README", "pre_commit": ["python3", "-c", "pass"]}]
        installed.write_text(json.dumps(self.config))
        self.assertIn("Uncommitted tracked", self.candidate().stderr)

    def test_existing_pre_merge_hook_cannot_bypass_policy(self):
        hook = self.repo / ".git/hooks/pre-merge-commit"
        hook.write_text("#!/bin/sh\nexit 0\n")
        hook.chmod(0o755)
        self.run_git("switch", "-c", "feat/old")
        self.assertEqual(self.candidate().returncode, 0)
        self.run_git("switch", "develop")
        result = self.run_git("merge", "--no-ff", "feat/old", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Merge source must", result.stderr)


if __name__ == "__main__":
    unittest.main()
