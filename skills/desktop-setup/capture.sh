#!/usr/bin/env bash
set -eu
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$here/files"
while IFS= read -r p; do
  [ -e "$HOME/$p" ] || { echo "略過（不存在）: $p"; continue; }
  (cd "$HOME" && rsync -aL --relative --delete --exclude '*.bak*' --exclude '*.backup*' --exclude '__pycache__' "./$p" "$here/files/")
done < "$here/manifest.txt"
apt-mark showmanual 2>/dev/null | sort > "$here/packages-apt-manual.txt"
echo "已擷取到 $here/files"
