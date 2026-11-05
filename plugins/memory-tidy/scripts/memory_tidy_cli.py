#!/usr/bin/env python3
import sys

import install
import tidy_any

COMMANDS = {"tidy": tidy_any.main, "install": install.main}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage: memory-tidy {tidy|install} [options]   (add --help after the command)", file=sys.stderr)
        return 2
    command = sys.argv[1]
    sys.argv = [f"memory-tidy {command}", *sys.argv[2:]]
    return COMMANDS[command]()


if __name__ == "__main__":
    sys.exit(main())
