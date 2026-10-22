import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import write_guard

BASE = '/home/cash/.agents/evidence/fluke-evidence-read-20261004'
ORIGINAL = "python3 - <<'PY'\nimport pathlib,json\np=pathlib.Path(" + repr(BASE) + ");d=json.loads((p/'v2-manual-hook-evidence.json').read_text());print(d['cases'])\nPY"

class EvidenceJsonKeyTests(unittest.TestCase):
    def rule(self, body):
        return write_guard.verdict({'tool_input': {'cmd': "python3 - <<'PY'\nimport pathlib,json\np=pathlib.Path(" + repr(BASE) + ");" + body + '\nPY'}})[0]

    def test_original_missing_key_rejected(self):
        self.assertEqual(write_guard.verdict({'tool_input': {'cmd': ORIGINAL}})[0], 'evidence-json-key')

    def test_actual_key_allowed(self):
        self.assertIsNone(self.rule("d=json.loads((p/'v2-manual-hook-evidence.json').read_text());print(d['manual_cases'])"))

    def test_dynamic_and_nested_allowed(self):
        for tail in ["print(d[name])", "print(d['manual_cases'][0]['missing'])", "print('d[\"cases\"]')", "d['cases']=[]"]:
            with self.subTest(tail=tail):
                self.assertIsNone(self.rule("d=json.loads((p/'v2-manual-hook-evidence.json').read_text());" + tail))

    def test_reassignment_and_module_rebinding_allowed(self):
        for body in ["d=json.loads((p/'v2-manual-hook-evidence.json').read_text());d=other;print(d['cases'])", "json=other;d=json.loads((p/'v2-manual-hook-evidence.json').read_text());print(d['cases'])", "pathlib=other;p=pathlib.Path('/unknown');d=json.loads((p/'v2-manual-hook-evidence.json').read_text());print(d['cases'])"]:
            with self.subTest(body=body): self.assertIsNone(self.rule(body))

    def test_outside_and_dynamic_path_allowed(self):
        for body in ["d=json.loads(pathlib.Path('/tmp/outside.json').read_text());print(d['cases'])", "d=json.loads((p/name).read_text());print(d['cases'])"]:
            with self.subTest(body=body): self.assertIsNone(self.rule(body))

    def test_builtin_write_allowed(self):
        self.assertIsNone(self.rule("open(p/'v2-manual-hook-evidence.json','w');d=json.loads((p/'v2-manual-hook-evidence.json').read_text());print(d['cases'])"))

    def test_writes_allowed(self):
        self.assertIsNone(self.rule("(p/'new.json').write_text('{}');d=json.loads((p/'new.json').read_text());print(d['cases'])"))

    def test_mutation_unknown_call_allowed(self):
        for tail in ["d.update(other);print(d['cases'])", "mutate(d);print(d['cases'])", "d['cases']=[];print(d['cases'])"]:
            self.assertIsNone(self.rule("d=json.loads((p/'v2-manual-hook-evidence.json').read_text());" + tail))

    def test_import_aliases_rejected(self):
        command = "python3 - <<'PY'\nfrom pathlib import Path\nfrom json import loads as decode\np=Path(" + repr(BASE) + ");d=decode((p/'v2-manual-hook-evidence.json').read_bytes());print(d['cases'])\nPY"
        self.assertEqual(write_guard.verdict({'tool_input': {'cmd': command}})[0], 'evidence-json-key')

    def test_fluke_known_literal_missing_key(self):
        base='/home/cash/orca/workspaces/Fluke/riichi-finetune/docs/superpowers/evidence/s07b-teaching-20261004'
        command="python3 - <<'PY'\nimport pathlib,json\np=pathlib.Path("+repr(base)+");d=json.loads((p/'s07b-source-principle-gap-readback.json').read_text());print(d['nonexistent'])\nPY"
        self.assertEqual(write_guard.verdict({'tool_input': {'cmd': command}})[0], 'evidence-json-key')

    def test_independent_alias_mutation_allowed(self):
        self.assertIsNone(self.rule("d=json.loads((p/'v2-manual-hook-evidence.json').read_text());e=d;e.update({'cases':[]});print(d['cases'])"))

    def test_independent_keyword_mutation_allowed(self):
        self.assertIsNone(self.rule("d=json.loads((p/'v2-manual-hook-evidence.json').read_text());mutate=lambda data:data.update({'cases':[]});mutate(data=d);print(d['cases'])"))

    def test_independent_same_expression_mutation_allowed(self):
        self.assertIsNone(self.rule("d=json.loads((p/'v2-manual-hook-evidence.json').read_text());mutate=lambda data:data.update({'cases':[]});print(mutate(d),d['cases'])"))

    def test_nonregular_evidence_refused_without_open(self):
        import os
        import stat
        from types import SimpleNamespace
        path=BASE + '/v2-manual-hook-evidence.json'
        with patch.object(write_guard.os, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFIFO, st_size=0)), patch.object(write_guard.os, 'open', side_effect=AssertionError('FIFO must not be opened')):
            self.assertIsNone(self.rule("d=json.loads((p/'v2-manual-hook-evidence.json').read_text());print(d['cases'])"))

if __name__ == '__main__': unittest.main()
