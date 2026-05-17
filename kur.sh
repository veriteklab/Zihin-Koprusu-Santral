#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Zihin Köprüsü v7.0 – Anahtar Teslim Kurulum Betiği  (DÜZELTİLMİŞ v2)
#
# Desteklenen: Ubuntu 20.04+ / Debian 11+ / Linux Mint 20+
#
# Değişiklikler v2:
#   - Tor: kurulu değilse apt ile otomatik kurar
#            kurulu + çalışıyorsa: mevcut Tor'u kullanır, hidden service rehberi gösterir
#            kurulu ama durmuşsa: kendi userspace torrc'siyle başlatır
#   - Telegram ayar şablonu oluşturulur (token girilmesi hatırlatılır)
#   - AI ayar şablonu oluşturulur
#   - Tüm dizin yapısı oluşturulur
#   - Vosk modeli indirilir
#   - Masaüstü kısayolu oluşturulur
#   - İzin sorunları giderildi
# ─────────────────────────────────────────────────────────────────────────────
set -e

MAVI='\033[0;36m'; YESIL='\033[0;32m'; SARI='\033[1;33m'
KIRMIZI='\033[0;31m'; SIFIR='\033[0m'
cikti()  { echo -e "${MAVI}[KUR]${SIFIR} $1"; }
basari() { echo -e "${YESIL}[✓]${SIFIR} $1"; }
uyari()  { echo -e "${SARI}[!]${SIFIR} $1"; }
hata()   { echo -e "${KIRMIZI}[✗]${SIFIR} $1"; exit 1; }

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUR_MODU="${1:---full}"

case "$KUR_MODU" in
    --minimal)
        TAM_KURULUM=0
        ;;
    --full|"")
        TAM_KURULUM=1
        ;;
    --tani)
        if [ -x "$KOK/birader_env/bin/python" ]; then
            "$KOK/birader_env/bin/python" "$KOK/tani.py"
        else
            python3 "$KOK/tani.py"
        fi
        exit $?
        ;;
    --help|-h)
        echo "Kullanım: ./kur.sh [--minimal|--full|--tani]"
        echo "  --minimal  Temel Python/ses/GUI bağımlılıkları ve Vosk modeli"
        echo "  --full     Minimal + uzuv, OCR, Playwright, Piper, Tor araçları"
        echo "  --tani     Kurulum yapmadan mevcut durumu raporla"
        exit 0
        ;;
    *)
        hata "Bilinmeyen seçenek: $KUR_MODU"
        ;;
esac

echo -e "${MAVI}"
echo "  ╔═════════════════════════════════════════════════╗"
echo "  ║     ZİHİN KÖPRÜSÜ v7.0 — KURULUM               ║"
echo "  ╚═════════════════════════════════════════════════╝"
echo -e "${SIFIR}"
uyari "Kurulum modu: $KUR_MODU"

# ── Python Kontrolü ──────────────────────────────────────────────────────────
cikti "Python kontrol ediliyor..."
PVER=$(python3 --version 2>&1 | awk '{print $2}')
PMAJ=$(echo "$PVER" | cut -d. -f1)
PMIN=$(echo "$PVER" | cut -d. -f2)
[ "$PMAJ" -lt 3 ] || ([ "$PMAJ" -eq 3 ] && [ "$PMIN" -lt 10 ]) && \
    hata "Python 3.10+ gerekli. Mevcut: $PVER"
basari "Python $PVER"

# ── Sudo Kontrolü ────────────────────────────────────────────────────────────
SUDO=""
if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    SUDO="sudo -n"
else
    uyari "Şifresiz sudo yok. Sistem paketleri/Tor/sudoers adımları atlanacak."
    uyari "Tam sistem kurulumu için terminalde sudo yetkisiyle tekrar çalıştırın."
fi

# ── Sistem Paketleri ─────────────────────────────────────────────────────────
if [ -n "$SUDO" ]; then
    cikti "Sistem paketleri kuruluyor..."
    $SUDO apt-get update -qq || uyari "apt update başarısız, devam ediliyor."
    $SUDO apt-get install -y -qq \
        python3-pip python3-venv python3-dev \
        portaudio19-dev ffmpeg libespeak-ng1 alsa-utils pulseaudio-utils \
        wget unzip \
        || uyari "Bazı paketler kurulamadı, devam ediliyor."
    if [ "$TAM_KURULUM" -eq 1 ]; then
        $SUDO apt-get install -y -qq \
            tor netcat-openbsd openssh-client sshpass \
            adb scrcpy xdotool wmctrl playerctl brightnessctl scrot \
            tesseract-ocr tesseract-ocr-tur tigervnc-viewer \
            || uyari "Bazı tam kurulum paketleri kurulamadı, devam ediliyor."
    fi
