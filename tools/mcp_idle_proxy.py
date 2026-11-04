#!/usr/bin/env python3
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time

REPLAY_ID = "__idle_proxy_init__"


class Proxy:
    def __init__(self, command, idle_seconds):
        self.command = command
        self.idle_seconds = idle_seconds
        self.child = None
        self.lock = threading.RLock()
        self.last = time.monotonic()
        self.inflight = set()
        self.init_line = None
        self.initialized_line = None
        self.discard_replay = False

    def spawn(self):
        self.child = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            start_new_session=True, bufsize=0,
        )
        threading.Thread(target=self.pump, args=(self.child,), daemon=True).start()

    def kill(self):
        child, self.child = self.child, None
        if child is None:
            return
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.inflight.clear()

    def send(self, line):
        self.child.stdin.write(line if line.endswith(b"\n") else line + b"\n")
        self.child.stdin.flush()

    def ensure_child(self):
        if self.child is not None and self.child.poll() is None:
            return
        self.spawn()
        if self.init_line is not None:
            replay = json.loads(self.init_line)
            replay["id"] = REPLAY_ID
            self.send(json.dumps(replay).encode())
            if self.initialized_line is not None:
                self.send(self.initialized_line)

    def pump(self, child):
        for line in child.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                msg = {}
            if msg.get("id") == REPLAY_ID:
                continue
            with self.lock:
                self.last = time.monotonic()
                self.inflight.discard(json.dumps(msg.get("id")))
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()

    def watch(self):
        while True:
            time.sleep(min(5, max(0.2, self.idle_seconds / 4)))
            with self.lock:
                if self.child is None or self.inflight:
                    continue
                if time.monotonic() - self.last >= self.idle_seconds:
                    self.kill()

    def run(self):
        self.spawn()
        threading.Thread(target=self.watch, daemon=True).start()
        for line in sys.stdin.buffer:
            try:
                msg = json.loads(line)
            except ValueError:
                msg = {}
            with self.lock:
                self.last = time.monotonic()
                if msg.get("method") == "initialize":
                    self.init_line = line
                elif msg.get("method") == "notifications/initialized":
                    self.initialized_line = line
                self.ensure_child()
                if "id" in msg and "method" in msg:
                    self.inflight.add(json.dumps(msg["id"]))
                self.send(line)
        with self.lock:
            self.kill()


def main():
    ap = argparse.ArgumentParser(description="MCP 閒置代理：閒置超時就關掉真正的 MCP 程式，下次請求再自動重開")
    ap.add_argument("--idle-seconds", type=float, default=900)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        ap.error("缺少要代理的 MCP 指令")
    Proxy(command, args.idle_seconds).run()


if __name__ == "__main__":
    sys.exit(main())
