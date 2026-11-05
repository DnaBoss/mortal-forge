import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

exe = [sys.argv[1]] if len(sys.argv) == 2 else [sys.executable, "-I", str(Path(__file__).resolve().parent.parent / "scripts/memory_tidy_cli.py")]
home = Path(tempfile.mkdtemp())
env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
sessions = home / ".claude/sessions"
sessions.mkdir(parents=True)
handoffs = home / ".local/state/idle-agents/handoffs"
FAKE = ("import subprocess,sys,time\n"
        "if len(sys.argv)>2: subprocess.Popen([sys.executable,'-c','import time;time.sleep(300)',sys.argv[2]])\n"
        "time.sleep(300)")
procs = {}


def make(name, child=None, started_ago=2):
    args = [sys.executable, "-c", FAKE, "claude"] + ([child] if child else [])
    p = subprocess.Popen(args)
    work = home / f"work-{name}"
    work.mkdir()
    slug = "".join(c if c.isalnum() else "-" for c in str(work))
    (home / ".claude/projects" / slug).mkdir(parents=True)
    (home / ".claude/projects" / slug / f"sess-{name}.jsonl").write_text(
        json.dumps({"type": "user", "message": {"content": f"task of {name}"}}) + "\n")
    (sessions / f"{p.pid}.json").write_text(json.dumps({
        "pid": p.pid, "kind": "interactive", "status": "idle", "cwd": str(work), "sessionId": f"sess-{name}",
        "updatedAt": (time.time() - 10 * 3600) * 1000, "startedAt": (time.time() - started_ago) * 1000}))
    procs[name] = p


def run(*args):
    return subprocess.run([*exe, "idle", *args], capture_output=True, text=True, encoding="utf-8", env=env).stdout


def fail(msg):
    for p in procs.values():
        p.kill()
    print("FAIL:", msg)
    sys.exit(1)


def wait_gone(p):
    for _ in range(20):
        if p.poll() is not None:
            return True
        time.sleep(0.5)
    return False


make("plain")
make("mcp", child="fake-mcp-server")
make("worker", child="long-build")
make("reused", started_ago=3600)
time.sleep(1.5)

out = run("--min-idle-hours", "99", "--apply")
if "keep" not in out or any(p.poll() is not None for p in procs.values()) or handoffs.exists():
    fail("too-short threshold must keep every session\n" + out)
out = run("--min-idle-hours", "4")
if "would_close" not in out or any(p.poll() is not None for p in procs.values()) or handoffs.exists():
    fail("preview must not close or write\n" + out)
if "kept_busy_children" not in out or "kept_pid_changed" not in out:
    fail("preview must show why sessions are kept\n" + out)
out = run("--min-idle-hours", "4", "--apply")
if not wait_gone(procs["plain"]) or not wait_gone(procs["mcp"]):
    fail("plain and mcp-only sessions must close\n" + out)
if procs["worker"].poll() is not None or procs["reused"].poll() is not None:
    fail("session with a running non-MCP child, or with a changed start time, must stay\n" + out)
texts = [f.read_text(encoding="utf-8") for f in handoffs.glob("*.md")]
if len(texts) != 2 or not any("task of plain" in t and "claude --resume sess-plain" in t for t in texts):
    fail(f"expected two handoffs for the closed sessions, got {len(texts)}\n" + out)
for p in procs.values():
    p.kill()
print("PASS: keep / preview / close with handoff / skip busy child / skip changed start")
