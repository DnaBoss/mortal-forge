import unittest
import write_guard
class EvidenceKindTest(unittest.TestCase):
 def test_invalid(self):
  for kind in ['commit','log','unknown']:
   for option in ['--evidence '+kind+'=/tmp/result','--evidence='+kind+'=/tmp/result']:
    self.assertEqual(write_guard.verdict({'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl '+option}})[0],'checkpoint-evidence-kind')
 def test_valid(self):
  for kind in ['git','file','symbol','test','command','screen','service','model_opinion','other']:
   self.assertIsNone(write_guard.verdict({'tool_input':{'cmd':'~/tools/cash-rule-checkpoint x.checkpoints.jsonl --evidence '+kind+'=/tmp/result'}})[0])
 def test_unrelated(self):
  self.assertIsNone(write_guard.verdict({'tool_input':{'cmd':'echo "cash-rule-checkpoint --evidence log=/tmp/a"'}})[0])
if __name__=='__main__':unittest.main()
