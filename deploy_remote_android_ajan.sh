#!/bin/bash
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UZAK_HOST="${1:-192.168.1.43}"
SUNUCU_URL="${2:-http://127.0.0.1:8767}"
TOKEN="${3:-zk-santral-yerel-test}"
CIHAZ_ID="${4:-j2-prime}"
SUNUCU_HOST="$(echo "$SUNUCU_URL" | sed -E 's#^https?://([^/:]+).*$#\1#')"
SUNUCU_PORT="$(echo "$SUNUCU_URL" | sed -E 's#^https?://[^/:]+:([0-9]+).*$#\1#; t; s#.*#80#')"

TMP_REMOTE="/tmp/zkpush"

A="$(base64 -w0 "$KOK/android/zk_santral_android_ajan.sh")"
W="$(base64 -w0 "$KOK/android/zk_santral_android_ajan_wrapper.sh")"

ssh "$UZAK_HOST" bash <<EOF
set -euo pipefail
mkdir -p "$TMP_REMOTE"
printf '%s' '$A' | base64 -d > "$TMP_REMOTE/zk_santral_android_ajan.sh"
printf '%s' '$W' | base64 -d > "$TMP_REMOTE/zk_santral_android_ajan_wrapper.sh"
cat > "$TMP_REMOTE/agent.env" <<CFG
SUNUCU_URL="$SUNUCU_URL"
SUNUCU_HOST="$SUNUCU_HOST"
SUNUCU_PORT="$SUNUCU_PORT"
ERISIM_TOKENI="$TOKEN"
CIHAZ_ID="$CIHAZ_ID"
AUTO_ANSWER="1"
POLL_SEC="1"
CFG
adb push "$TMP_REMOTE/zk_santral_android_ajan.sh" /data/local/tmp/zk_santral_android_ajan.sh >/dev/null
adb push "$TMP_REMOTE/zk_santral_android_ajan_wrapper.sh" /data/local/tmp/zk_santral_android_ajan_wrapper.sh >/dev/null
adb push "$TMP_REMOTE/agent.env" /data/local/tmp/zk_santral_agent.env >/dev/null
adb reverse tcp:8767 tcp:8767 >/dev/null 2>&1 || true
adb shell su -c 'chmod 755 /data/local/tmp/zk_santral_android_ajan.sh /data/local/tmp/zk_santral_android_ajan_wrapper.sh'
EOF

echo "Uzak ajan dagitimi tamamlandi: $UZAK_HOST"
echo "Tek seferlik test:"
echo "ssh $UZAK_HOST \"adb shell su -c 'TEK_SEFERLIK_TEST=1 sh /data/local/tmp/zk_santral_android_ajan_wrapper.sh'\""
