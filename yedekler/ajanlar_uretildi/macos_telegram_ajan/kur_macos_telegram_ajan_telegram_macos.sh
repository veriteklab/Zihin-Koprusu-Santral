#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_DOSYA="${SCRIPT_DIR}/zk_macos_telegram_ajan_telegram.py"
LABEL="com.zihinkoprusu.macos_telegram_ajan.telegram"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/ZihinKoprusu"
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
python3 --version >/dev/null 2>&1 || { echo "[HATA] Python 3 gerekli."; exit 1; }
python3 -m pip install --user --upgrade telethon
chmod +x "$PY_DOSYA"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>${PY_DOSYA}</string>
  </array>
  <key>WorkingDirectory</key><string>${SCRIPT_DIR}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${LOG_DIR}/macos_telegram_ajan-telegram.out.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/macos_telegram_ajan-telegram.err.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/${LABEL}"
echo "[ZK] macOS Telegram ajan kuruldu: ${LABEL}"
echo "[ZK] Log: ${LOG_DIR}/macos_telegram_ajan-telegram.out.log"
