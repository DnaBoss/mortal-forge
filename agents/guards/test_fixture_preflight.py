import tempfile
from pathlib import Path
import unittest
import write_guard


class FixturePreflightTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.script = self.root / 'godot-fixture-launcher.py'

    def tearDown(self):
        self.tmp.cleanup()

    def denied(self, source):
        self.script.write_text(source)
        return write_guard.invalid_fixture_preflight('python3 -u ' + str(self.script), str(self.root))

    def test_missing_inner_denied(self):
        self.assertTrue(self.denied("def gateway_running():\n    inner.write_text('print(1)')\n"))

    def test_missing_request_denied(self):
        nested = "from urllib.request import urlopen\nvalue = Request('http://localhost/')"
        self.assertTrue(self.denied("def gateway_running():\n    inner = folder / 'inner.py'\n    inner.write_text(" + repr(nested) + ")\n"))

    def test_supported_names_allowed(self):
        nested = "from urllib.request import Request, urlopen\nvalue = Request('http://localhost/')"
        self.assertFalse(self.denied("def gateway_running():\n    inner = folder / 'inner.py'\n    inner.write_text(" + repr(nested) + ")\n"))

    def test_oversize_browser_window_denied(self):
        self.assertTrue(self.denied('window.wait(stop_errors, seconds=420)'))

    def test_supported_browser_window_allowed(self):
        self.assertFalse(self.denied('window.wait(stop_errors, seconds=300)'))

    def test_dynamic_inner_allowed(self):
        self.assertFalse(self.denied('def gateway_running():\n    inner = other\n    inner.write_text(dynamic)'))

    def test_invalid_python_allowed(self):
        self.assertFalse(self.denied('def broken('))

    def test_missing_source_allowed(self):
        self.assertFalse(write_guard.invalid_fixture_preflight('python3 -u ' + str(self.script), str(self.root)))


if __name__ == '__main__':
    unittest.main()