else
    uyari "Sistem paket kurulumu atlandı."
fi
basari "Sistem paketleri ✓"

# ── Tor Kurulumu / Tespiti ───────────────────────────────────────────────────
cikti "Tor kontrol ediliyor..."
if [ "$TAM_KURULUM" -eq 0 ]; then
    uyari "Minimal mod: Tor kurulumu atlandı."
elif command -v tor &>/dev/null; then
    # Tor kurulu
    TOR_AKTIF=$(systemctl is-active tor 2>/dev/null || echo "inactive")
    if [ "$TOR_AKTIF" = "active" ]; then
        basari "Sistem Tor aktif — Zihin Köprüsü kendi torrc'sini kullanacak."
        uyari  "Hidden service için (isteğe bağlı — tam Tor gizliliği):"
        echo   "  sudo nano /etc/tor/torrc"
        echo   "  → Şunu ekleyin:"
        echo   "    HiddenServiceDir /var/lib/tor/zk_ssh/"
        echo   "    HiddenServicePort 22 127.0.0.1:22"
        echo   "    HiddenServiceDir /var/lib/tor/zk_web/"
        echo   "    HiddenServicePort 80 127.0.0.1:8765"
        echo   "  sudo systemctl restart tor"
        echo   "  sudo cat /var/lib/tor/zk_ssh/hostname"
        echo ""
    else
        uyari "Tor kurulu ama çalışmıyor. Zihin Köprüsü kendi torrc'siyle başlatacak."
    fi
else
    cikti "Tor bulunamadı, otomatik kuruluyor..."
    if [ -n "$SUDO" ]; then
        $SUDO apt-get install -y -qq tor || uyari "Tor kurulamadı. Manuel kurun: sudo apt install tor"
    else
        uyari "Tor kurulamadı: sudo yok. Manuel kurun: sudo apt install tor"
    fi
    if command -v tor &>/dev/null; then
        [ -n "$SUDO" ] && $SUDO systemctl enable tor --now 2>/dev/null || true
        basari "Tor kuruldu ve başlatıldı."
    else
        uyari "Tor kurulumu başarısız. Zihin Köprüsü Tor özellikleri olmadan çalışacak."
    fi
fi

# ── Dizin Yapısı ─────────────────────────────────────────────────────────────
cikti "Dizin yapısı oluşturuluyor..."
mkdir -p "$KOK"/{loglar,dil,web,pluginler,yedekler}
mkdir -p "$KOK/modeller/vosk-tr"
mkdir -p "$KOK/modeller/piper-tr"
mkdir -p "$KOK/tor_veri/hs_ssh"
mkdir -p "$KOK/tor_veri/hs_web"
# Eklenti slotları
for i in $(seq -w 1 10); do
    mkdir -p "$KOK/eklentiler/slot_$i"
done
# Tor veri dizinleri için doğru izinler
chmod 700 "$KOK/tor_veri" "$KOK/tor_veri/hs_ssh" "$KOK/tor_veri/hs_web" 2>/dev/null || true
basari "Dizinler ✓"

# ── Varsayılan JSON/YAML Dosyaları ──────────────────────────────────────────
cikti "Varsayılan yapılandırma dosyaları oluşturuluyor..."

# Telegram ayar şablonu (token girilmesi gerekiyor)
if [ ! -f "$KOK/telegram_ayar.json" ]; then
cat > "$KOK/telegram_ayar.json" << 'EOFJSON'
{
  "token": "BOT_TOKENINIZI_BURAYA_GIRIN",
  "chat_id": "CHAT_ID_NIZI_BURAYA_GIRIN",
  "aktif": false,
  "tor": false,
  "komut_al": true,
  "yanit_gonder": true,
  "log_gonder": false,
  "uzuv_bildir": true,
  "log_filtre": "HATA,KRİTİK",
  "izin_bilincler": ["ABİ", "BİRADER", "ABLA"]
}
EOFJSON
    basari "telegram_ayar.json şablonu oluşturuldu."
