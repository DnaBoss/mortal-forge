"""`git stash pop|drop|clear` touch a stash list shared by every worktree of the repository."""
import unittest
import write_guard


class StashSharedTest(unittest.TestCase):
    def rule(self, cmd):
        return write_guard.verdict({'tool_input': {'cmd': cmd}})[0]

    def test_pop_drop_clear_denied(self):
        for cmd in ['git stash pop', 'git stash pop -q', 'git stash drop', 'git stash drop stash@{1}',
                    'git stash clear', 'git -C /tmp/x stash pop']:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.rule(cmd), 'stash-shared-removal')

    def test_the_incident_shape_denied(self):
        # the push sits behind a failed && chain; the pop after ';' still runs and takes someone else's entry
        cmd = 'cp missing .env && git stash -q && (pnpm test); git stash pop -q && echo done'
        self.assertEqual(self.rule(cmd), 'stash-shared-removal')

    def test_explicit_flag_allows(self):
        self.assertIsNone(self.rule('STASH_OK=1; git stash list && git stash pop'))

    def test_reading_and_storing_allowed(self):
        for cmd in ['git stash list', 'git stash show --stat stash@{0}', 'git stash', 'git stash push -m x -- a.ts',
                    'git stash store -m msg 0123abc', 'echo "git stash pop"', 'git log --grep "stash pop"']:
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.rule(cmd))


if __name__ == '__main__':
    unittest.main()
