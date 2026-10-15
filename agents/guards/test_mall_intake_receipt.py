import unittest
import write_guard

class MallIntakeReceiptTest(unittest.TestCase):
    def check(self, expression, prefix='mall-api-intake-'):
        code="from pathlib import Path\nimport json\np=Path('/home/cash/.cache/"+prefix+"test')\nr=json.loads((p/'receipt.json').read_text())\n"+expression
        return write_guard.verdict({'tool_input':{'cmd':"python3 - <<'PY'\n"+code+"\nPY"}})[0]
    def test_top_level_cleanup_fields_denied(self):
        for field in ['remainingVolumes','cleanupErrors','remainingContainers']:
            with self.subTest(field=field):self.assertEqual(self.check("assert not r['"+field+"']"),'mall-intake-receipt-field')
    def test_nested_cleanup_allowed(self):
        self.assertIsNone(self.check("assert not r['cleanup']['remainingVolumes']"))
    def test_schema_inventory_allowed(self):
        self.assertIsNone(self.check("print(list(r))"))
    def test_other_receipt_shape_allowed(self):
        self.assertIsNone(self.check("assert not r['remainingVolumes']",'mall-queue-runtime-'))
    def test_different_variable_allowed(self):
        self.assertIsNone(self.check("other={'remainingVolumes':[]}\nassert not other['remainingVolumes']"))

    def test_mixed_queue_receipt_allowed(self):
        self.assertIsNone(self.check("q=json.loads(Path('/home/cash/.cache/mall-queue-runtime-test/receipt.json').read_text())\nassert not q['remainingVolumes']"))
    def test_mixed_api_receipt_still_denied(self):
        self.assertEqual(self.check("q=json.loads(Path('/home/cash/.cache/mall-queue-runtime-test/receipt.json').read_text())\nassert not r['remainingVolumes']"),'mall-intake-receipt-field')

    def test_queue_then_api_same_variable_allowed(self):
        self.assertIsNone(self.check("r=json.loads(Path('/home/cash/.cache/mall-queue-runtime-test/receipt.json').read_text())\nassert not r['remainingVolumes']\nr=json.loads((p/'receipt.json').read_text())\nassert not r['cleanup']['remainingVolumes']"))
    def test_api_then_queue_same_variable_denied(self):
        self.assertEqual(self.check("assert not r['remainingVolumes']\nr=json.loads(Path('/home/cash/.cache/mall-queue-runtime-test/receipt.json').read_text())"),'mall-intake-receipt-field')
