import unittest
import write_guard

class ReceiptPrintTest(unittest.TestCase):
    def verdict(self, code):
        return write_guard.verdict({'tool_input': {'cmd': "python3 - <<'PY'\n"+code+"\nPY"}})[0]
    def test_direct_three_fields_denied(self):
        for key in ['records','afterFinalStop','afterBackendStop']:
            with self.subTest(key=key):
                self.assertEqual(self.verdict("print(m['"+key+"'])"),'receipt-raw-print')
    def test_mixed_print_denied(self):
        self.assertEqual(self.verdict("print('count',1,m['records'])"),'receipt-raw-print')
    def test_counts_and_artifacts_allowed(self):
        for code in ["print(len(m['records']))", "print(sum(x['accepted'] for x in m['receipts']))", "p.write_text(json.dumps(m['records']))", "print(m['sourceRows'])", "print(m['records'][0]['requestId'])"]:
            with self.subTest(code=code): self.assertIsNone(self.verdict(code))
    def test_malformed_and_unrelated_allowed(self):
        self.assertIsNone(self.verdict("print("))
        self.assertIsNone(write_guard.verdict({'tool_input': {'cmd': "echo records"}})[0])
