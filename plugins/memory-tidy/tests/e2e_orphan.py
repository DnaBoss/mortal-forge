import os
import subprocess
import sys
import time
from pathlib import Path

exe = [sys.argv[1]] if len(sys.argv) == 2 else [sys.executable, "-I", str(Path(__file__).resolve().parent.parent / "scripts/memory_tidy_cli.py")]
MARK = "orphan-test-" + str(os.getpid())
CODE = "import time;time.sleep(300)"
LAUNCH = ("import subprocess,sys,os\n"
          "kw={'creationflags':0x00000008|0x00000200} if os.name=='nt' else {'start_new_session':True}\n"
          "p=subprocess.Popen([sys.executable,'-c',sys.argv[1],'claude',sys.argv[2]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**kw)\n"
          "print(p.pid)")
alive_child = subprocess.Popen([sys.executable, "-c", CODE, "claude", MARK + "-alive"])
orphan_pid = subprocess.run([sys.executable, "-c", LAUNCH, CODE, MARK + "-orphan"], check=True, capture_output=True, text=True).stdout.strip()
time.sleep(2)


def tidy(*args):
    return subprocess.run([*exe, "tidy", "--only", MARK, *args], capture_output=True, text=True, encoding="utf-8").stdout


def cleanup():
    alive_child.kill()
    tidy("--agent-idle-hours", "0", "--apply")


def fail(msg):
    cleanup()
    print("FAIL:", msg)
    sys.exit(1)


if os.name != "nt":
    ppid = subprocess.run(["ps", "-o", "ppid=", "-p", orphan_pid], capture_output=True, text=True).stdout.strip()
    comm = subprocess.run(["ps", "-o", "args=", "-p", ppid], capture_output=True, text=True).stdout.strip()
    if ppid != "1" and "systemd" not in comm:
        cleanup()
        os.kill(int(orphan_pid), 9)
        print(f"SKIP: this machine reparents orphans to '{comm[:60]}' (pid {ppid}), not to init")
        sys.exit(0)

if sys.platform.startswith("linux") and Path(f"/proc/{orphan_pid}/cgroup").read_text().strip().endswith(".service"):
    cleanup()
    os.kill(int(orphan_pid), 9)
    print("SKIP: the orphan runs inside a systemd service, which the tool leaves alone")
    sys.exit(0)

out = tidy("--agent-idle-hours", "99")
if "orphan processes: 0" not in out:
    fail("age threshold must keep it\n" + out)
out = tidy("--agent-idle-hours", "0")
if "orphan processes: 1" not in out or "[agent]" not in out:
    fail("preview must list exactly the orphan\n" + out)
out = tidy("--agent-idle-hours", "0", "--apply")
if "stopped" not in out:
    fail("orphan not stopped\n" + out)
time.sleep(1)
out = tidy("--agent-idle-hours", "0")
if "orphan processes: 0" not in out or alive_child.poll() is not None:
    fail("orphan must be gone and the parented process alive\n" + out)
alive_child.kill()
print("PASS: orphan claude stopped, parented claude and young orphan kept")
