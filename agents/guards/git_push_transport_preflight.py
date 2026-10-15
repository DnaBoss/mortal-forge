#!/usr/bin/env python3
"""Bounded transport preflight before a long Git push hook.

Used explicitly by a tool-call orchestrator before executing the same argv.
Resolves all per-command Git config before accepting the intended HTTPS URL.
It does not modify config, authenticate, access the network or execute push.
Shell/Python scripts must pass their actual argv, not a guessed URL.
"""
import argparse
import json
import os
import subprocess
import sys


def check(argv, cwd, expected):
    if not argv or os.path.basename(argv[0]) != "git" or len(argv) > 128:
        raise ValueError("expected a bounded literal git argv")
    if argv[0] != "/usr/bin/git":
        raise ValueError("expected the verified native Git executable")
    index = 1
    while index < len(argv) and argv[index].startswith("-"):
        if argv[index] not in ("-c", "-C") or index + 1 >= len(argv):
            raise ValueError("unsupported Git option; resolve it explicitly")
        index += 2
    if index >= len(argv) or argv[index] != "push":
        raise ValueError("expected a push command")
    rest = argv[index + 1:]
    if not rest or rest[0] != "origin":
        raise ValueError("expected the explicit origin remote")
    if not expected.startswith("https://") or len(expected) > 4096:
        raise ValueError("expected an explicit HTTPS URL")
    result = subprocess.run(
        ["/usr/bin/git", *argv[1:index]] + ["remote", "get-url", "--push", "--all", "origin"],
        cwd=cwd, capture_output=True, text=True, timeout=5, check=True,
    )
    urls = result.stdout.strip().splitlines()
    accepted = urls == [expected]
    return {"accepted": accepted, "resolved_url_matches": accepted,
            "push_url_count": len(urls)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    try:
        verdict = check(argv, args.cwd, args.expected)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"accepted": False, "reason": type(error).__name__}))
        return 2
    print(json.dumps(verdict))
    return 0 if verdict["accepted"] else 2


if __name__ == "__main__":
    sys.exit(main())
