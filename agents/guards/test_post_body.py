"""Writing a comment body and posting it in one command: the text goes out before anything was checked."""
import unittest
from post_body_guard import written_and_posted


class PostBodyTest(unittest.TestCase):
    def test_the_incident_shapes_flagged(self):
        # 2026-10-10: "13 screenshots" was typed into the body and posted; the count (12) ran in the same command
        cmd = ("cat > $S/comments/qa-2948.md <<'EOF'\n截圖 13 張\nEOF\n"
               "gh api repos/o/r/issues/2948/comments -F body=@$S/comments/qa-2948.md --jq .html_url; ls shots | rg -c '^qa-'")
        self.assertEqual(written_and_posted(cmd), "$S/comments/qa-2948.md")
        self.assertEqual(written_and_posted("echo hi > /tmp/b.md && gh pr create --body-file /tmp/b.md"), "/tmp/b.md")
        self.assertEqual(written_and_posted("sed -i 's/13/12/' /tmp/b.md && gh api x -F body=@/tmp/b.md"), "/tmp/b.md")
        self.assertEqual(written_and_posted('printf x >> "/tmp/b.md"; gh api x -F body=@"/tmp/b.md"'), "/tmp/b.md")

    def test_separate_steps_allowed(self):
        for cmd in [
            "gh api repos/o/r/issues/1/comments -F body=@/tmp/b.md",            # post only
            "cat > /tmp/b.md <<'EOF'\ntext\nEOF\nwc -l /tmp/b.md",               # write only
            "echo log > /tmp/run.log; gh api x -F body=@/tmp/b.md",             # writes another file
            "gh api x -F body=@/tmp/b.md 2>/dev/null",                           # stderr redirect is not a write of the body
            "gh api x -F body=@/tmp/b.md > /tmp/out.json",                       # output saved elsewhere
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(written_and_posted(cmd))

    def test_escape_hatch(self):
        self.assertIsNone(written_and_posted("POST_OK=1 echo hi > /tmp/b.md && gh api x -F body=@/tmp/b.md"))


if __name__ == "__main__":
    unittest.main()
