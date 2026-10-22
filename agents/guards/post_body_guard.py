"""A command that writes a comment/PR body file and posts it in the same breath leaves no
chance to check the text against the output of whatever was meant to verify it.

Fail open: only the literal case is flagged - the same path, as written, is both a redirect
target (or a `sed -i` target) and the source of a posted body.
"""
import re

# gh api ... -F body=@PATH   |   gh pr create/comment ... --body-file PATH
BODY_SOURCE = re.compile(r"""(?:\bbody=@|--body-file[=\s]+)(?P<q>["']?)(?P<path>[^\s"';|&]+)(?P=q)""")
# > PATH, >> PATH (not 2>, &>, >&)
REDIRECT = re.compile(r"""(?<![0-9&>])>{1,2}\s*(?P<q>["']?)(?P<path>[^\s"';|&<>]+)(?P=q)""")
SED_INPLACE = re.compile(r"\bsed\s+-i\b[^;|&\n]*")


def written_and_posted(command):
    """The body file this command both writes and posts, or None."""
    if re.match(r"\s*POST_OK=1\b", command):
        return None
    posted = {m.group("path") for m in BODY_SOURCE.finditer(command)}
    if not posted:
        return None
    written = {m.group("path") for m in REDIRECT.finditer(command)}
    for sed in SED_INPLACE.findall(command):
        written.update(path for path in posted if path in sed)
    both = sorted(posted & written)
    return both[0] if both else None
