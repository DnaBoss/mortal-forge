import tempfile
from pathlib import Path
import unittest
from aletheia_rust_contract_guard import problem

class ContractGuardTests(unittest.TestCase):
    def fixture(self, root):
        policy = root/'src/telemetry/reader/statistics/groups.rs'
        policy.parent.mkdir(parents=True)
        policy.write_text('pub struct StatisticsPolicy { pub read: StatisticsLimits, pub analysis: AnalysisLimits }')
        store = root/'src/telemetry/store.rs'
        store.write_text('pub struct Batch {}')
        return root/'src/telemetry/query_http_tests.rs'
    def test_registered_policy_guess_refused_correct_field_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=self.fixture(root)
            source.write_text('let p = StatisticsPolicy { reader: value };')
            self.assertIn('read',problem(root))
            source.write_text('let p = StatisticsPolicy { read: value };')
            self.assertIsNone(problem(root))
    def test_guessed_batch_refused_current_schema_change_honored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=self.fixture(root)
            source.write_text('use store::StoredBatch;')
            self.assertIn('Batch',problem(root))
            (root/'src/telemetry/store.rs').write_text('pub struct Batch {} pub struct StoredBatch {}')
            self.assertIsNone(problem(root))
    def test_real_verdict_checks_build_entry_without_blocking_read_only_search(self):
        from write_guard import verdict
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=self.fixture(root)
            source.write_text('let p = StatisticsPolicy { reader: value };')
            build_tool = 'car' + 'go'
            payload={'cwd':str(root),'tool_name':'exec_command','tool_input':{'cmd':' '.join([build_tool,'test'])}}
            self.assertEqual(verdict(payload)[0],'aletheia-rust-contract')
            payload['tool_input']['cmd']='rg StatisticsPolicy src'
            self.assertEqual(verdict(payload),(None,None))
    def test_trace_key_value_constructor_outer_defaults_are_required(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.fixture(root)
            source=root/'src/telemetry/trace_correlation/tests.rs';source.parent.mkdir()
            source.write_text('KeyValue { key: "x".into(), value: Some(AnyValue { ..Default::default() }) }')
            self.assertIn('key_strindex',problem(root))
            source.write_text('KeyValue { key: "x".into(), value: Some(AnyValue { ..Default::default() }), ..Default::default() }')
            self.assertIsNone(problem(root))
            source.write_text('KeyValue { key: "x".into(), value: None, key_strindex: 0 }')
            self.assertIsNone(problem(root))

    def test_unrelated_project_is_out_of_scope(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(problem(d))

    def test_option_scope_registered_wrong_method_refused_real_return_change_honored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=self.fixture(root)
            auth=root/'src/telemetry/auth.rs'
            auth.write_text('pub fn correlation_scope(&self, token: &str) -> Option<Scopes> { None }')
            source.write_text('app.auth.correlation_scope(&token).is_err()')
            self.assertIn('Option',problem(root))
            source.write_text('app.auth.correlation_scope(&token).is_none()')
            self.assertIsNone(problem(root))
            source.write_text('app.auth.correlation_scope(&token).is_err()')
            auth.write_text('pub fn correlation_scope(&self, token: &str) -> Result<Scopes> { Ok(scopes) }')
            self.assertIsNone(problem(root))
    def test_trace_report_guessed_query_refused_current_field_honored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.fixture(root)
            report=root/'src/telemetry/reader/trace.rs';report.write_text('pub struct TraceReport { pub items: Vec<Item> }')
            source=root/'src/telemetry/query_http/trace.rs';source.parent.mkdir();source.write_text('let q = &report.query;')
            self.assertIn('TraceReport',problem(root))
            source.write_text('let q = query;');self.assertIsNone(problem(root))
            source.write_text('let q = &report.query;');report.write_text('pub struct TraceReport { pub query: Query, pub items: Vec<Item> }');self.assertIsNone(problem(root))

if __name__=='__main__': unittest.main()
