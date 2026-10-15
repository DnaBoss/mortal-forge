#!/usr/bin/env python3
"""Exercise the Docker guard's real JSON hook entry point with Python heredocs."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


GUARD = Path(__file__).with_name('docker_scope_guard.py')


def heredoc(body):
    return "python3 - <<'PY'\n" + body + "\nPY\n"


def hook(command, key='command'):
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps({'tool_name': 'Bash', 'tool_input': {key: command}}),
        capture_output=True, text=True, timeout=5,
    )


class DockerAbsenceCaseGuardTests(unittest.TestCase):
    def test_raw_stderr_membership_is_rejected(self):
        for stderr in ['stderr', 'result.stderr', 'result.stderr.decode()']:
            for operator in ['in', 'not in']:
                with self.subTest(stderr=stderr, operator=operator):
                    result = hook(heredoc(f"assert 'No such object' {operator} {stderr}"))
                    self.assertEqual(result.returncode, 2, result.stderr)

    def test_lower_and_casefold_accept_both_docker_diagnostic_cases(self):
        for normalize in ['lower', 'casefold']:
            for diagnostic in ['error: no such object: owned-cid', 'Error: No such object: owned-cid']:
                body = (
                    "from types import SimpleNamespace\n"
                    f"result = SimpleNamespace(stderr={diagnostic!r})\n"
                    f"assert 'no such object' in result.stderr.{normalize}()"
                )
                command = heredoc(body)
                with self.subTest(normalize=normalize, diagnostic=diagnostic):
                    result = hook(command)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    executed = subprocess.run(['sh', '-c', command], capture_output=True, text=True, timeout=5)
                    self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_uppercase_needle_against_lowered_stderr_is_rejected(self):
        result = hook(heredoc("assert 'No such object' in result.stderr.lower()"))
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_cmd_input_uses_same_rule(self):
        result = hook(heredoc("assert 'No such object' in result.stderr"), key='cmd')
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_document_reference_is_allowed(self):
        command = "cat <<'DOC'\npython3 - <<'PY'\nassert 'No such object' in result.stderr\nPY\nDOC\n"
        self.assertEqual(hook(command).returncode, 0)

    def test_other_values_and_diagnostics_are_allowed(self):
        for body in ["assert 'No such object' in expected_text", "assert 'permission denied' in result.stderr", "note = \"'No such object' in result.stderr\""]:
            with self.subTest(body=body):
                self.assertEqual(hook(heredoc(body)).returncode, 0)

    def test_original_docker_scope_entry_still_allows_protected_verifier(self):
        result = hook('python3 scripts/monitoring/verify_docker_source.py --output unused.json')
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