else
    uyari "telegram_ayar.json zaten var, dokunulmadı."
fi

# AI ayar şablonu
if [ ! -f "$KOK/ai_ayar.json" ]; then
cat > "$KOK/ai_ayar.json" << 'EOFJSON'
{
  "saglayici": "gemini",
  "model": "",
  "api_anahtari": "",
  "api_url": "",
  "sistem_mesaji": "Sen Zihin Köprüsü sisteminin asistanısın. Kısa ve yardımsever Türkçe yanıtlar verirsin.",
  "max_gecmis": 20,
  "kullan_tor": false
}
EOFJSON
    basari "ai_ayar.json şablonu oluşturuldu."
fi

# Hitap ayarları
if [ ! -f "$KOK/hitap_ayar.json" ]; then
cat > "$KOK/hitap_ayar.json" << 'EOFJSON'
{
  "ABİ": "Sahip",
  "BİRADER": "Sahip",
  "BACİ": "Sahip",
  "ABLA": "Sahip",
  "UFAKLIK": "Sahip",
  "DAYI": "Sahip",
  "KUZEN": "Sahip"
}
EOFJSON
    basari "hitap_ayar.json oluşturuldu."
fi

# Uzuvlar boş şablon
if [ ! -f "$KOK/uzuvlar.json" ]; then
    echo '{"__meta__": {"onion_host": "", "onion_port": 22, "onion_kullanici": "zihin"}}' \
        > "$KOK/uzuvlar.json"
    basari "uzuvlar.json oluşturuldu."
fi

basari "Yapılandırma dosyaları ✓"

# ── Sanal Ortam ───────────────────────────────────────────────────────────────
cikti "Python sanal ortamı oluşturuluyor..."
if [ ! -f "$KOK/birader_env/bin/activate" ]; then
    python3 -m venv "$KOK/birader_env" || {
        uyari "python3 -m venv başarısız. virtualenv fallback deneniyor..."
        (python3 -m pip install --user -q virtualenv ||
         python3 -m pip install --user --break-system-packages -q virtualenv) &&
            python3 -m virtualenv "$KOK/birader_env" ||
            hata "Sanal ortam oluşturulamadı. Gerekli paket: python3-venv veya virtualenv"
    }
else
    uyari "Sanal ortam zaten var, yeniden kullanılacak."
fi
source "$KOK/birader_env/bin/activate"
pip install -q --upgrade pip setuptools wheel "Cython<3"
basari "Sanal ortam ✓"

# ── Python Paketleri ─────────────────────────────────────────────────────────
cikti "Python paketleri kuruluyor..."
if [ -f "$KOK/gereksinimler.txt" ]; then
    pip install -q -r "$KOK/gereksinimler.txt" || uyari "Bazı Python paketleri kurulamadı."
else
    pip install -q \
        vosk sounddevice gtts edge-tts pyyaml \
        google-generativeai PyQt6 requests psutil \
        "python-telegram-bot>=20.0" "python-socks>=2.0.0" "PySocks>=1.7.1" "telethon>=1.36.0" \
        playwright piper-tts \
        || uyari "Bazı Python paketleri kurulamadı."
fi
basari "Python paketleri ✓"

# Playwright tarayıcıları
if [ "${ZK_SKIP_PLAYWRIGHT:-0}" = "1" ]; then
    uyari "ZK_SKIP_PLAYWRIGHT=1: Playwright Chromium kurulumu atlandı."
elif [ "$TAM_KURULUM" -eq 1 ] && python -c "import playwright" >/dev/null 2>&1; then
    cikti "Playwright Chromium kurulumu kontrol ediliyor..."
    if command -v timeout >/dev/null 2>&1; then
        timeout 600 python -m playwright install chromium >/dev/null 2>&1 || \
            uyari "Playwright Chromium kurulamadı veya zaman aşımına uğradı. Manuel: source birader_env/bin/activate && python -m playwright install chromium"
    else
        python -m playwright install chromium >/dev/null 2>&1 || \
            uyari "Playwright Chromium kurulamadı. Manuel: source birader_env/bin/activate && python -m playwright install chromium"
    fi
fi

