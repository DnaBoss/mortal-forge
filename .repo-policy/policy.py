#!/usr/bin/env python3
"""Portable Gitflow hooks. No automatic staging, formatting, or network calls."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys

VERSION = "1.0.0"
TYPES = "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
SUBJECT = re.compile(rf"^(?:{TYPES})(?:\([a-z0-9][a-z0-9._/-]*\))?!?: \S.*$")
TOPIC = re.compile(r"^(feature|bug|docs|chore|refactor|test|ci)/[a-z0-9]+(?:[/-][a-z0-9]+)*$")
VERSION_BRANCH = re.compile(r"^(release|hotfix)/v?\d+\.\d+\.\d+(?:-[a-z0-9]+(?:[.-][a-z0-9]+)*)?$")
PROTECTED = {"main", "master", "develop", "dev"}
ZERO = "0" * 40


class Refused(Exception):
    pass


def git(*args, cwd=None, data=None, check=True, timeout=60):
    result = subprocess.run(["git", *args], cwd=cwd, input=data, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise Refused("git " + args[0] + " failed: " + result.stderr.decode(errors="replace").strip())
    return result


def text(*args):
    return git(*args).stdout.decode(errors="replace").strip()


def load_config():
    return json.loads(Path(__file__).with_name("config.json").read_text())


def branch_ok(name, config, protected=False):
    return bool(TOPIC.fullmatch(name) or VERSION_BRANCH.fullmatch(name)
                or name in config.get("legacy_branches", [])
                or (protected and name in PROTECTED))


def merging():
    return git("rev-parse", "--verify", "MERGE_HEAD", check=False).returncode == 0


def check_branch(config, phase="pre-commit"):
    branch = text("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch in PROTECTED:
        if merging():
            merged = text("rev-parse", "MERGE_HEAD")
            names = text("for-each-ref", "--format=%(refname:short)", "--points-at=" + merged, "refs/heads").splitlines()
        elif phase == "pre-merge-commit" and os.environ.get("GIT_REFLOG_ACTION", "").startswith("merge "):
            # Git invokes pre-merge-commit before writing MERGE_HEAD.
            names = os.environ["GIT_REFLOG_ACTION"][6:].split()
            for name in names:
                git("rev-parse", "--verify", "refs/heads/" + name)
        else:
            raise Refused(f"Direct commits on {branch} are forbidden. Create feature/ or bug/ from develop.")
        allowed = ("release/", "hotfix/") if branch in {"main", "master"} else (
            "feature/", "bug/", "docs/", "chore/", "refactor/", "test/", "ci/", "release/", "hotfix/")
        # A commit may have both a valid source branch and unrelated legacy aliases.
        valid = [name.startswith(allowed) and branch_ok(name, config) for name in names]
        acceptable = any(valid) if merging() else all(valid)
        if not names or not acceptable:
            raise Refused("Merge source must be a named Gitflow branch; main/master accepts release/ or hotfix/ only.")
    elif not branch_ok(branch, config):
        raise Refused("Invalid branch: use feature/<slug>, bug/<slug>, release/<semver>, or hotfix/<semver>.")


def check_message(message):
    lines = message.splitlines()
    first = next((line for line in lines if line and not line.startswith("#")), "")
    if first.startswith("Merge ") and merging():
        return
    if not SUBJECT.fullmatch(first) or len(first) > 100:
        raise Refused("Commit subject must be Conventional Commits, <=100 characters, e.g. fix(auth): reject expired token.")
    if first.startswith(("fixup!", "squash!")):
        raise Refused("Squash temporary commits before integration.")


def staged_paths(include_deleted=False):
    kinds = "ACMRD" if include_deleted else "ACMR"
    return [p.decode(errors="surrogateescape") for p in git("diff", "--cached", "--name-only", "--diff-filter=" + kinds, "-z").stdout.split(b"\0") if p]


def check_files(paths, staged=True, revision=None):
    for name in paths:
        leaf = Path(name).name
        if leaf in {"db_profiles.json", "governance.json", "approvals.json", "audit-log.jsonl"} or (
            leaf.startswith(".env") and leaf not in {".env.example", ".env.sample", ".env.template"}):
            raise Refused("Local credentials/runtime file must not be committed: " + name)
        if staged or revision:
            raw = git("show", (revision or "") + ":" + name).stdout
        else:
            raw = Path(name).read_bytes()
        if len(raw) > 2_000_000 or b"\0" in raw:
            continue
        if re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b", raw):
            raise Refused("Potential credential in " + name + "; value suppressed.")
        suffix = Path(name).suffix
        try:
            if suffix == ".py":
                ast.parse(raw, filename=name)
            elif suffix == ".json":
                json.loads(raw)
            elif suffix == ".sh":
                result = subprocess.run(["bash", "-n"], input=raw, capture_output=True, timeout=30)
                if result.returncode:
                    raise ValueError("shell syntax failed")
        except (SyntaxError, ValueError) as error:
            raise Refused("Syntax check failed: " + name + " (" + type(error).__name__ + ")") from error


def clean_gate_tree(staged=False):
    args = ("diff", "--quiet") if staged else ("diff", "--quiet", "HEAD", "--")
    if git(*args, check=False).returncode:
        raise Refused("Uncommitted tracked changes would invalidate the gate. Preserve them and use a clean worktree.")
    if git("ls-files", "--others", "--exclude-standard", "-z").stdout:
        raise Refused("Untracked files would contaminate the gate. Preserve them and use a clean worktree.")


def run_checks(config, phase, paths):
    # Language commands are selected from the actual changed files, not every manifest.
    for entry in config.get("checks", []):
        command = entry.get(phase)
        if not command or not any(re.search(entry["pattern"], p) for p in paths):
            continue
        if entry.get("requires") and not Path(entry["requires"]).is_file():
            if entry.get("optional_on_legacy_branch") and entry["requires"] not in paths:
                continue
            raise Refused("Required check prerequisite is missing: " + entry["requires"])
        clean_gate_tree(staged=phase == "pre_commit")
        print("[repo-policy] " + " ".join(command), file=sys.stderr)
        result = subprocess.run(command, timeout=entry.get("timeout", 900))
        if result.returncode:
            raise Refused("Project check failed: " + " ".join(command))


def prior_hook(phase, args, payload):
    state = Path(__file__).with_name("installation.json")
    if not state.exists():
        return
    config = json.loads(state.read_text())
    prior = config.get("prior_hooks_path")
    if not prior:
        return
    hook = Path(prior) / phase
    if not hook.is_absolute():
        hook = Path(text("rev-parse", "--show-toplevel")) / hook
    if phase in config.get("prior_executable_hooks", {}) and (not hook.is_file() or not os.access(hook, os.X_OK)):
        raise Refused("Previously active hook is missing or not executable: " + str(hook))
    if hook.is_file() and os.access(hook, os.X_OK):
        if phase in {"pre-commit", "pre-merge-commit", "pre-push"}:
            clean_gate_tree(staged=phase != "pre-push")
        print("[repo-policy] preserving existing " + str(hook), file=sys.stderr)
        result = subprocess.run([str(hook), *args], input=payload, timeout=1800)
        if result.returncode:
            raise Refused("Existing " + phase + " refused the operation.")


def push_updates(payload, config):
    changed = set()
    for line in payload.decode().splitlines():
        fields = line.split()
        if len(fields) != 4:
            raise Refused("Malformed pre-push input.")
        local_ref, local_oid, remote_ref, remote_oid = fields
        name = remote_ref.removeprefix("refs/heads/")
        if remote_ref.startswith("refs/heads/") and not branch_ok(name, config, protected=True):
            raise Refused("Invalid remote branch: " + name)
        if local_oid == ZERO:
            if remote_ref.startswith("refs/tags/"):
                raise Refused("Release tags must not be deleted.")
            if name in PROTECTED or name == config.get("default_branch"):
                raise Refused("Cannot delete primary/default branch: " + name)
            develop = text("rev-parse", "--verify", "refs/remotes/origin/develop")
            if remote_oid == ZERO or git("merge-base", "--is-ancestor", remote_oid, develop, check=False).returncode:
                raise Refused("Deletion requires fetched proof the remote tip is merged into develop.")
            continue
        if name in config.get("deployment_branches", []):
            raise Refused("Push triggers deployment on " + name + "; use the reviewed release procedure and explicit deployment authorization.")
        if remote_ref.startswith("refs/tags/"):
            if config.get("deployment_tags"):
                raise Refused("Release tag triggers publication/deployment; use the authorized release procedure.")
            if not re.fullmatch(r"refs/tags/v\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?", remote_ref):
                raise Refused("Release tags must use v<semver>.")
            if remote_oid != ZERO and remote_oid != local_oid:
                raise Refused("Existing release tags must not be rewritten.")
        elif remote_oid != ZERO and git("merge-base", "--is-ancestor", remote_oid, local_oid, check=False).returncode:
            raise Refused("Non-fast-forward push refused; fetch the remote tip and integrate without force.")
        if name in {"main", "master"}:
            branch = text("symbolic-ref", "--quiet", "--short", "HEAD")
            if not branch.startswith(("release/", "hotfix/")) and branch not in {"main", "master"}:
                raise Refused("Stable branches accept reviewed release/ or hotfix/ integration only.")
        commit_oid = text("rev-parse", local_oid + "^{commit}")
        if commit_oid != text("rev-parse", "HEAD"):
            raise Refused("Push one checked-out commit at a time so gates validate the actual outgoing tree.")
        base = remote_oid if remote_oid != ZERO else text("merge-base", commit_oid, "refs/remotes/origin/develop")
        changed.update(p.decode(errors="surrogateescape") for p in git("diff", "--name-only", "-z", base, commit_oid).stdout.split(b"\0") if p)
        # Old history remains valid; only outgoing commits absent from the rollout baseline are checked.
        baselines = [config["baseline"], *config.get("legacy_tips", [])]
        commits = text("rev-list", "--max-count=501", "--no-merges", base + ".." + commit_oid, *("^" + oid for oid in baselines)).splitlines()
        if len(commits) > 500:
            raise Refused("More than 500 new commits: split the review into bounded batches.")
        for oid in commits:
            check_message(text("show", "-s", "--format=%B", oid))
            historical = [p.decode(errors="surrogateescape") for p in git("diff-tree", "--root", "--no-commit-id", "-r", "--name-only", "--diff-filter=ACMR", "-z", oid).stdout.split(b"\0") if p]
            check_files(historical, revision=oid)
    return sorted(changed)


def audit(repo):
    root = str(Path(repo).resolve())
    return {"version": VERSION, "repository": root,
            "branch": git("branch", "--show-current", cwd=root, timeout=5).stdout.decode().strip(),
            "hooks_path": git("config", "--get", "core.hooksPath", cwd=root, check=False, timeout=5).stdout.decode().strip(),
            "develop": git("show-ref", "--verify", "refs/heads/develop", cwd=root, check=False, timeout=5).returncode == 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["pre-commit", "pre-merge-commit", "commit-msg", "pre-push", "audit"])
    parser.add_argument("args", nargs="*")
    parsed = parser.parse_args()
    try:
        if parsed.phase == "audit":
            print(json.dumps(audit(parsed.args[0] if parsed.args else ".")))
            return 0
        os.chdir(text("rev-parse", "--show-toplevel"))
        config = load_config()
        payload = sys.stdin.buffer.read() if parsed.phase == "pre-push" else None
        if parsed.phase in {"pre-commit", "pre-merge-commit"}:
            check_branch(config, parsed.phase)
            paths = staged_paths(include_deleted=True)
            git("diff", "--cached", "--check")
            check_files(staged_paths())
            run_checks(config, "pre_commit", paths)
        elif parsed.phase == "commit-msg":
            check_message(Path(parsed.args[0]).read_text())
        else:
            paths = push_updates(payload, config)
            if paths:
                clean_gate_tree()
            check_files([p for p in paths if Path(p).is_file()], staged=False)
            run_checks(config, "pre_push", paths)
        if parsed.phase == "pre-merge-commit":
            prior_hook("pre-commit", parsed.args, payload)
        prior_hook(parsed.phase, parsed.args, payload)
        return 0
    except (Refused, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        print("[repo-policy] " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
