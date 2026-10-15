"""Copy a Rust source file, writing every non-ASCII character as a \\u{...} escape.

Usage:
  python3 ~/tools/escape_non_ascii_rs.py SRC DST

Use it when repo rules want ASCII-only code but messages shown to users are not
English. Only correct when all non-ASCII text sits inside string or char literals:
outside a literal the escape is not valid Rust (comments get unreadable escapes).
Exit status: 0 written, 2 bad arguments or SRC equals DST.
"""
import os
import sys


def escape(text: str) -> str:
    return "".join(c if ord(c) < 128 else "\\u{%x}" % ord(c) for c in text)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    src, dst = argv
    if os.path.abspath(src) == os.path.abspath(dst):
        print("SRC and DST must differ", file=sys.stderr)
        return 2
    with open(src, encoding="utf-8") as handle:
        text = handle.read()
    with open(dst, "w", encoding="ascii") as handle:
        handle.write(escape(text))
    print("non-ascii chars escaped:", sum(1 for c in text if ord(c) >= 128))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
