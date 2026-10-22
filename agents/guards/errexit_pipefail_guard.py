"""A pipeline returns the exit status of its last command, so `set -e` or `&&` cannot see a
failure earlier in the pipe. Twice that let a dependent write run after a failed step:
2026-09-30 `pytest | tail -1 && git commit` committed failing tests; 2026-10-16 `set -e` in
zsh without pipefail let a checkpoint write go ahead after a failed piped check.

Flagged only when the command has no `pipefail` anywhere and either
  A. turns on errexit (`set -e...`, `set -o errexit`, `setopt errexit`) and contains a `|`, or
  B. has a `|` before an `&&` that leads to `git commit` or the checkpoint tool.
Heredoc bodies are data and are removed before lexing. Unparsable text fails open.
"""
import os
import re
import shlex

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
PIPE_TOKENS = {"|", "|&"}


def strip_heredocs(text):
    out, end = [], None
    for line in text.split("\n"):
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        out.append(line)
        m = HEREDOC.search(line)
        if m:
            end = m.group(2)
    return "\n".join(out)


def tokens(text):
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|\n()")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    return list(lexer)


def is_errexit(words):
    if not words:
        return False
    if words[0] == "set":
        if any(re.fullmatch(r"-[A-Za-z]*e[A-Za-z]*", w) for w in words[1:]):
            return True
        return any(a == "-o" and b == "errexit" for a, b in zip(words[1:], words[2:]))
    return words[0] == "setopt" and any(w.lower().replace("_", "") == "errexit" for w in words[1:])


def is_dependent_write(words):
    if not words:
        return False
    head = os.path.basename(words[0])
    if head == "git" and "commit" in words[1:3]:
        return True
    if head == "cash-rule-checkpoint":
        return True
    return any(os.path.basename(w) == "cash_rule_checkpoint.py" for w in words)


def problem(text):
    if len(text) > 65536 or re.match(r"\s*PIPE_OK=1\b", text):
        return False
    body = strip_heredocs(text)
    try:
        toks = tokens(body)
    except ValueError:
        return False
    if any("pipefail" in t for t in toks):
        return False
    groups, seps, current = [], [], []
    for t in toks:
        if t and all(c in ";&|\n()" for c in t):
            groups.append(current)
            seps.append(t)
            current = []
        else:
            current.append(t)
    groups.append(current)
    if not any(s in PIPE_TOKENS for s in seps):
        return False
    if any(is_errexit(g) for g in groups):
        return True
    seen_pipe = False
    for i, sep in enumerate(seps):
        seen_pipe |= sep in PIPE_TOKENS
        if seen_pipe and sep == "&&" and any(is_dependent_write(g) for g in groups[i + 1:]):
            return True
    return False
