#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Zihin Köprüsü v7.0 – Başlatıcı
# ./baslat.sh            → Tam mod (ses + GUI)
# ./baslat.sh --ses      → Sadece ses
# ./baslat.sh --gui      → Sadece GUI
# ./baslat.sh --tani     → Kurulum/dosya teşhisi
# ─────────────────────────────────────────────────────────────

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Konum kontrolü: zihin/ içinden çalıştırıldıysa otomatik düzelt ──────────
if [ "$(basename "$KOK")" = "zihin" ]; then
    echo -e "\033[1;33m[!]\033[0m baslat.sh zihin/ içinden çalıştırıldı, proje köküne geçiliyor..."
    KOK="$(dirname "$KOK")"
    exec "$KOK/baslat.sh" "$@"
fi

# ── zihin/ paketi burada mı? ────────────────────────────────────────────────
if [ ! -f "$KOK/zihin/__init__.py" ]; then
    echo -e "\033[0;31m[✗]\033[0m zihin/ paketi bulunamadı."
    echo "    Doğru kullanım: cd ~/Zihin_Koprusu && ./baslat.sh"
    exit 1
fi

VENV="$KOK/birader_env/bin/activate"
LOG_DIR="$KOK/loglar"
LOG="$LOG_DIR/sistem.log"
MOD="${1:-}"
PID_FILE="$KOK/.zihin.pid"

if [ "$MOD" = "--tani" ]; then
    if [ -x "$KOK/birader_env/bin/python" ]; then
        "$KOK/birader_env/bin/python" "$KOK/tani.py"
    else
        python3 "$KOK/tani.py"
    fi
    exit $?
fi

MAVI='\033[0;36m'; YESIL='\033[0;32m'; SARI='\033[1;33m'
KIRMIZI='\033[0;31m'; SIFIR='\033[0m'

cikti()  { echo -e "${MAVI}[ZK]${SIFIR} $1"; }
basari() { echo -e "${YESIL}[✓]${SIFIR} $1"; }
uyari()  { echo -e "${SARI}[!]${SIFIR} $1"; }
hata()   { echo -e "${KIRMIZI}[✗]${SIFIR} $1"; }

gui_hazir_mi() {
    [ -n "$DISPLAY" ] || return 1
    if command -v ldconfig >/dev/null 2>&1; then
        ldconfig -p 2>/dev/null | grep -q "libxcb-cursor.so.0" || return 2
    fi
    return 0
}

echo ""
echo -e "${MAVI}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║      ZİHİN KÖPRÜSÜ  v7.0                ║"
echo "  ║  Ses · Uzuv · AI · Tor/SSH Kontrol       ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${SIFIR}"

mkdir -p "$LOG_DIR"
for i in $(seq -w 1 10); do
    mkdir -p "$KOK/eklentiler/slot_$i"
done

# ── Sanal ortam ───────────────────────────────────────────────
if [ ! -f "$VENV" ]; then
    uyari "Sanal ortam yok, oluşturuluyor..."
    python3 -m venv "$KOK/birader_env" || {
        uyari "python3 -m venv başarısız. virtualenv fallback deneniyor..."
        (python3 -m pip install --user -q virtualenv ||
         python3 -m pip install --user --break-system-packages -q virtualenv) &&
            python3 -m virtualenv "$KOK/birader_env" ||
            { hata "venv oluşturulamadı. python3-venv veya virtualenv gerekli."; exit 1; }
    }
    source "$VENV"
    pip install -q --upgrade pip
    [ -f "$KOK/gereksinimler.txt" ] && pip install -q -r "$KOK/gereksinimler.txt"
    basari "Sanal ortam oluşturuldu."
else
    source "$VENV"
    basari "Sanal ortam yüklendi."
fi

cd "$KOK" || { hata "Proje dizinine girilemedi."; exit 1; }

if [ "$MOD" != "--tani" ]; then
    if [ -f "$PID_FILE" ]; then
        ESKI_PID="$(cat "$PID_FILE" 2>/dev/null)"
        if [ -n "$ESKI_PID" ] && kill -0 "$ESKI_PID" 2>/dev/null; then
            uyari "Zihin Koprusu zaten calisiyor (PID: $ESKI_PID)."
            uyari "Ayni anda ikinci kopya acilmadi; Telegram ve Tor cakismlari boyle engelleniyor."
            exit 0
        fi
    fi
    echo $$ > "$PID_FILE"
    trap 'rm -f "$PID_FILE"' EXIT INT TERM
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Başlatılıyor (Mod: ${MOD:-tam})" | tee -a "$LOG"

case "$MOD" in
    --ses)
        cikti "Ses modu..."
        python3 -m zihin.cekirdek
        ;;
    --gui)
        cikti "GUI modu..."
        if ! gui_hazir_mi; then
            uyari "Qt GUI bu ortamda acilamiyor. Eksik bagimlilik: libxcb-cursor0"
            uyari "Kurulum: sudo apt install libxcb-cursor0"
            exit 1
        fi
        python3 -c "
import sys
from zihin.arayuz import goster
app, pencere = goster(None)
sys.exit(app.exec())
"
        ;;
    --tani)
        cikti "Tanı modu..."
        python3 "$KOK/tani.py"
        ;;
    *)
        cikti "Tam mod..."
        GUI_MUMKUN=0
        if gui_hazir_mi; then
            GUI_MUMKUN=1
        fi

        if [ "$GUI_MUMKUN" -ne 1 ]; then
            uyari "GUI baslatilamiyor; cekirdek moduna dusuluyor."
            uyari "Muhtemel eksik paket: libxcb-cursor0"
            uyari "GUI icin: sudo apt install libxcb-cursor0"
            ZK_TERMINAL=1 python3 -m zihin.cekirdek
            exit $?
        fi

        # Masaüstü kısayolundan (Terminal=false) çalıştırılınca
        # terminal penceresi açılmaması için stdout/stderr log dosyasına yönlendir
        if [ -z "$ZK_TERMINAL" ] && [ -n "$DISPLAY" ]; then
            # GUI oturumu var, terminal göstermeden çalıştır
            exec python3 -c "
import sys, threading
from zihin.cekirdek import Cekirdek
from zihin.arayuz import goster

cekirdek = Cekirdek()
app, pencere = goster(cekirdek)

def ses_baslat():
    import time; time.sleep(1)
    cekirdek.baslat_arkaplanda()

threading.Thread(target=ses_baslat, daemon=True).start()
sys.exit(app.exec())
" >> "$LOG" 2>&1
        else
            # Terminal'den el ile çalıştırılıyor — log göster
            ZK_TERMINAL=1 python3 -c "
import sys, threading
from zihin.cekirdek import Cekirdek
from zihin.arayuz import goster

cekirdek = Cekirdek()
app, pencere = goster(cekirdek)

def ses_baslat():
    import time; time.sleep(1)
    cekirdek.baslat_arkaplanda()

threading.Thread(target=ses_baslat, daemon=True).start()
sys.exit(app.exec())
"
        fi
        ;;
esac
