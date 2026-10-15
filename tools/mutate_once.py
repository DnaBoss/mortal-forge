"""Negative control helper: apply one text mutation, run a test command, restore the file.

Usage:
  python3 ~/tools/mutate_once.py FILE OLD NEW -- CMD [ARGS...]

OLD must occur exactly once in FILE. The file is always restored, even when the
command crashes. Prints RED (command failed, the tests caught the mutation) or
GREEN (command passed, nobody checks this line) plus up to four summary lines.
Exit status: 0 RED, 1 GREEN, 2 bad arguments or anchor not unique.
"""
import subprocess
import sys

SUMMARY_MARKS = ("test result", "FAILED", "error[", "Tests ", " FAIL ", "×")


def main(argv: list[str]) -> int:
    if "--" not in argv or argv.index("--") != 3 or len(argv) < 5:
        print(__doc__, file=sys.stderr)
        return 2
    path, old, new = argv[:3]
    cmd = argv[4:]
    with open(path, encoding="utf-8") as handle:
        original = handle.read()
    count = original.count(old)
    if count != 1:
        print(f"anchor count={count}: {old!r}", file=sys.stderr)
        return 2
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(original.replace(old, new))
        run = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(original)
    lines = [
        line
        for line in (run.stdout + run.stderr).splitlines()
        if any(mark in line for mark in SUMMARY_MARKS)
    ]
    verdict = "RED" if run.returncode != 0 else "GREEN"
    print(verdict, "exit", run.returncode, "|", " / ".join(lines[:4]))
    return 0 if verdict == "RED" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
