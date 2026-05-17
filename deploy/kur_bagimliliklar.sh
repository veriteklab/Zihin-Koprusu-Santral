#!/bin/bash
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${1:-$KOK/.venv}"
REQ_FILE="${2:-$KOK/santral_gereksinimler.txt}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[santral] python3 bulunamadi" >&2
  exit 1
fi

if [ ! -f "$REQ_FILE" ]; then
  echo "[santral] gereksinim dosyasi bulunamadi: $REQ_FILE" >&2
  exit 1
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REQ_FILE"

echo "[santral] bagimliliklar hazir"
echo "  venv : $VENV_DIR"
echo "  req  : $REQ_FILE"
