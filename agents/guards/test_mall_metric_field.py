import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import write_guard

class MallMetricFieldTest(unittest.TestCase):
    def patch(self, body, name='queue-runtime-isolated.py'):
        return write_guard.verdict({'tool_input': {'patch': '*** Begin Patch\n*** Update File: /tmp/'+name+'\n@@\n'+body+'\n*** End Patch'}})[0]
    def test_bad_field_addition_denied(self):
        self.assertEqual(self.patch("+assert 'EventLoopLagMillis' in row"),'mall-metric-field')
    def test_actual_field_allowed(self):
        self.assertIsNone(self.patch("+assert 'EventLoopLagMs' in row"))
    def test_removal_allowed(self):
        self.assertIsNone(self.patch("-assert 'EventLoopLagMillis' in row\n+assert 'EventLoopLagMs' in row"))
    def test_other_file_and_prose_allowed(self):
        self.assertIsNone(self.patch("+assert 'EventLoopLagMillis' in row",'unrelated.py'))
        self.assertIsNone(self.patch('+text = "previous typo EventLoopLagMillis"'))
    def test_shell_write_denied(self):
        command="python3 - <<'PY'\np=Path('queue-runtime-isolated.py')\np.write_text(\"assert 'EventLoopLagMillis' in row\")\nPY"
        self.assertEqual(write_guard.verdict({'tool_input': {'cmd':command}})[0],'mall-metric-field')
    def test_shell_read_allowed(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        Path(directory, 'queue-runtime-isolated.py').touch()
        self.enterContext(patch('write_guard.os.getcwd', return_value=directory))
        self.assertIsNone(write_guard.verdict({'tool_input': {'cmd':"rg \"'EventLoopLagMillis' in row\" queue-runtime-isolated.py"}})[0])
