import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_tool_index import Scanner, save


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.state = self.home / "state"

    def write(self, name, content):
        p = self.home / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def scan(self, projects=()):
        with patch("ai_tool_index.shutil.which", return_value=None):
            return Scanner(self.home, projects, models=False).run()

    def snapshot(self):
        return json.loads((self.state / "snapshot.json").read_text())

    def test_no_secrets_and_correct_disabled_status(self):
        self.write(
            ".codex/config.toml",
            '[mcp_servers.demo]\ncommand="SECRET_COMMAND"\nargs=["SECRET_ARG"]\nenabled=false\n[mcp_servers.demo.env]\nTOKEN="SECRET_ENV"\n',
        )
        self.write(
            ".claude.json",
            json.dumps(
                {
                    "mcpServers": {
                        "remote": {
                            "url": "https://SECRET_URL",
                            "headers": {"Authorization": "SECRET_HEADER"},
                        }
                    }
                }
            ),
        )
        result = self.scan()
        self.assertNotIn("SECRET_", json.dumps(result))
        item = next(i for i in result["items"] if i["name"] == "demo")
        self.assertFalse(item["enabled"])
        self.assertIsNone(item["loaded"])
        self.assertIsNone(item["health"])

    def test_repeat_add_update_remove(self):
        config = self.write(".codex/config.toml", "[mcp_servers.demo]\nenabled=true\n")
        self.assertEqual(save(self.state, self.scan())["changes"], 1)
        self.assertEqual(save(self.state, self.scan())["changes"], 0)
        config.write_text("[mcp_servers.demo]\nenabled=false\n")
        save(self.state, self.scan())
        self.assertEqual(self.snapshot()["changes"][0]["action"], "updated")
        config.write_text("")
        save(self.state, self.scan())
        self.assertEqual(self.snapshot()["changes"][0]["action"], "removed")

    def test_parse_error_keeps_stale_not_removed(self):
        config = self.write(".codex/config.toml", "[mcp_servers.demo]\nenabled=true\n")
        save(self.state, self.scan())
        config.write_text("[")
        result = save(self.state, self.scan())
        self.assertTrue(result["errors"])
        self.assertTrue(self.snapshot()["items"][0]["stale"])
        self.assertNotIn("removed", [i["action"] for i in self.snapshot()["changes"]])

    def test_omitted_project_is_not_removed(self):
        project = self.home / "project"
        self.write("project/.mcp.json", json.dumps({"mcpServers": {"demo": {}}}))
        save(self.state, self.scan([project]))
        save(self.state, self.scan())
        self.assertTrue(self.snapshot()["items"][0]["stale"])
        self.assertNotIn("removed", [i["action"] for i in self.snapshot()["changes"]])

    def test_model_skip_preserves_prior_entry(self):
        first = self.scan()
        first["items"] = [
            {
                "id": "model",
                "name": "demo",
                "kind": "model",
                "source": "ollama:local",
                "scopes": ["ollama:local"],
            }
        ]
        first["sources"].append({"path": "ollama:local", "status": "ok"})
        save(self.state, first)
        save(self.state, self.scan())
        self.assertTrue(self.snapshot()["items"][0]["stale"])

    def test_skill_alias_dedup_and_content_change(self):
        skill = self.write(
            ".agents/skills/demo/SKILL.md",
            "---\ndescription: Find invoices\n---\nSECRET_BODY",
        )
        (self.home / ".codex/skills").mkdir(parents=True)
        (self.home / ".codex/skills/demo").symlink_to(skill.parent)
        result = self.scan()
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["hosts"], ["codex", "shared"])
        self.assertEqual(result["items"][0]["purpose"], "Find invoices")
        self.assertNotIn("SECRET_BODY", json.dumps(result))
        save(self.state, result)
        skill.write_text("---\ndescription: Find invoices\n---\nChanged")
        self.assertEqual(save(self.state, self.scan())["changes"], 1)

    def test_cached_versions_are_not_active_installations(self):
        self.write(
            ".claude/settings.json",
            json.dumps({"enabledPlugins": {"demo@market": True}}),
        )
        for version in ["1", "2"]:
            self.write(
                f".claude/plugins/cache/market/demo/{version}/skills/one/SKILL.md",
                "sample",
            )
        snapshot = self.scan()
        cached = [i for i in snapshot["items"] if i["kind"] == "plugin" and i["cached"]]
        self.assertEqual(len(cached), 2)
        self.assertTrue(
            all(i["installed"] is None and i["enabled"] is None for i in cached)
        )
        self.write(
            ".claude/plugins/installed_plugins.json",
            json.dumps(
                {
                    "plugins": {
                        "demo@market": [
                            {
                                "version": "2",
                                "installPath": str(
                                    self.home / ".claude/plugins/cache/market/demo/2"
                                ),
                            }
                        ]
                    }
                }
            ),
        )
        snapshot = self.scan()
        active = [
            i
            for i in snapshot["items"]
            if i["kind"] == "plugin" and i["cached"] and i["enabled"]
        ]
        self.assertEqual([i["version"] for i in active], ["2"])

    def test_removed_plugin_removes_its_children(self):
        path = self.write(
            ".claude/plugins/cache/market/demo/1/skills/one/SKILL.md", "sample"
        )
        self.write(
            ".claude/plugins/cache/market/demo/1/.mcp.json",
            json.dumps({"mcpServers": {"demo": {}}}),
        )
        save(self.state, self.scan())
        shutil.rmtree(path.parents[2])
        save(self.state, self.scan())
        self.assertFalse(self.snapshot()["items"])
        self.assertEqual(len(self.snapshot()["changes"]), 3)
        self.assertTrue(
            all(i["action"] == "removed" for i in self.snapshot()["changes"])
        )

    def test_large_skill_is_reported_as_error(self):
        self.write(".agents/skills/big/SKILL.md", "x" * (4 * 1024 * 1024 + 1))
        result = self.scan()
        self.assertFalse(result["items"])
        self.assertIn("error", [s["status"] for s in result["sources"]])


if __name__ == "__main__":
    unittest.main()
