#!/usr/bin/env python3
"""Reject commits whose staged text contains unresolved merge markers."""
import re
import subprocess
import sys


def has_conflict(content):
    return bool(re.search(rb"(?m)^(?:<<<<<<< |=======\r?$|>>>>>>> )", content))


def main():
    names = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"]
    ).split(b"\0")
    for name in filter(None, names):
        content = subprocess.check_output(["git", "show", b":" + name])
        if b"\0" not in content and has_conflict(content):
            print("拒絕提交：暫存內容仍有合併衝突標記", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
