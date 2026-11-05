#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tidy_any

LINUX = sys.platform.startswith("linux")
HOME = Path.home()
STATE = HOME / ".local/state/idle-agents"
LOG = STATE / "log.jsonl"
HANDOFFS = STATE / "handoffs"
START_TOLERANCE_SECONDS = 300
IGNORED_CHILDREN = (r"conhost(\.exe)?",)
SKIP_PREFIXES = ("<", "# AGENTS.md", "Caveat:")


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def is_agent(pid, name, procs):
    cmd = procs.get(pid, {}).get("cmd", "")
    return re.search(rf"(?:^|[\\/\s\"']){name}(?:\.exe)?(?:[\"'\s]|$)", cmd, re.I) is not None


def cmdline(pid, procs):
    return procs.get(pid, {}).get("cmd", "")


def rss_mb(pid):
    if LINUX:
        for line in read(f"/proc/{pid}/status").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) // 1024
        return 0
    if tidy_any.WINDOWS:
        return 0
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) // 1024 if out.isdigit() else 0


def ancestors(procs):
    return tidy_any.ancestors(os.getpid(), procs)


def claude_sessions(procs):
    found = []
    for meta in glob.glob(str(HOME / ".claude/sessions/*.json")):
        try:
            info = json.loads(read(meta))
        except ValueError:
            continue
        pid = info.get("pid")
        if not pid or not is_agent(pid, "claude", procs) or info.get("kind") != "interactive":
            continue
        if info.get("status") != "idle":
            continue
        cwd = info.get("cwd", "")
        slug = re.sub(r"[^A-Za-z0-9]", "-", cwd)
        transcript = HOME / ".claude/projects" / slug / f"{info['sessionId']}.jsonl"
        found.append({
            "tool": "claude", "pid": pid, "cwd": cwd, "session": info["sessionId"],
            "transcript": transcript, "last_active": info["updatedAt"] / 1000,
            "proc_start": info.get("procStart"), "started_at": info.get("startedAt"),
        })
    return found


def codex_rollout(pid):
    if LINUX:
        try:
            targets = [os.readlink(f"/proc/{pid}/fd/{fd}") for fd in os.listdir(f"/proc/{pid}/fd")]
        except OSError:
            return None
    elif tidy_any.WINDOWS:
        return None
    else:
        out = subprocess.run(["lsof", "-p", str(pid), "-Fn"], capture_output=True, text=True).stdout
        targets = [line[1:] for line in out.splitlines() if line.startswith("n/")]
    found = [Path(t) for t in targets if "/sessions/" in t and os.path.basename(t).startswith("rollout-")]
    return found[-1] if found else None


def rollout_cwd(rollout):
    try:
        first = json.loads(rollout.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except (OSError, ValueError, IndexError):
        return ""
    return first.get("payload", {}).get("cwd", "")


def codex_sessions(procs):
    found = []
    for pid in procs:
        if not is_agent(pid, "codex", procs) or "app-server" in cmdline(pid, procs):
            continue
        rollout = codex_rollout(pid)
        if rollout is None or not rollout.exists():
            continue
        found.append({
            "tool": "codex", "pid": pid, "cwd": rollout_cwd(rollout), "session": rollout.stem,
            "transcript": rollout, "last_active": rollout.stat().st_mtime,
        })
    return found


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in ("text", "input_text", "output_text"))


def transcript_messages(path):
    users, assistants = [], []
    for line in read(path).splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("isSidechain"):
            continue
        if obj.get("type") in ("user", "assistant"):
            role, message = obj["type"], obj.get("message", {})
        elif obj.get("type") == "response_item" and obj.get("payload", {}).get("type") == "message":
            message = obj["payload"]
            role = message.get("role")
        else:
            continue
        text = text_of(message.get("content", "")).strip()
        if not text:
            continue
        if role == "user" and not text.startswith(SKIP_PREFIXES):
            users.append(text)
        elif role == "assistant":
            assistants.append(text)
    return users, assistants


def git_state(cwd):
    def run(*args):
        try:
            out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    branch = run("branch", "--show-current")
    if branch is None:
        return None
    return {"branch": branch, "dirty": (run("status", "--short") or "").splitlines()}


def clip(text, limit):
    return text if len(text) <= limit else text[:limit] + "…"


def write_handoff(session, now):
    users, assistants = transcript_messages(session["transcript"])
    git = git_state(session["cwd"]) if session["cwd"] else None
    idle_h = (now - session["last_active"]) / 3600
    lines = [
        f"# 收尾記錄：{session['tool']} {session['session']}",
        "",
        f"- 產生時間：{datetime.fromtimestamp(now):%Y-%m-%d %H:%M:%S}",
        f"- 目錄：{session['cwd']}",
        f"- 最後活動：{datetime.fromtimestamp(session['last_active']):%Y-%m-%d %H:%M:%S}（閒置 {idle_h:.1f} 小時）",
        f"- 對話檔：{session['transcript']}",
        f"- 還原指令：{'claude --resume ' + session['session'] if session['tool'] == 'claude' else 'codex resume ' + session['session'].split('-')[-1]}",
        "",
        "## 原本的任務",
        clip(users[0], 1500) if users else "（讀不到使用者訊息）",
        "",
        "## 最近的使用者指示",
    ]
    lines += [f"- {clip(u, 400)}" for u in users[-5:]] or ["（無）"]
    lines += ["", "## 最後一則 AI 回覆", clip(assistants[-1], 2000) if assistants else "（無）", "", "## 程式碼狀態"]
    if git is None:
        lines.append("不是 git 目錄或讀不到。")
    else:
        lines.append(f"- 分支：{git['branch'] or '（分離 HEAD）'}")
        if git["dirty"]:
            lines.append(f"- 未提交的修改 {len(git['dirty'])} 項（關閉不會刪檔，但記得處理）：")
            lines += [f"  - `{d}`" for d in git["dirty"][:30]]
        else:
            lines.append("- 沒有未提交的修改")
    HANDOFFS.mkdir(parents=True, exist_ok=True)
    out = HANDOFFS / f"{datetime.fromtimestamp(now):%Y%m%d-%H%M%S}-{session['tool']}-{session['pid']}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def linux_start_ticks(pid):
    fields = read(f"/proc/{pid}/stat").rsplit(")", 1)[-1].split()
    return fields[19] if len(fields) > 19 else None


