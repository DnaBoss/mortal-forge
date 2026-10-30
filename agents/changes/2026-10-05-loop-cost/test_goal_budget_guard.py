import importlib.util,unittest
spec=importlib.util.spec_from_file_location('guard','/home/cash/.agents/guards/goal_budget_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BudgetGuard(unittest.TestCase):
 def event(self,args,name='create_goal'):return {'hook_event_name':'PreToolUse','tool_name':name,'tool_input':args}
 def test_budget_validation_removed(self):
  for value in [None,0,-1,True,'30000']:
   with self.subTest(value=value):self.assertEqual(m.decision(self.event({'token_budget':value})),{})
 def test_omitted_budget_allowed(self):
  for args in [{}, '{"objective":"test"}']:
   self.assertEqual(m.decision(self.event(args)),{})
 def test_explicit_positive_budget_allowed(self):self.assertEqual(m.decision(self.event({'token_budget':30000},'functions.create_goal')), {})
 def test_pause_and_read_allowed(self):
  for name in ['update_goal','get_goal','exec_command']:
   self.assertEqual(m.decision(self.event({},name)),{})
 def test_other_events_untouched(self):self.assertEqual(m.decision({'hook_event_name':'Stop','tool_name':'create_goal'}),{})
if __name__=='__main__':unittest.main()
