#!/usr/bin/env bash
# 固定白名單快取清理。預設只列；--apply 才執行。由每天 00:00／12:00 排程呼叫。
set -uo pipefail
apply=0
case "${1:-}" in
  "") ;;
  --apply) apply=1 ;;
  *) echo "usage: $0 [--apply]" >&2; exit 2 ;;
esac
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/disk-cleanup"
mkdir -p "$state_dir" || exit 1
exec 9>"$state_dir/lock"
flock -n 9 || { echo '已有清理執行中，本次略過'; exit 0; }
script_dir="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")" && pwd)"
run_log="$(mktemp "$state_dir/run-$(date +%Y%m%dT%H%M%S)-XXXXXX.log")" || exit 1
failed=()
used_bytes() { df -B1 --output=used / | tail -1 | tr -d ' '; }
run_step() {
  local name="$1" limit="$2"; shift 2
  echo "== $name" | tee -a "$run_log"
  if timeout --kill-after=5s "$limit" "$@" 2>&1 | tee -a "$run_log"; then
    echo "== $name: ok" | tee -a "$run_log"
  else
    failed+=("$name")
    echo "== $name: FAILED or timeout" | tee -a "$run_log"
  fi
}
before="$(used_bytes)"
if command -v docker >/dev/null 2>&1; then
  if [ "$apply" -eq 1 ]; then
    run_step docker-build-cache 120s docker builder prune --all --force --filter until=168h
  else
    run_step docker-build-cache 30s docker system df
  fi
fi
if [ "$apply" -eq 1 ]; then
  run_step regenerable-caches 600s python3 "$script_dir/disk_cache_cleanup.py" --apply
else
  run_step regenerable-caches 300s python3 "$script_dir/disk_cache_cleanup.py"
fi
# 僅沿用已明確授權的 Rust 舊副本回收，不刪共用 keeper 或未登記的工作樹。
fluke_repo="$HOME/work_space/private/Fluke"
if [ -d "$fluke_repo/.git" ]; then
  if [ "$apply" -eq 1 ]; then
    run_step rust-old-duplicates 125s python3 "$script_dir/disk_cache_cleanup.py" --rust-old-duplicates --apply
  else
    run_step rust-old-duplicates 20s python3 "$script_dir/disk_cache_cleanup.py" --rust-old-duplicates
  fi
fi
after="$(used_bytes)"
# 這是整台磁碟的淨變化，可能同時有其他程式寫入；不冒稱等於刪除檔案大小。
net_change=$((after - before))
python3 - "$state_dir/log.jsonl" "$apply" "$before" "$after" "$run_log" "${failed[@]}" <<'LOG'
import sys,json,datetime
path,apply,before,after,run_log=sys.argv[1:6]
before,after=int(before),int(after)
record={'ts':datetime.datetime.now().astimezone().isoformat(), 'apply':bool(int(apply)),
        'used_before':before, 'used_after':after, 'net_change_bytes':after-before,
        'freed_bytes':max(0,before-after), 'failed':sys.argv[6:], 'run_log':run_log}
with open(path,'a') as stream: stream.write(json.dumps(record,ensure_ascii=False)+'\n')
LOG
echo "apply=$apply failed=${#failed[@]} net_change_bytes=$net_change log=$run_log"
[ "${#failed[@]}" -eq 0 ]
