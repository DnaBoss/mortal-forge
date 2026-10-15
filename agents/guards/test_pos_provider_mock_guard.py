import tempfile
import unittest
from pathlib import Path
from pos_provider_mock_guard import invalid_reply_problem,problem
GOOD = """if (path === '/B2CInvoice/Invalid') {
    return new Response(JSON.stringify({ MerchantID: config.merchantId, TransCode: 1, Data: encryptEcpayInvoiceData({ RtnCode: 1, InvoiceNo: request.InvoiceNo }, config.hashKey, config.hashIv) }));
  }
"""
class GuardTests(unittest.TestCase):
    def test_valid(self): self.assertIsNone(invalid_reply_problem(GOOD))
    def test_missing_merchant(self): self.assertIsNotNone(invalid_reply_problem(GOOD.replace('MerchantID: config.merchantId, ','')))
    def test_missing_invoice(self): self.assertIsNotNone(invalid_reply_problem(GOOD.replace(', InvoiceNo: request.InvoiceNo','')))
    def test_other_endpoint(self): self.assertIsNone(invalid_reply_problem('InvoicePrint only'))
    def test_unknown_shape(self): self.assertIsNotNone(invalid_reply_problem('/B2CInvoice/Invalid'))
    def test_launch_and_read(self):
        with tempfile.TemporaryDirectory() as d:
            preload=Path(d)/'test-provider-preload.cjs';preload.write_text(GOOD)
            launcher=Path(d)/'start-auto-invoice3-atomic.cjs';launcher.write_text('const preload="'+str(preload)+'";')
            self.assertIsNone(problem('node '+str(launcher)+' api',d))
            preload.write_text(GOOD.replace(', InvoiceNo: request.InvoiceNo',''))
            self.assertIsNotNone(problem('node '+str(launcher)+' api',d))
            self.assertIsNone(problem('cat '+str(launcher),d))
            self.assertIsNone(problem('node another-script.cjs',d))
    def test_missing_launcher(self): self.assertIsNotNone(problem('node /missing/start-auto-invoice3-atomic.cjs api','/tmp'))
if __name__=='__main__':unittest.main()
