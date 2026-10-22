"""`git rev-parse --short` (or --verify) takes one revision; two print nothing and fail."""
import unittest
import write_guard


class RevParseManyTest(unittest.TestCase):
    def rule(self, cmd):
        return write_guard.verdict({'tool_input': {'cmd': cmd}})[0]

    def test_two_revisions_denied(self):
        for cmd in ['git rev-parse --short HEAD origin/dev',
                    'git -C /tmp/x rev-parse --short origin/dev origin/main',
                    'git rev-parse --verify HEAD origin/dev',
                    'git rev-parse --short=9 HEAD origin/dev',
                    'cd x && git rev-parse --short HEAD origin/feature/y && echo ok']:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.rule(cmd), 'rev-parse-many')

    def test_one_revision_per_call_allowed(self):
        for cmd in ['git rev-parse --short HEAD',
                    'git rev-parse --short HEAD 2>/dev/null',
                    'git rev-parse --short HEAD; git rev-parse --short origin/dev',
                    'git rev-parse HEAD origin/dev',
                    'git rev-parse --show-toplevel',
                    'git rev-parse --abbrev-ref HEAD',
                    'echo "git rev-parse --short A B"',
                    'git log -1 --format=%h origin/dev']:
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.rule(cmd))


if __name__ == '__main__':
    unittest.main()
