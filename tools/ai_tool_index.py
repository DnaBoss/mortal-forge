#!/usr/bin/env python3
"""Local inventory. Only allowlisted metadata leaves source configuration files."""

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024
MAX_ITEMS = 20000


def read_data(path):
    if not path.is_file():
        raise ValueError("not_regular_file")
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("not_regular_file")
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("source_too_large")
    return tomllib.loads(raw.decode()) if path.suffix == ".toml" else json.loads(raw)


def safe_name(value):
    value = str(value)
    return (
        value
        if re.fullmatch(r"[\w @./:+()\-]{1,240}", value)
        else "[unrecognized name]"
    )


def stamp():
    return datetime.datetime.now(datetime.UTC).isoformat()


class Scanner:
    def __init__(self, home, projects=(), models=True):
        self.home = home
        self.projects = projects
        self.models = models
        self.items = {}
        self.sources = []
        self.scope = None

    def add(
        self,
        kind,
        name,
        source,
        host,
        *,
        version=None,
        enabled=None,
        installed=None,
        parent=None,
        location=None,
        fingerprint=None,
        purpose=None,
        cached=None,
    ):
        key = hashlib.sha256(f"{kind}\0{source}\0{name}".encode()).hexdigest()[:24]
        scopes = sorted(
            set(self.items.get(key, {}).get("scopes", []) + [str(self.scope or source)])
        )
        self.items[key] = {
            "id": key,
            "kind": kind,
            "name": safe_name(name),
            "source": str(source),
            "hosts": sorted(set(host)),
            "version": version,
            "enabled": enabled if isinstance(enabled, bool) else None,
            "scopes": scopes,
            "purpose": purpose,
            "cached": cached,
            "installed": installed,
            "parent": parent,
            "location": location,
            "fingerprint": fingerprint,
            "loaded": None,
            "health": None,
            "last_used": None,
            "calls": None,
            "cost": None,
        }
        if len(self.items) > MAX_ITEMS:
            raise ValueError("too_many_items")
        return key

    def source(self, path, fn):
        self.scope = str(path)
        before = set(self.items)
        try:
            if not path.exists():
                self.sources.append({"path": str(path), "status": "missing"})
                return
            fn(read_data(path))
            self.sources.append({"path": str(path), "status": "ok"})
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            for key in set(self.items) - before:
                del self.items[key]
            self.sources.append({"path": str(path), "status": "error"})

    def config(self, path, host):
        def collect(data):
            for name, item in data.get(
                "mcp_servers", data.get("mcpServers", {})
            ).items():
                if not isinstance(item, dict):
                    raise TypeError("invalid_mcp")
                self.add(
                    "mcp",
                    name,
                    path,
                    [host],
                    enabled=item.get("enabled", not item.get("disabled", False)),
                )
            for name, item in data.get(
                "plugins", data.get("enabledPlugins", {})
            ).items():
                enabled = (
                    item
                    if isinstance(item, bool)
                    else item.get("enabled")
                    if isinstance(item, dict)
                    else None
                )
                self.add("plugin", name, path, [host], enabled=enabled)
            for project, settings in data.get("projects", {}).items():
                if isinstance(settings, dict):
                    for name, item in settings.get("mcpServers", {}).items():
                        self.add(
                            "mcp",
                            name,
                            str(path) + "#" + project,
                            [host],
                            enabled=None,
                            location=project,
                        )

        self.source(path, collect)

    def skills(self, root, host, parent=None, active=None):
        self.scope = str(root)
        if not root.exists():
            self.sources.append({"path": str(root), "status": "missing"})
            return
        count = 0
        try:
            # Root and its immediate skill directories may be symlinks. Deeper
            # symlinks are not followed, preventing cycles and arbitrary walks.
            candidates = [root / "SKILL.md"]
            for child in root.iterdir():
                if child.is_dir():

                    def walk_error(error):
                        raise error

                    for base, dirs, files in os.walk(child, onerror=walk_error):
                        depth = len(Path(base).relative_to(child).parts)
                        dirs[:] = (
                            sorted(
                                d
                                for d in dirs
                                if not d.startswith(".")
                                and d not in ("node_modules", "target", "__pycache__")
                            )
                            if depth < 6
                            else []
                        )
                        count += 1
                        if count > MAX_ITEMS:
                            raise ValueError("too_many_directories")
                        if "SKILL.md" in files:
                            candidates.append(Path(base) / "SKILL.md")
            for file in candidates:
                if not file.is_file():
                    continue
                resolved = file.resolve()
                with resolved.open("rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise ValueError("not_regular_file")
                    raw = stream.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("skill_too_large")
                text = raw.decode("utf-8", errors="replace")
                match = (
                    re.search(
                        r"^description:\s*(.{0,1200})$", text[:4096], re.MULTILINE
                    )
                    if text.startswith("---")
                    else None
                )
                key = self.add(
                    "skill",
                    resolved.parent.name,
                    resolved,
                    [host],
                    installed=True if parent is None else active,
                    cached=parent is not None,
                    purpose=match[1] if match else None,
                    parent=parent,
                    location=str(file),
                    fingerprint=hashlib.sha256(raw).hexdigest(),
                )
                # Merge aliases across agent hosts using the resolved file identity.
                self.items[key]["hosts"] = sorted(
                    set(self.items[key]["hosts"] + self.skill_hosts.get(key, []))
                )
                self.skill_hosts[key] = self.items[key]["hosts"]
            self.sources.append({"path": str(root), "status": "ok"})
        except (OSError, ValueError):
            self.sources.append({"path": str(root), "status": "error"})

    def plugins(self, base, host):
        registry = base / "installed_plugins.json"

        def installed(data):
            for name, installs in data.get("plugins", {}).items():
                for entry in installs:
                    location = entry.get("installPath")
                    self.add(
                        "plugin",
                        name,
                        str(registry) + "#" + str(location),
                        [host],
                        version=safe_name(entry.get("version", "unknown")),
                        installed=Path(location).is_dir() if location else None,
                        location=location,
                    )

        self.source(registry, installed)
        active_paths = {
            i["location"]
            for i in self.items.values()
            if i["kind"] == "plugin" and i["installed"] is True and i["location"]
        }
        cache = base / "cache"
        self.scope = str(cache)
        if cache.exists():
            for market in sorted(cache.iterdir()):
                if not market.is_dir():
                    continue
                for plugin in sorted(market.iterdir()):
                    if not plugin.is_dir():
                        continue
                    for version in sorted(plugin.iterdir()):
                        if not version.is_dir():
                            continue
                        name = plugin.name + "@" + market.name
                        self.scope = str(cache)
                        active = str(version) in active_paths
                        key = self.add(
                            "plugin",
                            name,
                            version.resolve(),
                            [host],
                            installed=True if active else None,
                            cached=True,
                            version=safe_name(version.name),
                            location=str(version),
                        )
                        self.skills(
                            version / "skills", host, key, True if active else None
                        )
                        for manifest in [version / ".mcp.json", version / "mcp.json"]:
                            if manifest.is_file():

                                def bundled(data, key=key, manifest=manifest):
                                    for name in data.get("mcpServers", data):
                                        self.add(
                                            "mcp", name, manifest, [host], parent=key
                                        )

                                self.source(manifest, bundled)
            self.sources.append({"path": str(cache), "status": "ok"})
        else:
            self.sources.append({"path": str(cache), "status": "missing"})

    def run(self):
        self.skill_hosts = {}
        h = self.home
        for rel, host in [
            (".codex/config.toml", "codex"),
            (".claude.json", "claude"),
            (".claude/settings.json", "claude"),
            (".gemini/settings.json", "gemini"),
            (".cursor/mcp.json", "cursor"),
            (".codeium/windsurf/mcp_config.json", "windsurf"),
        ]:
            self.config(h / rel, host)
        for root in self.projects:
            for rel, host in [
                (".mcp.json", "claude"),
                (".claude/settings.json", "claude"),
                (".codex/config.toml", "codex"),
                (".cursor/mcp.json", "cursor"),
            ]:
                self.config(root / rel, host)
            for rel, host in [
                (".agents/skills", "shared"),
                (".claude/skills", "claude"),
                (".codex/skills", "codex"),
            ]:
                self.skills(root / rel, host)
        for rel, host in [
            (".agents/skills", "shared"),
            (".codex/skills", "codex"),
            (".claude/skills", "claude"),
            (".gemini/skills", "gemini"),
        ]:
            self.skills(h / rel, host)
        for host in ["codex", "claude"]:
            base = h / ("." + host) / "plugins"
            try:
                self.plugins(base, host)
            except (OSError, ValueError):
                self.sources.append({"path": str(base / "cache"), "status": "error"})
        catalog = h / "tools/tools.json"
        self.source(
            catalog,
            lambda data: [
                self.add(
                    "tool",
                    item["name"],
                    catalog,
                    ["shared"],
                    location=item.get("location"),
                    purpose=str(item.get("purpose", ""))[:1200],
                )
                for item in data
            ],
        )
        self.scope = "PATH"
        self.sources.append({"path": "PATH", "status": "ok"})
        for name in [
            "codex",
            "claude",
            "gemini",
            "ollama",
            "localai",
            "codegraph",
            "mortal-tools",
            "gateway-chat",
        ]:
            binary = shutil.which(name)
            if binary:
                self.add(
                    "application",
                    name,
                    "PATH",
                    ["system"],
                    installed=True,
                    location=binary,
                )
        self.scope = "ollama:local"
        if self.models:
            try:

                class NoRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, *args, **kwargs):
                        return None

                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}), NoRedirect()
                )
                with opener.open(
                    "http://127.0.0.1:11434/api/tags", timeout=3
                ) as response:
                    raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("models_too_large")
                for model in json.loads(raw)["models"]:
                    self.add(
                        "model",
                        model["name"],
                        "ollama:local",
                        ["ollama"],
                        installed=True,
                        version=safe_name(model.get("digest", "unknown")),
                    )
                self.sources.append({"path": "ollama:local", "status": "ok"})
            except (OSError, ValueError, KeyError):
                self.sources.append({"path": "ollama:local", "status": "error"})
        else:
            self.sources.append({"path": "ollama:local", "status": "skipped"})
        # Reconcile plugin registration to cache records without claiming activation.
        registrations = {
            (i["name"], tuple(i["hosts"])): i
            for i in self.items.values()
            if i["kind"] == "plugin" and i["enabled"] is not None
        }
        for item in self.items.values():
            if item["kind"] == "plugin" and item["installed"] is True:
                registration = registrations.get((item["name"], tuple(item["hosts"])))
                if registration:
                    item["enabled"] = registration["enabled"]
            parent = self.items.get(item["parent"])
            if parent:
                item["enabled"] = parent["enabled"]
        return {
            "schema": 1,
            "projects": [str(p) for p in self.projects],
            "scanned_at": stamp(),
            "items": sorted(self.items.values(), key=lambda i: i["id"]),
            "sources": self.sources,
        }


