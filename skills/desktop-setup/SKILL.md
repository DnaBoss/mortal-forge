---
name: desktop-setup
description: 在新電腦還原 cash 的桌面外觀、佈景主題、終端機、編輯器與輸入法設定；或把這台電腦目前的設定重新擷取進版本庫。
---

這台電腦：KDE Plasma 6.6 / Wayland，終端機 Konsole，編輯器 Kate，shell 是 zsh + oh-my-zsh（主題 arrow）+ p10k 檔，輸入法 fcitx5。

最簡單：在新電腦 clone 本倉庫後執行 `skills/desktop-setup/bootstrap.sh`（加 `-y` 則全部自動同意）。它會補裝缺的套件、oh-my-zsh 與外掛、圖示主題，預覽變動，確認後套用。

只還原設定檔（先預覽，再套用）：
1. `./apply.sh` 只列出會變動的檔案，不改任何東西。
2. `./apply.sh --apply` 套用；被覆蓋的舊檔先放到 `~/.desktop-setup-backup-時間`。
3. 登出再登入，桌面設定才會完整生效。

擷取目前設定：`./capture.sh`。範圍由 `manifest.txt` 決定，結果在 `files/`，已安裝套件清單在 `packages-apt-manual.txt`。

包含：圖示主題（icons.tar.xz，約 13MB，由 bootstrap.sh 解開）、Plasma 外觀（WhiteSur 主題、Gruvbox 配色、Kvantum、aurorae 視窗邊框、桌布、版面範本 com.cash.macos-stable）、快捷鍵、Konsole 設定檔（iTerm-Gruvbox、MesloLGS NF 13）、Kate、GTK、字型、fcitx5、zsh/p10k/vim/git 設定。

不包含：
- oh-my-zsh 本體與外掛：不放進版本庫，由 bootstrap.sh 依固定版本下載。
- 桌面面板與圖示位置（`plasma-org.kde.plasma.desktop-appletsrc`，含個人檔名）：改用版面範本還原。
- 螢幕設定（kwinoutputconfig.json、kscreen）、密碼庫、任何金鑰或權杖。
- Claude、Codex、Obsidian、Godot、Unity、Unreal 等應用程式設定。

套用 apt 套件清單前先人工檢視 `packages-apt-manual.txt`，不要整份直接安裝。
