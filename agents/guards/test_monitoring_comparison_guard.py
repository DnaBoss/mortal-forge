#!/usr/bin/env python3
"""Run the existing comparison guard entry point against owned source fixtures."""
import json
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
DOCKER = Path('/home/cash/work_space/private/aletheia/scripts/monitoring/verify_docker_source.py')
COMMAND = 'python3 scripts/monitoring/verify_docker_source.py --status-lifecycle --output unused.json'


def hook(command, docker_source=None, otel_source=None):
    with tempfile.TemporaryDirectory(prefix='comparison-guard-test-') as temporary:
        root = Path(temporary)
        overrides = {}
        for field, source in [('DOCKER_SCRIPT', docker_source), ('SCRIPT', otel_source)]:
            if source is not None:
                path = root / (field + '.py')
                path.write_text(source)
                overrides[field] = str(path)
        runner = (
            "import importlib.util,json,sys; from pathlib import Path; "
            "spec=importlib.util.spec_from_file_location('guard',sys.argv[1]); "
            "guard=importlib.util.module_from_spec(spec); spec.loader.exec_module(guard); "
            "[setattr(guard,key,Path(value)) for key,value in json.loads(sys.argv[2]).items()]; "
            "raise SystemExit(guard.main())"
        )
        return subprocess.run(
            [sys.executable, '-c', runner, str(HERE / 'monitoring_comparison_guard.py'), json.dumps(overrides)],
            input=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}}),
            capture_output=True, text=True, timeout=5,
        )


def saved_rows_line(source):
    return next(line for line in source.splitlines() if line.strip().startswith('frame["rows"] ='))


def lifecycle_source():
    source = DOCKER.read_text()
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'lifecycle_rows')
    return ast.get_source_segment(source, function) + '\n'


class MonitoringComparisonGuardTests(unittest.TestCase):
    def test_old_unsaved_docker_fixture_is_rejected_by_real_entry(self):
        source = lifecycle_source()
        old = source.replace(saved_rows_line(source), '    # old failure path: no raw rows retained')
        result = hook(COMMAND, docker_source=old)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_current_fixed_docker_source_is_allowed_by_real_entry(self):
        result = hook(COMMAND)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_late_saved_rows_are_rejected(self):
        source = lifecycle_source()
        line = saved_rows_line(source)
        source = source.replace(line, '').replace('    return rows\n', line + '\n    return rows\n', 1)
        result = hook(COMMAND, docker_source=source)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_incomplete_or_unattached_or_filtered_raw_rows_are_rejected(self):
        source = lifecycle_source()
        variants = [
            source.replace('"canonical_base64": base64.b64encode(row[3]).decode()', '"canonical_base64": ""', 1),
            source.replace('    reads.append(frame)', '    # frame not attached to proof', 1),
            source.replace('    reads.append(frame)', '    if False:\n        reads.append(frame)', 1),
            source.replace('for row in rows]', 'for row in rows[:8]]', 1),
            source.replace('"rejected": row[2]', '"rejected": row[1]', 1),
        ]
        for candidate in variants:
            with self.subTest(candidate=candidate[saved_rows_line(source).find('frame'):][:80]):
                result = hook(COMMAND, docker_source=candidate)
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_other_docker_modes_do_not_require_lifecycle_capture(self):
        for mode in ['--status-source', '--status-homepage', '--capacity-homepage', '']:
            result = hook('python3 scripts/monitoring/verify_docker_source.py ' + mode, docker_source='')
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_otel_positive_and_negative_fixtures_still_apply(self):
        source = '''def verify():
    if normalized_message != actual_message:
        evidence = {"comparison_mismatch": {"actual": actual_message, "expected": normalized_message, "signal": "metrics"}}
        raise RuntimeError("comparison")
'''
        command = 'python3 scripts/monitoring/verify_otel_collector.py --output unused.json'
        self.assertEqual(hook(command, otel_source=source).returncode, 0)
        unsafe = source.replace('        evidence = ', '        discarded = ').replace('"actual": actual_message, ', '')
        self.assertEqual(hook(command, otel_source=unsafe).returncode, 2)

    def test_current_otel_source_still_allowed(self):
        result = hook('python3 scripts/monitoring/verify_otel_collector.py --output unused.json')
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
