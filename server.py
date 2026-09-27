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

ROOT = Path(os.environ["MORTAL_FLUKE_ROOT"]).resolve()
if not (ROOT / "scripts/fluke_preview.sh").is_file():
    raise RuntimeError("MORTAL_FLUKE_ROOT must point to the Fluke checkout")
EVIDENCE = ROOT / "docs/superpowers/evidence/table-visual-upgrade/mcp-operations"
SERVER = FastMCP("mortal-mcp", host="127.0.0.1", port=18765, stateless_http=True, json_response=True)


def execute(argv: list[str], *, mutation: bool, timeout: int = 180) -> dict:
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
def fluke_validate(scenario: Literal["clock", "sidepot", "bot-ledger", "full-table", "ledger-restart", "bot-restart"]) -> dict:
    """Run a bounded isolated PLAY test; creates/deletes only its own test DB. Never infers full V1 completion."""
    output = EVIDENCE / ("test-" + uuid.uuid4().hex)
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
