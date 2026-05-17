#!/system/bin/sh
#
# Ajan wrapper: kalici ortam degiskenleri ile calistirmak icin.
#

BASE="/data/local/tmp"
SCRIPT="$BASE/zk_santral_android_ajan.sh"
CFG="$BASE/zk_santral_agent.env"

if [ -f "$CFG" ]; then
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    case "$line" in
      \#*) continue ;;
    esac
    eval "export $line"
  done < "$CFG"
fi

exec sh "$SCRIPT"
