"""Prevent unconditional Cargo execution after a Python preflight heredoc."""
import unittest
import write_guard


class PreflightOrderTest(unittest.TestCase):
    def rule(self, cmd):
        return write_guard.verdict({'tool_input': {'cmd': cmd}})[0]

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


if __name__ == '__main__':
    unittest.main()
