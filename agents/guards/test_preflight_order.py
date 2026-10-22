"""Prevent unconditional Cargo execution after a Python preflight heredoc."""
import unittest
import write_guard


class PreflightOrderTest(unittest.TestCase):
    def rule(self, cmd):
        return write_guard.verdict({'tool_input': {'cmd': cmd}})[0]

    def test_checkpoint_and_commit_must_be_separate(self):
        for separator in ['\n', '; ', ' && ']:
            command = '~/tools/cash-rule-checkpoint x.checkpoints.jsonl --task t' + separator + 'git commit -m x'
            self.assertEqual(self.rule(command), 'checkpoint-commit-order')

    def test_checkpoint_alone_allowed(self):
        self.assertIsNone(self.rule('~/tools/cash-rule-checkpoint x.checkpoints.jsonl --task t'))

    def test_commit_message_and_echo_are_not_checkpoint_commands(self):
        self.assertIsNone(self.rule('git commit -m "cash-rule-checkpoint"'))
        self.assertIsNone(self.rule('echo "cash-rule-checkpoint x"; git commit -m x'))

    def test_failed_preflight_fallthrough_denied(self):
        for tag in ["PY", "'PY'", '"PY"']:
            for action in ['build', 'test', 'clippy', 'run']:
                with self.subTest(tag=tag, action=action):
                    cmd = 'python3 - <<' + tag + '\nraise AssertionError()\nPY\ncargo ' + action
                    self.assertEqual(self.rule(cmd), 'cargo-unchecked-preflight')

    def test_git_worktree_fallthrough_denied(self):
        cmd="python3 - <<'PY'\nraise AssertionError()\nPY\ngit worktree add /tmp/test feature/test"
        self.assertEqual(self.rule(cmd),'git-unchecked-preflight')

    def test_git_worktree_checked_chain_allowed(self):
        self.assertIsNone(self.rule("python3 - <<'PY' &&\nassert True\nPY\ngit worktree add /tmp/test feature/test"))
        self.assertIsNone(self.rule('git worktree add /tmp/test feature/test'))

    def test_checked_chain_allowed(self):
        self.assertIsNone(self.rule("python3 - <<'PY' &&\nassert True\nPY\ncargo build"))
        self.assertIsNone(self.rule('cargo build --locked'))

    def test_non_python_and_non_cargo_allowed(self):
        self.assertIsNone(self.rule("cat <<'PY'\ntext\nPY\ncargo build"))
        self.assertIsNone(self.rule("python3 - <<'PY'\nassert True\nPY\ngit status"))

    def test_only_following_command_is_examined(self):
        self.assertIsNone(self.rule("python3 - <<'PY'\ntext = 'cargo build'\nPY\necho done"))

    def test_edit_then_verify_fallthrough_denied(self):
        # 2026-10-08 and 2026-10-10 (ai-mall): the edit script aborted, the tests ran anyway on old content
        for follow in ['(pnpm --filter @crossec/api exec vitest run x.test.ts > log 2>&1)',
                       'pnpm --filter @crossec/api exec vitest run x.test.ts',
                       'node scripts/mutation-check.mjs a.ts --test-path=a.test.ts',
                       'npx vitest run', 'pytest -q']:
            with self.subTest(follow=follow):
                cmd = "python3 - <<'EOF'\nassert s.count(old) == 2\nEOF\n" + follow
                self.assertEqual(self.rule(cmd), 'edit-then-verify-unchained')

    def test_edit_then_verify_checked_chain_allowed(self):
        self.assertIsNone(self.rule("python3 - <<'EOF' && pnpm --filter x exec vitest run\nassert True\nEOF"))
        self.assertIsNone(self.rule("python3 - <<'EOF' &&\nassert True\nEOF\npnpm --filter x exec vitest run"))
        self.assertIsNone(self.rule('pnpm --filter x exec vitest run'))
        self.assertIsNone(self.rule("python3 - <<'EOF'\nassert True\nEOF\ngit status --short"))


if __name__ == '__main__':
    unittest.main()
