"""Check structured completion independently of response wording and Stop retry count."""

import importlib.util
import json
from pathlib import Path


def problems(payload):
    tools = Path(__file__).resolve().parents[2] / "tools"
    module_path = tools / "cash_rule_delivery.py"
    registry = Path.home() / ".local/state/cash-rule-delivery/plans"
    if not registry.exists():
        return []
    # Registry entries are only made by the delivery writer. Never scan arbitrary repos.
    cwd = Path(payload.get("cwd") or ".").resolve()
    entries = list(registry.glob("*.json"))
    if len(entries) > 512:
        return ["交付登記超過檢查上限；須先整理登記，不能視為已驗收。"]
    out = []
    for entry in entries:
        try:
            data = json.loads(entry.read_text())
            if (
                data.get("session_ids")
                and payload.get("session_id")
                and payload["session_id"] not in data["session_ids"]
            ):
                continue
            project = Path(data["project"]).resolve()
            if cwd != project and project not in cwd.parents:
                continue
            checkpoints = Path(data["checkpoints"])
            if not checkpoints.exists():
                out.append("已登記交付的進度紀錄不見了；須恢復紀錄，不能略過交付。")
                continue
            if checkpoints.stat().st_size > 4 * 1024 * 1024:
                out.append("進度紀錄超過交付檢查上限；尚未驗收。")
                continue
            records = [
                json.loads(line)
                for line in checkpoints.read_text().splitlines()
                if line.strip()
            ]
            latest = next(
                (r for r in reversed(records) if r.get("task_id") == data["task"]), None
            )
            if not latest or latest["task_state"] != "COMPLETE":
                continue
            spec = importlib.util.spec_from_file_location(
                "cash_rule_delivery_state", module_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            issue = module.gate(
                checkpoints, data["task"], latest["step_id"], "COMPLETE", "DONE", []
            )
            if issue:
                out.append(issue)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError):
            out.append("已登記交付的檢查資料無法讀取；不得宣稱整體交付。")
    return out
