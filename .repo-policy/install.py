#!/usr/bin/env python3
"""Install a private, recoverable hook snapshot without modifying the worktree."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def install(repo, source, include_worktrees=False):
    repo = Path(git(repo, "rev-parse", "--show-toplevel"))
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    worktrees = git(repo, "worktree", "list", "--porcelain")
    if worktrees.count("worktree ") > 1 and not include_worktrees:
        raise RuntimeError("Multiple registered worktrees: shared core.hooksPath requires per-worktree review first.")
    previous = subprocess.run(["git", "-C", str(repo), "config", "--get", "core.hooksPath"], capture_output=True, text=True).stdout.strip()
    if previous and (Path(previous) / "installation.json").exists():
        raise RuntimeError("Policy already installed. Restore the recorded installation before replacing it.")
    local = subprocess.run(["git", "-C", str(repo), "config", "--local", "--get", "core.hooksPath"], capture_output=True, text=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = common / "repo-policy" / stamp
    target.mkdir(parents=True, mode=0o700)
    for name in ["policy.py", "config.json"]:
        shutil.copy2(source / name, target / name)
    policy_config = json.loads((target / "config.json").read_text())
    policy_config["legacy_branches"] = sorted(set(policy_config.get("legacy_branches", [])) | set(git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()))
    policy_config["legacy_tips"] = git(repo, "for-each-ref", "--format=%(objectname)", "refs/heads").splitlines()
    (target / "config.json").write_text(json.dumps(policy_config, ensure_ascii=False, indent=2) + "\n")
    prior = previous or str(common / "hooks")
    state = {"version": "1.0.0", "repository": str(repo), "prior_hooks_path": prior,
             "prior_local_hooks_path": local.stdout.strip() if local.returncode == 0 else None,
             "installed_hooks_path": str(target), "installed_at": stamp,
             "shared_worktrees_reviewed": worktrees.splitlines()}
    policy_hooks = {"pre-commit", "pre-merge-commit", "commit-msg", "pre-push"}
    for hook in sorted(policy_hooks):
        (target / hook).write_text('#!/bin/sh\nexec python3 "$(dirname "$0")/policy.py" ' + hook + ' "$@"\n')
        (target / hook).chmod(0o755)
    # Preserve every other hook as a wrapper, including post-checkout and pre-merge-commit.
    prior_dir = Path(prior)
    if not prior_dir.is_absolute():
        prior_dir = repo / prior_dir
    if prior_dir.is_dir():
        originals = target / "original-hooks"
        originals.mkdir(mode=0o700)
        state["prior_executable_hooks"] = {}
        for old in prior_dir.iterdir():
            if old.is_file() and os.access(old, os.X_OK) and not old.name.endswith(".sample"):
                shutil.copy2(old, originals / old.name)
                state["prior_executable_hooks"][old.name] = hashlib.sha256(old.read_bytes()).hexdigest()
            if old.name in policy_hooks or old.name.endswith(".sample"):
                continue
            if old.is_file() and os.access(old, os.X_OK):
                # Shell quote apostrophes in the fixed original path.
                quoted = "'" + str(old).replace("'", "'\\''") + "'"
                (target / old.name).write_text('#!/bin/sh\nexec ' + quoted + ' "$@"\n')
                (target / old.name).chmod(0o755)
    (target / "installation.json").write_text(json.dumps(state, indent=2) + "\n")
    git(repo, "config", "--local", "core.hooksPath", str(target))
    return state


def restore(repo, record):
    state = json.loads(record.read_text())
    if str(Path(git(repo, "rev-parse", "--show-toplevel"))) != state["repository"]:
        raise RuntimeError("Recovery record belongs to another checkout.")
    if git(repo, "config", "--local", "--get", "core.hooksPath") != state["installed_hooks_path"]:
        raise RuntimeError("Hook configuration changed since installation; refuse to overwrite it.")
    previous = state["prior_local_hooks_path"]
    if previous is None:
        git(repo, "config", "--local", "--unset", "core.hooksPath")
    else:
        git(repo, "config", "--local", "core.hooksPath", previous)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--include-worktrees", action="store_true", help="Explicitly apply shared hooks to every reviewed worktree; no worktree files are modified.")
    args = parser.parse_args()
    if args.restore:
        restore(args.repo, args.restore)
    else:
        print(json.dumps(install(args.repo, args.source, args.include_worktrees), indent=2))


if __name__ == "__main__":
    main()
