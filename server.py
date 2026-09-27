# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.30.0"]
# ///
"""Local MCP adapter; operational logic stays in the existing repo scripts."""
from pathlib import Path
from typing import Literal
import fcntl
import json
import os
import signal
import subprocess
import tempfile
import uuid

from mcp.server.fastmcp import FastMCP

ROOT = Path(os.environ["MORTAL_FLUKE_ROOT"]).resolve() if os.environ.get("MORTAL_FLUKE_ROOT") else None
EVIDENCE = (ROOT / "docs/superpowers/evidence/table-visual-upgrade/mcp-operations") if ROOT else Path.home() / ".local/state/mortal-mcp/evidence"
SERVER = FastMCP("mortal-mcp", host="127.0.0.1", port=18765, stateless_http=True, json_response=True)


def execute(argv: list[str], *, mutation: bool, timeout: int = 180) -> dict:
    if ROOT is None or not (ROOT / "scripts/fluke_preview.sh").is_file():
        return {"ok": False, "reason": "Fluke adapter unavailable; configure MORTAL_FLUKE_ROOT"}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    log_path = EVIDENCE / (uuid.uuid4().hex + ".log")
    # Host-wide lock: multiple MCP clients/worktrees cannot duplicate operations.
    with open(Path(tempfile.gettempdir()) / f"fluke-operations-{os.getuid()}.lock", "a") as lock:
        if mutation:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"ok": False, "reason": "operation_in_progress; inspect owner, do not retry automatically"}
        with log_path.open("wb") as log:
            process = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            timed_out = False
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                # Allow isolated runner's finally block to release its own resources.
                os.killpg(process.pid, signal.SIGINT)
                try:
                    code = process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
        with log_path.open("rb") as log:
            log.seek(max(0, log_path.stat().st_size - 1800))
            tail = log.read().decode(errors="replace")
        return {"ok": code == 0 and not timed_out, "exit_code": code,
                "timed_out": timed_out, "log": str(log_path), "tail": tail,
                "next": "inspect retained evidence before retry" if code or timed_out else "done"}


ROUTES = {
    "fluke-playtest": ["fluke_status", "fluke_open_preview", "fluke_restart_preview"],
    "fluke-isolated-godot": ["fluke_validate"],
    "fluke-mahjong-service-tests": ["fluke_validate(scenario=mahjong)"],
    "mortal-mcp": ["mortal_catalog", "mortal_guide"],
    "list-tools": ["mortal_catalog", "mortal_guide"],
}

def catalog_entries() -> list[dict]:
    location = Path(os.environ.get("MORTAL_TOOL_CATALOG", str(Path.home() / "tools/tools.json")))
    if not location.is_file():
        return []
    if location.stat().st_size > 2_000_000:
        raise ValueError("Catalog exceeds 2MB limit")
    entries = json.loads(location.read_text())
    if not isinstance(entries, list) or any(not isinstance(e, dict) or not isinstance(e.get("name"), str) for e in entries):
        raise ValueError("Invalid tool catalog")
    return entries

@SERVER.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def mortal_catalog(query: str = "", limit: int = 10) -> dict:
    """Search reusable tools before writing shell workflows; returns routes, never executes catalog text."""
    if len(query) > 200 or not 1 <= limit <= 50:
        raise ValueError("query max 200 characters; limit 1..50")
    entries = [e for e in catalog_entries() if query.casefold() in json.dumps(e, ensure_ascii=False).casefold()]
    return {"ok": True, "total": len(entries), "tools": [{"name": e["name"], "purpose": e.get("purpose"), "mcp": ROUTES.get(e["name"], []), "execution": "mcp" if e["name"] in ROUTES else "existing_shell_only"} for e in entries[:limit]], "note": "Empty catalog: configure MORTAL_TOOL_CATALOG or register tools; no arbitrary execution."}

@SERVER.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def mortal_guide(name: str) -> dict:
    """Read one registered tool's use, prerequisites and risks, plus shared skill. Does not execute it."""
    for entry in catalog_entries():
        if entry["name"] == name:
            return {"ok": True, "tool": entry, "mcp": ROUTES.get(name, []), "skill": mortal_skill()}
    return {"ok": False, "reason": "Unknown registered tool"}

@SERVER.resource("mortal://skills/shared")
def mortal_skill() -> str:
    return (Path(__file__).parent / ".agents/skills/mortal-tools/SKILL.md").read_text()


@SERVER.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def fluke_status() -> dict:
    """Read preview service PIDs, health and frozen build. Health is not gameplay acceptance."""
    result = execute(["bash", "scripts/fluke_preview.sh", "status"], mutation=False, timeout=10)
    build = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "fluke-preview/build.json"
    if build.exists():
        result["build"] = json.loads(build.read_text())
    return result


@SERVER.tool(annotations={"destructiveHint": False, "idempotentHint": True})
def fluke_open_preview() -> dict:
    """Open existing PLAY preview, or create it when absent. Does not upgrade/restart active Gateway."""
    return execute(["bash", "scripts/fluke_preview.sh", "start"], mutation=True)


@SERVER.tool(annotations={"destructiveHint": True, "idempotentHint": False})
def fluke_restart_preview() -> dict:
    """Authorized PLAY upgrade: backup, refund committed stacks, preserve history, then restart preview only. Aborts unfinished hands; requires user's restart instruction."""
    return execute(["bash", "scripts/fluke_preview.sh", "restart"], mutation=True)



@SERVER.tool(annotations={"destructiveHint": True, "idempotentHint": False})
def fluke_validate(scenario: Literal["clock", "sidepot", "bot-ledger", "full-table", "ledger-restart", "bot-restart", "mahjong"]) -> dict:
    """Run a bounded isolated PLAY test; creates/deletes only its own test DB. Never infers full V1 completion."""
    output = EVIDENCE / ("test-" + uuid.uuid4().hex)
    if scenario == "mahjong":
        # This shared shell entry owns the same host lock, including CLI calls.
        # Do not acquire it twice across parent/child processes.
        result = execute(["bash", "scripts/mahjong/validate_services.sh", "all", str(output)], mutation=False, timeout=200)
    else:
        result = execute(["python3", "scripts/visual_probe/run_isolated_godot.py", "--scenario", scenario, "--output", str(output)], mutation=True)
    result["evidence"] = str(output)
    return result


@SERVER.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def fluke_audit_continuity() -> dict:
    """Read-only two-minute PLAY audit: ten-table progress, stack/escrow, journal balance, rejected actions. Not full gameplay acceptance."""
    output = EVIDENCE / ("continuity-" + uuid.uuid4().hex)
    result = execute(["python3", "scripts/visual_probe/audit_preview_continuity.py", "--output", str(output)], mutation=False, timeout=160)
    result["evidence"] = str(output)
    return result


if __name__ == "__main__":
    SERVER.run(transport="streamable-http")