# ── Vosk Türkçe Model ────────────────────────────────────────────────────────
MODEL_YOLU="$KOK/modeller/vosk-tr/vosk-model-small-tr-0.3"
if [ ! -d "$MODEL_YOLU" ]; then
    cikti "Vosk Türkçe model indiriliyor (~50MB)..."
    URL="https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip"
    wget -q --show-progress -O /tmp/vosk-tr.zip "$URL" && {
        unzip -q /tmp/vosk-tr.zip -d "$KOK/modeller/vosk-tr/"
        rm /tmp/vosk-tr.zip
        basari "Vosk modeli ✓"
    } || uyari "Vosk modeli indirilemedi. Manuel indirin: $URL → $MODEL_YOLU"
else
    basari "Vosk modeli zaten mevcut ✓"
fi

# ── Piper Türkçe TTS Model ───────────────────────────────────────────────────
PIPER_MODEL="$KOK/modeller/piper-tr/tr_TR-dfki-medium.onnx"
PIPER_CONFIG="$KOK/modeller/piper-tr/tr_TR-dfki-medium.onnx.json"
PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/tr/tr_TR/dfki/medium"
if [ "$TAM_KURULUM" -eq 0 ]; then
    uyari "Minimal mod: Piper model indirimi atlandı."
elif command -v piper >/dev/null 2>&1; then
    if [ ! -f "$PIPER_MODEL" ] || [ ! -f "$PIPER_CONFIG" ]; then
        cikti "Piper Türkçe model indiriliyor (~64MB)..."
        wget -q --show-progress -O "$PIPER_MODEL" \
            "$PIPER_BASE/tr_TR-dfki-medium.onnx" && \
        wget -q -O "$PIPER_CONFIG" \
            "$PIPER_BASE/tr_TR-dfki-medium.onnx.json" && \
            basari "Piper Türkçe modeli ✓" || \
            uyari "Piper modeli indirilemedi. Manuel kaynak: $PIPER_BASE/"
    else
        basari "Piper modeli zaten mevcut ✓"
    fi
else
    uyari "piper komutu bulunamadı. Offline TTS için: pip install piper-tts"
fi

# ── dil/tr.json ──────────────────────────────────────────────────────────────
# Olası kaynakları sırayla dene; hiçbiri yoksa gömülü içerikle oluştur
cikti "Dil dosyası kontrol ediliyor..."
if [ ! -f "$KOK/dil/tr.json" ]; then
    # 1. Betikle aynı dizinde var mı?
    for kaynak in \
        "$KOK/dil/tr.json" \
        "$KOK/zihin/dil/tr.json" \
        "$(dirname "$0")/dil/tr.json"
    do
        if [ -f "$kaynak" ]; then
            cp "$kaynak" "$KOK/dil/tr.json"
            basari "dil/tr.json kopyalandı: $kaynak"
            break
        fi
    done
fi

