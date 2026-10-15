#!/usr/bin/env python3
"""Dispatch one over-long Rust function to the local code model and splice the result.

Usage: split_long_fn.py <file.rs> <fn_name>
Extracts the function starting at <start_line> (ends at the first line equal to the
start line's indent + "}"), asks `localai code` for a behavior-identical split under
100 lines without #[allow], and replaces it in place. A backup is written to
<file>.split.bak. Verification (build/test/clippy) is the caller's job.
"""
import re, subprocess, sys

path, name = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().split("\n")
hits = [i + 1 for i, l in enumerate(lines) if re.match(r"\s*(pub(\([^)]*\))? )?(async )?fn " + re.escape(name) + r"\b", l)]
if len(hits) != 1:
    sys.exit(f"expected exactly one fn {name}, found {len(hits)}")
start = hits[0]
# include attributes/doc comments directly above
while start > 1 and re.match(r"\s*(#\[|///)", lines[start - 2]):
    start -= 1
fn_line = hits[0]
indent = re.match(r"\s*", lines[fn_line - 1]).group(0)
end = next(i for i in range(fn_line, len(lines)) if lines[i] == indent + "}")
old = "\n".join(lines[start - 1:end + 1])
open(path + ".split.bak", "w", encoding="utf-8").write("\n".join(lines))
open("/tmp/split_fn.rs", "w", encoding="utf-8").write(old)
task = ("Refactor this Rust function so every resulting function body is under 100 lines, with IDENTICAL "
        "behavior. Extract private helpers (methods in the same impl if it uses self, else free functions "
        "placed right after it). Keep names, error variants, event order and borrow semantics; use &mut "
        "where the original mutated. No #[allow]. Output ONLY the full replacement code.")
out = subprocess.run(["localai", "code", "--timeout", "600", "--max-tokens", "8192", task, "/tmp/split_fn.rs"],
                     capture_output=True, text=True, timeout=660).stdout.strip()
out = re.sub(r"^```\w*\n", "", out); out = re.sub(r"\n```\s*$", "", out)
if "fn " not in out:
    sys.exit("local model returned no code")
base = min((len(re.match(r"\s*", l).group(0)) for l in out.split("\n") if l.strip()), default=0)
new = "\n".join((indent + l[base:]) if l.strip() else l for l in out.split("\n"))
lines[start - 1:end + 1] = new.split("\n")
open(path, "w", encoding="utf-8").write("\n".join(lines))
print(f"replaced lines {start}-{end + 1} ({end - start + 2} lines) with {len(new.splitlines())} lines")
