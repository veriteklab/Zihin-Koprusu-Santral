"""
Zihin Köprüsü – Gelişmiş İstemci Üreteci

Üretilen istemci özellikleri:
  - Tor kurulu değilse otomatik kurar (Linux/Android)
  - Kurulum tamamlanınca sunucuya "hazırım" bildirimi gönderir
  - SSH ters tünel açar ve komut bekler
  - Gelen komutları çalıştırır, çıktıyı sunucuya bildirir
  - Sistemle birlikte otomatik başlar (systemd / Termux .bashrc)
  - Windows: OpenSSH + Tor Browser desteği kontrolü
  - Android/Termux: root gerekmez

Her uzuv için iki dosya üretilir:
  zk_<uzuv_id>.py     → istemci Python scripti
  kur_<uzuv_id>.sh    → tek tıkla kurulum betiği (Tor + systemd servis)
"""
from __future__ import annotations

import os
import re
import subprocess
import shutil
import zipfile
import sys
import tempfile
from dataclasses import dataclass

from .logcu import Logcu

KAYNAK = "İSTEMCİ"


@dataclass
class IstemciAyar:
    uzuv_id: str = ""
    uzuv_ad: str = ""
    uzuv_tip: str = "linux"          # linux | windows | android
    baglanti_modu: str = "ssh_reverse"  # ssh_reverse | tor_http | tor_https | telegram_agent
    onion_host: str = ""             # Merkez sunucu adresi
    onion_port: int = 22
    ssh_kullanici: str = "zihin"
    ssh_anahtar: str = ""
    tor_proxy: str = "127.0.0.1:9050"
    sessiz_mod: bool = True
    otomatik_baslat: bool = True
    bildirim_url: str = ""           # Sunucu HTTP bildirim endpoint'i
    yerel_ssh_port: int = 22         # Android için 8022
    ses_aktar: bool = False          # İleride: mikrofon akışı (şimdilik placeholder)
    windows_format: str = ""         # "Python + .bat" | "Yalnızca .bat" | "C++"
    android_format: str = ""         # "Termux" | "APK — Buildozer"
    derle_paket: bool = True         # APK/EXE seçildiyse normalde gerçek paketi derler.
    http_host: str = "0.0.0.0"
    http_port: int = 8787
    http_token: str = ""
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_session: str = "zk_limb"
    telegram_chat: str = ""


