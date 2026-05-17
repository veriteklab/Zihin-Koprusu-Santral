#!/bin/bash
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$KOK/santral_ayar.json"
PYTHON_BIN=""

if [ -x "$KOK/.venv/bin/python3" ]; then
  PYTHON_BIN="$KOK/.venv/bin/python3"
elif [ -x "$KOK/birader_env/bin/python3" ]; then
  PYTHON_BIN="$KOK/birader_env/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "[santral] python3 bulunamadi" >&2
  exit 1
fi

if [ ! -f "$CONFIG" ]; then
  echo "[santral] $CONFIG yok. santral_ayar.ornek.json kopyalanmali." >&2
  exit 1
fi

PYTHON_DIR="$(dirname "$PYTHON_BIN")"
export PATH="$PYTHON_DIR:$PATH"

cd "$KOK"
exec "$PYTHON_BIN" -m zihin.santral_main --config "$CONFIG" serve
