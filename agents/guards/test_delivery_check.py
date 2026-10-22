"""Real Stop JSON entrypoint tests; all artifacts are owned temporary fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

GUARD = Path(os.environ.get('DELIVERY_TEST_FINISH', str(Path(__file__).with_name('finish_check.py'))))


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.temp.name)
        tools = self.cwd / 'tools'
        tools.mkdir()
        (tools / 'list_tools.py').write_text('def load_catalog(p): return []\n')
        self.payload = {'cwd': str(self.cwd), 'session_id': 'test-session',
                        'hook_event_name': 'Stop', 'last_assistant_message': '程式已完成，必要驗證通過。\n交付收據：delivery.json'}
        version = self.art('version.txt', 'usable v1\n')
        validation = self.art('validation.json', {'unit': 'tool', 'version_sha256': version['sha256'],
                                                 'checks': [{'name': 'true-negative-and-positive', 'result': 'pass'}]})
        readback = self.art('readback.json', {'unit': 'tool', 'version_sha256': version['sha256'],
                                             'entrypoint': 'version.txt', 'result': 'pass'})
        self.receipt = {'schema_version': 1, 'cwd': str(self.cwd), 'session_id': 'test-session',
                        'units': [{'id': 'tool', 'version': version, 'validation': validation,
                                   'delivery': {'status': 'available', 'entrypoint': 'version.txt',
                                                'entrypoint_artifact': version, 'readback': readback}}]}

    def tearDown(self):
        self.temp.cleanup()

    def art(self, name, data):
        data = json.dumps(data).encode() if isinstance(data, dict) else data.encode()
        (self.cwd / name).write_bytes(data)
        return {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}

    def hook(self, expected, payload=None):
        (self.cwd / 'delivery.json').write_text(json.dumps(self.receipt))
        r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload or self.payload),
                           text=True, capture_output=True, timeout=10, env={**os.environ, 'HOME': str(self.cwd)})
        self.assertEqual(r.returncode, 0, r.stderr)
        actual = json.loads(r.stdout).get('decision') if r.stdout.strip() else None
        self.assertEqual(actual, 'block' if expected == 'block' else None, r.stdout)
        return r

    def test_missing_receipt_blocks_completed_tested_unit(self):
        p = {**self.payload, 'last_assistant_message': '功能已完成，必要驗證通過。'}
        self.hook('block', p)

    def test_actual_same_version_entrypoint_allows(self):
        self.hook('allow')

    def test_changed_version_blocks(self):
        (self.cwd / 'version.txt').write_text('different build')
        self.hook('block')

    def test_old_validation_version_blocks(self):
        self.receipt['units'][0]['validation'] = self.art('validation.json', {
            'unit': 'tool', 'version_sha256': '0'*64, 'checks': [{'name': 'unit', 'result': 'pass'}]})
        self.hook('block')

    def test_failed_skipped_and_unrun_necessary_checks_block(self):
        for status in ['fail', 'skip', 'not_run']:
            with self.subTest(status=status):
                self.receipt['units'][0]['validation'] = self.art('validation.json', {
                    'unit': 'tool', 'version_sha256': self.receipt['units'][0]['version']['sha256'],
                    'checks': [{'name': 'necessary', 'result': status}]})
                self.hook('block')

    def test_pending_delivery_blocks(self):
        self.receipt['units'][0]['delivery'] = {'status': 'pending', 'reason': '下輪再部署'}
        self.hook('block')

    def test_fake_boolean_flags_do_not_prove_delivery(self):
        self.receipt['units'][0]['delivery'] = {'status': 'available', 'available': True, 'deployed': True}
        self.hook('block')

    def test_missing_entrypoint_blocks(self):
        self.receipt['units'][0]['delivery']['entrypoint'] = 'missing.bin'
        self.hook('block')

    def test_old_readback_version_blocks(self):
        self.receipt['units'][0]['delivery']['readback'] = self.art('readback.json', {
            'unit': 'tool', 'version_sha256': '0'*64, 'entrypoint': 'version.txt', 'result': 'pass'})
        self.hook('block')

    def test_deployed_same_version_actual_readback_allows(self):
        d = self.receipt['units'][0]['delivery']
        d.update(status='deployed', entrypoint='https://example.test/version')
        d['readback'] = self.art('readback.json', {'unit': 'tool',
            'version_sha256': self.receipt['units'][0]['version']['sha256'],
            'entrypoint': d['entrypoint'], 'result': 'pass', 'kind': 'deployment_readback'})
        self.hook('allow')

    def test_build_is_not_deployment_readback(self):
        self.receipt['units'][0]['delivery']['status'] = 'deployed'
        self.hook('block')

    def test_exceptions_require_specific_original_evidence(self):
        for status in ['unauthorized', 'paused', 'read_only', 'failed']:
            with self.subTest(status=status):
                reason = '使用者只授權離線修改，沒有遠端部署授權' if status != 'failed' else '發布程序exit1，原stderr保存'
                source = self.art('original-instruction-or-exit.txt', reason + '\n')
                evidence = self.art('exception.json', {'unit': 'tool', 'status': status,
                                                       'reason': reason, 'source': source})
                self.receipt['units'][0]['delivery'] = {'status': status, 'reason': reason,
                                                       'next_action': '回報可審閱版本及缺少授權', 'evidence': evidence}
                self.hook('allow')

    def test_bare_exception_reason_is_not_enough(self):
        self.receipt['units'][0]['delivery'] = {'status': 'unauthorized', 'reason': '待部署', 'next_action': '等'}
        self.hook('block')

    def test_exception_source_must_be_real_original_not_path_string(self):
        reason = '使用者要求暫停'
        self.receipt['units'][0]['delivery'] = {'status': 'paused', 'reason': reason, 'next_action': '等待新指令',
            'evidence': self.art('exception.json', {'unit': 'tool', 'status': 'paused', 'reason': reason,
                                                    'source': 'does-not-exist.txt'})}
        self.hook('block')

    def test_exception_conflicting_original_blocks(self):
        d = {'status': 'paused', 'reason': '使用者要求暫停', 'next_action': '等待新指令'}
        d['evidence'] = self.art('exception.json', {'unit': 'tool', 'status': 'unauthorized',
                                                  'reason': d['reason'], 'source': 'user'})
        self.receipt['units'][0]['delivery'] = d
        self.hook('block')

    def test_wrong_session_and_workspace_block(self):
        for key in ['session_id', 'cwd']:
            with self.subTest(key=key):
                old = self.receipt[key]; self.receipt[key] = 'other'
                self.hook('block'); self.receipt[key] = old

    def test_duplicate_units_block(self):
        self.receipt['units'].append(copy.deepcopy(self.receipt['units'][0]))
        self.hook('block')

    def test_progress_test_or_readonly_audit_is_not_forced_to_deploy(self):
        for text in ['目前窄測通過，實作仍在進行。', '唯讀審查完成；原檔未修改。', '這輪只盤點，不恢復目標。']:
            self.hook('allow', {**self.payload, 'last_assistant_message': text})

    def test_quoted_example_and_code_are_not_completion_claims(self):
        self.hook('allow', {**self.payload, 'last_assistant_message': '> 程式已完成，必要驗證通過。\n```\n交付收據：missing.json\n```'})

    def test_oversize_receipt_blocks(self):
        self.receipt['padding'] = 'x'*(1024*1024)
        self.hook('block')


if __name__ == '__main__':
    unittest.main()