# Hâlâ yoksa gömülü içerikle oluştur (bağımsız kurulum garantisi)
if [ ! -f "$KOK/dil/tr.json" ]; then
cat > "$KOK/dil/tr.json" << 'EOFJSON'
{
  "sistem": {
    "baslik": "Zihin Köprüsü",
    "hazir": "Zihin Köprüsü hazır.",
    "kapaniyor": "Zihin Köprüsü kapatılıyor.",
    "basladi": "Sistem başladı.",
    "devir": "Komuta hazırım.",
    "anlamadim": "Anlamadım, tekrar söyler misiniz?",
    "hata": "Bir hata oluştu.",
    "tamamlandi": "İşlem tamamlandı.",
    "iptal": "İptal edildi.",
    "onay": "Onaylandı.",
    "bekle": "Lütfen bekleyin.",
    "hazirlanıyor": "Hazırlanıyor...",
    "baglanıyor": "Bağlanıyor...",
    "baglandi": "Bağlandı.",
    "baglanti_kesildi": "Bağlantı kesildi."
  },
  "ses": {
    "dinleniyor": "Dinleniyor...",
    "anlasildi": "Anlaşıldı.",
    "model_yuklenemedi": "Ses modeli yüklenemedi.",
    "mikrofon_hatasi": "Mikrofon erişim hatası.",
    "tts_hatasi": "Ses sentezi başarısız.",
    "gurultu_fazla": "Ortam gürültüsü fazla, lütfen tekrarlayın."
  },
  "komut": {
    "bulunamadi": "Komut bulunamadı.",
    "calistirildi": "Komut çalıştırıldı.",
    "hata": "Komut hata verdi.",
    "zaman_asimi": "Komut zaman aşımına uğradı.",
    "yetki_yok": "Bu işlem için yetkiniz yok."
  },
  "ai": {
    "basladi": "Yapay zeka hazır.",
    "yanıt_yok": "Şu an yanıt veremiyorum, lütfen tekrar deneyin.",
    "anahtar_yok": "API anahtarı bulunamadı.",
    "baglanti_hatasi": "Yapay zeka bağlantı hatası."
  },
  "arayuz": {
    "baslat": "Başlat", "durdur": "Durdur", "ayarlar": "Ayarlar",
    "gunluk": "Günlük", "uzuvlar": "Uzuvlar", "eklentiler": "Eklentiler",
    "hakkinda": "Hakkında", "cikis": "Çıkış",
    "aktif_bilinc": "Aktif Bilinç", "durum": "Durum",
    "dinleniyor": "Dinleniyor", "bosta": "Boşta",
    "konusuyor": "Konuşuyor", "dusunuyor": "Düşünüyor",
    "hata_durumu": "Hata", "slot_bos": "Boş Alan",
    "slot_ekle": "Eklenti Ekle", "slot_calistir": "Çalıştır",
    "slot_klasor_ac": "Klasörü Aç", "log_temizle": "Günlüğü Temizle",
    "kaydet": "Kaydet", "iptal": "İptal", "kapat": "Kapat"
  },
  "bilincler": {
    "ABİ": "Abi", "BİRADER": "Birader", "BACİ": "Bacı",
    "ABLA": "Abla", "UFAKLIK": "Ufaklık", "DAYI": "Dayı", "KUZEN": "Kuzen"
  },
  "yetki": {
    "izleyici": "İzleyici", "kontrol": "Kontrol",
    "tam": "Tam Yetki", "acil": "Acil"
  }
}
EOFJSON
    basari "dil/tr.json gömülü içerikle oluşturuldu."
fi

# ── İzinler ──────────────────────────────────────────────────────────────────
chmod +x "$KOK/baslat.sh" "$KOK/kur.sh" 2>/dev/null || true

# ── SVG İkon ─────────────────────────────────────────────────────────────────
cikti "İkon oluşturuluyor..."
IKON_DIR="$KOK/assets"
mkdir -p "$IKON_DIR"
cat > "$IKON_DIR/icon.svg" << 'SVGEOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="22" fill="#0d0f14"/>
  <polygon points="64,18 108,42 108,86 64,110 20,86 20,42" fill="none" stroke="#00e5ff" stroke-width="4"/>
  <polygon points="64,34 94,51 94,77 64,94 34,77 34,51" fill="none" stroke="#7c4dff" stroke-width="2.5"/>
  <circle cx="64" cy="64" r="10" fill="#00e5ff"/>
  <line x1="64" y1="34" x2="64" y2="54" stroke="#00e5ff" stroke-width="2"/>
  <line x1="64" y1="74" x2="64" y2="94" stroke="#00e5ff" stroke-width="2"/>
  <line x1="34" y1="51" x2="51" y2="60" stroke="#00e5ff" stroke-width="2"/>
  <line x1="77" y1="68" x2="94" y2="77" stroke="#00e5ff" stroke-width="2"/>
  <line x1="94" y1="51" x2="77" y2="60" stroke="#00e5ff" stroke-width="2"/>
  <line x1="51" y1="68" x2="34" y2="77" stroke="#00e5ff" stroke-width="2"/>
</svg>
SVGEOF

# SVG'yi PNG'ye çevir (isteğe bağlı, rsvg-convert varsa)
if command -v rsvg-convert &>/dev/null; then
    rsvg-convert -w 128 -h 128 "$IKON_DIR/icon.svg" -o "$IKON_DIR/icon.png" 2>/dev/null &&         basari "PNG ikon oluşturuldu." || true
elif command -v convert &>/dev/null; then
    convert -background none "$IKON_DIR/icon.svg" -resize 128x128 "$IKON_DIR/icon.png" 2>/dev/null &&         basari "PNG ikon oluşturuldu (ImageMagick)." || true
fi
IKON="${IKON_DIR}/icon.png"
[ -f "$IKON" ] || IKON="$IKON_DIR/icon.svg"
basari "İkon hazır: $IKON"

