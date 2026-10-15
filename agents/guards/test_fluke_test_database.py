import unittest
import write_guard
FLUKE = '/home/cash/orca/workspaces/Fluke/riichi-finetune'
class FlukeTestDatabaseTest(unittest.TestCase):
    def rule(self, cmd, cwd=FLUKE):
        return write_guard.verdict({'tool_input': {'cmd': cmd, 'workdir': cwd}})[0]
    def test_wrong_fixture_denied(self):
        self.assertEqual(self.rule('docker run --rm -e POSTGRES_DB=fluke_test postgres:16-alpine'), 'fluke-test-database')
    def test_wrong_url_denied(self):
        self.assertEqual(self.rule('export FLUKE_TEST_DATABASE_URL=postgres://tester:test@127.0.0.1:5432/fluke_test\n./scripts/check.sh pre-push'), 'fluke-test-database')
    def test_other_literal_database_denied(self):
        self.assertEqual(self.rule('FLUKE_TEST_DATABASE_URL="postgresql://tester:test@localhost:5432/test_other?sslmode=disable" cargo test'), 'fluke-test-database')
    def test_expected_allowed(self):
        self.assertIsNone(self.rule('docker run -e POSTGRES_DB=fluke_v1_ledger_test postgres:16-alpine'))
        self.assertIsNone(self.rule('export FLUKE_TEST_DATABASE_URL=postgres://tester:test@127.0.0.1:5432/fluke_v1_ledger_test\n./scripts/check.sh pre-push'))
    def test_other_repo_allowed(self):
        self.assertIsNone(self.rule('docker run -e POSTGRES_DB=fluke_test postgres:16-alpine', '/home/cash/work_space/private/aletheia'))
    def test_readonly_mentions_allowed(self):
        for cmd in ["rg 'POSTGRES_DB=fluke_test' docs", "echo 'FLUKE_TEST_DATABASE_URL=postgres://localhost/fluke_test'", "cat <<'EOF'\nPOSTGRES_DB=fluke_test\nEOF", "python3 -c 'print(\"POSTGRES_DB=fluke_test\")'", '# POSTGRES_DB=fluke_test', "env rg 'POSTGRES_DB=fluke_test' docs"]:
            self.assertIsNone(self.rule(cmd), cmd)
    def test_dynamic_allowed(self):
        for cmd in ['docker run -e POSTGRES_DB=$task_db postgres:16-alpine', 'export FLUKE_TEST_DATABASE_URL="postgres://tester:test@localhost:$port/$task_db"', 'export FLUKE_TEST_DATABASE_URL="$url"']:
            self.assertIsNone(self.rule(cmd), cmd)
    def test_cd_other_repo_allowed(self):
        self.assertIsNone(self.rule('cd /home/cash/work_space/private/aletheia\ndocker run -e POSTGRES_DB=fluke_test postgres:16-alpine'))
    def test_cd_fluke_denied(self):
        self.assertEqual(self.rule('cd /home/cash/orca/workspaces/Fluke/riichi-finetune\ndocker run -e POSTGRES_DB=fluke_test postgres:16-alpine', '/tmp'), 'fluke-test-database')
    def test_quoted_document_write_allowed(self):
        self.assertIsNone(self.rule("printf '%s' 'POSTGRES_DB=fluke_test' > note.md"))
    def test_real_hook_process_deny_and_allow(self):
        import json
        import subprocess
        import sys
        from pathlib import Path
        for database, denied in [('fluke_test', True), ('fluke_v1_ledger_test', False)]:
            payload = {'tool_name':'exec_command', 'tool_input':{'workdir':FLUKE,
                'cmd':'docker create -e POSTGRES_DB=' + database + ' postgres:16-alpine'}}
            result = subprocess.run([sys.executable, str(Path(write_guard.__file__))],
                input=json.dumps(payload), text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0)
            if denied:
                decision = json.loads(result.stdout)['hookSpecificOutput']
                self.assertEqual(decision['permissionDecision'], 'deny')
                self.assertEqual(decision['hookEventName'], 'PreToolUse')
                self.assertIn('fluke_v1_ledger_test', decision['permissionDecisionReason'])
            else:
                self.assertEqual(result.stdout, '')
if __name__ == '__main__':
    unittest.main()