def same_instance(session, procs, now):
    proc = procs.get(session["pid"])
    if proc is None:
        return False
    if LINUX and session.get("proc_start"):
        return linux_start_ticks(session["pid"]) == str(session["proc_start"])
    if session.get("started_at"):
        return abs((now - proc["age"]) - session["started_at"] / 1000) <= START_TOLERANCE_SECONDS
    return True


def busy_children(pid, procs):
    kids = [k for k in tidy_any.descendants(pid, procs) if k != pid]
    covered = set()
    for k in kids:
        if tidy_any.matches(tidy_any.MCP_PATTERNS, cmdline(k, procs)):
            covered.update(tidy_any.descendants(k, procs))
    return [k for k in kids if k not in covered and not tidy_any.matches(IGNORED_CHILDREN, cmdline(k, procs))]


def stop(pid, procs):
    if tidy_any.WINDOWS:
        return subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True).returncode == 0
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        time.sleep(0.5)
        if not is_agent(pid, "claude", tidy_any.list_procs()) and not is_agent(pid, "codex", tidy_any.list_procs()):
            return True
    return False


def meminfo_gb():
    out = {}
    for line in read("/proc/meminfo").splitlines():
        key, value = line.split(":", 1)
        out[key] = int(value.split()[0]) / 1048576
    return out


def memory_report():
    if not LINUX:
        print("記憶體拆解報告僅支援 Linux")
        return
    m = meminfo_gb()
    used = m["MemTotal"] - m["MemFree"] - m["Buffers"] - m["Cached"] - m["SReclaimable"]
    parts = {
        "程式實際佔用": m["AnonPages"],
        "核心不可回收": m["SUnreclaim"] + m["PageTables"] + m["KernelStack"],
    }
    mm = read("/sys/block/zram0/mm_stat").split()
    if mm:
        parts["zram 壓縮區"] = int(mm[2]) / 2**30
    for gtt in glob.glob("/sys/class/drm/card*/device/mem_info_gtt_used"):
        parts["GPU 共用記憶體"] = parts.get("GPU 共用記憶體", 0) + int(read(gtt)) / 2**30
    print(f"已用 {used:.1f}G／總量 {m['MemTotal']:.0f}G；快取 {m['Buffers'] + m['Cached'] + m['SReclaimable']:.0f}G（可回收，不算佔用）")
    for name, value in parts.items():
        print(f"  {name} {value:.1f}G")
    print(f"  其他未對帳 {used - sum(parts.values()):.1f}G")
    totals = {}
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            name = read(f"/proc/{entry}/comm").strip()
            totals[name] = totals.get(name, 0) + rss_mb(entry)
    print("程式別合計（前 8）：")
    for name, mb in sorted(totals.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {mb}MB {name}")


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="找出閒置的 claude／codex，寫收尾記錄後關閉；預設只預覽")
    ap.add_argument("--min-idle-hours", type=float, default=4)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true", help="只印記憶體用量拆解")
    args = ap.parse_args()
    if args.report:
        memory_report()
        return 0

    now = time.time()
    procs = tidy_any.list_procs()
    skip = ancestors(procs)
    sessions = [s for s in claude_sessions(procs) + codex_sessions(procs) if s["pid"] not in skip]
    rows = []
    for s in sorted(sessions, key=lambda s: s["last_active"]):
        idle_h = (now - s["last_active"]) / 3600
        row = {"tool": s["tool"], "pid": s["pid"], "cwd": s["cwd"], "idle_hours": round(idle_h, 1), "rss_mb": rss_mb(s["pid"])}
        if idle_h < args.min_idle_hours:
            row["action"] = "keep"
        elif not same_instance(s, tidy_any.list_procs(), now):
            row["action"] = "kept_pid_changed"
        elif busy := busy_children(s["pid"], procs):
            row["action"] = "kept_busy_children"
            row["children"] = [cmdline(k, procs)[:80] for k in busy[:3]]
        elif not args.apply:
            row["action"] = "would_close"
        else:
            try:
                row["handoff"] = str(write_handoff(s, now))
                row["action"] = "closed" if stop(s["pid"], procs) else "close_failed"
            except OSError as exc:
                row["action"] = "kept_handoff_failed"
                row["error"] = str(exc)
        rows.append(row)
        print(f"{row['action']:<20} {s['tool']:<6} pid={s['pid']:<8} idle={row['idle_hours']:>6}h rss={row['rss_mb']}MB {s['cwd']}")
        for child in row.get("children", []):
            print(f"{'':<20} running: {child}")
    if args.apply:
        STATE.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": now, "rows": rows}, ensure_ascii=False) + "\n")
    print(f"共 {len(rows)} 個，閒置超過 {args.min_idle_hours} 小時：{sum(r['action'] in ('would_close', 'closed', 'close_failed') for r in rows)} 個可關閉")


if __name__ == "__main__":
    sys.exit(main())
