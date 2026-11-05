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
          "subprocess.Popen([sys.executable,'-c',sys.argv[1],'claude',sys.argv[2]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**kw)")
alive_child = subprocess.Popen([sys.executable, "-c", CODE, "claude", MARK + "-alive"])
subprocess.run([sys.executable, "-c", LAUNCH, CODE, MARK + "-orphan"], check=True)
time.sleep(2)


def tidy(*args):
    return subprocess.run([*exe, "tidy", "--only", MARK, *args], capture_output=True, text=True, encoding="utf-8").stdout



def fail(msg):
    alive_child.kill()
    tidy("--agent-idle-hours", "0", "--apply")
    print("FAIL:", msg)
    sys.exit(1)


out = tidy("--agent-idle-hours", "99")
if MARK in out:
    fail("age threshold must keep it\n" + out)
out = tidy("--agent-idle-hours", "0")
if MARK + "-orphan" not in out or MARK + "-alive" in out:
    fail("preview must list only the orphan\n" + out)
out = tidy("--agent-idle-hours", "0", "--apply")
if "stopped" not in out:
    fail("orphan not stopped\n" + out)
time.sleep(1)
out = tidy("--agent-idle-hours", "0")
if MARK in out or alive_child.poll() is not None:
    fail("orphan must be gone and the parented process alive\n" + out)
alive_child.kill()
print("PASS: orphan claude stopped, parented claude and young orphan kept")
