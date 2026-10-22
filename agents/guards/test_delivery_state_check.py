import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class StateHookTests(unittest.TestCase):
    def test_structured_incomplete_completion_is_blocked_beyond_three_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            guards = home / ".agents/guards"
            guards.mkdir(parents=True)
            tools = home / "tools"
            tools.mkdir()
            source = Path(__file__).parent
            for name in (
                "finish_check.py",
                "delivery_check.py",
                "delivery_state_check.py",
                "card_status_check.py",
            ):
                shutil.copyfile(source / name, guards / name)
            module_source = source / "cash_rule_delivery.py"
            if not module_source.exists():
                module_source = source.parents[1] / "tools/cash_rule_delivery.py"
            shutil.copyfile(module_source, tools / "cash_rule_delivery.py")
            (tools / "list_tools.py").write_text("def load_catalog(path): return []\n")
            project = home / "project"
            project.mkdir()
            cp = project / "t.checkpoints.jsonl"
            cp.write_text(
                json.dumps({"task_id": "t", "task_state": "COMPLETE", "step_id": "S1"})
                + "\n"
            )
            registry = home / ".local/state/cash-rule-delivery/plans"
            registry.mkdir(parents=True)
            (registry / "task.json").write_text(
                json.dumps(
                    {
                        "project": str(project),
                        "checkpoints": str(cp),
                        "task": "t",
                        "kinds": {"S1": "milestone"},
                    }
                )
            )
            payload = {
                "cwd": str(project),
                "last_assistant_message": "狀態回報",
                "hook_event_name": "Stop",
            }
            for _ in range(5):
                result = subprocess.run(
                    [sys.executable, str(guards / "finish_check.py")],
                    input=json.dumps(payload),
                    text=True,
                    capture_output=True,
                    env=dict(os.environ, HOME=str(home)),
                    timeout=10,
                )
                self.assertEqual(
                    json.loads(result.stdout).get("decision"), "block", result.stdout
                )
            cp.write_text(
                json.dumps({"task_id": "t", "task_state": "RUNNING", "step_id": "S2"})
                + "\n"
            )
            result = subprocess.run(
                [sys.executable, str(guards / "finish_check.py")],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                env=dict(os.environ, HOME=str(home)),
                timeout=10,
            )
            self.assertEqual(result.stdout, "", result.stdout)


if __name__ == "__main__":
    unittest.main()