# ── Masaüstü Kısayolu ────────────────────────────────────────────────────────
cikti "Masaüstü kısayolu oluşturuluyor..."
DESK="$HOME/.local/share/applications/zihin-koprusu.desktop"
MASAUSTU="$HOME/Desktop"
[ -d "$HOME/Masaüstü" ] && MASAUSTU="$HOME/Masaüstü"   # Türkçe masaüstü

mkdir -p "$(dirname "$DESK")"

cat > "$DESK" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Zihin Köprüsü
GenericName=Ses Tabanlı Uzuv Sistemi
Comment=Zihin Köprüsü v7.0 — Sesli komut, Tor/SSH, AI
Exec=$KOK/baslat.sh
Icon=$IKON
Terminal=false
StartupNotify=true
Categories=Utility;Accessibility;Network;
Keywords=ses;komut;tor;ssh;ai;asistan
EOF
chmod +x "$DESK"

# Masaüstüne de kopyala (varsa)
if [ -d "$MASAUSTU" ]; then
    cp "$DESK" "$MASAUSTU/zihin-koprusu.desktop" 2>/dev/null || true
    chmod +x "$MASAUSTU/zihin-koprusu.desktop" 2>/dev/null || true
    uyari "Masaüstü simgesi çalışmazsa: sağ tık → Güvenilir olarak işaretle"
fi

# uygulama menüsünü güncelle
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
basari "Masaüstü kısayolu ✓"

# ── Otomatik Başlatma (PC Açılışında) ────────────────────────────────────────
cikti "Otomatik başlatma ayarlanıyor..."
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/zihin-koprusu.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Zihin Köprüsü
Comment=Zihin Köprüsü v7.0 otomatik başlat
Exec=$KOK/baslat.sh
Icon=$IKON
Terminal=false
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF
basari "Otomatik başlatma eklendi (~/.config/autostart/)"
uyari "Otomatik başlatmayı kapatmak için:"
echo "  GUI → Ayarlar → Sistem → 'PC Açılışında Başlat' kutusunu kaldır"
echo "  veya: rm ~/.config/autostart/zihin-koprusu.desktop"

# ── Sonuç ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${YESIL}"
echo "  ╔═════════════════════════════════════════════════╗"
echo "  ║       KURULUM TAMAMLANDI! ✓                     ║"
echo "  ╚═════════════════════════════════════════════════╝"
echo -e "${SIFIR}"
echo ""
cikti "Başlatmak için:   ./baslat.sh"
cikti "Sadece ses:       ./baslat.sh --ses"
cikti "Sadece GUI:       ./baslat.sh --gui"
echo ""
uyari "API anahtarları için (en az birini ayarlayın):"
echo "  export GEMINI_API_KEY='anahtarınız'     >> ~/.bashrc"
echo "  export OPENAI_API_KEY='anahtarınız'     >> ~/.bashrc"
echo "  export ANTHROPIC_API_KEY='anahtarınız'  >> ~/.bashrc"
echo "  source ~/.bashrc"
echo ""
uyari "Telegram botu için telegram_ayar.json düzenleyin:"
echo "  nano $KOK/telegram_ayar.json"
echo "  → token ve chat_id girin, aktif: true yapın"
echo ""
uyari "Hitap adını değiştirmek için:"
echo "  nano $KOK/hitap_ayar.json"
echo ""

# Tor için sudoers — şifresiz hidden service dosyası okuma
SUDOERS_F="/etc/sudoers.d/zihin-koprusu"
if [ -n "$SUDO" ] && [ ! -f "$SUDOERS_F" ]; then
    cikti "Tor sudoers kuralı ekleniyor..."
    printf '%s ALL=(ALL) NOPASSWD: /bin/cat /var/lib/tor/zk_ssh/hostname, /bin/cat /var/lib/tor/zk_web/hostname, /usr/bin/tee -a /etc/tor/torrc, /usr/bin/systemctl reload tor, /usr/bin/systemctl restart tor\n' "$USER" \
        | $SUDO tee "$SUDOERS_F" > /dev/null 2>&1 && \
        basari "Tor sudoers eklendi ✓" || \
        uyari "Tor sudoers eklenemedi — onion adresi için manuel: sudo ./kur.sh"
elif [ -z "$SUDO" ]; then
    uyari "Tor sudoers kuralı atlandı: sudo yok."
fi

echo ""
basari "════ Zihin Köprüsü kurulumu tamamlandı! ════"
echo "  ./baslat.sh ile başlatın"
echo ""
