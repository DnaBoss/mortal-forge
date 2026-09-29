import subprocess
import unittest
from unittest.mock import Mock

import audit_futures_empty_bars as tool


class AuditFuturesEmptyBarsTests(unittest.TestCase):
    def test_sends_one_read_only_batched_query_and_returns_database_result(self):
        completed = subprocess.CompletedProcess([], 0, b'[{"symbol":"TXF"}]\n', b"")
        runner = Mock(return_value=completed)

        result = tool.run_once(runner=runner)

        self.assertEqual((result.stdout, result.stderr, result.returncode),
                         (completed.stdout, completed.stderr, 0))
        runner.assert_called_once()
        call = runner.call_args
        self.assertEqual(call.args[0], [
            "docker", "exec", "-i", "helios-postgres", "psql", "-X", "-q", "-A", "-t",
            "-v", "ON_ERROR_STOP=1", "-U", "helios", "-d", "helios",
        ])
        sql = call.kwargs["input"].decode()
        self.assertIn("BEGIN READ ONLY", sql)
        self.assertIn("FROM mkt_1m", sql)
        self.assertIn("volume = 0", sql)
        self.assertIn("volume IS NULL", sql)
        self.assertIn("quality_status", sql)
        self.assertEqual(call.kwargs["timeout"], 150)

    def test_timeout_stops_without_retry(self):
        runner = Mock(side_effect=subprocess.TimeoutExpired(["docker"], 150))

        result = tool.run_once(runner=runner)

        self.assertEqual(result.returncode, 124)
        self.assertIn(b"timed out", result.stderr)
        runner.assert_called_once()


if __name__ == "__main__":
    unittest.main()
