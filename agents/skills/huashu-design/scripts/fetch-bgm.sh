#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../assets"
base="https://raw.githubusercontent.com/alchaincyf/huashu-design/master/assets"
for f in bgm-ad bgm-educational-alt bgm-educational bgm-tech bgm-tutorial-alt bgm-tutorial; do
  [ -s "$f.mp3" ] || curl -fsSL -o "$f.mp3" "$base/$f.mp3"
done
sha256sum -c bgm.sha256
