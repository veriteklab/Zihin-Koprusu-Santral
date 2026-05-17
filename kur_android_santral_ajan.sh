#!/bin/bash
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUNUCU_URL="${1:-http://127.0.0.1:8767}"
TOKEN="${2:-degistir-beni-uzun-rastgele-token}"
CIHAZ_ID="${3:-j2-prime}"
UZAK_DIZIN="/data/local/tmp"
SUNUCU_HOST="$(echo "$SUNUCU_URL" | sed -E 's#^https?://([^/:]+).*$#\1#')"
SUNUCU_PORT="$(echo "$SUNUCU_URL" | sed -E 's#^https?://[^/:]+:([0-9]+).*$#\1#; t; s#.*#80#')"

adb wait-for-device
adb reverse tcp:8767 tcp:8767 >/dev/null 2>&1 || true
adb shell su -c "mkdir -p $UZAK_DIZIN"
adb push "$KOK/android/zk_santral_android_ajan.sh" "$UZAK_DIZIN/zk_santral_android_ajan.sh" >/dev/null
adb push "$KOK/android/zk_santral_android_ajan_wrapper.sh" "$UZAK_DIZIN/zk_santral_android_ajan_wrapper.sh" >/dev/null

cat > /tmp/zk_santral_agent.env <<EOF
SUNUCU_URL="$SUNUCU_URL"
SUNUCU_HOST="$SUNUCU_HOST"
SUNUCU_PORT="$SUNUCU_PORT"
ERISIM_TOKENI="$TOKEN"
CIHAZ_ID="$CIHAZ_ID"
AUTO_ANSWER="1"
POLL_SEC="1"
EOF
adb push /tmp/zk_santral_agent.env "$UZAK_DIZIN/zk_santral_agent.env" >/dev/null
rm -f /tmp/zk_santral_agent.env

adb shell su -c "chmod 755 $UZAK_DIZIN/zk_santral_android_ajan.sh $UZAK_DIZIN/zk_santral_android_ajan_wrapper.sh"
echo "Kuruldu: $UZAK_DIZIN"
echo "Test icin:"
echo "adb shell su -c 'TEK_SEFERLIK_TEST=1 sh $UZAK_DIZIN/zk_santral_android_ajan_wrapper.sh'"
echo "Surekli calistirmak icin:"
echo "adb shell su -c 'nohup sh $UZAK_DIZIN/zk_santral_android_ajan_wrapper.sh >/data/local/tmp/zk_santral_agent.log 2>&1 &'"
