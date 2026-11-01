#!/usr/bin/env bash
set -eu
here=$(cd "$(dirname "$0")" && pwd)
mode=${1:-}
stamp=$(date +%Y%m%d-%H%M%S)
backup="$HOME/.desktop-setup-backup-$stamp"
flags=(-a --itemize-changes --backup --backup-dir="$backup")
if [ "$mode" != "--apply" ]; then
  flags+=(--dry-run)
  echo "預覽模式：不會改任何檔案。確認後加 --apply 執行。"
fi
[ -d "$here/files" ] || { echo "找不到 files/，請先跑 capture.sh"; exit 1; }
rsync "${flags[@]}" "$here/files/" "$HOME/"
if [ "$mode" = "--apply" ]; then
  fc-cache -f >/dev/null 2>&1 || true
  echo "已套用。被覆蓋的舊檔在 $backup。請登出再登入，讓桌面設定生效。"
fi
