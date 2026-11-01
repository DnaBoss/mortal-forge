export ZSH="$HOME/.oh-my-zsh"

if [[ -r "$HOME/.shell_path" ]]; then
  source "$HOME/.shell_path"
fi

ZSH_THEME="arrow"
DEFAULT_USER="cash"

plugins=(
  git
  git-open
  zsh-autosuggestions
  zsh-syntax-highlighting
)

ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=240'

HISTFILE="$HOME/.zsh_history"
HISTSIZE=10000
SAVEHIST=10000
setopt append_history
setopt share_history
setopt hist_ignore_dups
setopt hist_ignore_space
setopt inc_append_history

autoload -Uz compinit
compinit
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'

alias ll='ls -lah'
alias la='ls -A'
alias ..='cd ..'
alias ...='cd ../..'
alias reload-zsh='source ~/.zshrc'

source "$ZSH/oh-my-zsh.sh"

theme-gallery() {
  "$ZSH/tools/theme_chooser.sh" -s | ${PAGER:-less} -R
}

theme-preview() {
  if [[ -z "$1" ]]; then
    echo "Usage: theme-preview <theme-name>"
    return 1
  fi
  "$ZSH/tools/theme_chooser.sh" "$1"
}

theme-use() {
  if [[ -z "$1" ]]; then
    echo "Usage: theme-use <theme-name>"
    return 1
  fi
  local theme_file
  if [[ -f "$ZSH/themes/$1.zsh-theme" || -f "$ZSH/custom/themes/$1.zsh-theme" ]]; then
    perl -0pi -e 's/^ZSH_THEME="[^"]*"/ZSH_THEME="'$1'"/m' "$HOME/.zshrc"
    echo "Using theme: $1"
    source "$HOME/.zshrc"
  else
    echo "Theme not found: $1"
    return 1
  fi
}

theme-pick() {
  local selected
  selected=$(
    {
      find "$ZSH/themes" "$ZSH/custom/themes" -maxdepth 1 -name '*.zsh-theme' -type f 2>/dev/null
    } | sed 's#.*/##; s#\.zsh-theme$##' | sort -u |
      fzf --height=80% --border --prompt='theme > ' \
        --preview="$ZSH/tools/theme_chooser.sh {}" \
        --preview-window=right:65%:wrap
  )
  [[ -n "$selected" ]] && theme-use "$selected"
}

# Google Cloud CLI: add gcloud/bq/gsutil to PATH and enable completion.
if [ -f '/Users/cash/google-cloud-sdk/path.zsh.inc' ]; then . '/Users/cash/google-cloud-sdk/path.zsh.inc'; fi
if [ -f '/Users/cash/google-cloud-sdk/completion.zsh.inc' ]; then . '/Users/cash/google-cloud-sdk/completion.zsh.inc'; fi

# Hermes Agent — ensure ~/.local/bin is on PATH
export PATH="$HOME/.local/bin:$PATH"

# PostgreSQL client — use native psql against Docker-exposed ports such as localhost:55432.
export PATH="/opt/homebrew/opt/libpq/bin:$PATH"

# npm global bin (hermes-managed node) — makes globally-installed CLIs like ccusage available
export PATH="$HOME/.hermes/node/bin:$PATH"

# ccusage — monitor Claude Code token / cost usage
alias ccu='ccusage'                     # 今日用量（每日報表，預設）
alias ccu-live='ccusage blocks --live'  # 即時儀表板（5 小時 block 燃燒率）
alias ccu-day='ccusage daily'           # 每日明細
alias ccu-week='ccusage weekly'         # 每週彙總
alias ccu-month='ccusage monthly'       # 每月彙總
alias ccu-session='ccusage session'     # 依對話 session 分組

# claude-view — 完整網頁儀表板（http://localhost:47892）
export CLAUDE_VIEW_TELEMETRY=0          # 關閉匿名遙測（隱私），要開啟改成 1
alias cv='claude-view'                   # 啟動 mission control 儀表板

# hawk-staging 快速 SSH（AI ops 機）
alias hawk='ssh hawk-staging'                    # 直接進機器
alias hawk-ai='ssh -t hawk-staging claude'       # 進機器並直接開機器上的 Claude

# >>> Codex installer >>>
export PATH="/home/cash/.local/bin:$PATH"
# <<< Codex installer <<<

# Agent Pool Gateway — Claude Code routes through the local Gateway.
# export ANTHROPIC_BASE_URL="http://127.0.0.1:18080"

# Enter the Gateway key with `aigw` when starting a Gateway session.
aigw() {
  # export ANTHROPIC_BASE_URL="http://127.0.0.1:18080"
  unset ANTHROPIC_API_KEY
  read -rs 'ANTHROPIC_AUTH_TOKEN?Gateway key: '
  echo
  export ANTHROPIC_AUTH_TOKEN
}
