#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS=("$HOME/.claude/skills" "$HOME/.codex/skills")
linked=0
kept=0
skipped=0

for target in "${TARGETS[@]}"; do
  mkdir -p "$target"
  for dir in "$SRC"/skills/*/; do
    name="$(basename "$dir")"
    if [ ! -f "$dir/SKILL.md" ] || [ -L "${dir%/}" ]; then
      skipped=$((skipped + 1))
      continue
    fi
    if [ -e "$target/$name" ] || [ -L "$target/$name" ]; then
      kept=$((kept + 1))
    else
      ln -s "${dir%/}" "$target/$name"
      linked=$((linked + 1))
    fi
  done
done

mkdir -p "$HOME/.claude"
if [ ! -e "$HOME/.claude/CLAUDE.md" ]; then
  printf '@%s/RULES.md\n' "$SRC" > "$HOME/.claude/CLAUDE.md"
  echo "已建立 ~/.claude/CLAUDE.md，指向 $SRC/RULES.md"
else
  echo "~/.claude/CLAUDE.md 已存在，未改動；請自行確認有引用 $SRC/RULES.md"
fi

echo "新連結 $linked 個、已存在 $kept 個、略過 $skipped 個（指向其他倉庫的連結或沒有 SKILL.md）"

if command -v ai-tool-index >/dev/null 2>&1; then
  ai-tool-index scan
else
  echo "找不到 ai-tool-index；略過掃描。索引工具在倉庫外，請另行安裝。"
fi