def open_db(state):
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(state / "index.sqlite3", timeout=5)
    db.execute(
        "CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, at TEXT NOT NULL, document TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS changes (scan INTEGER, action TEXT, item_id TEXT, kind TEXT, name TEXT)"
    )
    return db


def save(state, snapshot):
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / "scan.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with open_db(state) as db:
            previous = db.execute(
                "SELECT document FROM snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
            old = (
                {i["id"]: i for i in json.loads(previous[0])["items"]}
                if previous
                else {}
            )
            new = {i["id"]: i for i in snapshot["items"]}
            # A partial scan keeps the last known entries, explicitly marked stale.
            statuses = {s["path"]: s["status"] for s in snapshot["sources"]}
            errors = [p for p, status in statuses.items() if status == "error"]

            def status_for(path):
                ancestors = [
                    p for p in statuses if path == p or path.startswith(p + "/")
                ]
                return statuses[max(ancestors, key=len)] if ancestors else None

            for key, item in old.items():
                if key not in new and any(
                    status_for(p) in (None, "error", "skipped")
                    for p in item.get("scopes", [item["source"]])
                ):
                    new[key] = dict(item, stale=True)
            snapshot["items"] = sorted(new.values(), key=lambda i: i["id"])
            changes = []
            for key in sorted(old.keys() | new.keys()):
                action = (
                    "added"
                    if key not in old
                    else "removed"
                    if key not in new
                    else "updated"
                    if old[key] != new[key]
                    else None
                )
                if action:
                    item = new.get(key, old.get(key))
                    changes.append(
                        {
                            "action": action,
                            "id": key,
                            "kind": item["kind"],
                            "name": item["name"],
                        }
                    )
            snapshot["changes"] = changes
            raw = json.dumps(snapshot, ensure_ascii=False, indent=2)
            if len(raw.encode()) > 16 * 1024 * 1024:
                raise ValueError("snapshot_too_large")
            scan = db.execute(
                "INSERT INTO snapshots(at,document) VALUES (?,?)",
                (snapshot["scanned_at"], raw),
            ).lastrowid
            db.executemany(
                "INSERT INTO changes VALUES (?,?,?,?,?)",
                [(scan, c["action"], c["id"], c["kind"], c["name"]) for c in changes],
            )
            # Keep a bounded 100-scan history.
            db.execute("DELETE FROM changes WHERE scan <= ?", (scan - 100,))
            db.execute("DELETE FROM snapshots WHERE id <= ?", (scan - 100,))
        fd, temp = tempfile.mkstemp(dir=state)
        try:
            with os.fdopen(fd, "w") as output:
                output.write(raw)
            os.replace(temp, state / "snapshot.json")
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return {
        "scanned_at": snapshot["scanned_at"],
        "total": len(new),
        "changes": len(changes),
        "errors": errors,
        "state": str(state),
    }


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(
        description="Search local AI tools without reading credentials into the index"
    )
    parser.add_argument(
        "--state", type=Path, default=Path.home() / ".local/state/ai-tool-index"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--project", type=Path, action="append", default=[])
    scan.add_argument("--no-models", action="store_true")
    find = sub.add_parser("search")
    find.add_argument("query", nargs="?", default="")
    find.add_argument(
        "--kind", choices=["application", "tool", "skill", "mcp", "plugin", "model"]
    )
    find.add_argument("--limit", type=int, default=30)
    sub.add_parser("status")
    sub.add_parser("history")
    args = parser.parse_args()
    try:
        if args.command == "scan":
            if len(args.project) > 50:
                raise ValueError("too_many_projects")
            projects = args.project
            if not projects and (args.state / "snapshot.json").exists():
                projects = [
                    Path(p)
                    for p in json.loads((args.state / "snapshot.json").read_text()).get(
                        "projects", []
                    )
                ]
            print(
                json.dumps(
                    save(
                        args.state,
                        Scanner(Path.home(), projects, not args.no_models).run(),
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if not (args.state / "snapshot.json").exists():
            raise ValueError("run_scan_first")
        snapshot = json.loads((args.state / "snapshot.json").read_text())
        if args.command == "search":
            if len(args.query) > 200 or not 1 <= args.limit <= 100:
                raise ValueError("invalid_search")
            items = [
                i
                for i in snapshot["items"]
                if (not args.kind or i["kind"] == args.kind)
                and args.query.casefold()
                in json.dumps(i, ensure_ascii=False).casefold()
            ]
            result = {
                "scanned_at": snapshot["scanned_at"],
                "total": len(items),
                "items": items[: args.limit],
            }
        elif args.command == "history":
            with open_db(args.state) as db:
                result = [
                    {"scan": s, "action": a, "kind": k, "name": n}
                    for s, a, k, n in db.execute(
                        "SELECT scan,action,kind,name FROM changes ORDER BY scan DESC, item_id LIMIT 100"
                    )
                ]
        else:
            result = {
                "scanned_at": snapshot["scanned_at"],
                "counts": {
                    k: sum(i["kind"] == k for i in snapshot["items"])
                    for k in sorted({i["kind"] for i in snapshot["items"]})
                },
                "sources": snapshot["sources"],
                "unknown": "loaded, health, last_used, calls, cost",
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
