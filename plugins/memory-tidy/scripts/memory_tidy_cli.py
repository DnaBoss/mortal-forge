#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import idle_agents
import install
import session_hint
import tidy_any


def run_all():
    hours = []
    if "--min-idle-hours" in sys.argv:
        hours = ["--min-idle-hours", sys.argv[sys.argv.index("--min-idle-hours") + 1]]
    apply = ["--apply"] if "--apply" in sys.argv else []
    tmp = ["--tmp"] if apply else []
    sys.argv = ["memory-tidy idle", *hours, *apply]
    code = idle_agents.main()
    sys.argv = ["memory-tidy tidy", *apply, *tmp]
    return code or tidy_any.main()


COMMANDS = {"tidy": tidy_any.main, "idle": idle_agents.main, "all": run_all, "install": install.main, "hint": session_hint.main}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage: memory-tidy {all|idle|tidy|install|hint} [options]   (add --help after the command)", file=sys.stderr)
        return 2
    command = sys.argv[1]
    sys.argv = [f"memory-tidy {command}", *sys.argv[2:]]
    return COMMANDS[command]()


if __name__ == "__main__":
    sys.exit(main())
