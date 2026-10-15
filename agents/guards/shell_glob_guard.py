"""zsh aborts the whole command line when an unquoted glob matches no file; flag the literal cases.

Fail open: anything this cannot evaluate with certainty (variables, heredocs, `case` patterns,
`[[ ]]` tests, arithmetic, a `cd` it cannot follow, `[...]` and `{...}` patterns) is allowed.

`?` counts as a glob too: an unquoted URL query string (`jobs?per_page=50`) aborts the line.
"""
import glob
import os

SEPARATORS = "|;&()<>"
UNSURE = "$`{}[]"


def split_words(line):
    """Return [(word, has_unquoted_star_or_question_mark, unsure)] or None when quotes do not balance."""
    words, cur, star, unsure, started = [], [], False, False, False
    quote = None
    i = 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == quote:
                quote = None
            elif c == "\\" and quote == '"' and i + 1 < len(line):
                i += 1
                cur.append(line[i])
            else:
                if quote == '"' and c in "$`":
                    unsure = True
                cur.append(c)
        elif c in "'\"":
            quote, started = c, True
        elif c == "\\" and i + 1 < len(line):
            i += 1
            cur.append(line[i])
            started = True
        elif c.isspace() or c in SEPARATORS:
            if started or cur:
                words.append(("".join(cur), star, unsure))
            cur, star, unsure, started = [], False, False, False
            if c in SEPARATORS:
                words.append((c, False, False))
        else:
            if c in "*?":
                star = True
            elif c in UNSURE:
                unsure = True
            cur.append(c)
        i += 1
    if quote:
        return None
    if started or cur:
        words.append(("".join(cur), star, unsure))
    return words


def unmatched_glob(text, base):
    """Return the first word with an unquoted `*` or `?` that matches nothing, else None."""
    if "GLOB_OK=1" in text or len(text) > 65536 or "<<" in text or "$((" in text:
        return None
    cwd = base
    for line in text.splitlines():
        words = split_words(line)
        if words is None:
            return None
        if any(w in ("case", "[[", "((") for w, _s, _u in words):
            return None
        i = 0
        while i < len(words):
            word, star, unsure = words[i]
            if word in ("cd", "pushd", "popd"):
                if word != "cd" or i + 1 >= len(words):
                    return None
                target, target_star, target_unsure = words[i + 1]
                if target_star or target_unsure or target in ("-", "") or target in SEPARATORS:
                    return None
                cwd = os.path.normpath(os.path.join(cwd, os.path.expanduser(target)))
                i += 2
                continue
            if star and not unsure:
                pattern = os.path.join(cwd, os.path.expanduser(word))
                try:
                    if not glob.glob(pattern, recursive=True):
                        return word
                except (OSError, ValueError):
                    return None
            i += 1
    return None
