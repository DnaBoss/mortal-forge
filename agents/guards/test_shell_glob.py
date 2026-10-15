"""An unquoted glob that matches nothing makes zsh abort the whole command line ("no matches found")."""
import os
import tempfile
import unittest
import write_guard
from shell_glob_guard import unmatched_glob


class ShellGlobTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.base = self.dir.name
        os.makedirs(os.path.join(self.base, "src", "auth"))
        for name in ("vitest.config.ts", "src/auth/auth.routes.ts"):
            open(os.path.join(self.base, name), "w").close()

    def tearDown(self):
        self.dir.cleanup()

    def test_the_incident_shapes_flagged(self):
        # 2026-10-10: each of these aborted the whole line, so the rg in front of the pipe never ran
        for cmd, word in [
            ("rg -n TZ vitest.config.* vitest.setup.* 2>/dev/null | head", "vitest.setup.*"),
            ("rg -n me src/auth/*.routes.ts src/user/*.routes.ts", "src/user/*.routes.ts"),
            ("cd src && ls auth/*.ts user/*.ts", "user/*.ts"),
            ("find . -name *.tmp", "*.tmp"),
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(unmatched_glob(cmd, self.base), word)

    def test_unquoted_question_mark_flagged(self):
        # 2026-10-10 (second time): a URL query string is a glob to zsh, and the whole line aborted
        for cmd, word in [
            ("gh api repos/o/r/actions/runs/1/jobs?per_page=50 --jq .x", "repos/o/r/actions/runs/1/jobs?per_page=50"),
            ("tail -n 1 out.log; gh api repos/o/r/pulls?state=open", "repos/o/r/pulls?state=open"),
            ("curl -s https://example.test/health?verbose=1", "https://example.test/health?verbose=1"),
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(unmatched_glob(cmd, self.base), word)

    def test_question_mark_quoted_or_matching_allowed(self):
        for cmd in [
            "gh api 'repos/o/r/actions/runs/1/jobs?per_page=50'",
            'gh api "repos/o/r/pulls?state=open"',
            "ls vitest.config.t?",
            "echo $?",
            "test $? -eq 0 && echo ok",
            "GLOB_OK=1 curl -s https://example.test/health?verbose=1",
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(unmatched_glob(cmd, self.base))

    def test_matching_or_quoted_globs_allowed(self):
        for cmd in [
            "ls vitest.config.*",
            "rg -n x src --glob '!*.test.ts'",
            'rg -n "a.*b" src',
            "find . -name '*.tmp'",
            "ls src/**/*.routes.ts",
            "echo done \\*",
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(unmatched_glob(cmd, self.base))

    def test_unsure_cases_fail_open(self):
        for cmd in [
            "ls $S/missing-*.log",
            'case "$run" in *:completed:*) break;; esac',
            "[[ $x == *foo* ]] && echo y",
            "echo $((2 * 3))",
            'cd "$DIR" && ls nothing-*.txt',
            "python3 - <<'EOF'\nprint(2 * 3)\nEOF",
            "ls nothing-[ab]*.txt",
            "GLOB_OK=1 ls nothing-*.txt",
            "ls 'unbalanced-*.txt",
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(unmatched_glob(cmd, self.base))

    def test_wired_for_the_zsh_tool_only(self):
        old = os.environ.get("SHELL")
        os.environ["SHELL"] = "/usr/bin/zsh"
        try:
            cmd = "ls nothing-here-*.txt"
            self.assertEqual(
                write_guard.verdict({"tool_input": {"command": cmd}, "cwd": self.base})[0], "unmatched-shell-glob")
            self.assertIsNone(write_guard.verdict({"tool_input": {"cmd": cmd}, "cwd": self.base})[0])
            os.environ["SHELL"] = "/bin/bash"
            self.assertIsNone(write_guard.verdict({"tool_input": {"command": cmd}, "cwd": self.base})[0])
        finally:
            if old is None:
                os.environ.pop("SHELL", None)
            else:
                os.environ["SHELL"] = old


if __name__ == "__main__":
    unittest.main()
