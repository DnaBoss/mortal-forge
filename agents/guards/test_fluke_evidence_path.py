import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import write_guard

EXACT_ORIGINAL_COMMAND = "python3 - <<'PY'\nimport pathlib,json\np=pathlib.Path('docs/superpowers/evidence/s07b-teaching-20261004');d=json.loads((p/'s07b-source-principle-gap-inventory-readback.json').read_text());print(json.dumps(d,indent=2)[:2500])\nPY"


class FlukeEvidencePathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fluke = Path(self.tmp.name) / 'Fluke'
        self.base = self.fluke / 'task/docs/superpowers/evidence/run'
        self.base.mkdir(parents=True)
        (self.base / 'known.json').write_text('{}')

    def tearDown(self):
        self.tmp.cleanup()

    def rule(self, body):
        command = "python3 - <<'PY'\nfrom pathlib import Path\nimport json\n" + body + '\nPY'
        with patch.object(write_guard, 'FLUKE_WORKSPACES', str(self.fluke), create=True):
            return write_guard.verdict({'tool_name': 'exec_command', 'tool_input': {
                'cmd': command, 'workdir': str(self.fluke / 'task')}})[0]

    def test_root_json_join_missing_rejected(self):
        body = f"p=Path({str(self.base)!r});json.loads((p/'wrong.json').read_text())"
        self.assertEqual(self.rule(body), 'fluke-evidence-read-path')

    def test_unmodified_original_module_command_rejected(self):
        payload = {'tool_name': 'exec_command', 'tool_input': {
            'cmd': EXACT_ORIGINAL_COMMAND,
            'workdir': '/home/cash/orca/workspaces/Fluke/riichi-finetune'}}
        self.assertEqual(write_guard.verdict(payload)[0], 'fluke-evidence-read-path')

    def test_imported_module_and_alias_known_literals_rejected(self):
        for body in [f"import pathlib,json\np=pathlib.Path({str(self.base)!r});(p/'wrong.json').read_text()",
                     f"import pathlib as paths\np=paths.Path({str(self.base)!r});(p/'wrong.json').read_bytes()"]:
            with self.subTest(body=body):
                self.assertEqual(self.rule(body), 'fluke-evidence-read-path')

    def test_module_reassignment_and_unrecognized_object_allowed(self):
        for body in [f"import pathlib\npathlib=other\np=pathlib.Path({str(self.base)!r});(p/'wrong.json').read_text()",
                     f"import pathlib as paths\npaths=other\np=paths.Path({str(self.base)!r});(p/'wrong.json').read_text()",
                     f"import pathlib\nimport other as pathlib\np=pathlib.Path({str(self.base)!r});(p/'wrong.json').read_text()",
                     f"import pathlib\nfrom other import pathlib\np=pathlib.Path({str(self.base)!r});(p/'wrong.json').read_text()",
                     f"p=other.Path({str(self.base)!r});(p/'wrong.json').read_text()"]:
            with self.subTest(body=body):
                self.assertIsNone(self.rule(body))

    def test_module_existing_dynamic_outside_and_write_allowed(self):
        for expression in [f"p=pathlib.Path({str(self.base)!r});(p/'known.json').read_text()",
                           f"p=pathlib.Path({str(self.base)!r});(p/name).read_text()",
                           f"p=pathlib.Path({str(self.base)!r});(p/'new.json').write_text('{{}}')",
                           "pathlib.Path('/nonexistent/docs/superpowers/evidence/x.json').read_text()"]:
            with self.subTest(expression=expression):
                self.assertIsNone(self.rule('import pathlib\n' + expression))

    def test_correct_literal_join_allowed(self):
        self.assertIsNone(self.rule(f"p=Path({str(self.base)!r});json.loads((p/'known.json').read_text())"))

    def test_multiple_literal_joins_and_alias_rejected(self):
        self.assertEqual(self.rule(f"p=Path({str(self.base.parent)!r});q=p/'run';r=q/'wrong.json';r.read_bytes()"), 'fluke-evidence-read-path')

    def test_direct_absolute_read_rejected(self):
        self.assertEqual(self.rule(f"Path({str(self.base / 'wrong.json')!r}).read_bytes()"), 'fluke-evidence-read-path')

    def test_open_read_forms_rejected(self):
        for expression in ["(p/'wrong.json').open()", "(p/'wrong.json').open(mode='rb')", "open(p/'wrong.json', 'r')"]:
            with self.subTest(expression=expression):
                self.assertEqual(self.rule(f"p=Path({str(self.base)!r});{expression}"), 'fluke-evidence-read-path')

    def test_writes_and_created_then_read_allowed(self):
        for expression in ["(p/'new.json').write_text('{}')", "(p/'new.json').write_bytes(b'{}')", "(p/'new.json').open('w')", "open(p/'new.json',mode='wb')", "(p/'new.json').write_text('{}');(p/'new.json').read_text()"]:
            with self.subTest(expression=expression):
                self.assertIsNone(self.rule(f"p=Path({str(self.base)!r});{expression}"))

    def test_dynamic_paths_and_modes_allowed(self):
        for expression in ["(p/name).read_text()", "Path(value).read_text()", "p.joinpath('wrong.json').read_text()", "(p/'wrong.json').open(mode=mode)", "p=other;(p/'wrong.json').read_text()"]:
            with self.subTest(expression=expression):
                self.assertIsNone(self.rule(f"p=Path({str(self.base)!r});{expression}"))

    def test_outside_evidence_allowed(self):
        self.assertIsNone(self.rule(f"Path({str(self.fluke / 'task/cache/wrong.json')!r}).read_text()"))
        self.assertIsNone(self.rule("Path('/nonexistent/docs/superpowers/evidence/wrong.json').read_text()"))

    def test_nonexecuted_and_invalid_source_allowed(self):
        self.assertIsNone(self.rule(f"def unused():\n    Path({str(self.base / 'wrong.json')!r}).read_text()"))
        self.assertIsNone(self.rule("Path('invalid').read_text(??)"))
        payload = {'tool_input': {'cmd': f"cat <<'PY'\nPath({str(self.base / 'wrong.json')!r}).read_text()\nPY"}}
        self.assertIsNone(write_guard.verdict(payload)[0])

    def test_manual_true_hook_json_actual_root_paths(self):
        base = '/home/cash/orca/workspaces/Fluke/riichi-finetune/docs/superpowers/evidence/s07b-teaching-20261004'
        for name, denied in [('s07b-source-principle-gap-inventory-readback.json', True), ('s07b-source-principle-gap-readback.json', False)]:
            command = f"python3 - <<'PY'\nfrom pathlib import Path\nimport json\np=Path({base!r});json.loads((p/{name!r}).read_text())\nPY"
            payload = {'tool_name': 'exec_command', 'tool_input': {'cmd': command, 'workdir': '/home/cash/orca/workspaces/Fluke/riichi-finetune'}}
            result = subprocess.run([sys.executable, write_guard.__file__], input=json.dumps(payload), text=True, capture_output=True, timeout=5, check=True)
            self.assertEqual(bool(result.stdout), denied)
            if denied:
                self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')


if __name__ == '__main__':
    unittest.main()