class IstemciUretici:
    def __init__(self, logcu: Logcu):
        self.log = logcu
        self.proje_kok = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.son_uretim_hatasi = ""

    def uret(self, ayar: IstemciAyar, cikti_klasoru: str) -> list[str]:
        """Hedef tipe göre istemci dosyalarını üretir. Dosya yolları listesi döner."""
        self.son_uretim_hatasi = ""
        ayar.uzuv_id = self._guvenli_id(ayar.uzuv_id)
        if not ayar.uzuv_id:
            self.log.hata(KAYNAK, "uzuv_id boş veya geçersiz.")
            return []
        if not ayar.uzuv_ad:
            ayar.uzuv_ad = ayar.uzuv_id
        os.makedirs(cikti_klasoru, exist_ok=True)
        tip = ayar.uzuv_tip.lower()
        baglanti_modu = (ayar.baglanti_modu or "ssh_reverse").lower()
        fmt = (ayar.android_format or ayar.windows_format or "").lower()

        if tip == "android" and ("apk" in fmt or "buildozer" in fmt):
            dosyalar = self._android_apk_istemci(ayar, cikti_klasoru)
        elif baglanti_modu in ("tor_http", "tor_https", "http_agent", "http"):
            if tip == "linux":
                dosyalar = self._linux_http_istemci(ayar, cikti_klasoru)
            elif tip == "mac":
                dosyalar = self._mac_http_istemci(ayar, cikti_klasoru)
            elif tip == "windows":
                dosyalar = self._windows_http_istemci(ayar, cikti_klasoru)
            elif tip == "android":
                dosyalar = self._android_http_istemci(ayar, cikti_klasoru)
            else:
                self.log.uyari(KAYNAK, f"HTTP ajan icin bilinmeyen uzuv tipi: {tip}")
                return []
        elif baglanti_modu in ("telegram_agent", "telegram"):
            if tip == "linux":
                dosyalar = self._linux_telegram_istemci(ayar, cikti_klasoru)
            elif tip == "mac":
                dosyalar = self._mac_telegram_istemci(ayar, cikti_klasoru)
            elif tip == "windows":
                dosyalar = self._windows_telegram_istemci(ayar, cikti_klasoru)
            elif tip == "android":
                dosyalar = self._android_telegram_istemci(ayar, cikti_klasoru)
            else:
                self.log.uyari(KAYNAK, f"Telegram ajan icin bilinmeyen uzuv tipi: {tip}")
                return []
        elif tip == "linux":
            dosyalar = self._linux_istemci(ayar, cikti_klasoru)
        elif tip == "mac":
            dosyalar = self._mac_istemci(ayar, cikti_klasoru)
        elif tip == "windows":
            fmt = (ayar.windows_format or "").lower()
            if "c++" in fmt:
                dosyalar = self._windows_cpp_istemci(ayar, cikti_klasoru)
            elif "yalnızca" in fmt or "powershell" in fmt or ("bat" in fmt and "python" not in fmt):
                dosyalar = self._windows_bat_istemci(ayar, cikti_klasoru)
            else:
                dosyalar = self._windows_istemci(ayar, cikti_klasoru)  # Python + .bat
        elif tip == "android":
            dosyalar = self._android_istemci(ayar, cikti_klasoru)  # Termux
        else:
            self.log.uyari(KAYNAK, f"Bilinmeyen uzuv tipi: {tip}")
            return []

        self.log.bilgi(KAYNAK, f"{len(dosyalar)} dosya üretildi: {cikti_klasoru}")

        # Otomatik derleme — platform'a göre
        tip = ayar.uzuv_tip.lower()
        gercek_paket = ""

        if ayar.derle_paket and tip == "android" and ("apk" in fmt or "buildozer" in fmt):
            # APK otomatik derle
            apk = self._apk_derle(cikti_klasoru)
            if apk:
                gercek_paket = apk
                dosyalar = [apk]
        elif ayar.derle_paket and tip == "windows" and "c++" in fmt:
            # EXE otomatik derle (mingw cross-compiler)
            exe = self._exe_derle(cikti_klasoru, ayar.uzuv_id)
            if exe:
                gercek_paket = exe
                dosyalar = [exe] + [d for d in dosyalar if os.path.basename(d) in ("kur_exe.bat", "kaldir_exe.bat")]

        rapor = self._uretim_raporu_yaz(
            ayar, cikti_klasoru, dosyalar, gercek_paket, self.son_uretim_hatasi
        )
        paket = self._dagitim_paketi_olustur(ayar, cikti_klasoru, dosyalar + ([rapor] if rapor else []))
        if rapor:
            dosyalar.append(rapor)
        if paket:
            dosyalar.append(paket)

        return dosyalar

    @staticmethod
    def _guvenli_id(deger: str) -> str:
        """Dosya/servis adlarında güvenli uzuv kimliği üret."""
        deger = (deger or "").strip().lower()
        deger = re.sub(r"[^a-z0-9_-]+", "_", deger)
        deger = re.sub(r"_+", "_", deger).strip("_-")
        return deger[:48]

    def _hedef_artifakt_turu(self, a: IstemciAyar) -> str:
        tip = (a.uzuv_tip or "").lower()
        fmt = (a.android_format or a.windows_format or "").lower()
        if tip == "android" and ("apk" in fmt or "buildozer" in fmt):
            return "apk"
        if tip == "windows" and "c++" in fmt:
            return "exe"
        if tip == "windows" and ("yalnızca" in fmt or "yalnizca" in fmt or "bat" in fmt):
            return "bat"
        return "py"

    @staticmethod
    def _komut_yolu(ad: str) -> str:
        proje_kok = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        adaylar = [
            shutil.which(ad),
            os.path.expanduser(os.path.join("~", ".local", "bin", ad)),
            os.path.join(proje_kok, "birader_env", "bin", ad),
            os.path.join(os.path.dirname(sys.executable), ad),
        ]
        for aday in adaylar:
            if aday and os.path.exists(aday):
                return aday
        return ""

    def _uretim_raporu_yaz(
        self,
        a: IstemciAyar,
        klasor: str,
        dosyalar: list[str],
        gercek_paket: str = "",
        hata_detayi: str = "",
    ) -> str:
        hedef = self._hedef_artifakt_turu(a)
        rapor = os.path.join(klasor, "URETIM_RAPORU.txt")
        satirlar = [
            "Zihin Koprusu Istemci Uretim Raporu",
            "===================================",
            "",
            f"Uzuv ID: {a.uzuv_id}",
            f"Uzuv Adi: {a.uzuv_ad}",
            f"Hedef Tip: {a.uzuv_tip}",
            f"Baglanti Modu: {a.baglanti_modu}",
            f"Istenen Paket: {hedef.upper()}",
            f"Gercek Derleme: {'EVET' if a.derle_paket else 'HAYIR'}",
            "",
        ]
        if gercek_paket and os.path.exists(gercek_paket):
            satirlar += [
                "Durum: BASARILI",
                f"Gercek paket hazirlandi: {os.path.basename(gercek_paket)}",
                "",
            ]
        else:
            satirlar += [
                "Durum: KAYNAK PAKETI HAZIR" if not hata_detayi else "Durum: DERLEME BASARISIZ",
                "",
                "Not:",
                "Bu klasorde calisabilir istemci kaynaklari ve kurulum dosyalari hazirlandi.",
            ]
            if hata_detayi:
                satirlar += [
                    "Gercek paket olusturulamadi.",
                    f"Hata ozeti: {hata_detayi}",
                ]
            elif hedef == "apk":
                if a.derle_paket:
                    satirlar += [
                        "Gercek .apk icin Buildozer gerekiyor.",
                        "Bu makinede Buildozer bulunamadigi icin Android proje paketi uretildi.",
                    ]
                else:
                    satirlar += [
                    "Gercek APK derlemesi kullanici tercihiyle calistirilmadi.",
                    "Bu nedenle yalnizca Android Buildozer proje paketi hazirlandi.",
                    ]
            elif hedef == "exe":
                if a.derle_paket:
                    satirlar += [
                        "Gercek .exe icin MinGW-w64 veya benzeri Windows derleyicisi gerekiyor.",
                        "Bu makinede derleyici bulunamadigi icin Windows kaynak paketi uretildi.",
                    ]
                else:
                    satirlar += [
                    "Gercek EXE derlemesi kullanici tercihiyle calistirilmadi.",
                    "Bu nedenle yalnizca Windows kaynak paketi hazirlandi.",
                    ]
            else:
                satirlar += [
                    "Secilen mod icin calisabilir kaynak istemci dosyalari uretildi.",
                ]
            satirlar.append("")

        satirlar.append("Uretilen dosyalar:")
        for yol in dosyalar:
            satirlar.append(f"- {os.path.basename(yol)}")
        satirlar += [
            "",
            "Dagitim:",
            "- Tek klasor yerine DAGITIM_PAKETI.zip dosyasini kullanabilirsiniz.",
            "- Gercek .apk/.exe gerekiyorsa bu paketi derleme ortaminda tekrar acin.",
            "",
        ]
        with open(rapor, "w", encoding="utf-8") as f:
            f.write("\n".join(satirlar) + "\n")
        return rapor

    def _dagitim_paketi_olustur(self, a: IstemciAyar, klasor: str, dosyalar: list[str]) -> str:
        paket = os.path.join(klasor, "DAGITIM_PAKETI.zip")
        try:
            with zipfile.ZipFile(paket, "w", zipfile.ZIP_DEFLATED) as zf:
                for yol in dosyalar:
                    if yol and os.path.isfile(yol):
                        zf.write(yol, arcname=os.path.basename(yol))
            self.log.bilgi(KAYNAK, f"Dagitim paketi hazirlandi: {paket}")
            return paket
        except Exception as e:
            self.log.uyari(KAYNAK, f"Dagitim paketi olusturulamadi: {e}")
            return ""

    @staticmethod
    def _windows_task_bat(
        servis_adi: str,
        calistir_komutu: str,
        baslik: str,
        once: list[str] | None = None,
    ) -> str:
        once_satirlari = "\r\n".join(once or [])
        if once_satirlari:
            once_satirlari += "\r\n"
        tr_komut = calistir_komutu.replace('"', r'\"')
        return f'''@echo off
setlocal
cd /d "%~dp0"
echo [ZK] {baslik}
{once_satirlari}echo [ZK] Zamanlanmis gorev kuruluyor: {servis_adi}
schtasks /Create /TN "{servis_adi}" /TR "{tr_komut}" /SC ONLOGON /RL HIGHEST /F
if %errorlevel% neq 0 (
    echo [HATA] Gorev kurulamadi. Bu dosyayi Yonetici olarak calistirin.
    pause
    exit /b 1
)
echo [ZK] Gorev baslatiliyor...
schtasks /Run /TN "{servis_adi}"
echo [ZK] Kurulum tamamlandi.
pause
'''

    @staticmethod
    def _windows_task_kaldir_bat(servis_adi: str) -> str:
        return f'''@echo off
echo [ZK] Zamanlanmis gorev kaldiriliyor: {servis_adi}
schtasks /End /TN "{servis_adi}" >nul 2>&1
schtasks /Delete /TN "{servis_adi}" /F
echo [ZK] Kaldirma tamamlandi.
pause
'''

    @staticmethod
    def _mac_launchd_sh(
        a: IstemciAyar,
        py_dosya_adi: str,
        etiket: str,
        aciklama: str,
        pip_paketleri: str = "",
    ) -> str:
        pip_satiri = (
            f'python3 -m pip install --user --upgrade {pip_paketleri}\n'
            if pip_paketleri else ""
        )
        return f'''#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PY_DOSYA="${{SCRIPT_DIR}}/{py_dosya_adi}"
LABEL="com.zihinkoprusu.{a.uzuv_id}.{etiket}"
PLIST="$HOME/Library/LaunchAgents/${{LABEL}}.plist"
LOG_DIR="$HOME/Library/Logs/ZihinKoprusu"
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
python3 --version >/dev/null 2>&1 || {{ echo "[HATA] Python 3 gerekli."; exit 1; }}
{pip_satiri}chmod +x "$PY_DOSYA"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${{LABEL}}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>${{PY_DOSYA}}</string>
  </array>
  <key>WorkingDirectory</key><string>${{SCRIPT_DIR}}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${{LOG_DIR}}/{a.uzuv_id}-{etiket}.out.log</string>
  <key>StandardErrorPath</key><string>${{LOG_DIR}}/{a.uzuv_id}-{etiket}.err.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/${{LABEL}}"
echo "[ZK] {aciklama} kuruldu: ${{LABEL}}"
echo "[ZK] Log: ${{LOG_DIR}}/{a.uzuv_id}-{etiket}.out.log"
'''

    @staticmethod
    def _mac_launchd_kaldir_sh(a: IstemciAyar, etiket: str) -> str:
        return f'''#!/bin/bash
set -e
LABEL="com.zihinkoprusu.{a.uzuv_id}.{etiket}"
PLIST="$HOME/Library/LaunchAgents/${{LABEL}}.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "[ZK] Kaldirildi: ${{LABEL}}"
'''

    @staticmethod
    def _merkez_host(a: IstemciAyar) -> str:
        return (a.onion_host or "").strip()

    @staticmethod
    def _merkez_port(a: IstemciAyar) -> int:
        return int(a.onion_port or 22)

    @staticmethod
    def _tor_gerekli_mi(a: IstemciAyar) -> bool:
        mod = (a.baglanti_modu or "").lower()
        host = (a.onion_host or "").lower()
        return mod in ("tor_ssh",) or host.endswith(".onion")

    @classmethod
    def _merkez_etiketi(cls, a: IstemciAyar) -> str:
        host = cls._merkez_host(a)
        if not host:
            return "MERKEZ_ADRESI_GIRIN"
        return f"{host}:{cls._merkez_port(a)}"

    def _http_ajan_python(self, a: IstemciAyar, hedef: str) -> str:
        sema = "https" if (a.baglanti_modu or "").lower() == "tor_https" else "http"
        return f'''#!/usr/bin/env python3
"""
Zihin Koprusu HTTP Ajanı
Uzuv: {a.uzuv_ad} ({a.uzuv_id})
Hedef: {hedef}
"""
import json
import os
import platform
import subprocess
import tempfile
import shutil
import socket
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UZUV_ID = "{a.uzuv_id}"
UZUV_AD = "{a.uzuv_ad}"
HTTP_HOST = "{a.http_host or '0.0.0.0'}"
HTTP_PORT = {a.http_port}
HTTP_TOKEN = "{a.http_token}"
SEMA = "{sema}"
BILDIRIM_URL = "{a.bildirim_url}"
BAGLANTI_YONTEMI = "{(a.baglanti_modu or 'tor_http').lower()}"

def _yerel_ip_bul() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return ""

def _hazir_bildir():
    if not BILDIRIM_URL:
        return
    try:
        veri = json.dumps({{
            "olay": "hazir",
            "uzuv_id": UZUV_ID,
            "uzuv_ad": UZUV_AD,
            "host": socket.gethostname(),
            "ip": _yerel_ip_bul(),
            "http_port": HTTP_PORT,
            "http_token": HTTP_TOKEN,
            "baglanti_yontemi": BAGLANTI_YONTEMI,
            "tip": platform.system().lower() or "http",
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
        }}).encode("utf-8")
        req = urllib.request.Request(
            BILDIRIM_URL.rstrip("/") + "/uzuv_bildir",
            data=veri,
            headers={{"Content-Type": "application/json"}},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15)
        print("[ZK] Merkeze hazir bildirimi gonderildi.")
    except Exception as exc:
        print(f"[ZK] Hazir bildirimi gonderilemedi: {{exc}}")

def _yetki(headers) -> bool:
    if not HTTP_TOKEN:
        return True
    return headers.get("X-ZK-Token", "") == HTTP_TOKEN

def _komut_calistir(komut: str) -> tuple[int, str]:
    kabuk = komut
    if platform.system().lower().startswith("win"):
        kabuk = f'powershell -Command "{{komut}}"'
    try:
        r = subprocess.run(
            kabuk,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            errors="replace",
        )
        cikti = (r.stdout + r.stderr).strip()
        return r.returncode, cikti or "Komut tamamlandi."
    except subprocess.TimeoutExpired:
        return 124, "Zaman asimi."
    except Exception as exc:
        return 500, f"Hata: {{exc}}"

def _ekran_goruntu_al() -> tuple[int, bytes, str]:
    if platform.system().lower().startswith("win"):
        fd, gecici = tempfile.mkstemp(prefix="zk_http_screen_", suffix=".png")
        os.close(fd)
        try:
            komut = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                "$bmp = New-Object System.Drawing.Bitmap "
                "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, "
                "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height; "
                "$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
                "$gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); "
                "$bmp.Save('{{gecici}}', [System.Drawing.Imaging.ImageFormat]::Png); "
                "$gfx.Dispose(); $bmp.Dispose()"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", komut],
                capture_output=True,
                timeout=30,
                text=True,
                errors="replace",
            )
            if r.returncode == 0 and os.path.exists(gecici) and os.path.getsize(gecici) > 0:
                with open(gecici, "rb") as f:
                    return 200, f.read(), "image/png"
        except Exception:
            pass
        finally:
            try:
                os.unlink(gecici)
            except OSError:
                pass

    adaylar = []
    if shutil.which("gnome-screenshot"):
        adaylar.append(["gnome-screenshot", "-f"])
    if shutil.which("scrot"):
        adaylar.append(["scrot"])
    if shutil.which("import"):
        adaylar.append(["import", "-window", "root"])
    if os.path.exists("/system/bin/screencap") or shutil.which("screencap"):
        adaylar.append(["screencap", "-p"])
    for taban in adaylar:
        fd, gecici = tempfile.mkstemp(prefix="zk_http_screen_", suffix=".png")
        os.close(fd)
        try:
            cmd = list(taban) + [gecici]
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode == 0 and os.path.exists(gecici) and os.path.getsize(gecici) > 0:
                with open(gecici, "rb") as f:
                    return 200, f.read(), "image/png"
        except Exception:
            pass
        finally:
            try:
                os.unlink(gecici)
            except OSError:
                pass
    return 500, b"Ekran goruntusu alinamadi.", "text/plain; charset=utf-8"

class ZKAjan(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, kod: int, veri: dict):
        icerik = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(icerik)))
        self.end_headers()
        self.wfile.write(icerik)

    def _raw(self, kod: int, icerik: bytes, tur: str):
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(icerik)))
        self.end_headers()
        self.wfile.write(icerik)

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/", "/health"):
            self._json(200, {{
                "durum": "ok",
                "uzuv_id": UZUV_ID,
                "uzuv_ad": UZUV_AD,
                "platform": platform.platform(),
                "sema": SEMA,
                "ip": _yerel_ip_bul(),
                "http_port": HTTP_PORT,
            }})
            return
        if self.path.rstrip("/") == "/ekran":
            kod, icerik, tur = _ekran_goruntu_al()
            self._raw(kod, icerik, tur)
            return
        self._json(404, {{"durum": "hata", "mesaj": "Yol bulunamadi"}})

    def do_POST(self):
        if not _yetki(self.headers):
            self._json(403, {{"durum": "hata", "mesaj": "Yetkisiz"}})
            return
        if self.path.rstrip("/") != "/komut":
            self._json(404, {{"durum": "hata", "mesaj": "Yol bulunamadi"}})
            return
        try:
            uzunluk = int(self.headers.get("Content-Length", "0"))
            ham = self.rfile.read(uzunluk).decode("utf-8") if uzunluk else "{{}}"
            veri = json.loads(ham or "{{}}")
            komut = (veri.get("komut") or "").strip()
            if not komut:
                self._json(400, {{"durum": "hata", "mesaj": "Komut bos"}})
                return
            kod, sonuc = _komut_calistir(komut)
            self._json(200, {{
                "durum": "ok" if kod == 0 else "hata",
                "returncode": kod,
                "sonuc": sonuc,
                "uzuv_id": UZUV_ID,
            }})
        except Exception as exc:
            self._json(500, {{"durum": "hata", "mesaj": str(exc)}})

def main():
    sunucu = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), ZKAjan)
    print(f"[ZK] HTTP ajan basladi: {{HTTP_HOST}}:{{HTTP_PORT}} | uzuv={{UZUV_AD}}")
    _hazir_bildir()
    sunucu.serve_forever()

if __name__ == "__main__":
    main()
'''

    def _telegram_ajan_python(self, a: IstemciAyar, hedef: str) -> str:
        return f'''#!/usr/bin/env python3
"""
Zihin Koprusu Telegram Uzuv Ajani
Uzuv: {a.uzuv_ad} ({a.uzuv_id})
Hedef: {hedef}
"""
import asyncio
import os
import platform
import re
import shutil
import subprocess
import tempfile

from telethon import TelegramClient, events

UZUV_ID = "{a.uzuv_id}"
UZUV_AD = "{a.uzuv_ad}"
API_ID = {a.telegram_api_id or 0}
API_HASH = "{a.telegram_api_hash}"
SESSION = "{a.telegram_session or a.uzuv_id}"
CHAT = "{a.telegram_chat}"

TASK_RE = re.compile(r"ZK_TASK\\|(?P<gorev_id>[^|]+)\\|(?P<uzuv_id>[^|]+)\\|(?P<tur>[a-z_]+)")

def _komut_calistir(komut: str) -> tuple[bool, str]:
    try:
        kabuk = komut
        if platform.system().lower().startswith("win"):
            kabuk = f'powershell -Command "{{komut}}"'
        r = subprocess.run(kabuk, shell=True, capture_output=True, text=True, timeout=60, errors="replace")
        cikti = (r.stdout + r.stderr).strip() or "Komut tamamlandi."
        return r.returncode == 0, cikti[:3000]
    except Exception as exc:
        return False, f"Hata: {{exc}}"

def _ekran_goruntu_al() -> str:
    if platform.system().lower().startswith("win"):
        fd, gecici = tempfile.mkstemp(prefix="zk_tg_screen_", suffix=".png")
        os.close(fd)
        komut = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$bmp = New-Object System.Drawing.Bitmap "
            "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, "
            "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height; "
            "$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
            "$gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); "
            f"$bmp.Save('{{gecici}}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$gfx.Dispose(); $bmp.Dispose()"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", komut], capture_output=True, timeout=30)
        return gecici if r.returncode == 0 and os.path.exists(gecici) else ""
    adaylar = []
    if shutil.which("gnome-screenshot"):
        adaylar.append(["gnome-screenshot", "-f"])
    if shutil.which("scrot"):
        adaylar.append(["scrot"])
    if shutil.which("import"):
        adaylar.append(["import", "-window", "root"])
    if os.path.exists("/system/bin/screencap") or shutil.which("screencap"):
        adaylar.append(["screencap", "-p"])
    for taban in adaylar:
        fd, gecici = tempfile.mkstemp(prefix="zk_tg_screen_", suffix=".png")
        os.close(fd)
        try:
            r = subprocess.run(list(taban) + [gecici], capture_output=True, timeout=30)
            if r.returncode == 0 and os.path.exists(gecici) and os.path.getsize(gecici) > 0:
                return gecici
        except Exception:
            pass
        try:
            os.unlink(gecici)
        except OSError:
            pass
    return ""

async def main():
    if not API_ID or not API_HASH or not CHAT:
        raise SystemExit("API_ID, API_HASH ve CHAT tanimli olmali.")
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    print(f"[ZK] Telegram ajan basladi | uzuv={{UZUV_ID}}")

    @client.on(events.NewMessage(chats=CHAT))
    async def handler(event):
        metin = event.raw_text or ""
        es = TASK_RE.search(metin)
        if not es:
            return
        if es.group("uzuv_id") != UZUV_ID:
            return
        gorev_id = es.group("gorev_id")
        tur = es.group("tur")
        if tur == "komut":
            km = re.search(r"Komut:\\s*`([^`]+)`", metin)
            if not km:
                return
            ok, sonuc = _komut_calistir(km.group(1))
            durum = "ok" if ok else "hata"
            await client.send_message(CHAT, f"/uzuv_cevap {{gorev_id}} {{durum}} {{sonuc}}")
        elif tur == "ekran":
            yol = _ekran_goruntu_al()
            if yol and os.path.exists(yol):
                try:
                    await client.send_file(CHAT, yol, caption=f"/uzuv_ekran_cevap {{gorev_id}}")
                finally:
                    try:
                        os.unlink(yol)
                    except OSError:
                        pass
            else:
                await client.send_message(CHAT, f"/uzuv_cevap {{gorev_id}} hata ekran_alinamadi")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
'''

    def _linux_telegram_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}_telegram.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_telegram.sh")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}_telegram.sh")
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(self._telegram_ajan_python(a, "Linux Telegram Ajan"))
        os.chmod(py_dosya, 0o755)
        sh_kod = f'''#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PY_DOSYA="${{SCRIPT_DIR}}/zk_{a.uzuv_id}_telegram.py"
SERVIS_ADI="zk-telegram-{a.uzuv_id}"
python3 --version >/dev/null 2>&1 || {{ echo "Python 3 gerekli"; exit 1; }}
python3 -m pip install --user --upgrade telethon
chmod +x "$PY_DOSYA"
sudo tee /etc/systemd/system/${{SERVIS_ADI}}.service >/dev/null << EOF
[Unit]
Description=Zihin Koprusu Telegram Ajan - {a.uzuv_ad}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
ExecStart=/usr/bin/python3 ${{PY_DOSYA}}
Restart=always
RestartSec=10
WorkingDirectory=${{SCRIPT_DIR}}

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now ${{SERVIS_ADI}}
echo "[ZK] Telegram ajan kuruldu: ${{SERVIS_ADI}}"
'''
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(sh_kod)
        os.chmod(sh_dosya, 0o755)
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(f'''#!/bin/bash
set -e
SERVIS_ADI="zk-telegram-{a.uzuv_id}"
sudo systemctl disable --now ${{SERVIS_ADI}} >/dev/null 2>&1 || true
sudo rm -f /etc/systemd/system/${{SERVIS_ADI}}.service
sudo systemctl daemon-reload
echo "[ZK] Telegram ajan kaldirildi: ${{SERVIS_ADI}}"
''')
        os.chmod(kaldir_dosya, 0o755)
        return [py_dosya, sh_dosya, kaldir_dosya]

    def _mac_telegram_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}_telegram.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_telegram_macos.sh")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}_telegram_macos.sh")
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(self._telegram_ajan_python(a, "macOS Telegram Ajan"))
        os.chmod(py_dosya, 0o755)
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(self._mac_launchd_sh(
                a, os.path.basename(py_dosya), "telegram",
                "macOS Telegram ajan", "telethon"
            ))
        os.chmod(sh_dosya, 0o755)
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(self._mac_launchd_kaldir_sh(a, "telegram"))
        os.chmod(kaldir_dosya, 0o755)
        return [py_dosya, sh_dosya, kaldir_dosya]

    def _windows_telegram_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}_telegram.py")
        bat_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_telegram.bat")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}_telegram.bat")
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(self._telegram_ajan_python(a, "Windows Telegram Ajan"))
        servis = f"ZK-Telegram-{a.uzuv_id}"
        bat_kod = self._windows_task_bat(
            servis,
            f'python "%~dp0zk_{a.uzuv_id}_telegram.py"',
            f"Telegram ajan kurulumu - {a.uzuv_ad}",
            [
                "python --version >nul 2>&1 || (echo [HATA] Python bulunamadi.& pause & exit /b 1)",
                "python -m pip install --upgrade telethon",
            ],
        )
        with open(bat_dosya, "w", encoding="utf-8") as f:
            f.write(bat_kod)
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(self._windows_task_kaldir_bat(servis))
        return [py_dosya, bat_dosya, kaldir_dosya]

    def _android_telegram_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}_telegram.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_telegram_termux.sh")
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(self._telegram_ajan_python(a, "Android / Termux Telegram Ajan"))
        os.chmod(py_dosya, 0o755)
        sh_kod = f'''#!/data/data/com.termux/files/usr/bin/bash
pkg install -y python
pip install telethon
chmod +x "$(dirname "$0")/zk_{a.uzuv_id}_telegram.py"
echo "[ZK] Telegram ajan baslatiliyor..."
python3 "$(dirname "$0")/zk_{a.uzuv_id}_telegram.py"
'''
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(sh_kod)
        os.chmod(sh_dosya, 0o755)
        return [py_dosya, sh_dosya]

    def _linux_http_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}_http.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_http.sh")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}_http.sh")
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(self._http_ajan_python(a, "Linux HTTP Ajan"))
        os.chmod(py_dosya, 0o755)
        sh_kod = f'''#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PY_DOSYA="${{SCRIPT_DIR}}/zk_{a.uzuv_id}_http.py"
python3 --version >/dev/null 2>&1 || {{ echo "Python 3 gerekli"; exit 1; }}
chmod +x "$PY_DOSYA"
SERVIS_ADI="zk-http-{a.uzuv_id}"
sudo tee /etc/systemd/system/${{SERVIS_ADI}}.service >/dev/null << EOF
[Unit]
Description=Zihin Koprusu HTTP Ajan - {a.uzuv_ad}
After=network.target

[Service]
Type=simple
User=$(whoami)
ExecStart=/usr/bin/python3 ${{PY_DOSYA}}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now ${{SERVIS_ADI}}
echo "[ZK] HTTP ajan kuruldu: http://{a.http_host or '0.0.0.0'}:{a.http_port}"
'''
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(sh_kod)
        os.chmod(sh_dosya, 0o755)
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(f'''#!/bin/bash
set -e
SERVIS_ADI="zk-http-{a.uzuv_id}"
sudo systemctl disable --now ${{SERVIS_ADI}} >/dev/null 2>&1 || true
sudo rm -f /etc/systemd/system/${{SERVIS_ADI}}.service
sudo systemctl daemon-reload
echo "[ZK] HTTP ajan kaldirildi: ${{SERVIS_ADI}}"
''')
        os.chmod(kaldir_dosya, 0o755)
        return [py_dosya, sh_dosya, kaldir_dosya]

    def _mac_http_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}_http.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_http_macos.sh")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}_http_macos.sh")
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(self._http_ajan_python(a, "macOS HTTP Ajan"))
        os.chmod(py_dosya, 0o755)
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(self._mac_launchd_sh(
                a, os.path.basename(py_dosya), "http",
                "macOS HTTP ajan"
            ))
        os.chmod(sh_dosya, 0o755)
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(self._mac_launchd_kaldir_sh(a, "http"))
        os.chmod(kaldir_dosya, 0o755)
        return [py_dosya, sh_dosya, kaldir_dosya]

    def _windows_http_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}_http.py")
        bat_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_http.bat")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}_http.bat")
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(self._http_ajan_python(a, "Windows HTTP Ajan"))
        servis = f"ZK-HTTP-{a.uzuv_id}"
        bat_kod = self._windows_task_bat(
            servis,
            f'python "%~dp0zk_{a.uzuv_id}_http.py"',
            f"HTTP ajan kurulumu - {a.uzuv_ad}",
            ["python --version >nul 2>&1 || (echo [HATA] Python bulunamadi.& pause & exit /b 1)"],
        )
        with open(bat_dosya, "w", encoding="utf-8") as f:
            f.write(bat_kod)
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(self._windows_task_kaldir_bat(servis))
        return [py_dosya, bat_dosya, kaldir_dosya]

    def _android_http_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}_http.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_http_termux.sh")
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(self._http_ajan_python(a, "Android / Termux HTTP Ajan"))
        os.chmod(py_dosya, 0o755)
        sh_kod = f'''#!/data/data/com.termux/files/usr/bin/bash
pkg install -y python
chmod +x "$(dirname "$0")/zk_{a.uzuv_id}_http.py"
echo "[ZK] HTTP ajan baslatiliyor..."
python3 "$(dirname "$0")/zk_{a.uzuv_id}_http.py"
'''
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(sh_kod)
        os.chmod(sh_dosya, 0o755)
        return [py_dosya, sh_dosya]

    # ─────────────────────────────────────────────────────────────────────────
    # LINUX İSTEMCİSİ
    # ─────────────────────────────────────────────────────────────────────────

    def _linux_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}.sh")
        merkez_host = self._merkez_host(a) or "MERKEZ_ADRESI_GIRIN"
        merkez_port = self._merkez_port(a)
        merkez_etiket = self._merkez_etiketi(a)
        tor_gerekli = self._tor_gerekli_mi(a)
        py_proxy = '        "-o", f"ProxyCommand=nc -x {TOR_PROXY} %h %p",\n' if tor_gerekli else ""
        tor_sabit = f'TOR_PROXY    = "{a.tor_proxy}"' if tor_gerekli else 'TOR_PROXY    = ""'
        tor_fonksiyon = '''
# ── Tor Kontrolü ───────────────────────────────────────────────────────────
def tor_calisiyor_mu() -> bool:
    try:
        import socket as _s
        s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 9050))
        s.close()
        return True
    except Exception:
        return False

def tor_hazirla() -> bool:
    if not shutil.which("tor"):
        print("[ZK] Tor kurulu değil, kuruluyor...")
        ret = subprocess.run(
            ["sudo", "apt-get", "install", "-y", "tor", "netcat-openbsd"],
            capture_output=True
        )
        if ret.returncode != 0:
            print("[ZK] Tor kurulamadı! Lütfen manuel kurun: sudo apt install tor")
            return False
    if not tor_calisiyor_mu():
        print("[ZK] Tor başlatılıyor...")
        subprocess.run(["sudo", "systemctl", "enable", "--now", "tor"],
                       capture_output=True)
        for _ in range(15):
            time.sleep(2)
            if tor_calisiyor_mu():
                print("[ZK] Tor hazır.")
                return True
        print("[ZK] Tor başlatılamadı!")
        return False
    return True
''' if tor_gerekli else '''
def tor_hazirla() -> bool:
    return True
'''
        sh_paketler = "tor netcat-openbsd openssh-client" if tor_gerekli else "openssh-client"
        servis_sonrasi = "After=network.target tor.service\nWants=tor.service" if tor_gerekli else "After=network.target"
        tor_kurulum = '''
# Tor servisi
bilgi "Tor başlatılıyor..."
sudo systemctl enable tor --now 2>/dev/null || true
sleep 3
tamam "Tor yapılandırıldı."
''' if tor_gerekli else ""

        # ── Python istemci ────────────────────────────────────────────────────
        py_kod = f'''#!/usr/bin/env python3
"""
Zihin Köprüsü İstemcisi — {a.uzuv_ad} ({a.uzuv_id})
Hedef : Linux / Mac
Merkez: {merkez_etiket}

Bu dosya otomatik üretilmiştir.
"""
import subprocess, time, os, sys, socket, json, threading, shutil

SUNUCU_HOST  = "{merkez_host}"
SUNUCU_PORT  = {merkez_port}
KULLANICI    = "{a.ssh_kullanici}"
ANAHTAR      = "{a.ssh_anahtar}"
{tor_sabit}
YEREL_PORT   = 2222          # Sunucunun dinleyeceği ters-tünel portu
BILDIRIM_URL = "{a.bildirim_url}"
UZUV_ID      = "{a.uzuv_id}"
UZUV_AD      = "{a.uzuv_ad}"
{tor_fonksiyon}

# ── Sunucuya Bildirim ──────────────────────────────────────────────────────
def hazir_bildir():
    """Kurulum tamamlandı — sunucuya hazırım bildirimi gönder."""
    if not BILDIRIM_URL:
        print("[ZK] Bildirim URL tanımlı değil, atlanıyor.")
        return
    try:
        import urllib.request
        veri = json.dumps({{
            "olay":    "hazir",
            "uzuv_id": UZUV_ID,
            "uzuv_ad": UZUV_AD,
            "host":    socket.gethostname(),
            "ip":      socket.gethostbyname(socket.gethostname()),
            "zaman":   time.strftime("%Y-%m-%d %H:%M:%S"),
        }}).encode("utf-8")
        req = urllib.request.Request(
            BILDIRIM_URL.rstrip("/") + "/uzuv_bildir",
            data=veri,
            headers={{"Content-Type": "application/json"}},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=15)
        print("[ZK] Sunucuya 'hazırım' bildirimi gönderildi.")
    except Exception as exc:
        print(f"[ZK] Bildirim gönderilemedi: {{exc}}")

# ── SSH Ters Tünel ─────────────────────────────────────────────────────────
def baglan() -> subprocess.Popen:
    args = [
        "ssh", "-N", "-R",
        f"{{YEREL_PORT}}:localhost:{a.yerel_ssh_port}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ExitOnForwardFailure=yes",
        "-p", str(SUNUCU_PORT),
{py_proxy}    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{{KULLANICI}}@{{SUNUCU_HOST}}")
    return subprocess.Popen(args)

# ── Ana Döngü ──────────────────────────────────────────────────────────────
def main():
    print(f"[ZK] Zihin Köprüsü istemcisi başlıyor — {{UZUV_AD}} ({{UZUV_ID}})")

    if not tor_hazirla():
        print("[ZK] Gerekli bağlantı servisi hazırlanamadı.")
        sys.exit(1)

    # İlk bağlantı kurulduktan sonra bildir
    bildirim_gonderildi = False

    while True:
        print("[ZK] SSH tüneliyle bağlanıyor...")
        proc = baglan()

        if not bildirim_gonderildi:
            time.sleep(3)           # Tünel kurulmasını bekle
            hazir_bildir()
            bildirim_gonderildi = True

        proc.wait()
        print("[ZK] Bağlantı kesildi. 15 saniye sonra yeniden denenecek...")
        time.sleep(15)

if __name__ == "__main__":
    main()
'''
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(py_kod)
        os.chmod(py_dosya, 0o755)

        # ── Kurulum betiği ────────────────────────────────────────────────────
        sh_kod = f'''#!/bin/bash
# ──────────────────────────────────────────────────────────
# Zihin Köprüsü — Linux İstemci Kurulumu
# Uzuv: {a.uzuv_ad} ({a.uzuv_id})
# Merkez: {merkez_etiket}
# ──────────────────────────────────────────────────────────
set -e

YESIL=\'\\033[0;32m\'; MAVI=\'\\033[0;36m\'; KIRMIZI=\'\\033[0;31m\'; SIFIR=\'\\033[0m\'
tamam()  {{ echo -e "${{YESIL}}[✓]${{SIFIR}} $1"; }}
bilgi()  {{ echo -e "${{MAVI}}[*]${{SIFIR}} $1"; }}
hata()   {{ echo -e "${{KIRMIZI}}[✗]${{SIFIR}} $1"; exit 1; }}

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PY_DOSYA="${{SCRIPT_DIR}}/zk_{a.uzuv_id}.py"

echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   ZİHİN KÖPRÜSÜ — İSTEMCİ KURULUMU       ║"
echo "  ║   {a.uzuv_ad:<41}║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""

# Python kontrolü
bilgi "Python kontrol ediliyor..."
python3 --version &>/dev/null || hata "Python 3 bulunamadı."
tamam "Python bulundu."

# Bağımlılıklar
bilgi "Sistem paketleri kontrol ediliyor..."
sudo apt-get install -y -qq {sh_paketler} 2>/dev/null || {{
    echo "Paket kurulumu başarısız, devam ediliyor..."
}}
tamam "Paketler hazır."
{tor_kurulum}

# Dosya izni
chmod +x "$PY_DOSYA"

# Systemd servis (otomatik başlatma)
bilgi "Systemd servisi oluşturuluyor..."
SERVIS_ADI="zk-istemci-{a.uzuv_id}"
KULLANICI="$(whoami)"

sudo tee /etc/systemd/system/${{SERVIS_ADI}}.service > /dev/null << EOF
[Unit]
Description=Zihin Koprusu Istemci — {a.uzuv_ad}
{servis_sonrasi}

[Service]
Type=simple
User=${{KULLANICI}}
ExecStart=/usr/bin/python3 ${{PY_DOSYA}}
Restart=always
RestartSec=20
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ${{SERVIS_ADI}}
tamam "Servis kuruldu ve başlatıldı: ${{SERVIS_ADI}}"

echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║       KURULUM TAMAMLANDI! ✓               ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""
bilgi "Durumu kontrol et: sudo systemctl status ${{SERVIS_ADI}}"
bilgi "Logları gör:       sudo journalctl -u ${{SERVIS_ADI}} -f"
bilgi "Durdur:            sudo systemctl stop ${{SERVIS_ADI}}"
echo ""
'''
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(sh_kod)
        os.chmod(sh_dosya, 0o755)

        return [py_dosya, sh_dosya]

    def _mac_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_macos.sh")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}_macos.sh")
        merkez_host = self._merkez_host(a) or "MERKEZ_ADRESI_GIRIN"
        merkez_port = self._merkez_port(a)
        merkez_etiket = self._merkez_etiketi(a)
        tor_gerekli = self._tor_gerekli_mi(a)
        py_proxy = '        "-o", f"ProxyCommand=nc -x {TOR_PROXY} %h %p",\n' if tor_gerekli else ""
        tor_sabit = f'TOR_PROXY    = "{a.tor_proxy}"' if tor_gerekli else 'TOR_PROXY    = ""'
        tor_fonksiyon = '''
def tor_hazirla() -> bool:
    try:
        import socket as _s
        s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 9050))
        s.close()
        return True
    except Exception:
        print("[ZK] Tor proxy 127.0.0.1:9050 ulasilamiyor. Tor Browser veya tor servisini acin.")
        return False
''' if tor_gerekli else '''
def tor_hazirla() -> bool:
    return True
'''
        py_kod = f'''#!/usr/bin/env python3
"""
Zihin Koprusu macOS SSH Reverse Ajan
Uzuv: {a.uzuv_ad} ({a.uzuv_id})
Merkez: {merkez_etiket}
"""
import json
import socket
import subprocess
import sys
import time
import urllib.request

SUNUCU_HOST  = "{merkez_host}"
SUNUCU_PORT  = {merkez_port}
KULLANICI    = "{a.ssh_kullanici}"
ANAHTAR      = "{a.ssh_anahtar}"
{tor_sabit}
YEREL_PORT   = 2222
BILDIRIM_URL = "{a.bildirim_url}"
UZUV_ID      = "{a.uzuv_id}"
UZUV_AD      = "{a.uzuv_ad}"
{tor_fonksiyon}

def hazir_bildir():
    if not BILDIRIM_URL:
        return
    try:
        veri = json.dumps({{
            "olay": "hazir",
            "uzuv_id": UZUV_ID,
            "uzuv_ad": UZUV_AD,
            "host": socket.gethostname(),
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tip": "mac",
        }}).encode("utf-8")
        req = urllib.request.Request(
            BILDIRIM_URL.rstrip("/") + "/uzuv_bildir",
            data=veri,
            headers={{"Content-Type": "application/json"}},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15)
        print("[ZK] Merkeze hazir bildirimi gonderildi.")
    except Exception as exc:
        print(f"[ZK] Bildirim gonderilemedi: {{exc}}")

def baglan() -> subprocess.Popen:
    args = [
        "ssh", "-N", "-R", f"{{YEREL_PORT}}:localhost:{a.yerel_ssh_port}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ExitOnForwardFailure=yes",
        "-p", str(SUNUCU_PORT),
{py_proxy}    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{{KULLANICI}}@{{SUNUCU_HOST}}")
    return subprocess.Popen(args)

def main():
    print(f"[ZK] macOS ajan basliyor: {{UZUV_AD}}")
    if not tor_hazirla():
        sys.exit(1)
    bildirildi = False
    while True:
        proc = baglan()
        if not bildirildi:
            time.sleep(3)
            hazir_bildir()
            bildirildi = True
        proc.wait()
        print("[ZK] Baglanti kesildi. 15 saniye sonra yeniden denenecek.")
        time.sleep(15)

if __name__ == "__main__":
    main()
'''
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(py_kod)
        os.chmod(py_dosya, 0o755)
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(self._mac_launchd_sh(
                a, os.path.basename(py_dosya), "ssh",
                "macOS SSH reverse ajan"
            ))
        os.chmod(sh_dosya, 0o755)
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(self._mac_launchd_kaldir_sh(a, "ssh"))
        os.chmod(kaldir_dosya, 0o755)
        return [py_dosya, sh_dosya, kaldir_dosya]

    # ─────────────────────────────────────────────────────────────────────────
    # WINDOWS İSTEMCİSİ
    # ─────────────────────────────────────────────────────────────────────────

    def _windows_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}.py")
        bat_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}.bat")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}.bat")
        merkez_host = self._merkez_host(a) or "MERKEZ_ADRESI_GIRIN"
        merkez_port = self._merkez_port(a)
        merkez_etiket = self._merkez_etiketi(a)
        tor_gerekli = self._tor_gerekli_mi(a)
        tor_sabit = f'TOR_PROXY    = "{a.tor_proxy}"' if tor_gerekli else 'TOR_PROXY    = ""'
        py_proxy = '        "-o", f"ProxyCommand={nc_cmd} -x {TOR_PROXY} %h %p",\n' if tor_gerekli else ""
        tor_yardim = (
            '    if not tor_calisiyor_mu():\n'
            '        print("[ZK] UYARI: Tor çalışmıyor. Lütfen Tor Browser veya Expert Bundle başlatın.")\n'
            '        print("[ZK]        İndirme: https://www.torproject.org/download/tor/")\n'
            '        time.sleep(10)\n'
        ) if tor_gerekli else ""
        tor_fonksiyon = '''
def tor_calisiyor_mu() -> bool:
    try:
        import socket as _s
        s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 9050))
        s.close()
        return True
    except Exception:
        return False
''' if tor_gerekli else ""
        bat_tor_yardim = (
            "echo [*] Tor Browser veya Expert Bundle calisiyor mu kontrol ediliyor...\r\n"
            "echo [!] Eger Tor calismiyorsa lutfen Tor Browser'i acin veya:\r\n"
            "echo     https://www.torproject.org/download/tor/ adresinden Expert Bundle indirin.\r\n"
            "echo.\r\n"
        ) if tor_gerekli else ""

        py_kod = f'''#!/usr/bin/env python3
"""
Zihin Köprüsü İstemcisi — {a.uzuv_ad} ({a.uzuv_id})
Hedef : Windows 10/11
Gereksinim: Python 3.10+ , OpenSSH (Windows özellik olarak){", Tor Browser veya Expert Bundle" if tor_gerekli else ""}

Merkez: {merkez_etiket}
Bu dosya otomatik üretilmiştir.
"""
import subprocess, time, os, sys, socket, json, shutil

SUNUCU_HOST  = "{merkez_host}"
SUNUCU_PORT  = {merkez_port}
KULLANICI    = "{a.ssh_kullanici}"
ANAHTAR      = r"{a.ssh_anahtar}"
{tor_sabit}
YEREL_PORT   = 2222
BILDIRIM_URL = "{a.bildirim_url}"
UZUV_ID      = "{a.uzuv_id}"
UZUV_AD      = "{a.uzuv_ad}"
{tor_fonksiyon}

def hazir_bildir():
    if not BILDIRIM_URL:
        return
    try:
        import urllib.request
        veri = json.dumps({{
            "olay": "hazir", "uzuv_id": UZUV_ID,
            "uzuv_ad": UZUV_AD, "host": socket.gethostname(),
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
        }}).encode("utf-8")
        req = urllib.request.Request(
            BILDIRIM_URL.rstrip("/") + "/uzuv_bildir",
            data=veri,
            headers={{"Content-Type": "application/json"}},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=15)
        print("[ZK] Sunucuya hazirım bildirimi gönderildi.")
    except Exception as e:
        print(f"[ZK] Bildirim hatası: {{e}}")

def baglan() -> subprocess.Popen:
    nc_cmd = "nc"
    if TOR_PROXY:
        for candidate in ["nc", "ncat"]:
            if shutil.which(candidate):
                nc_cmd = candidate
                break

    args = [
        "ssh", "-N", "-R", f"{{YEREL_PORT}}:localhost:22",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-p", str(SUNUCU_PORT),
{py_proxy}    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{{KULLANICI}}@{{SUNUCU_HOST}}")
    return subprocess.Popen(args, creationflags=0x08000000)

def main():
    print(f"[ZK] Windows istemcisi başlıyor — {{UZUV_AD}}")
{tor_yardim}

    bildirim_gonderildi = False
    while True:
        print("[ZK] Bağlanıyor...")
        proc = baglan()
        if not bildirim_gonderildi:
            time.sleep(3)
            hazir_bildir()
            bildirim_gonderildi = True
        proc.wait()
        print("[ZK] Yeniden bağlanıyor (15s)...")
        time.sleep(15)

if __name__ == "__main__":
    main()
'''
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(py_kod)

        servis = f"ZK-SSH-{a.uzuv_id}"
        bat_kod = self._windows_task_bat(
            servis,
            f'python "%~dp0zk_{a.uzuv_id}.py"',
            f"Windows SSH ajan kurulumu - {a.uzuv_ad}",
            [
                "python --version >nul 2>&1 || (echo [HATA] Python bulunamadi. https://python.org adresinden indirin.& pause & exit /b 1)",
                "where ssh >nul 2>&1 || (echo [HATA] OpenSSH bulunamadi. Windows Ozellikleri > OpenSSH Client etkinlestirin.& pause & exit /b 1)",
                bat_tor_yardim.rstrip(),
            ] if bat_tor_yardim else [
                "python --version >nul 2>&1 || (echo [HATA] Python bulunamadi. https://python.org adresinden indirin.& pause & exit /b 1)",
                "where ssh >nul 2>&1 || (echo [HATA] OpenSSH bulunamadi. Windows Ozellikleri > OpenSSH Client etkinlestirin.& pause & exit /b 1)",
            ],
        )
        with open(bat_dosya, "w", encoding="utf-8") as f:
            f.write(bat_kod)
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(self._windows_task_kaldir_bat(servis))

        return [py_dosya, bat_dosya, kaldir_dosya]

    # ─────────────────────────────────────────────────────────────────────────
    # ANDROID / TERMUX İSTEMCİSİ
    # ─────────────────────────────────────────────────────────────────────────

    def _android_istemci(self, a: IstemciAyar, klasor: str) -> list[str]:
        py_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}.py")
        sh_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_termux.sh")
        merkez_host = self._merkez_host(a) or "MERKEZ_ADRESI_GIRIN"
        merkez_port = self._merkez_port(a)
        merkez_etiket = self._merkez_etiketi(a)
        tor_gerekli = self._tor_gerekli_mi(a)
        tor_sabit = 'TOR_PROXY    = "127.0.0.1:9050"' if tor_gerekli else 'TOR_PROXY    = ""'
        py_proxy = '        "-o", f"ProxyCommand=nc -x {TOR_PROXY} %h %p",\n' if tor_gerekli else ""
        tor_fonksiyon = '''
def tor_calisiyor_mu() -> bool:
    try:
        import socket as _s
        s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 9050))
        s.close()
        return True
    except Exception:
        return False

def tor_hazirla() -> bool:
    if not shutil.which("tor"):
        print("[ZK] Tor kuruluyor (Termux)...")
        ret = subprocess.run(["pkg", "install", "-y", "tor"], capture_output=True)
        if ret.returncode != 0:
            print("[ZK] Tor kurulamadı!")
            return False
    if not tor_calisiyor_mu():
        print("[ZK] Tor başlatılıyor...")
        subprocess.Popen(["tor"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(15):
            time.sleep(2)
            if tor_calisiyor_mu():
                print("[ZK] Tor hazır.")
                return True
        return False
    return True
''' if tor_gerekli else '''
def tor_hazirla() -> bool:
    return True
'''
        sh_paketler = "python openssh tor netcat-openbsd" if tor_gerekli else "python openssh"
        termux_kurulum = "pkg install python openssh torsocks tor" if tor_gerekli else "pkg install python openssh"

        py_kod = f'''#!/data/data/com.termux/files/usr/bin/python3
"""
Zihin Köprüsü İstemcisi — Android/Termux
Uzuv: {a.uzuv_ad} ({a.uzuv_id})
Merkez: {merkez_etiket}

Root GEREKMEZ — Termux SSH portu 8022'dir.
Termux kurulum: {termux_kurulum}
"""
import subprocess, time, os, sys, socket, json, shutil

SUNUCU_HOST  = "{merkez_host}"
SUNUCU_PORT  = {merkez_port}
KULLANICI    = "{a.ssh_kullanici}"
ANAHTAR      = "{a.ssh_anahtar}"
{tor_sabit}
YEREL_PORT   = 2222
BILDIRIM_URL = "{a.bildirim_url}"
UZUV_ID      = "{a.uzuv_id}"
UZUV_AD      = "{a.uzuv_ad}"
TERMUX_SSH_PORT = 8022     # Termux sshd varsayılan portu
{tor_fonksiyon}

def hazir_bildir():
    if not BILDIRIM_URL:
        return
    try:
        import urllib.request
        veri = json.dumps({{
            "olay": "hazir", "uzuv_id": UZUV_ID,
            "uzuv_ad": UZUV_AD, "host": socket.gethostname(),
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
        }}).encode("utf-8")
        req = urllib.request.Request(
            BILDIRIM_URL.rstrip("/") + "/uzuv_bildir",
            data=veri,
            headers={{"Content-Type": "application/json"}},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=15)
        print("[ZK] Sunucuya hazırım bildirimi gönderildi.")
    except Exception as e:
        print(f"[ZK] Bildirim hatası: {{e}}")

def sshd_baslat():
    """Termux SSH sunucusunu başlatır (8022 portu)."""
    try:
        subprocess.Popen(["sshd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        print("[ZK] Termux sshd başlatıldı (port 8022).")
    except Exception as e:
        print(f"[ZK] sshd başlatılamadı: {{e}}")

def baglan() -> subprocess.Popen:
    args = [
        "ssh", "-N", "-R",
        f"{{YEREL_PORT}}:localhost:{{TERMUX_SSH_PORT}}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ExitOnForwardFailure=yes",
        "-p", str(SUNUCU_PORT),
{py_proxy}    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{{KULLANICI}}@{{SUNUCU_HOST}}")
    return subprocess.Popen(args)

def main():
    print(f"[ZK] Termux istemcisi başlıyor — {{UZUV_AD}}")

    if not tor_hazirla():
        print("[ZK] Gerekli bağlantı servisi hazırlanamadı!")
        sys.exit(1)

    sshd_baslat()

    bildirim_gonderildi = False
    while True:
        print("[ZK] Bağlanıyor...")
        proc = baglan()
        if not bildirim_gonderildi:
            time.sleep(3)
            hazir_bildir()
            bildirim_gonderildi = True
        proc.wait()
        print("[ZK] Yeniden bağlanıyor (15s)...")
        time.sleep(15)

if __name__ == "__main__":
    main()
'''
        with open(py_dosya, "w", encoding="utf-8") as f:
            f.write(py_kod)
        os.chmod(py_dosya, 0o755)

        sh_kod = f'''#!/bin/bash
# Zihin Köprüsü — Termux Kurulum Betiği
# Uzuv: {a.uzuv_ad} ({a.uzuv_id})
echo "[ZK] Termux istemci kurulumu başlıyor..."

# Gerekli paketler
pkg install -y {sh_paketler}

# SSH anahtarı yoksa oluştur
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
    echo "[ZK] SSH anahtarı oluşturuldu."
    echo "[ZK] Sunucunuza şu açık anahtarı ekleyin:"
    cat ~/.ssh/id_rsa.pub
fi

# Otomatik başlatma (.bashrc)
ISTEMCI_YOL="$(cd "$(dirname "$0")" && pwd)/zk_{a.uzuv_id}.py"
BASHRC="$HOME/.bashrc"
if ! grep -q "zk_{a.uzuv_id}" "$BASHRC" 2>/dev/null; then
    echo "" >> "$BASHRC"
    echo "# Zihin Köprüsü istemcisi" >> "$BASHRC"
    echo "python3 $ISTEMCI_YOL &" >> "$BASHRC"
    echo "[ZK] Otomatik başlatma .bashrc'ye eklendi."
fi

chmod +x "$ISTEMCI_YOL"
echo "[ZK] Kurulum tamamlandı!"
echo "[ZK] Başlatmak için: python3 $ISTEMCI_YOL"
echo "[ZK] Termux'u yeniden başlatınca otomatik çalışır."
'''
        with open(sh_dosya, "w", encoding="utf-8") as f:
            f.write(sh_kod)
        os.chmod(sh_dosya, 0o755)

        return [py_dosya, sh_dosya]

    # ─────────────────────────────────────────────────────────────────────────
    # WINDOWS - Yalnizca .bat
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # WINDOWS - Yalnizca .bat (PowerShell/cmd, Python gerektirmez)
    # ─────────────────────────────────────────────────────────────────────────

    def _windows_bat_istemci(self, a: "IstemciAyar", klasor: str) -> list:
        bat_dosya = os.path.join(klasor, f"zk_{a.uzuv_id}.bat")
        kur_dosya = os.path.join(klasor, f"kur_{a.uzuv_id}_bat.bat")
        kaldir_dosya = os.path.join(klasor, f"kaldir_{a.uzuv_id}_bat.bat")
        merkez_host = self._merkez_host(a) or "MERKEZ_ADRESI_GIRIN"
        merkez_port = self._merkez_port(a)
        merkez_etiket = self._merkez_etiketi(a)
        tor_gerekli = self._tor_gerekli_mi(a)
        satirlar = [
            "@echo off",
            "REM Zihin Koprusu Windows .bat Istemci",
            f"REM Uzuv: {a.uzuv_ad} ({a.uzuv_id})",
            f"REM Merkez: {merkez_etiket}",
            "REM Gereksinim: OpenSSH (Win10+)" + (", Tor Expert Bundle" if tor_gerekli else ""),
            "",
            f"set SUNUCU={merkez_host}",
            f"set PORT={merkez_port}",
            f"set KULLANICI={a.ssh_kullanici}",
            f"set TOR_PROXY={a.tor_proxy if tor_gerekli else ''}",
            "set YEREL_PORT=2222",
            "",
            "echo [ZK] Baslaniyor...",
            "",
            ":DONGU",
            "echo [ZK] Baglaniliyor...",
            "ssh -N -R %YEREL_PORT%:localhost:22 ^",
            "    -o StrictHostKeyChecking=no ^",
            "    -o ServerAliveInterval=30 ^",
            "    -p %PORT% ^",
            "    %KULLANICI%@%SUNUCU%",
            "",
            "echo [ZK] Kesildi. 15 saniye bekleniyor...",
            "timeout /t 15 /nobreak >nul",
            "goto DONGU",
        ]
        if tor_gerekli:
            satirlar.insert(satirlar.index("    %KULLANICI%@%SUNUCU%"), '    -o "ProxyCommand=nc -x %TOR_PROXY% %%h %%p" ^')
        bat_kod = "\r\n".join(satirlar) + "\r\n"
        with open(bat_dosya, "w", encoding="utf-8") as f:
            f.write(bat_kod)
        servis = f"ZK-BAT-{a.uzuv_id}"
        with open(kur_dosya, "w", encoding="utf-8") as f:
            f.write(self._windows_task_bat(
                servis,
                f'cmd /c "%~dp0zk_{a.uzuv_id}.bat"',
                f"Windows BAT ajan kurulumu - {a.uzuv_ad}",
                ["where ssh >nul 2>&1 || (echo [HATA] OpenSSH bulunamadi. Windows Ozellikleri > OpenSSH Client etkinlestirin.& pause & exit /b 1)"],
            ))
        with open(kaldir_dosya, "w", encoding="utf-8") as f:
            f.write(self._windows_task_kaldir_bat(servis))
        self.log.bilgi("ISTEMCI", f"Windows .bat uretildi: {bat_dosya}")
        return [bat_dosya, kur_dosya, kaldir_dosya]

    # ─────────────────────────────────────────────────────────────────────────
    # WINDOWS - C++ (cmake ile derlenir)
    # ─────────────────────────────────────────────────────────────────────────

    def _windows_cpp_istemci(self, a: "IstemciAyar", klasor: str) -> list:
        merkez_host = self._merkez_host(a) or "MERKEZ_ADRESI_GIRIN"
        merkez_port = self._merkez_port(a)
        merkez_etiket = self._merkez_etiketi(a)
        tor_gerekli = self._tor_gerekli_mi(a)
        cpp_dosya   = os.path.join(klasor, f"zk_{a.uzuv_id}.cpp")
        cmake_dosya = os.path.join(klasor, "CMakeLists.txt")
        build_bat   = os.path.join(klasor, "derle.bat")
        kur_bat     = os.path.join(klasor, "kur_exe.bat")
        kaldir_bat  = os.path.join(klasor, "kaldir_exe.bat")

        cpp_satirlar = [
            "/* Zihin Koprusu C++ SSH Tunnel Client",
            f" * Uzuv: {a.uzuv_ad} ({a.uzuv_id})",
            f" * Merkez: {merkez_etiket}",
            " * Derle: cmake -B build && cmake --build build --config Release",
            " */",
            "#include <windows.h>",
            "#include <stdio.h>",
            '#pragma comment(lib, "ws2_32.lib")',
            "",
            f'#define SUNUCU_HOST  "{merkez_host}"',
            f"#define SUNUCU_PORT  {merkez_port}",
            f'#define KULLANICI    "{a.ssh_kullanici}"',
            "#define YEREL_PORT   2222",
            "#define SURE_MS      15000",
            "",
            "void baglan() {",
            "    char cmd[1024];",
            "    snprintf(cmd, sizeof(cmd),",
            '        "ssh -N -R %d:localhost:22 "',
            '        "-o StrictHostKeyChecking=no "',
            '        "-o ServerAliveInterval=30 "',
            '        "-p %d "',
            '        "%s@%s",',
            "        YEREL_PORT, SUNUCU_PORT, KULLANICI, SUNUCU_HOST);",
            "    system(cmd);",
            "}",
            "",
            "int main() {",
            '    printf("[ZK] C++ istemci basliyor...\\n");',
            "    while(1) { baglan(); Sleep(SURE_MS); }",
            "    return 0;",
            "}",
        ]
        if tor_gerekli:
            cpp_satirlar.insert(21, r'        "-o \"ProxyCommand=nc -x 127.0.0.1:9050 %%h %%p\" "')
        cmake_satirlar = [
            "cmake_minimum_required(VERSION 3.15)",
            "project(ZihinKoprusu)",
            f"add_executable(zk_{a.uzuv_id} zk_{a.uzuv_id}.cpp)",
            "target_link_libraries(zk_{} ws2_32)".format(a.uzuv_id),
        ]
        build_satirlar = [
            "@echo off",
            "echo Derleniyor...",
            "cmake -B build -DCMAKE_BUILD_TYPE=Release",
            "cmake --build build --config Release",
            f"if exist build\\Release\\zk_{a.uzuv_id}.exe (",
            "    echo BASARI: .exe hazirlandi.",
            f"    copy build\\Release\\zk_{a.uzuv_id}.exe .",
            ") else ( echo HATA: Derleme basarisiz. )",
            "pause",
        ]
        with open(cpp_dosya,   "w", encoding="utf-8") as f:
            f.write("\n".join(cpp_satirlar) + "\n")
        with open(cmake_dosya, "w", encoding="utf-8") as f:
            f.write("\n".join(cmake_satirlar) + "\n")
        with open(build_bat,   "w", encoding="utf-8") as f:
            f.write("\r\n".join(build_satirlar) + "\r\n")
        servis = f"ZK-EXE-{a.uzuv_id}"
        with open(kur_bat, "w", encoding="utf-8") as f:
            f.write(self._windows_task_bat(
                servis,
                f'"%~dp0zk_{a.uzuv_id}.exe"',
                f"Windows EXE ajan kurulumu - {a.uzuv_ad}",
                ["where ssh >nul 2>&1 || (echo [HATA] OpenSSH bulunamadi. Windows Ozellikleri > OpenSSH Client etkinlestirin.& pause & exit /b 1)"],
            ))
        with open(kaldir_bat, "w", encoding="utf-8") as f:
            f.write(self._windows_task_kaldir_bat(servis))
        self.log.bilgi("ISTEMCI", f"Windows C++ kaynak uretildi: {klasor}")
        return [cpp_dosya, cmake_dosya, build_bat, kur_bat, kaldir_bat]

    # ─────────────────────────────────────────────────────────────────────────
    # ANDROID - APK (Buildozer / Kivy)
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # ANDROID - APK (Buildozer otomatik derleme)
    # ─────────────────────────────────────────────────────────────────────────

    def _android_apk_istemci(self, a: "IstemciAyar", klasor: str) -> list:
        """Buildozer projesi oluştur ve APK'yı otomatik derle."""
        merkez_host = self._merkez_host(a) or "MERKEZ_ADRESI_GIRIN"
        merkez_port = self._merkez_port(a)
        main_py    = os.path.join(klasor, "main.py")
        spec_dosya = os.path.join(klasor, "buildozer.spec")

        satirlar_main = [
            "# -*- coding: utf-8 -*-",
            "from kivy.app import App",
            "from kivy.uix.boxlayout import BoxLayout",
            "from kivy.uix.label import Label",
            "from kivy.uix.button import Button",
            "from kivy.clock import Clock",
            "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer",
            "import subprocess, threading, socket, json, time",
            "",
            f'SUNUCU_HOST  = "{merkez_host}"',
            f"SUNUCU_PORT  = {merkez_port}",
            f'BILDIRIM_URL = "{a.bildirim_url}"',
            f'UZUV_ID      = "{a.uzuv_id}"',
            f'UZUV_AD      = "{a.uzuv_ad}"',
            f'HTTP_HOST    = "{a.http_host or "0.0.0.0"}"',
            f"HTTP_PORT    = {a.http_port or 8787}",
            f'HTTP_TOKEN   = "{a.http_token}"',
            f'BAGLANTI_TURU = "{(a.baglanti_modu or "tor_http").lower()}"',
            "SUNUCU = None",
            "",
            "def yerel_ip_bul():",
            "    try:",
            "        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)",
            "        s.connect((SUNUCU_HOST, SUNUCU_PORT if SUNUCU_PORT > 0 else 80))",
            "        ip = s.getsockname()[0]",
            "        s.close()",
            "        return ip",
            "    except Exception:",
            "        try:",
            "            return socket.gethostbyname(socket.gethostname())",
            "        except Exception:",
            "            return ''",
            "",
            "def hazir_bildir():",
            "    if not BILDIRIM_URL: return",
            "    try:",
            "        import urllib.request",
            '        veri = json.dumps({"olay":"hazir","uzuv_id":UZUV_ID,',
            '            "uzuv_ad":UZUV_AD,"host":socket.gethostname(),',
            '            "ip":yerel_ip_bul(),"http_port":HTTP_PORT,',
            '            "http_token":HTTP_TOKEN,"baglanti_yontemi":"tor_http","tip":"android"}).encode()',
            "        req = urllib.request.Request(",
            '            BILDIRIM_URL.rstrip("/")+"/uzuv_bildir",',
            '            data=veri,headers={"Content-Type":"application/json"},method="POST")',
            "        urllib.request.urlopen(req, timeout=15)",
            "    except Exception as e: print(f'Bildirim: {e}')",
            "",
            "def komut_calistir(komut):",
            "    try:",
            "        r = subprocess.run(komut, shell=True, capture_output=True, text=True, timeout=45)",
            "        cikti = (r.stdout + r.stderr).strip() or 'Komut tamamlandi.'",
            "        return r.returncode, cikti[:5000]",
            "    except Exception as e:",
            "        return 500, str(e)",
            "",
            "def yetki(headers):",
            "    if not HTTP_TOKEN:",
            "        return True",
            "    return headers.get('X-ZK-Token','') == HTTP_TOKEN",
            "",
            "class ZKAjan(BaseHTTPRequestHandler):",
            "    def log_message(self, fmt, *args):",
            "        pass",
            "    def json_yanit(self, kod, veri):",
            "        icerik = json.dumps(veri, ensure_ascii=False).encode('utf-8')",
            "        self.send_response(kod)",
            "        self.send_header('Content-Type', 'application/json; charset=utf-8')",
            "        self.send_header('Content-Length', str(len(icerik)))",
            "        self.end_headers()",
            "        self.wfile.write(icerik)",
            "    def do_GET(self):",
            "        if self.path.rstrip('/') in ('', '/', '/health'):",
            "            self.json_yanit(200, {'durum':'ok','uzuv_id':UZUV_ID,'uzuv_ad':UZUV_AD,'ip':yerel_ip_bul(),'http_port':HTTP_PORT})",
            "            return",
            "        self.json_yanit(404, {'durum':'hata','mesaj':'Yol bulunamadi'})",
            "    def do_POST(self):",
            "        if not yetki(self.headers):",
            "            self.json_yanit(403, {'durum':'hata','mesaj':'Yetkisiz'})",
            "            return",
            "        if self.path.rstrip('/') != '/komut':",
            "            self.json_yanit(404, {'durum':'hata','mesaj':'Yol bulunamadi'})",
            "            return",
            "        uzunluk = int(self.headers.get('Content-Length', '0'))",
            "        ham = self.rfile.read(uzunluk).decode('utf-8') if uzunluk else '{}'",
            "        veri = json.loads(ham or '{}')",
            "        komut = (veri.get('komut') or '').strip()",
            "        if not komut:",
            "            self.json_yanit(400, {'durum':'hata','mesaj':'Komut bos'})",
            "            return",
            "        kod, sonuc = komut_calistir(komut)",
            "        self.json_yanit(200, {'durum':'ok' if kod == 0 else 'hata','returncode':kod,'sonuc':sonuc})",
            "",
            "def ajan_baslat():",
            "    global SUNUCU",
            "    if SUNUCU is not None:",
            "        return True",
            "    try:",
            "        SUNUCU = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), ZKAjan)",
            "        threading.Thread(target=SUNUCU.serve_forever, daemon=True).start()",
            "        return True",
            "    except Exception as e:",
            "        print(f'Ajan baslatma hatasi: {e}')",
            "        SUNUCU = None",
            "        return False",
            "",
            "class ZKApp(App):",
            "    def build(self):",
            "        layout = BoxLayout(orientation='vertical',padding=20)",
            f"        self.lbl = Label(text='ZK: {a.uzuv_ad}\\nHazirlaniyor...')",
            "        btn = Button(text='Baslat',size_hint_y=None,height=50)",
            "        btn.bind(on_press=lambda _: self._baslat())",
            "        layout.add_widget(self.lbl); layout.add_widget(btn)",
            "        self._baslat(); return layout",
            "    def _baslat(self):",
            "        if ajan_baslat():",
            "            Clock.schedule_once(lambda dt: hazir_bildir(), 1)",
            "            self.lbl.text = f'Aktif HTTP Ajan\\n{yerel_ip_bul()}:{HTTP_PORT}'",
            "        else:",
            "            self.lbl.text = 'Ajan baslatilamadi'",
            "",
            "if __name__ == '__main__': ZKApp().run()",
        ]

        spec_satirlar = [
            "[app]",
            f"title = ZK {a.uzuv_ad}",
            f"package.name = zk_{a.uzuv_id.replace('-','_')}",
            "package.domain = com.zkcenter",
            "source.dir = .",
            "source.include_exts = py",
            "version = 1.0",
            "requirements = python3,kivy",
            "orientation = portrait",
            "android.permissions = INTERNET",
            "android.api = 31",
            "android.minapi = 24",
            "android.archs = arm64-v8a",
            "android.accept_sdk_license = True",
            "",
            "[buildozer]",
            "log_level = 2",
        ]

        with open(main_py,    "w", encoding="utf-8") as f:
            f.write("\n".join(satirlar_main) + "\n")
        with open(spec_dosya, "w", encoding="utf-8") as f:
            f.write("\n".join(spec_satirlar) + "\n")

        self.log.bilgi(KAYNAK, f"Buildozer projesi hazırlandı: {klasor}")
        return [main_py, spec_dosya]

    def _apk_derle(self, klasor: str) -> str:
        """
        Buildozer ile APK'yı otomatik derle.
        buildozer kurulu değilse önce kurar.
        Tamamlanınca .apk dosyasının yolunu döner.
        """
        buildozer_cmd = self._komut_yolu("buildozer")
        if not buildozer_cmd:
            self.log.hata(KAYNAK, "buildozer bulunamadı. './kur.sh --full' veya venv kurulumu gerekli.")
            return ""

        # Bağımlılıklar
        for paket in ["openjdk-17-jdk", "libffi-dev", "libssl-dev",
                      "autoconf", "libtool", "pkg-config", "zlib1g-dev"]:
            subprocess.run(
                ["sudo", "-n", "apt-get", "install", "-y", "-qq", paket],
                capture_output=True)

        # APK derle
        self.log.bilgi(KAYNAK,
            "APK derleniyor... (ilk seferde ~15 dakika sürebilir)")
        try:
            env = os.environ.copy()
            venv_bin = os.path.join(self.proje_kok, "birader_env", "bin")
            local_bin = os.path.expanduser(os.path.join("~", ".local", "bin"))
            env["PATH"] = os.pathsep.join([
                os.path.join(java17_home, "bin") if os.path.isdir(java17_home := "/usr/lib/jvm/java-17-openjdk-amd64") else "",
                local_bin,
                venv_bin,
                env.get("PATH", ""),
            ]).strip(os.pathsep)
            if os.path.isdir(java17_home):
                env["JAVA_HOME"] = java17_home
            shim_dir = os.path.join(self.proje_kok, "android_build_shim")
            mevcut_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = shim_dir + (os.pathsep + mevcut_pythonpath if mevcut_pythonpath else "")
            build_klasoru = klasor
            gecici_mi = False
            if any(ord(ch) > 127 for ch in klasor):
                build_klasoru = tempfile.mkdtemp(prefix="zk_apk_build_", dir="/tmp")
                gecici_mi = True
                for ad in ("main.py", "buildozer.spec"):
                    kaynak = os.path.join(klasor, ad)
                    if os.path.exists(kaynak):
                        shutil.copy2(kaynak, os.path.join(build_klasoru, ad))
                self.log.uyari(
                    KAYNAK,
                    f"APK derleme için ASCII geçici klasör kullanılıyor: {build_klasoru}"
                )
            gradle_cache = os.path.expanduser("~/.cache/zihin_koprusu/gradle")
            os.makedirs(gradle_cache, exist_ok=True)
            env["GRADLE_USER_HOME"] = gradle_cache
            r = None
            for deneme in range(1, 3):
                if deneme > 1:
                    self.log.uyari(KAYNAK, "APK derleme tekrar deneniyor (gecici ag/clone hatasi olabilir).")
                r = subprocess.run(
                    [buildozer_cmd, "android", "debug"],
                    cwd=build_klasoru,
                    capture_output=True, text=True,
                    env=env,
                    timeout=1800  # 30 dakika max
                )
                tum_cikti = (r.stdout or "") + "\n" + (r.stderr or "")
                gecici_ag_hatasi = any(
                    metin in tum_cikti.lower()
                    for metin in ("rpc başarısız", "rpc failed", "unexpected disconnect", "early eof")
                )
                if r.returncode == 0 or not gecici_ag_hatasi:
                    break
            # bin/ klasöründe .apk ara
            bin_dir = os.path.join(build_klasoru, "bin")
            if os.path.isdir(bin_dir):
                for f in os.listdir(bin_dir):
                    if f.endswith(".apk"):
                        apk_yol = os.path.join(bin_dir, f)
                        if gecici_mi:
                            hedef_apk = os.path.join(klasor, f)
                            shutil.copy2(apk_yol, hedef_apk)
                            apk_yol = hedef_apk
                        self.log.bilgi(KAYNAK, f"✓ APK hazır: {apk_yol}")
                        return apk_yol
            hata_ozet = "\n".join(
                [satir for satir in (r.stdout + "\n" + r.stderr).splitlines() if satir.strip()][-30:]
            )
            self.son_uretim_hatasi = hata_ozet or f"Buildozer cikis kodu: {r.returncode}"
            self.log.hata(KAYNAK,
                f"APK bulunamadı. buildozer çıktısı:\n{hata_ozet}")
            return ""
        except subprocess.TimeoutExpired:
            self.son_uretim_hatasi = "APK derleme zaman asimi (30dk)."
            self.log.hata(KAYNAK, "APK derleme zaman aşımı (30dk).")
            return ""
        except Exception as e:
            self.son_uretim_hatasi = str(e)
            self.log.hata(KAYNAK, f"APK derleme hatası: {e}")
            return ""

    def _exe_derle(self, klasor: str, uzuv_id: str) -> str:
        """
        mingw-w64 cross-compiler ile Windows EXE üretir.
        Linux üzerinde Windows binary derlenir — wine gerekmez.
        """
        import shutil

        cpp_dosya = os.path.join(klasor, f"zk_{uzuv_id}.cpp")
        exe_dosya = os.path.join(klasor, f"zk_{uzuv_id}.exe")

        if not os.path.exists(cpp_dosya):
            self.log.hata(KAYNAK, f"C++ kaynak bulunamadı: {cpp_dosya}")
            return ""

        # mingw-w64 yüklü mü?
        derleyici = None
        for kandidat in ["x86_64-w64-mingw32-gcc",
                          "i686-w64-mingw32-gcc"]:
            if shutil.which(kandidat):
                derleyici = kandidat
                break

        if not derleyici:
            self.log.bilgi(KAYNAK, "mingw-w64 yükleniyor...")
            r = subprocess.run(
                ["sudo", "-n", "apt-get", "install", "-y", "-qq",
                 "gcc-mingw-w64"],
                capture_output=True, text=True)
            if r.returncode == 0:
                derleyici = "x86_64-w64-mingw32-gcc"
            else:
                self.log.hata(KAYNAK, "mingw-w64 kurulamadı.")
                return ""

        # Derle
        r = subprocess.run(
            [derleyici, cpp_dosya, "-o", exe_dosya,
             "-lws2_32", "-static", "-mwindows"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0 and os.path.exists(exe_dosya):
            self.log.bilgi(KAYNAK, f"✓ EXE hazır: {exe_dosya}")
            return exe_dosya
        else:
            self.son_uretim_hatasi = (r.stderr[:300] or "EXE derleme basarisiz.").strip()
            self.log.hata(KAYNAK,
                f"EXE derleme hatası:\n{r.stderr[:300]}")
            return ""
