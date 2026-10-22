#!/usr/bin/env bash
# Daily read-only disk report: what is using space and what grew. Deletes nothing.
# Usage: disk-check.sh
# Writes the report to ~/.local/state/disk-check/report-latest.txt (and a dated copy),
# appends one JSON line to log.jsonl, and sends a desktop notification when the disk
# grew by GROWTH_ALERT_GIB or more since the previous run, or usage reaches USED_ALERT_PCT.
set -uo pipefail

GROWTH_ALERT_GIB="${DISK_CHECK_GROWTH_GIB:-10}"
USED_ALERT_PCT="${DISK_CHECK_USED_PCT:-80}"
BIG_DIR_GIB=5
TARGET_MIN_GIB=1
KEEP_REPORTS=30

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/disk-check"
log_file="$state_dir/log.jsonl"
report="$state_dir/report-$(date +%F).txt"
mkdir -p "$state_dir" || exit 1

exec 9>"$state_dir/lock"
flock -n 9 || { echo "another disk-check run holds the lock, skipping" >&2; exit 0; }

gib() { awk -v b="$1" 'BEGIN { printf "%.1f", b / 1073741824 }'; }

used="$(df -B1 --output=used / | tail -1 | tr -d ' ')"
pct="$(df --output=pcent / | tail -1 | tr -dc '0-9')"
prev="$(tail -1 "$log_file" 2>/dev/null | sed -n 's/.*"used_bytes":\([0-9]*\).*/\1/p')"
delta=0
[ -n "$prev" ] && delta=$((used - prev))

{
  echo "Disk report $(date '+%F %T %Z')"
  echo "used: $(gib "$used") GiB (${pct}%)   change since previous run: $(gib "$delta") GiB"
  echo
  echo "== home folders >= ${BIG_DIR_GIB} GiB =="
  du -x -BM --max-depth=1 "$HOME" 2>/dev/null | sort -rn | awk -v m="$BIG_DIR_GIB" 'NR > 1 && $1 + 0 >= m * 1024 { printf "%.1fG  %s\n", $1 / 1024, $2 }'
  echo
  echo "== ~/.cache folders >= 1 GiB =="
  du -x -BM --max-depth=1 "$HOME/.cache" 2>/dev/null | sort -rn | awk 'NR > 1 && $1 + 0 >= 1024 { printf "%.1fG  %s\n", $1 / 1024, $2 }'
  echo
  echo "== Rust target folders >= ${TARGET_MIN_GIB} GiB (size, days since last build, path) =="
  now="$(date +%s)"
  find "$HOME/work_space" "$HOME/orca" "$HOME/services" "$HOME/Documents" -xdev -type d -name target -prune 2>/dev/null |
    while read -r t; do
      [ -d "$t/debug" ] || [ -d "$t/release" ] || [ -f "$t/CACHEDIR.TAG" ] || continue
      mib="$(du -sx -BM "$t" 2>/dev/null | cut -f1 | tr -d M)"
      [ "${mib:-0}" -ge $((TARGET_MIN_GIB * 1024)) ] || continue
      size=$((mib / 1024))
      newest="$(find "$t" -maxdepth 2 -printf '%T@\n' 2>/dev/null | sort -n | tail -1)"
      echo "${size}G  $(((now - ${newest%.*}) / 86400))d  $t"
    done | sort -rn
  echo
  echo "== files >= 1 GiB written in the last 24h =="
  find "$HOME" -xdev -type f -mmin -1440 -size +1G -printf '%s\t%p\n' 2>/dev/null | sort -rn | head -20 |
    awk -F'\t' '{ printf "%.1fG  %s\n", $1 / 1073741824, $2 }'
  echo
  echo "== Docker =="
  if command -v docker >/dev/null 2>&1; then
    docker system df 2>&1
    echo "largest volumes:"
    docker system df -v --format '{{json .Volumes}}' 2>/dev/null |
      python3 -c 'import json,sys
for v in sorted(json.load(sys.stdin), key=lambda v: ("GB" in v["Size"], float(v["Size"].rstrip("kMGTB") or 0)), reverse=True)[:5]:
    print("  ", v["Size"], "links=" + str(v["Links"]), v["Name"][:48])' 2>/dev/null
  else
    echo "docker not found"
  fi
  echo
  echo "== system folders =="
  du -sh /var/cache/apt /var/crash /var/log/journal /var/lib/systemd/coredump /usr/share/ollama 2>/dev/null
} > "$report" 2>&1

cp -f "$report" "$state_dir/report-latest.txt"
ls -1t "$state_dir"/report-20*.txt 2>/dev/null | tail -n +$((KEEP_REPORTS + 1)) | while read -r old; do rm -f "$old"; done

alert=""
[ "$delta" -ge $((GROWTH_ALERT_GIB * 1073741824)) ] && alert="grew $(gib "$delta") GiB since previous run"
[ "$pct" -ge "$USED_ALERT_PCT" ] && alert="${alert:+$alert; }usage ${pct}%"

printf '{"ts":"%s","used_bytes":%s,"used_pct":%s,"delta_bytes":%s,"alert":"%s"}\n' \
  "$(date -Is)" "$used" "$pct" "$delta" "$alert" >> "$log_file"

if [ -n "$alert" ]; then
  echo "ALERT: $alert (report: $state_dir/report-latest.txt)"
  command -v notify-send >/dev/null 2>&1 &&
    notify-send -u normal "Disk check" "$alert. Report: $state_dir/report-latest.txt" || true
else
  echo "ok: used $(gib "$used") GiB (${pct}%), change $(gib "$delta") GiB (report: $state_dir/report-latest.txt)"
fi
