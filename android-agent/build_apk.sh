#!/bin/bash
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_ROOT="${ANDROID_SDK_ROOT:-/home/yabutsa06/android-sdk}"
BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$SDK_ROOT/build-tools/36.0.0}"
PLATFORM_DIR="${ANDROID_PLATFORM_DIR:-$SDK_ROOT/platforms/android-36}"
ANDROID_JAR="$PLATFORM_DIR/android.jar"

APP_DIR="$KOK/app"
MANIFEST="$APP_DIR/src/main/AndroidManifest.xml"
JAVA_DIR="$APP_DIR/src/main/java"
ASSETS_DIR="$APP_DIR/src/main/assets"
BUILD_DIR="$KOK/build"
SRC_COPY_DIR="$BUILD_DIR/src-java"
CLASSES_DIR="$BUILD_DIR/classes"
DEX_DIR="$BUILD_DIR/dex"
CLASSES_JAR="$BUILD_DIR/classes.jar"
UNSIGNED_APK="$BUILD_DIR/zk-santral-agent-unsigned.apk"
ALIGNED_APK="$BUILD_DIR/zk-santral-agent-aligned.apk"
FINAL_APK="$BUILD_DIR/zk-santral-agent-debug.apk"
KEYSTORE="$BUILD_DIR/debug.keystore"

AAPT="$BUILD_TOOLS/aapt"
D8="$BUILD_TOOLS/d8"
ZIPALIGN="$BUILD_TOOLS/zipalign"
APKSIGNER="$BUILD_TOOLS/apksigner"

for bin in "$AAPT" "$D8" "$ZIPALIGN" "$APKSIGNER" javac keytool jar; do
  if ! command -v "$bin" >/dev/null 2>&1 && [ ! -x "$bin" ]; then
    echo "[android-agent] eksik arac: $bin" >&2
    exit 1
  fi
done

if [ ! -f "$ANDROID_JAR" ]; then
  echo "[android-agent] android.jar bulunamadi: $ANDROID_JAR" >&2
  exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$CLASSES_DIR" "$DEX_DIR" "$SRC_COPY_DIR"

cp -R "$JAVA_DIR"/. "$SRC_COPY_DIR"/

SERVER_URL="${ZK_SERVER_URL:-http://127.0.0.1:8767}"
TOKEN="${ZK_TOKEN:-degistir-beni-uzun-rastgele-token}"
DEVICE_ID="${ZK_DEVICE_ID:-j2-prime-agent}"

AGENT_CONFIG="$SRC_COPY_DIR/com/zihinkoprusu/santral/agent/AgentConfig.java"
sed -i \
  -e "s|__SERVER_URL__|$SERVER_URL|g" \
  -e "s|__TOKEN__|$TOKEN|g" \
  -e "s|__DEVICE_ID__|$DEVICE_ID|g" \
  "$AGENT_CONFIG"

mapfile -t KAYNAKLAR < <(find "$SRC_COPY_DIR" -name "*.java" | sort)
if [ "${#KAYNAKLAR[@]}" -eq 0 ]; then
  echo "[android-agent] Java kaynak dosyasi bulunamadi" >&2
  exit 1
fi

javac \
  -source 8 \
  -target 8 \
  -encoding UTF-8 \
  -classpath "$ANDROID_JAR" \
  -d "$CLASSES_DIR" \
  "${KAYNAKLAR[@]}"

jar --create --file "$CLASSES_JAR" -C "$CLASSES_DIR" .

"$D8" \
  --lib "$ANDROID_JAR" \
  --min-api 23 \
  --output "$DEX_DIR" \
  "$CLASSES_JAR"

"$AAPT" package \
  -f \
  -M "$MANIFEST" \
  -I "$ANDROID_JAR" \
  -A "$ASSETS_DIR" \
  -F "$UNSIGNED_APK"

(cd "$DEX_DIR" && "$AAPT" add "$UNSIGNED_APK" classes.dex)

"$ZIPALIGN" -f 4 "$UNSIGNED_APK" "$ALIGNED_APK"

if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair \
    -keystore "$KEYSTORE" \
    -storepass android \
    -keypass android \
    -alias androiddebugkey \
    -dname "CN=Android Debug,O=Android,C=US" \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000
fi

"$APKSIGNER" sign \
  --ks "$KEYSTORE" \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out "$FINAL_APK" \
  "$ALIGNED_APK"

echo "$FINAL_APK"
