"""Contract fixtures: accepting each invalid stream would hide a named defect."""
import json
import subprocess
import sys
import unittest
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

class Checkpoints(unittest.TestCase):
    def test_cli_rejects_invalid_and_accepts_valid(self):
        for name, code in [('valid-lifecycle', 0), ('invalid-step-skip', 1)]:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_checkpoints.py'),
                                     str(ROOT / f'tests/fixtures/{name}.jsonl')], capture_output=True)
            self.assertEqual(result.returncode, code, result.stderr)

    def test_cli_rejects_bad_json_without_echoing_secrets(self):
        valid = (ROOT / 'tests/fixtures/valid-lifecycle.jsonl').read_text().splitlines()[0]
        for content in ['', '{"secret":"SENTINEL_SECRET",', 'NaN', valid.replace('"iteration": 1', '"iteration": 1e999'), valid.replace('"iteration": 1', '"iteration": 1, "iteration": 1')]:
            with self.subTest(content_kind=len(content)), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'input.jsonl'
                path.write_text(content)
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_checkpoints.py'), str(path)], capture_output=True)
                self.assertEqual(result.returncode, 1)
                self.assertNotIn(b'SENTINEL_SECRET', result.stdout + result.stderr)
                self.assertNotIn(b'Traceback', result.stdout + result.stderr)

    def test_infinite_measurement_is_rejected(self):
        from validate_checkpoints import validate_records
        record = json.loads((ROOT / 'tests/fixtures/valid-task-only.jsonl').read_text())
        record['usage']['elapsed_seconds'] = dict(value=float('inf'), status='exact', source='clock')
        self.assertTrue(validate_records([record]))


def fixture_test(path):
    def test(self):
        from validate_checkpoints import validate_records
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        errors = validate_records(rows)
        self.assertEqual(not errors, path.name.startswith('valid-'), errors)
    return test

for path in sorted((ROOT / 'tests/fixtures').glob('*.jsonl')):
    setattr(Checkpoints, 'test_' + path.stem.replace('-', '_'), fixture_test(path))

if __name__ == '__main__':
    unittest.main()
