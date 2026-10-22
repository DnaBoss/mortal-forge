import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from delivery_check import check_receipt


class BrowserUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.version = self.art('version', {'build': 'v2'})
        self.proofs = {}
        for name in ('current_entry', 'previous_entry', 'missing_asset_negative', 'cache_revalidation'):
            self.proofs[name] = self.art(name, {'check': name, 'result': 'pass', 'version_sha256': self.version['sha256']})
        self.readback = {'unit': 'web', 'version_sha256': self.version['sha256'], 'result': 'pass',
                         'kind': 'deployment_readback', 'entrypoint': 'https://fluke.exactlyone.dev/',
                         'browser_upgrade': self.proofs}
        self.validation = self.art('validation', {'unit': 'web', 'version_sha256': self.version['sha256'],
                                                 'checks': [{'name': 'test', 'result': 'pass'}]})

    def tearDown(self):
        self.tmp.cleanup()

    def art(self, name, data):
        raw = json.dumps(data).encode()
        (self.cwd / name).write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def receipt(self):
        return {'schema_version': 1, 'cwd': str(self.cwd), 'session_id': 'test',
                'units': [{'id': 'web', 'version': self.version, 'validation': self.validation,
                           'delivery': {'status': 'deployed', 'entrypoint': self.readback['entrypoint'],
                                        'readback': self.art('readback', self.readback)}}]}

    def test_complete_upgrade_passes(self):
        check_receipt(self.receipt(), self.cwd, 'test')

    def test_each_missing_proof_rejected_without_surface_hint(self):
        original = copy.deepcopy(self.proofs)
        for name in original:
            with self.subTest(name=name):
                self.readback['browser_upgrade'] = {k: v for k, v in original.items() if k != name}
                with self.assertRaises(ValueError):
                    check_receipt(self.receipt(), self.cwd, 'test')

    def test_wrong_version_rejected(self):
        self.readback['browser_upgrade']['previous_entry'] = self.art('wrong',
            {'check': 'previous_entry', 'result': 'pass', 'version_sha256': 'wrong'})
        with self.assertRaises(ValueError):
            check_receipt(self.receipt(), self.cwd, 'test')

    def test_changed_proof_rejected(self):
        (self.cwd / 'previous_entry').write_text('{}')
        with self.assertRaises(ValueError):
            check_receipt(self.receipt(), self.cwd, 'test')


if __name__ == '__main__':
    unittest.main()
