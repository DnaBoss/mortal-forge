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

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)", "claude"])
sessions = home / ".claude/sessions"
sessions.mkdir(parents=True)
work = home / "work"
work.mkdir()
slug = "".join(c if c.isalnum() else "-" for c in str(work))
transcripts = home / ".claude/projects" / slug
transcripts.mkdir(parents=True)
(transcripts / "sess1.jsonl").write_text(json.dumps({"type": "user", "message": {"content": "fix the login bug"}}) + "\n")
old = (time.time() - 10 * 3600) * 1000
(sessions / f"{child.pid}.json").write_text(json.dumps(
    {"pid": child.pid, "kind": "interactive", "status": "idle", "cwd": str(work), "sessionId": "sess1", "updatedAt": old}))
handoffs = home / ".local/state/idle-agents/handoffs"


def run(*args):
    return subprocess.run([*exe, "idle", *args], capture_output=True, text=True, encoding="utf-8", env=env).stdout


def fail(msg):
    child.kill()
    print("FAIL:", msg)
    sys.exit(1)


out = run("--min-idle-hours", "99", "--apply")
if "keep" not in out or child.poll() is not None or handoffs.exists():
    fail("too-short threshold must keep the session\n" + out + f" poll={child.poll()} h={handoffs.exists()}")
out = run("--min-idle-hours", "4")
if "would_close" not in out or child.poll() is not None or handoffs.exists():
    fail("preview must not close or write\n" + out)
out = run("--min-idle-hours", "4", "--apply")
files = list(handoffs.glob("*.md")) if handoffs.exists() else []
if not files:
    fail("no handoff written\n" + out)
if "fix the login bug" not in files[0].read_text(encoding="utf-8") or "claude --resume sess1" not in files[0].read_text(encoding="utf-8"):
    fail("handoff content wrong\n" + files[0].read_text(encoding="utf-8"))
for _ in range(20):
    if child.poll() is not None:
        break
    time.sleep(0.5)
else:
    fail("session not closed\n" + out)
print("PASS: keep / preview / handoff + close")
