#!/bin/bash
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVIS_DIZIN="/etc/systemd/system"
KULLANICI="${SUDO_USER:-$USER}"
WORKDIR_DEFAULT="$KOK"
CONFIG_DEFAULT="$KOK/santral_ayar.json"
SERVER_URL_DEFAULT="http://127.0.0.1:8767"
DEVICE_ID_DEFAULT="j2-prime"

WORKDIR="${1:-$WORKDIR_DEFAULT}"
CONFIG="${2:-$CONFIG_DEFAULT}"
DEVICE_ID="${3:-$DEVICE_ID_DEFAULT}"
SERVER_URL="${4:-$SERVER_URL_DEFAULT}"

if [ ! -f "$WORKDIR/baslat_santral.sh" ]; then
  echo "[santral] baslat_santral.sh bulunamadi: $WORKDIR" >&2
  exit 1
fi

if [ ! -f "$CONFIG" ]; then
  echo "[santral] config bulunamadi: $CONFIG" >&2
  exit 1
fi

tmp_main="$(mktemp)"
tmp_adb="$(mktemp)"
cleanup() {
  rm -f "$tmp_main" "$tmp_adb"
}
trap cleanup EXIT

sed \
  -e "s|__USER__|$KULLANICI|g" \
  -e "s|__WORKDIR__|$WORKDIR|g" \
  "$KOK/deploy/zk-santral.service" > "$tmp_main"

sed \
  -e "s|__USER__|$KULLANICI|g" \
  -e "s|__WORKDIR__|$WORKDIR|g" \
  -e "s|__CONFIG__|$CONFIG|g" \
  -e "s|__DEVICE_ID__|$DEVICE_ID|g" \
  -e "s|__SERVER_URL__|$SERVER_URL|g" \
  "$KOK/deploy/zk-santral-adb-poller.service" > "$tmp_adb"

sudo cp "$tmp_main" "$SERVIS_DIZIN/zk-santral.service"
sudo cp "$tmp_adb" "$SERVIS_DIZIN/zk-santral-adb-poller.service"
sudo systemctl daemon-reload
sudo systemctl enable --now zk-santral.service
sudo systemctl enable --now zk-santral-adb-poller.service

echo "[santral] kuruldu"
echo "  user      : $KULLANICI"
echo "  workdir   : $WORKDIR"
echo "  config    : $CONFIG"
echo "  device_id : $DEVICE_ID"
echo "  server    : $SERVER_URL"
echo
echo "Durum komutlari:"
echo "  sudo systemctl status zk-santral.service"
echo "  sudo systemctl status zk-santral-adb-poller.service"
