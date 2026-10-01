#!/usr/bin/env python3
"""Tests for git_guard.py and finish_check.py. Run: python3 -m unittest test_guards -v"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_hook(script, payload, home):
    env = dict(os.environ, HOME=home,
               CASH_RULE_VALIDATOR_PY=os.path.expanduser("~/.cache/cash-rule-validator/bin/python"))
    r = subprocess.run([sys.executable, str(HERE / script)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=60)
    return r.returncode, r.stdout.strip()


class GitGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = cls.tmp.name
        cls.main_repo = os.path.join(cls.home, "main_repo")
        cls.feat_repo = os.path.join(cls.home, "feat_repo")
        for path, branch in ((cls.main_repo, "main"), (cls.feat_repo, "feature/x")):
            subprocess.run(["git", "init", "-q", "-b", branch, path], check=True)
        cls.plain_dir = os.path.join(cls.home, "plain")
        os.mkdir(cls.plain_dir)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def decide(self, cmd, cwd=None):
        _, out = run_hook("git_guard.py", {"tool_input": {"command": cmd}, "cwd": cwd or self.feat_repo}, self.home)
        if not out:
            return "allow"
        spec = json.loads(out)["hookSpecificOutput"]
        return "deny" if spec.get("permissionDecision") == "deny" else "warn"

    def test_force_push_forms_denied(self):
        for cmd in ["git push --force origin x", "git push -f", "git push -uf origin x", "git push -fu origin x",
                    "git push origin +main", "git push --force-with-lease", "env git push --force",
                    "env -u FOO git push -f", "command git push -f", "sudo git push -f", "sudo -u bob git push -f",
                    "timeout 30 git push -f", "nohup git push --force", "FOO=1 git push -f",
                    "bash -lc 'git push -f'",
                    "python3 -c 'import subprocess; subprocess.run([\"git\",\"push\",\"--force\"])'"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decide(cmd), "deny")

    def test_normal_commands_allowed(self):
        for cmd in ["git push origin feature/x", "git push -u origin feature/x", "git push --follow-tags",
                    "git commit -m 'fix: x'", "git status", "grep -r force .", "echo git push -f docs"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decide(cmd), "allow")

    def test_protected_commit_denied_in_all_forms(self):
        for cmd in ["git commit -m x", "env git commit -m x", "command git commit -m x", "git -c a=b commit -m x"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decide(cmd, cwd=self.main_repo), "deny")

    def test_cd_is_followed(self):
        self.assertEqual(self.decide(f"cd {self.main_repo} && git commit -m x", cwd=self.feat_repo), "deny")
        self.assertEqual(self.decide(f"cd {self.feat_repo} && git commit -m x", cwd=self.main_repo), "allow")
        self.assertEqual(self.decide("cd ../main_repo && git commit -m x", cwd=self.feat_repo), "deny")

    def test_non_repo_commit_allowed_quietly(self):
        self.assertEqual(self.decide("git commit -m x", cwd=self.plain_dir), "allow")

    def test_log_has_no_command_text(self):
        secret = "ghp_SECRETTOKEN123"
        self.decide(f"git push https://{secret}@github.com/x/y.git feature/x")
        log = Path(self.home, ".local/state/agent-guards/git_guard.jsonl").read_text()
        self.assertNotIn(secret, log)
        self.assertIn("cmd_sha256", log.splitlines()[-1])


class FinishCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.repo = os.path.join(self.home, "repo")
        subprocess.run(["git", "init", "-q", "-b", "feature/x", self.repo], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def add_catalog(self):
        tools = Path(self.home, "tools")
        tools.mkdir()
        Path(tools, "list_tools.py").write_text("def load_catalog(p):\n    return []\n")

    def stop(self, extra=None, home=None):
        payload = {"cwd": self.repo, **(extra or {})}
        return run_hook("finish_check.py", payload, home or self.home)

    def test_clean_repo_passes(self):
        self.add_catalog()
        rc, out = self.stop()
        self.assertEqual((rc, out), (0, ""))

    def test_bad_checkpoint_blocks(self):
        self.add_catalog()
        Path(self.repo, "docs").mkdir()
        Path(self.repo, "docs/x.checkpoint.jsonl").write_text('{"not": "a checkpoint"}\n')
        _, out = self.stop()
        self.assertEqual(json.loads(out)["decision"], "block")
        self.assertIn("x.checkpoint.jsonl", json.loads(out)["reason"])

    def test_second_stop_still_reports(self):
        self.add_catalog()
        Path(self.repo, "docs").mkdir()
        Path(self.repo, "docs/x.checkpoint.jsonl").write_text('{"not": "a checkpoint"}\n')
        _, out = self.stop({"stop_hook_active": True})
        msg = json.loads(out)
        self.assertNotIn("decision", msg)
        self.assertIn("未通過", msg["systemMessage"])

    def test_checker_fault_is_not_silent(self):
        # No ~/tools/list_tools.py in this HOME: the checker itself is broken.
        _, out = self.stop()
        msg = json.loads(out)
        self.assertNotIn("decision", msg)
        self.assertIn("檢查器故障", msg["systemMessage"])


class LessonsContextTest(unittest.TestCase):
    def test_keeps_newest_entries_when_over_budget(self):
        sys.path.insert(0, str(HERE))
        import lessons_context
        text = "# header\n\n" + "".join(f"{i}. old lesson {i}\n" + "x" * 50 + "\n" for i in range(1, 30)) \
            + "## 2026-10-01 newest lesson\n- body\n"
        out = lessons_context.select(text, budget=400)
        self.assertIn("newest lesson", out)
        self.assertIn("# header", out)
        self.assertNotIn("old lesson 1\n", out)
        self.assertLessEqual(len(out.encode()), 400 + 200)  # note line allowance

    def test_small_file_unchanged(self):
        sys.path.insert(0, str(HERE))
        import lessons_context
        self.assertEqual(lessons_context.select("# h\n1. a\n", budget=400), "# h\n1. a\n")


if __name__ == "__main__":
    unittest.main()
