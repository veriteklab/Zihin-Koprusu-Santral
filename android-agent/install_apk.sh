#!/bin/bash
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APK="${1:-$KOK/build/zk-santral-agent-debug.apk}"
ADB_BIN="${ADB_BIN:-adb}"

if [ ! -f "$APK" ]; then
  echo "[android-agent] apk bulunamadi: $APK" >&2
  exit 1
fi

"$ADB_BIN" install -r "$APK"
echo "[android-agent] kuruldu: $APK"
