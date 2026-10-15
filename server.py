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
    "ssd-scan": ["ssd_scan_start", "ssd_scan_report"],
    "fluke-playtest": ["fluke_status", "fluke_open_preview", "fluke_restart_preview"],
    "fluke-isolated-godot": ["fluke_validate"],
    "fluke-mahjong-service-tests": ["fluke_validate(scenario=mahjong)"],
    "orca-claude-env": ["orca_claude_env_check", "orca_stop_stale_daemon"],
    "mortal-mcp": ["mortal_catalog", "mortal_guide"],
    "list-tools": ["mortal_catalog", "mortal_guide"],
    "localai": ["localai_dispatch"],
    "remote-zip-extract": ["remote_zip_list", "remote_zip_extract"],
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


ORCA_TOOL = Path(os.environ.get("MORTAL_ORCA_TOOL", str(Path.home() / "tools/orca_claude_env/orca_claude_env.py")))
ORCA_EVIDENCE = Path.home() / ".local/state/mortal-mcp/evidence/orca"


def run_orca_tool(args: list[str], timeout: int) -> dict:
    if not ORCA_TOOL.is_file():
        return {"ok": False, "reason": f"ORCA tool missing: {ORCA_TOOL}"}
    try:
        done = subprocess.run(["python3", str(ORCA_TOOL), *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timed_out; inspect process state before retry"}
    try:
        result = json.loads(done.stdout)
    except ValueError:
        return {"ok": False, "exit_code": done.returncode, "tail": (done.stdout + done.stderr)[-1800:]}
    result.setdefault("ok", done.returncode == 0)
    return result


@SERVER.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def orca_claude_env_check() -> dict:
    """Read-only: find ORCA terminal daemons that pass a stale ANTHROPIC_BASE_URL to Claude Code, and list ORCA Claude sessions with resume ids. No model call."""
    return run_orca_tool(["check"], timeout=20)


@SERVER.tool(annotations={"destructiveHint": True, "idempotentHint": False})
def orca_stop_stale_daemon(pid: int) -> dict:
    """Authorized fix: save resume list, then SIGTERM one daemon that check reported as stale. Closes every Claude session in that daemon; requires user's instruction."""
    return run_orca_tool(["stop-daemon", "--pid", str(pid), "--evidence", str(ORCA_EVIDENCE)], timeout=30)


@SERVER.resource("mortal://skills/orca-claude-env")
def orca_claude_env_skill() -> str:
    return (Path(__file__).parent / "skills/orca-claude-env/SKILL.md").read_text()


LOCALAI = Path.home() / ".local/bin/localai"
REMOTE_ZIP = Path.home() / "tools/remote_zip_extract.py"


def run_tool_json(argv: list[str], timeout: int) -> dict:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timed_out; inspect before retry"}
    return {"ok": done.returncode == 0, "exit_code": done.returncode,
            "stdout": done.stdout[-3500:], "stderr": done.stderr[-1500:]}


def inside_home(path: str) -> bool:
    return Path(path).expanduser().resolve().is_relative_to(Path.home())


@SERVER.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def localai_dispatch(role: Literal["code", "review", "second"], task: str, paths: list[str] = [], timeout: int = 300) -> dict:
    """Dispatch a bounded task to local Ollama models (memory gate enforced by localai). The answer is a lead to verify, not evidence. Paths must be inside $HOME."""
    bad = [p for p in paths if not inside_home(p)]
    if bad:
        return {"ok": False, "reason": f"paths outside home: {bad}"}
    timeout = max(30, min(timeout, 900))
    # "--" stops a task that starts with "-" from being parsed as a localai flag.
    return run_tool_json([str(LOCALAI), role, "--timeout", str(timeout), "--", task, *paths], timeout + 30)


@SERVER.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def remote_zip_list(url: str, match: str = "") -> dict:
    """List members of a remote https zip (e.g. Godot .tpz) via HTTP Range; downloads only the directory."""
    argv = ["python3", str(REMOTE_ZIP), url, "--list"] + (["--match", match] if match else [])
    return run_tool_json(argv, 120)


@SERVER.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True})
def remote_zip_extract(url: str, out_dir: str, match: list[str]) -> dict:
    """Download only the matching members of a remote https zip into out_dir (inside $HOME). Overwrites same-named files there."""
    if not match:
        return {"ok": False, "reason": "match must be non-empty"}
    if not inside_home(out_dir):
        return {"ok": False, "reason": f"out_dir outside home: {out_dir}"}
    argv = ["python3", str(REMOTE_ZIP), url, "--out", str(Path(out_dir).expanduser().resolve())]
    for item in match:
        argv += ["--match", item]
    return run_tool_json(argv, 600)



@SERVER.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def ssd_scan_report() -> dict:
    """Read bounded SSD inventory and status. Does not start or delete anything."""
    root = Path.home() / ".local/state/ssd-scan"
    result = {}
    for name in ["status", "report"]:
        path = root / (name + ".json")
        if not path.exists():
            result[name] = {"status": "not_run"}
        elif path.is_symlink() or path.stat().st_size > 2000000:
            raise ValueError("Unsafe or oversized SSD report")
        else:
            result[name] = json.loads(path.read_text())
    return result


@SERVER.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True})
def ssd_scan_start() -> dict:
    """Start only the fixed read-only SSD inventory unit; no caller-controlled command."""
    done = subprocess.run(["systemctl", "--user", "start", "--no-block", "ssd-scan.service"],
                          capture_output=True, text=True, timeout=5)
    return {"ok": done.returncode == 0, "status": "starting" if done.returncode == 0 else "failed",
            "error": done.stderr[:500] if done.returncode else None}

if __name__ == "__main__":
    SERVER.run(transport="streamable-http")
