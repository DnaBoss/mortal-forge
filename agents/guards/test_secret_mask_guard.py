"""sed/perl substitution that masks a secret after printing it: fails open when the regex misses."""
import unittest
from secret_mask_guard import problem


class SecretMaskTest(unittest.TestCase):
    def test_incident_shapes_flagged(self):
        for cmd in [
            # 2026-10-19 ai-mall #3207: the mask missed and the seed password was printed
            "grep -o 'SEED_EMAIL=[^ ]* .{0,200}' log.jsonl | head -5 | sed 's/SEED_PASSWORD=[^ ]*/SEED_PASSWORD=***/'",
            "sed -E 's/(password|PASSWORD)[^,}]*/\\1:<masked>/g' $S/seed.mjs | head -120",
            "rg -o 'input.{0,300}' t.jsonl | sed -E 's/(password|密碼)[^,]*/\\1:<masked>/Ig' | head -8",
            "rg -n DATABASE_URL apps/api/.env | sed 's/:[^:@]*@/:***@/'",
            "grep -E '^DATABASE_URL' .env | sed -E 's#//[^@]*@#//***@#'",
            "curl -s localhost:7000 | perl -pe 's/token=\\w+/token=REDACTED/g'",
            "cat cfg | sed -e 's|secret: .*|secret: [hidden]|'",
        ]:
            with self.subTest(cmd=cmd):
                self.assertTrue(problem(cmd))

    def test_allowed(self):
        for cmd in [
            "sed -n 1,40p scripts/lib/mask.mjs | rg -n '//' | head -12",   # reads code about masking
            "sed -i 's/請確認貨號/請確認號碼/' spec.ts",                      # normal substitution
            "sed 's/\\*\\*/__/g' README.md",                                 # markdown bold, not a mask
            "echo 's/x/***/'",                                               # no sed or perl
            "python3 - <<'EOF'\nimport subprocess\nsubprocess.run(['sed', 's/a/***/'])\nEOF\nls",  # heredoc body
            "rg -c password .env",                                           # count only
            "sed -n 's/^PORT=//p' .env",                                     # prints a non-secret field
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(problem(cmd))


if __name__ == "__main__":
    unittest.main()
