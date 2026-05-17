#!/system/bin/sh
#
# Zihin Koprusu Santral Android ajan iskeleti
# Rootlu cihazlarda gelen cagrilari izleyip PC'deki santral sunucusuna yollar.
# Termux veya adb shell icinden calistirilabilir.
#

SUNUCU_URL="${SUNUCU_URL:-http://192.168.1.43:8767}"
SUNUCU_HOST="${SUNUCU_HOST:-192.168.1.43}"
SUNUCU_PORT="${SUNUCU_PORT:-8767}"
ERISIM_TOKENI="${ERISIM_TOKENI:-degistir-beni}"
CIHAZ_ID="${CIHAZ_ID:-android-santral}"
DURUM_DOSYASI="${DURUM_DOSYASI:-/data/local/tmp/zk_santral_state}"
POLL_SEC="${POLL_SEC:-1}"
AUTO_ANSWER="${AUTO_ANSWER:-1}"
TEK_SEFERLIK_TEST="${TEK_SEFERLIK_TEST:-0}"

sunucu_host_port() {
  if [ -n "$SUNUCU_HOST" ] && [ -n "$SUNUCU_PORT" ]; then
    echo "${SUNUCU_HOST}:${SUNUCU_PORT}"
    return 0
  fi
  echo "$SUNUCU_URL" | sed -E 's#^https?://([^/]+).*$#\1#'
}

sunucu_host() {
  sunucu_host_port | cut -d: -f1
}

sunucu_port() {
  hp="$(sunucu_host_port)"
  if echo "$hp" | grep -q ':'; then
    echo "$hp" | cut -d: -f2
  else
    echo "80"
  fi
}

json_post() {
  payload="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS -H "Content-Type: application/json" \
      -d "$payload" \
      "$SUNUCU_URL/api/v1/events" >/dev/null
    return $?
  fi

  body_len=$(echo -n "$payload" | wc -c | tr -d ' ')
  req=$(cat <<EOF
POST /api/v1/events HTTP/1.1
Host: $(sunucu_host_port)
Content-Type: application/json
Content-Length: $body_len
Connection: close

$payload
EOF
)
  echo "$req" | toybox nc -w 10 "$(sunucu_host)" "$(sunucu_port)" >/dev/null
}

mevcut_numara() {
  dumpsys telephony.registry 2>/dev/null | grep -m1 "mCallIncomingNumber" | sed 's/.*=//'
}

mevcut_durum() {
  dumpsys telephony.registry 2>/dev/null | grep -m1 "mCallState=" | sed 's/.*=//'
}

otomatik_cevapla() {
  [ "$AUTO_ANSWER" = "1" ] || return 0
  input keyevent KEYCODE_HEADSETHOOK >/dev/null 2>&1 || true
}

hangup() {
  input keyevent KEYCODE_ENDCALL >/dev/null 2>&1 || true
}

olay_gonder() {
  event_type="$1"
  phone_number="$2"
  state="$3"
  call_id="$4"
  payload=$(cat <<EOF
{"token":"$ERISIM_TOKENI","device_id":"$CIHAZ_ID","event_type":"$event_type","phone_number":"$phone_number","state":"$state","call_id":"$call_id"}
EOF
)
  json_post "$payload"
}

tek_seferlik_test() {
  call_id="test-$(date +%s)"
  olay_gonder "healthcheck" "" "idle" "$call_id"
  exit $?
}

if [ "$TEK_SEFERLIK_TEST" = "1" ]; then
  tek_seferlik_test
fi

echo "idle|" > "$DURUM_DOSYASI"

while true; do
  durum="$(mevcut_durum)"
  numara="$(mevcut_numara)"
  onceki="$(cat "$DURUM_DOSYASI" 2>/dev/null || echo "idle|")"
  onceki_durum="$(echo "$onceki" | cut -d'|' -f1)"
  onceki_call_id="$(echo "$onceki" | cut -d'|' -f2)"

  if [ "$durum" = "1" ] && [ "$onceki_durum" != "1" ]; then
    call_id="$(date +%s)"
    echo "1|$call_id" > "$DURUM_DOSYASI"
    olay_gonder "incoming" "$numara" "ringing" "$call_id"
    otomatik_cevapla
  elif [ "$durum" = "2" ] && [ "$onceki_durum" != "2" ]; then
    call_id="${onceki_call_id:-$(date +%s)}"
    echo "2|$call_id" > "$DURUM_DOSYASI"
    olay_gonder "answered" "$numara" "active" "$call_id"
  elif [ "$durum" = "0" ] && [ "$onceki_durum" != "0" ]; then
    call_id="${onceki_call_id:-$(date +%s)}"
    echo "0|" > "$DURUM_DOSYASI"
    olay_gonder "hangup" "$numara" "idle" "$call_id"
  fi
  sleep "$POLL_SEC"
done
