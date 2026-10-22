"""errexit or && after a pipe without pipefail: a failure before the last pipe stage is invisible."""
import unittest
from errexit_pipefail_guard import problem


class ErrexitPipefailTest(unittest.TestCase):
    def test_incident_shapes_flagged(self):
        for cmd in [
            # 2026-09-30 JobResearch
            "uv run pytest -q | tail -1 && git commit -m x",
            # 2026-10-16 local-mall-monitoring: set -e without pipefail, piped check, then checkpoint
            "set -e; python3 check.py | tee out.log; uv run python3 /home/cash/tools/cash_rule_checkpoint.py f --task t",
            "set -eu\nrg -c x file | head -n 1\ncp a b",
            "set -o errexit; a | b",
            "setopt err_exit; a |& b",
            "make test | tail -n 3 && cash-rule-checkpoint f --task t",
        ]:
            with self.subTest(cmd=cmd):
                self.assertTrue(problem(cmd))

    def test_allowed(self):
        for cmd in [
            "setopt pipefail; set -e; a | b; git commit -m x",
            "set -o pipefail; uv run pytest -q | tail -1 && git commit -m x",
            "set -e; a; b && git commit -m x",                     # no pipe
            "a | b; git commit -m x",                              # commit not chained to the pipe with &&
            "a || b && git commit -m x",                           # || is not a pipe
            "echo 'set -e; a | b'",                                # quoted text
            "python3 - <<'EOF'\nimport os\nx = 1 | 2\nEOF\nset -e; cp a b",  # pipe only inside heredoc body
            "rg -n x file | head -n 5",                            # plain read pipeline
            "PIPE_OK=1 set -e; a | b",
        ]:
            with self.subTest(cmd=cmd):
                self.assertFalse(problem(cmd))


if __name__ == "__main__":
    unittest.main()
