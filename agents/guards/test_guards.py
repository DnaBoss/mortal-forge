#!/usr/bin/env python3
"""Tests for git_guard.py, write_guard.py and finish_check.py. Run: python3 -m unittest test_guards -v"""
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_hook(script, payload, home):
    env = dict(os.environ, HOME=home,
               CASH_RULE_VALIDATOR_PY=os.path.expanduser("~/.cache/cash-rule-validator/bin/python"))
    r = subprocess.run([sys.executable, str(HERE / script)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=60)
    return r.returncode, r.stdout.strip()


def decision(out):
    if not out:
        return "allow"
    spec = json.loads(out)["hookSpecificOutput"]
    return "deny" if spec.get("permissionDecision") == "deny" else "warn"


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
        return decision(out)

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

    def test_protected_commit_message_names_accepted_prefixes(self):
        _, out = run_hook("git_guard.py", {"tool_input": {"command": "git commit -m x"}, "cwd": self.main_repo}, self.home)
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("feature/", reason)
        self.assertNotIn("feat/", reason)

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


class WriteGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = cls.tmp.name
        cls.repo = os.path.join(cls.home, "repo")
        subprocess.run(["git", "init", "-q", "-b", "feature/x", cls.repo], check=True)
        Path(cls.repo, "clean.txt").write_text("a\n")
        Path(cls.repo, "edited.txt").write_text("a\n")
        subprocess.run(["git", "-C", cls.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", cls.repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                       check=True)
        Path(cls.repo, "edited.txt").write_text("b\n")  # uncommitted change

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def shell(self, cmd, cwd=None):
        _, out = run_hook("write_guard.py", {"tool_name": "Bash", "tool_input": {"command": cmd},
                                             "cwd": cwd or self.repo}, self.home)
        return decision(out)

    def tool(self, name, tool_input):
        _, out = run_hook("write_guard.py", {"tool_name": name, "tool_input": tool_input, "cwd": self.repo}, self.home)
        return decision(out)

    def test_direct_checkpoint_writes_denied(self):
        for cmd in ["echo '{}' >> loops/a.checkpoints.jsonl", "cat x > docs/loops/a.checkpoints.jsonl",
                    "printf '%s\\n' '{}' | tee -a loops/a.checkpoints.jsonl",
                    "sed -i 's/a/b/' loops/a.checkpoints.jsonl", "rm loops/a.checkpoints.jsonl",
                    "mv loops/a.checkpoints.jsonl loops/b.checkpoints.jsonl", "truncate -s 0 loops/a.checkpoints.jsonl",
                    "python3 -c \"open('loops/a.checkpoints.jsonl','a').write('{}')\"",
                    "bash -lc 'echo x >> loops/a.checkpoints.jsonl'"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.shell(cmd), "deny")

    def test_checkpoint_reads_and_tool_writes_allowed(self):
        for cmd in ["cat loops/a.checkpoints.jsonl", "validate_checkpoints.py loops/a.checkpoints.jsonl 2>&1 | head",
                    "wc -l loops/a.checkpoints.jsonl > /tmp/count.txt",
                    "~/tools/cash-rule-checkpoint loops/a.checkpoints.jsonl --task t --step S01 --target x",
                    "python3 ~/tools/cash_rule_checkpoint.py loops/a.checkpoints.jsonl --task t",
                    "cp loops/a.checkpoints.jsonl /tmp/backup.jsonl", "echo hello >> notes.md"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.shell(cmd), "allow")

    def test_edit_tools_cannot_touch_checkpoints(self):
        self.assertEqual(self.tool("Write", {"file_path": "/x/loops/a.checkpoints.jsonl", "content": "{}"}), "deny")
        self.assertEqual(self.tool("Edit", {"file_path": "/x/a.checkpoints.jsonl", "old_string": "a", "new_string": "b"}), "deny")
        self.assertEqual(self.tool("apply_patch", {"patch": "*** Begin Patch\n*** Update File: loops/a.checkpoints.jsonl\n"}), "deny")
        self.assertEqual(self.tool("Read", {"file_path": "/x/loops/a.checkpoints.jsonl"}), "allow")
        self.assertEqual(self.tool("Write", {"file_path": "/x/loops/a.loop.md", "content": "x"}), "allow")

    def test_pkill_full_denied(self):
        for cmd in ["pkill -f 'http.server 18321'", "pgrep -f 'tsx watch' | xargs kill", "pkill -9 -f node",
                    "pgrep -fl node", "pkill --full node", "sudo pkill -f node", "cd /tmp && pkill -f x"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.shell(cmd), "deny")

    def test_pkill_without_full_allowed(self):
        for cmd in ["pgrep -x node", "pkill node", "kill 1234", "ss -ltnp | grep 3000", "echo pkill -f docs"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.shell(cmd), "allow")

    def test_discarding_uncommitted_file_denied(self):
        for cmd in ["git checkout -- edited.txt", "git checkout edited.txt", "git checkout HEAD -- edited.txt",
                    "git checkout -- .", "git restore edited.txt", "git restore --worktree edited.txt",
                    f"cd {self.repo} && git checkout -- edited.txt"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.shell(cmd), "deny")

    def test_discard_allowed_when_explicit_or_harmless(self):
        for cmd in ["DISCARD=1 git checkout -- edited.txt", "git checkout -- clean.txt", "git checkout -b feature/y",
                    "git checkout main", "git restore --staged edited.txt", "git stash", "git status"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.shell(cmd), "allow")

    def test_log_has_no_input_text(self):
        secret = "ghp_SECRETTOKEN123"
        self.shell(f"echo {secret} >> loops/a.checkpoints.jsonl")
        log = Path(self.home, ".local/state/agent-guards/write_guard.jsonl").read_text()
        self.assertNotIn(secret, log)
        self.assertIn("checkpoint-write", log.splitlines()[-1])


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

    def bad_checkpoint(self, rel):
        Path(self.repo, rel).parent.mkdir(parents=True, exist_ok=True)
        Path(self.repo, rel).write_text('{"not": "a checkpoint"}\n')

    def stop(self, extra=None, home=None):
        payload = {"cwd": self.repo, **(extra or {})}
        return run_hook("finish_check.py", payload, home or self.home)

    def test_clean_repo_passes(self):
        self.add_catalog()
        rc, out = self.stop()
        self.assertEqual((rc, out), (0, ""))

    def test_bad_checkpoint_blocks_anywhere_in_repo(self):
        self.add_catalog()
        for rel in ["docs/x.checkpoints.jsonl", "loops/x.checkpoints.jsonl", "loops/multi/x.checkpoints.jsonl",
                    "x.checkpoints.jsonl"]:
            with self.subTest(rel=rel):
                self.bad_checkpoint(rel)
                _, out = self.stop()
                self.assertEqual(json.loads(out)["decision"], "block")
                self.assertIn(rel, json.loads(out)["reason"])
                os.remove(os.path.join(self.repo, rel))
                self.assertEqual(self.stop(), (0, ""))  # passing stop resets the block counter

    def test_vendored_and_hidden_dirs_skipped(self):
        self.add_catalog()
        for rel in ["node_modules/x/a.checkpoints.jsonl", ".cache/a.checkpoints.jsonl", "target/a.checkpoints.jsonl"]:
            self.bad_checkpoint(rel)
        self.assertEqual(self.stop(), (0, ""))

    def test_keeps_blocking_until_fixed_then_gives_up(self):
        self.add_catalog()
        self.bad_checkpoint("loops/x.checkpoints.jsonl")
        for n in (1, 2, 3):
            _, out = self.stop({"stop_hook_active": n > 1})
            self.assertEqual(json.loads(out).get("decision"), "block", f"stop {n}")
            self.assertIn(f"第 {n} 次", json.loads(out)["reason"])
        _, out = self.stop({"stop_hook_active": True})
        msg = json.loads(out)
        self.assertNotIn("decision", msg)
        self.assertIn("gave_up", msg["systemMessage"])
        last = json.loads(Path(self.home, ".local/state/agent-guards/finish_check.jsonl").read_text().splitlines()[-1])
        self.assertTrue(last["gave_up"])
        # A passing stop resets the counter: the next problem is blocked again.
        os.remove(os.path.join(self.repo, "loops/x.checkpoints.jsonl"))
        self.assertEqual(self.stop(), (0, ""))
        self.bad_checkpoint("loops/x.checkpoints.jsonl")
        _, out = self.stop()
        self.assertEqual(json.loads(out)["decision"], "block")

    def test_stale_running_loop_in_template_format_blocks(self):
        self.add_catalog()
        Path(self.repo, "src.py").write_text("x = 1\n")
        subprocess.run(["git", "-C", self.repo, "add", "src.py"], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "feat: x"],
                       check=True)
        loop = Path(self.repo, "loops/task.loop.md")
        loop.parent.mkdir()
        loop.write_text("# T LOOP\n\nProtocol version: `1.2.0`\n\n## 目前狀態（LOOP 投影）\n\n- task 狀態／目前 step：RUNNING／S01\n")
        old = time.time() - 2 * 24 * 3600
        os.utime(loop, (old, old))
        _, out = self.stop()
        self.assertEqual(json.loads(out)["decision"], "block")
        self.assertIn("task.loop.md", json.loads(out)["reason"])

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
