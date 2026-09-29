import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import list_tools as tool


class CatalogTests(unittest.TestCase):
    def test_real_catalog(self):
        names = {row['name'] for row in tool.load_catalog('/home/cash/tools/tools.json')}
        self.assertIn('list-tools', names)
        self.assertIn('audit-futures-empty-bars', names)

    def test_missing_field_rejected(self):
        with patch.object(tool.Path, 'read_text', return_value='[{"name":"bad"}]'):
            with self.assertRaises(ValueError):
                tool.load_catalog('/unused')

    def test_duplicate_rejected(self):
        row = tool.load_catalog('/home/cash/tools/tools.json')[0]
        with patch.object(tool.Path, 'read_text', return_value=tool.json.dumps([row, row])):
            with self.assertRaises(ValueError):
                tool.load_catalog('/unused')

    def test_search_match(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(tool.main(['ripgrep']), 0)
        self.assertIn('rg —', out.getvalue())
        self.assertNotIn('localai —', out.getvalue())

    def test_no_match(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(tool.main(['no-such-tool-719872']), 1)

    def test_missing_location_fails(self):
        with patch.object(tool, 'location_exists', return_value=False):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(['--check']), 2)


if __name__ == '__main__':
    unittest.main()
