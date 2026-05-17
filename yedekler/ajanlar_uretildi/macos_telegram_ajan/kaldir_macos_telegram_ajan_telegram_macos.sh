#!/bin/bash
set -e
LABEL="com.zihinkoprusu.macos_telegram_ajan.telegram"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "[ZK] Kaldirildi: ${LABEL}"
