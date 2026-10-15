import unittest
from pathlib import Path
from rust_index_helpers_guard import protected, error_context

class Helpers(unittest.TestCase):
    def setUp(self):
        self.source=Path('/home/cash/work_space/private/aletheia/tests/telemetry_index_cli.rs').read_text()
    def test_actual_helpers_pass(self):
        self.assertTrue(protected(self.source))
    def test_test_assertions_still_allowed(self):
        self.assertTrue(protected(self.source+'\n#[test]\nfn example(){assert_eq!(Ok::<_, ()>(1).unwrap(),1);}\n'))
    def test_conn_unwrap_refused(self):
        self.assertFalse(protected(self.source.replace('Ok(rusqlite::Connection::open(self.db())?)','Ok(rusqlite::Connection::open(self.db()).unwrap())')))
    def test_json_unwrap_refused(self):
        self.assertFalse(protected(self.source.replace('let out = self.run(args)?;','let out = self.run(args).unwrap();')))
    def test_missing_result_refused(self):
        self.assertFalse(protected(self.source.replace('-> Result<serde_json::Value>','-> serde_json::Value')))
    def test_missing_helper_refused(self):
        self.assertFalse(protected(self.source.replace('fn conn(', 'fn renamed(')))
    def test_truncated_source_refused(self):
        self.assertFalse(protected('fn conn(&self) -> Result<Connection> {'))

if __name__=='__main__':
    unittest.main()

class ErrorContext(unittest.TestCase):
    def test_actual_cursor_preserves_error_context(self):
        self.assertTrue(error_context(Path('/home/cash/work_space/private/aletheia/src/telemetry/cursor.rs').read_text()))
    def test_wildcard_error_discarding_is_refused(self):
        for source in ['x.map_err(|_| anyhow!("bad"))?', 'x . map_err ( | _ | anyhow!("bad"))?', 'x.map_err(\n|_| anyhow!("bad"))?']:
            with self.subTest(source=source):
                self.assertFalse(error_context(source))
    def test_context_and_captured_source_remain_allowed(self):
        self.assertTrue(error_context('x.context("bad")?'))
        self.assertTrue(error_context('x.map_err(|e| anyhow::Error::new(e).context("bad"))?'))

class CumulativeScope(unittest.TestCase):
    def invoke(self, content, exists=True):
        import tempfile, io, contextlib
        from unittest.mock import patch
        import rust_index_helpers_guard as guard
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'cumulative.rs'
            if exists:
                path.write_text(content)
            with patch.object(guard,'CUMULATIVE',path,create=True), patch('sys.stdin',io.StringIO('{"cwd":"/home/cash/work_space/private/aletheia"}')), contextlib.redirect_stderr(io.StringIO()):
                return guard.main()
    def test_cumulative_wildcard_discard_refused(self):
        self.assertEqual(self.invoke('x.map_err(|_| Reason::Overflow)'),2)
    def test_cumulative_missing_source_refused(self):
        self.assertEqual(self.invoke('',False),2)
    def test_cumulative_context_preserving_source_pass(self):
        self.assertEqual(self.invoke('x.context("numeric conversion")?'),0)

class QueryScope(unittest.TestCase):
    def invoke(self, content, exists=True):
        import tempfile, io, contextlib
        from unittest.mock import patch
        import rust_index_helpers_guard as guard
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'query-tests.rs'
            if exists:
                path.write_text(content)
            with patch.object(guard,'QUERY_TESTS',path), patch('sys.stdin',io.StringIO('{"cwd":"/home/cash/work_space/private/aletheia"}')), contextlib.redirect_stderr(io.StringIO()):
                return guard.main()
    def test_query_wildcard_error_discard_refused(self):
        self.assertEqual(self.invoke('stop_tx.send(()).map_err(|_| anyhow!("stopped"))?;'),2)
    def test_query_missing_source_refused(self):
        self.assertEqual(self.invoke('',False),2)
    def test_query_current_source_passes(self):
        self.assertEqual(self.invoke(Path('/home/cash/work_space/private/aletheia/src/telemetry/query_http/tests.rs').read_text()),0)
