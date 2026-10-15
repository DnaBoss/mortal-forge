import tempfile
from pathlib import Path
import unittest
from postgres_backup_guard import problem
from write_guard import verdict

class BackupVersionGuardTests(unittest.TestCase):
    def test_host_dump_and_restore_target_are_blocked(self):
        for tool in ('pg_dump','pg_restore','/usr/bin/pg_dump'):
            self.assertIsNotNone(problem(f'{tool} --port 5434 --dbname crossec_3018_returns', '/tmp'))
    def test_python_heredoc_is_blocked(self):
        command="python3 - <<'PY'\nassert port == 5434\nrun(['pg_dump', '--file', output])\nPY\n"
        self.assertIsNotNone(problem(command,'/tmp'))
        result=verdict({'tool_name':'Bash','tool_input':{'cmd':command},'cwd':'/tmp'})
        self.assertEqual(result[0],'postgres-backup-version')
    def test_external_python_script_is_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'restore.py';path.write_text("db='crossec_3018_returns'\nrun(['pg_restore', '--dbname', db])\n")
            self.assertIsNotNone(problem(f'python3 {path}',folder))
    def test_container_tools_and_readonly_inspection_allowed(self):
        for cmd in ('docker exec own-db pg_dump --dbname crossec_3018_returns', 'pg_dump --version', 'pg_restore --list /tmp/crossec_3018.dump', 'cat /tmp/restore.py', 'pg_dump --port 5432 --dbname other'):
            self.assertIsNone(problem(cmd,'/tmp'))
    def test_python_container_allowed(self):
        self.assertIsNone(problem("python3 - <<'PY'\ndb='crossec_3018_returns'\nrun(['docker','exec','own-db','pg_dump',db])\nPY\n",'/tmp'))
    def test_file_creation_is_not_execution(self):
        self.assertIsNone(problem("cat > /tmp/example.py <<'PY'\ndb='crossec_3018_returns'\nrun(['pg_dump',db])\nPY\n",'/tmp'))

if __name__=='__main__':unittest.main()
