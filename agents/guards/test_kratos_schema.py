"""Reject the observed default-schema guess when the project config excludes it."""
from pathlib import Path
import tempfile
import unittest
import write_guard


class KratosSchemaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / 'deploy/systemd/kratos.yml'
        self.config.parent.mkdir(parents=True)
        self.config.write_text('identity:\n  default_schema_id: person\n  schemas:\n  - id: person\n')

    def tearDown(self):
        self.temp.cleanup()

    def verdict(self, text, edit=False, cwd=None):
        return write_guard.verdict({'cwd':str(cwd or self.root),'tool_input':{'new_string' if edit else 'cmd':text}})[0]

    def test_guessed_default_denied(self):
        self.assertEqual(self.verdict("body={'schema_id':'default'}"),'kratos-schema-default')
        self.assertEqual(self.verdict('{"schema_id": "default"}'),'kratos-schema-default')

    def test_edit_denied(self):
        self.assertEqual(self.verdict("body={'schema_id':'default'}",edit=True),'kratos-schema-default')

    def test_registered_and_dynamic_schema_allowed(self):
        self.assertIsNone(self.verdict("body={'schema_id':'person'}"))
        self.assertIsNone(self.verdict("body={'schema_id':config['identity']['default_schema_id']}"))

    def test_default_actually_registered_allowed(self):
        self.config.write_text('identity:\n  schemas:\n  - id: person\n  - id: default\n')
        self.assertIsNone(self.verdict("body={'schema_id':'default'}"))

    def test_nested_working_directory_checked(self):
        nested=self.root/'subdir';nested.mkdir()
        self.assertEqual(self.verdict("body={'schema_id':'default'}",cwd=nested),'kratos-schema-default')

    def test_no_known_config_allowed(self):
        self.config.unlink()
        self.assertIsNone(self.verdict("body={'schema_id':'default'}"))

    def test_shell_workdir_respected(self):
        command=next(value for value in self.test_guessed_default_denied.__func__.__code__.co_consts if isinstance(value,str) and value.startswith("body="))
        with tempfile.TemporaryDirectory() as other:
            result=write_guard.verdict({'cwd':str(self.root),'tool_input':{'workdir':other,'cmd':command}})[0]
            self.assertIsNone(result)

    def test_prose_not_schema_literal_allowed(self):
        self.assertIsNone(self.verdict('default schema description'))


if __name__ == '__main__':
    unittest.main()
