#!/usr/bin/env bash
set -eu
here=$(cd "$(dirname "$0")" && pwd)
yes=0
[ "${1:-}" = "-y" ] && yes=1

ask() {
  [ "$yes" = 1 ] && return 0
  read -r -p "$1 [y/N] " a
  [ "$a" = "y" ] || [ "$a" = "Y" ]
}

need=()
for c in git rsync zsh curl; do command -v "$c" >/dev/null || need+=("$c"); done
if [ "${#need[@]}" -gt 0 ]; then
  echo "缺少套件: ${need[*]}"
  if ask "用 apt 安裝它們（需要 sudo）？"; then
    sudo apt-get install -y "${need[@]}"
  else
    echo "已取消"; exit 1
  fi
fi

if [ ! -d "$HOME/.oh-my-zsh" ]; then
  git clone https://github.com/ohmyzsh/ohmyzsh.git "$HOME/.oh-my-zsh"
  git -C "$HOME/.oh-my-zsh" checkout d2b7f557cceaddb16ba89bbf8200d8a8df35c4d8
fi
custom="$HOME/.oh-my-zsh/custom/plugins"
mkdir -p "$custom"
[ -d "$custom/zsh-autosuggestions" ] || { git clone https://github.com/zsh-users/zsh-autosuggestions "$custom/zsh-autosuggestions"; git -C "$custom/zsh-autosuggestions" checkout 85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5; }
[ -d "$custom/zsh-syntax-highlighting" ] || { git clone https://github.com/zsh-users/zsh-syntax-highlighting "$custom/zsh-syntax-highlighting"; git -C "$custom/zsh-syntax-highlighting" checkout 2fc57d63067c18b1100ecdbf684fa5baf49459d1; }
[ -d "$custom/git-open" ] || git clone https://github.com/paulirish/git-open "$custom/git-open"

mkdir -p "$HOME/.local/share/icons"
for t in Gruvbox-Dark WhiteSur WhiteSur-dark WhiteSur-light WhiteSur-cursors; do
  [ -d "$HOME/.local/share/icons/$t" ] || tar -xJf "$here/icons.tar.xz" -C "$HOME/.local/share/icons" "$t"
done

"$here/apply.sh"
if ask "確認以上變動，現在套用？"; then
  "$here/apply.sh" --apply
  echo "完成。預設 shell 要換成 zsh 請執行: chsh -s \$(command -v zsh)；然後登出再登入。"
else
  echo "未套用。之後可執行 $here/apply.sh --apply"
fi
