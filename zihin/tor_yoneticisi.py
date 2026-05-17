"""
Zihin Köprüsü – Tor Yöneticisi
Merkez sunucu için Tor hidden service ve web paneli üretimi.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import socket
import threading
import time
from typing import Callable, Optional

from .logcu import Logcu

KAYNAK = "TOR"

TORRC_SABLONU = """\
# Zihin Köprüsü – Otomatik oluşturuldu  ({tarih})

SocksPort {socks_port}
ControlPort {control_port}
DataDirectory {data_dir}
Log notice file {log_dosya}

# ── Zihin Köprüsü Hidden Services ─────────────────────────────
HiddenServiceDir {hs_ssh_dir}
HiddenServicePort 22 127.0.0.1:22

HiddenServiceDir {hs_web_dir}
HiddenServicePort 80 127.0.0.1:{web_port}
"""

WEB_INDEX = """\
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Zihin Köprüsü — Kontrol Paneli</title>
<style>
  body {{ background:#0d0f14; color:#e8eaf0; font-family:'Courier New',monospace;
         margin:0; padding:40px; }}
  h1   {{ color:#00e5ff; letter-spacing:4px; }}
  p    {{ color:#7a8099; }}
  .badge {{ display:inline-block; background:#1a1e2a; border:1px solid #252b3b;
            padding:6px 14px; border-radius:6px; margin:4px; color:#00e676; }}
  a    {{ color:#00e5ff; }}
</style>
</head>
<body>
<h1>⬡ ZİHİN KÖPRÜSÜ</h1>
<p>v6.0 — Ses Tabanlı Dijital Uzuv Sistemi</p>
<hr style="border-color:#252b3b;">
<h2 style="color:#7c4dff;">Sunucu Durumu</h2>
<span class="badge">🟢 Çevrimiçi</span>
<span class="badge">🧅 Tor Hidden Service</span>
<span class="badge">🔒 SSH Aktif</span>
<p style="margin-top:30px;color:#4a5068;font-size:12px;">
Bu sunucu Zihin Köprüsü tarafından otomatik oluşturulmuştur.</p>
</body>
</html>
"""

# Sistem Tor torrc'ye eklenecek blok
SISTEM_TORRC_EKI = """

# ── Zihin Köprüsü (otomatik eklendi) ──
HiddenServiceDir /var/lib/tor/zk_ssh/
HiddenServicePort 22 127.0.0.1:22

HiddenServiceDir /var/lib/tor/zk_web/
HiddenServicePort 80 127.0.0.1:8765
"""


class TorYoneticisi:
    def __init__(self, logcu: Logcu, proje_yolu: str):
        self.log = logcu
        self.proje_yolu = proje_yolu

        self.tor_veri_dizini = os.path.join(proje_yolu, "tor_veri")
        self.hs_ssh_dir      = os.path.join(self.tor_veri_dizini, "hs_ssh")
        self.hs_web_dir      = os.path.join(self.tor_veri_dizini, "hs_web")
        self.web_dizini      = os.path.join(proje_yolu, "web")
        self.torrc_yolu      = os.path.join(self.tor_veri_dizini, "torrc")
        self.web_port        = 8765
        self.socks_port      = 19050
        self.control_port    = 19051

        self._web_server: Optional[subprocess.Popen] = None
        self._web_server_thread: Optional[threading.Thread] = None
        self._web_httpd = None
        self._tor_proc:   Optional[subprocess.Popen] = None
        self._izle_thread: Optional[threading.Thread] = None
        self._durum_dinleyiciler: list[Callable[[str], None]] = []
        self._kayit_dinleyiciler: list[Callable[[dict], None]] = []

        self._sistem_tor_var: Optional[bool] = None
        self._sistem_tor_calisiyor: Optional[bool] = None
        self._onion_dinleyiciler: list = []

    def _port_kullaniliyor_mu(self, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.4)
                return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False

    def _uygun_tor_portlarini_sec(self):
        socks_aday = [self.socks_port, 29050, 39050, 49050]
        control_aday = [self.control_port, 29051, 39051, 49051]
        for socks, control in zip(socks_aday, control_aday):
            if socks == control:
                continue
            if not self._port_kullaniliyor_mu(socks) and not self._port_kullaniliyor_mu(control):
                if socks != self.socks_port or control != self.control_port:
                    self.log.uyari(
                        KAYNAK,
                        f"Tor portlari dolu; SocksPort={socks}, ControlPort={control} kullanılacak."
                    )
                    self.socks_port = socks
                    self.control_port = control
                return
        raise RuntimeError("Uygun boş Tor portları bulunamadı.")

    def _uygun_web_portu_sec(self):
        adaylar = [self.web_port] + list(range(self.web_port + 1, self.web_port + 25))
        for port in adaylar:
            if not self._port_kullaniliyor_mu(port):
                if port != self.web_port:
                    self.log.uyari(KAYNAK, f"Web portu {self.web_port} dolu; {port} kullanılacak.")
                    self.web_port = port
                return
        raise RuntimeError("Uygun boş web portu bulunamadı.")

    # ── Dinleyiciler ─────────────────────────────────────────────────────────

    def durum_dinleyici_ekle(self, fn: Callable[[str], None]):
        self._durum_dinleyiciler.append(fn)

    def kayit_dinleyici_ekle(self, fn: Callable[[dict], None]):
        self._kayit_dinleyiciler.append(fn)

    def _bildir(self, mesaj: str):
        self.log.bilgi(KAYNAK, mesaj)
        for fn in self._durum_dinleyiciler:
            try:
                fn(mesaj)
            except Exception:
                pass

    # ── Otomatik Tespit ──────────────────────────────────────────────────────

    def sistem_tor_var_mi(self) -> bool:
        if self._sistem_tor_var is None:
            self._sistem_tor_var = shutil.which("tor") is not None
        return self._sistem_tor_var

    def sistem_tor_calisiyor_mu(self) -> bool:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", "tor"],
                capture_output=True, text=True
            )
            calisiyor = r.stdout.strip() == "active"
            self._sistem_tor_calisiyor = calisiyor
            return calisiyor
        except Exception:
            try:
                r = subprocess.run(["pgrep", "-x", "tor"], capture_output=True)
                return r.returncode == 0
            except Exception:
                return False

    def durum_raporu(self) -> dict:
        tor_var  = self.sistem_tor_var_mi()
        tor_cali = self.sistem_tor_calisiyor_mu() if tor_var else False
        kendi    = self._tor_proc is not None and self._tor_proc.poll() is None

        aktif = tor_cali or kendi
        return {
            "sistem_tor_kurulu":    tor_var,
            "sistem_tor_calisiyor": tor_cali,
            "kendi_tor_calisiyor":  kendi,
            "herhangi_tor":         aktif,
            "calisiyor":            aktif,
            "socks_port":           self.socks_port,
            "ssh_onion":            self.onion_adresi_al("ssh"),
            "web_onion":            self.onion_adresi_al("web"),
            "torrc_yolu":           self.torrc_yolu,
            "web_dizini":           self.web_dizini,
            "web_port":             self.web_port,
        }

    def kurulum_rehberi(self) -> str:
        if self.sistem_tor_var_mi():
            return (
                "Sistemde Tor kurulu. Hidden service için:\n"
                "  sudo nano /etc/tor/torrc\n"
                "  — Şunu ekleyin:\n"
                f"{SISTEM_TORRC_EKI}\n"
                "  sudo systemctl restart tor\n"
                "  sudo cat /var/lib/tor/zk_ssh/hostname  # SSH onion adresiniz\n"
                "  sudo cat /var/lib/tor/zk_web/hostname  # Web onion adresiniz\n"
            )
        else:
            return (
                "Sistemde Tor bulunamadı.\n"
                "Zihin Köprüsü kendi Tor sunucusunu kurup başlatacak.\n"
                "  sudo apt-get install -y tor\n"
                "  veya: ./kur.sh çalıştırın.\n"
            )

    # ── Kurulum ──────────────────────────────────────────────────────────────

    def kur(self) -> bool:
        try:
            self._uygun_tor_portlarini_sec()
            self._uygun_web_portu_sec()
            os.makedirs(self.tor_veri_dizini, exist_ok=True)
            os.makedirs(self.hs_ssh_dir, exist_ok=True)
            os.makedirs(self.hs_web_dir, exist_ok=True)
            os.makedirs(self.web_dizini, exist_ok=True)

            # Tor 700 izin ister
            os.chmod(self.tor_veri_dizini, 0o700)
            os.chmod(self.hs_ssh_dir, 0o700)
            os.chmod(self.hs_web_dir, 0o700)

            self._torrc_yaz()
            self._web_dizini_kur()
            self._bildir("Tor kurulumu tamamlandı.")
            return True
        except Exception as e:
            self.log.hata(KAYNAK, f"Kurulum hatası: {e}")
            return False

    def _torrc_yaz(self):
        from datetime import datetime

        log_dosya = os.path.join(self.tor_veri_dizini, "tor.log")
        icerik = TORRC_SABLONU.format(
            tarih=datetime.now().strftime("%Y-%m-%d %H:%M"),
            socks_port=self.socks_port,
            control_port=self.control_port,
            data_dir=self.tor_veri_dizini,
            log_dosya=log_dosya,
            hs_ssh_dir=self.hs_ssh_dir,
            hs_web_dir=self.hs_web_dir,
            web_port=self.web_port,
        )
        with open(self.torrc_yolu, "w") as f:
            f.write(icerik)
        self._bildir(f"torrc yazıldı: {self.torrc_yolu}")

    def _web_dizini_kur(self):
        os.makedirs(self.web_dizini, exist_ok=True)
        index = os.path.join(self.web_dizini, "index.html")
        if not os.path.exists(index):
            with open(index, "w", encoding="utf-8") as f:
                f.write(WEB_INDEX)
        self._bildir(f"Web dizini: {self.web_dizini}")

    # ── Başlat (Ana Mantık) ──────────────────────────────────────────────────

    def baslat(self) -> bool:
        """
        Tor başlatma mantığı (3 senaryo):

        1. Sistem Tor kurulu + çalışıyor
           → Mevcut Tor'u kullan. Sadece web sunucusu başlat.
             Sistem hidden service rehberini göster (sudo ile eklemek için).

        2. Sistem Tor kurulu ama çalışmıyor
           → Kendi torrc'miz ile başlatmayı dene.

        3. Tor hiç kurulu değil
           → apt ile OTOMATİK kur, sonra kendi torrc'miz ile başlat.
        """
        tor_var  = self.sistem_tor_var_mi()
        tor_cali = self.sistem_tor_calisiyor_mu() if tor_var else False

        # Senaryo 1: Sistem Tor çalışıyor — yine de kendi hidden service'imizi başlat
        # (Sistem Tor SocksPort 9050'yi kullanır, biz 9051'de kendi instance'ımızı çalıştırırız)
        if tor_var and tor_cali:
            self._bildir("Sistem Tor aktif. Kendi hidden service başlatılıyor...")
            # torrc oluştur (farklı SocksPort ile)
            self._uygun_web_portu_sec()
            if not os.path.exists(self.torrc_yolu):
                self.kur()
            else:
                self._torrc_yaz()
            self._web_baslat()
            try:
                self._tor_proc = subprocess.Popen(
                    ["tor", "-f", self.torrc_yolu],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                self._bildir("Kendi Tor instance başlatıldı.")
                self._izle_thread = threading.Thread(
                    target=self._hostname_bekle, daemon=True)
                self._izle_thread.start()
                return True
            except Exception as e:
                # Kendi instance başlatılamadı — sistem Tor hostname'e bak
                self.log.uyari(KAYNAK, f"Kendi Tor başlatılamadı: {e}")
                threading.Thread(
                    target=self._sistem_tor_hostname_kontrol,
                    daemon=True).start()
                return True

        # Senaryo 3: Tor kurulu değil → apt ile kur
        if not tor_var:
            self._bildir("Tor kurulu değil, otomatik kurulum başlatılıyor...")
            cikti = self.sistem_tor_kur()
            self.log.bilgi(KAYNAK, f"apt çıktısı:\n{cikti[:500]}")
            # Cache sıfırla
            self._sistem_tor_var = None
            if not self.sistem_tor_var_mi():
                self.log.hata(KAYNAK,
                    "Tor kurulamadı. Lütfen manual olarak kurun:\n"
                    "  sudo apt-get install -y tor\n"
                    "Ardından yeniden başlatın.")
                return False
            self._bildir("Tor kuruldu, başlatılıyor...")

        # Senaryo 2 + 3: Kendi torrc'miz ile başlat
        if not os.path.exists(self.torrc_yolu):
            if not self.kur():
                return False
        else:
            self._uygun_web_portu_sec()
            self._torrc_yaz()

        try:
            self._web_baslat()
            self._tor_proc = subprocess.Popen(
                ["tor", "-f", self.torrc_yolu],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self._bildir("Tor başlatıldı (kullanıcı modu).")
            self._izle_thread = threading.Thread(
                target=self._hostname_bekle, daemon=True)
            self._izle_thread.start()
            return True
        except FileNotFoundError:
            self.log.hata(KAYNAK, "Tor çalıştırılamadı. 'sudo apt install tor'")
            return False
        except Exception as e:
            self.log.hata(KAYNAK, f"Tor başlatma hatası: {e}")
            return False

    def durdur(self):
        if self._tor_proc:
            self._tor_proc.terminate()
            self._tor_proc = None
        httpd = self._web_httpd
        if httpd:
            try:
                httpd.shutdown()
            except Exception as e:
                self.log.uyari(KAYNAK, f"Web sunucusu kapatılamadı: {e}")
            self._web_httpd = None
        self._web_server_thread = None
        self._bildir("Tor durduruldu.")

    def yeniden_baslat(self):
        self.durdur()
        time.sleep(1)
        self.baslat()

    def _web_baslat(self):
        """
        Statik dosya sunumu + POST /uzuv_bildir endpoint'i olan HTTP sunucusu.
        python3 -m http.server POST alamaz; bu yüzden threading.Thread ile
        kendi BaseHTTPRequestHandler'ımızı çalıştırıyoruz.
        """
        if self._web_httpd and self._web_server_thread and self._web_server_thread.is_alive():
            return

        yonetici = self
        web_dizini = self.web_dizini
        bildir_fn  = self._bildir
        log_fn     = self.log
        port       = self.web_port
        kaynak     = KAYNAK
        kayit_dinleyiciler = self._kayit_dinleyiciler

        from http.server import BaseHTTPRequestHandler, HTTPServer
        import json as _json

        class ZKHTTPServer(HTTPServer):
            allow_reuse_address = True

        class ZKHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass   # Terminali kirletme

            def do_GET(self):
                # Statik dosya servis et
                dosya_yolu = os.path.join(web_dizini,
                                          self.path.lstrip("/") or "index.html")
                if os.path.isfile(dosya_yolu):
                    with open(dosya_yolu, "rb") as f:
                        icerik = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(icerik)
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not found")

            def do_POST(self):
                if self.path.rstrip("/") == "/uzuv_bildir":
                    try:
                        uzunluk = int(self.headers.get("Content-Length", 0))
                        veri_raw = self.rfile.read(uzunluk)
                        veri = _json.loads(veri_raw.decode("utf-8"))

                        uzuv_id  = veri.get("uzuv_id", "?")
                        uzuv_ad  = veri.get("uzuv_ad", "?")
                        host     = veri.get("host", "?")
                        zaman    = veri.get("zaman", "?")

                        mesaj = (f"🟢 UZUV HAZIR: {uzuv_ad} ({uzuv_id}) "
                                 f"| host={host} | {zaman}")
                        bildir_fn(mesaj)
                        log_fn.bilgi(kaynak, mesaj)
                        for fn in list(kayit_dinleyiciler):
                            try:
                                fn(dict(veri))
                            except Exception as exc:
                                log_fn.uyari(kaynak, f"Uzuv kayit dinleyici hatasi: {exc}")

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(b'{"durum":"ok"}')
                    except Exception as e:
                        log_fn.hata(kaynak, f"/uzuv_bildir hata: {e}")
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'{"durum":"hata"}')
                else:
                    self.send_response(404)
                    self.end_headers()

        def _sunucu_calistir():
            try:
                sunucu = ZKHTTPServer(("0.0.0.0", port), ZKHandler)
                yonetici._web_httpd = sunucu
                bildir_fn(f"Web sunucusu 0.0.0.0:{port} üzerinde çalışıyor "
                          f"(/uzuv_bildir endpoint aktif).")
                sunucu.serve_forever()
            except OSError as e:
                log_fn.hata(kaynak, f"Web sunucusu başlatılamadı (port {port} meşgul?): {e}")
            except Exception as e:
                log_fn.hata(kaynak, f"Web sunucusu hatası: {e}")
            finally:
                try:
                    if yonetici._web_httpd:
                        yonetici._web_httpd.server_close()
                except Exception:
                    pass
                yonetici._web_httpd = None

        self._web_server_thread = threading.Thread(
            target=_sunucu_calistir, daemon=True)
        self._web_server_thread.start()

    def _hostname_bekle(self):
        hostname_dosyasi = os.path.join(self.hs_ssh_dir, "hostname")
        for _ in range(40):
            if self._tor_proc and self._tor_proc.poll() is not None:
                try:
                    kalan = self._tor_proc.stdout.read() if self._tor_proc.stdout else ""
                except Exception:
                    kalan = ""
                self.log.hata(
                    KAYNAK,
                    "Gömülü Tor erken kapandı."
                    + (f" Çıktı: {kalan[-400:]}" if kalan else "")
                )
                return
            if os.path.exists(hostname_dosyasi):
                onion = self.onion_adresi_al("ssh")
                if onion:
                    self._bildir(f"SSH Onion adresi hazır: {onion}")
                    self._onion_hazir_bildir(onion)
                    return
            time.sleep(2)
        self.log.uyari(KAYNAK, "SSH Onion adresi 80 saniyede oluşmadı.")

    def _onion_hazir_bildir(self, onion: str):
        """Onion adresi hazır olunca kayıtlı dinleyicileri çağır."""
        for fn in self._onion_dinleyiciler:
            try:
                fn(onion)
            except Exception as e:
                self.log.uyari(KAYNAK, f"Onion dinleyici hatası: {e}")

    def onion_hazir_dinleyici_ekle(self, fn):
        """GUI/cekirdek onion hazır olunca buradan haberdar olur."""
        self._onion_dinleyiciler.append(fn)

    def _sistem_tor_hostname_kontrol(self):
        """
        Sistem Tor hidden service hostname'ini bul.
        Önce dosyayı direkt okumayı dene, izin yoksa sudo ile dene,
        o da olmazsa torrc'ye otomatik ekleyip Tor'u reload et.
        """
        import time as _t

        sistem_hs_yollar = [
            "/var/lib/tor/zk_ssh/hostname",
            "/var/lib/tor/zihin_koprusu/hostname",
            os.path.expanduser("~/.tor/zk_ssh/hostname"),
        ]

        # 1. Direkt okuma
        for yol in sistem_hs_yollar:
            if os.path.exists(yol):
                try:
                    with open(yol) as f:
                        onion = f.read().strip()
                    if onion:
                        self._bildir(f"Sistem Tor SSH Onion: {onion}")
                        self._onion_hazir_bildir(onion)
                        return
                except PermissionError:
                    pass

        # 2. sudo ile oku
        for yol in sistem_hs_yollar:
            try:
                r = subprocess.run(
                    ["sudo", "-n", "cat", yol],
                    capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and r.stdout.strip():
                    onion = r.stdout.strip()
                    self._bildir(f"Sistem Tor SSH Onion (sudo): {onion}")
                    self._onion_hazir_bildir(onion)
                    return
            except Exception:
                pass

        # 3. torrc'ye otomatik ekle ve reload et
        self._bildir("Hidden service bulunamadı. torrc güncelleniyor...")
        if self.sistem_torrc_guncelle():
            # Tor reload olduktan sonra hostname oluşması için bekle
            self._bildir("Tor yeniden başlatıldı, onion adresi bekleniyor (~30sn)...")
            for deneme in range(6):
                _t.sleep(10)
                for yol in sistem_hs_yollar:
                    try:
                        r = subprocess.run(
                            ["sudo", "-n", "cat", yol],
                            capture_output=True, text=True, timeout=5)
                        if r.returncode == 0 and r.stdout.strip():
                            onion = r.stdout.strip()
                            self._bildir(f"✓ Onion hazır: {onion}")
                            self._onion_hazir_bildir(onion)
                            return
                    except Exception:
                        pass
            self._bildir(
                "Onion adresi hâlâ oluşmadı.\n"
                "Manuel kontrol: sudo cat /var/lib/tor/zk_ssh/hostname")
        else:
            self._bildir(
                "Sistem torrc güncellenemedi — sudo izni gerekiyor.\n"
                + self.kurulum_rehberi())

    # ── Bilgi ────────────────────────────────────────────────────────────────

    def onion_adresi_al(self, servis: str = "ssh") -> str:
        dizin = self.hs_ssh_dir if servis == "ssh" else self.hs_web_dir
        dosya = os.path.join(dizin, "hostname")
        if os.path.exists(dosya):
            try:
                with open(dosya) as f:
                    return f.read().strip()
            except Exception:
                pass

        sistem_yollar = {
            "ssh": ["/var/lib/tor/zk_ssh/hostname",
                    "/var/lib/tor/zihin_koprusu/hostname"],
            "web": ["/var/lib/tor/zk_web/hostname"],
        }
        for yol in sistem_yollar.get(servis, []):
            # Direkt oku
            if os.path.exists(yol):
                try:
                    with open(yol) as f:
                        return f.read().strip()
                except PermissionError:
                    pass
            # sudo ile dene
            try:
                r = subprocess.run(
                    ["sudo", "-n", "cat", yol],
                    capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            except Exception:
                pass
        return ""

    def calisıyor_mu(self) -> bool:
        if self._tor_proc and self._tor_proc.poll() is None:
            return True
        return self.sistem_tor_calisiyor_mu()

    def durum_al(self) -> dict:
        return self.durum_raporu()

    # ── Sistem Tor apt Kurulum ───────────────────────────────────────────────

    def sistem_tor_kur(self) -> str:
        """apt ile Tor kurar (sudo gerektirir)."""
        try:
            r = subprocess.run(
                ["sudo", "apt-get", "install", "-y", "tor", "netcat-openbsd"],
                capture_output=True, text=True, timeout=180
            )
            self._sistem_tor_var = None
            return r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return "Kurulum zaman aşımına uğradı."
        except Exception as e:
            return f"Hata: {e}"

    def sistem_torrc_guncelle(self) -> bool:
        """
        Sistem torrc'ye Zihin Köprüsü hidden service bloğunu ekler.
        sudo gerektirir.
        """
        sistem_torrc = "/etc/tor/torrc"
        try:
            # torrc'yi oku (direkt veya sudo ile)
            try:
                with open(sistem_torrc) as f:
                    mevcut = f.read()
            except PermissionError:
                r = subprocess.run(
                    ["sudo", "-n", "cat", sistem_torrc],
                    capture_output=True, text=True, timeout=5)
                mevcut = r.stdout if r.returncode == 0 else ""

            if "Zihin" in mevcut and "HiddenServiceDir" in mevcut:
                self._bildir("Sistem torrc zaten güncel.")
                # Yine de reload et — belki henüz onion oluşmamış
                subprocess.run(
                    ["sudo", "-n", "systemctl", "reload", "tor"],
                    capture_output=True, timeout=10)
                return True

            # Bloğu ekle
            result = subprocess.run(
                ["sudo", "-n", "tee", "-a", sistem_torrc],
                input=SISTEM_TORRC_EKI,
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # Restart yerine reload — daha hızlı
                subprocess.run(
                    ["sudo", "-n", "systemctl", "reload", "tor"],
                    capture_output=True, timeout=15)
                self._bildir(
                    "Sistem torrc güncellendi, Tor reload edildi.")
                return True
            else:
                # sudo -n başarısız — kullanıcıya rehber göster
                self.log.uyari(KAYNAK,
                    "torrc güncellemek için sudo şifre gerekiyor.\n"
                    + self.kurulum_rehberi())
                return False
        except Exception as e:
            self.log.hata(KAYNAK, f"torrc güncelleme hatası: {e}")
            return False

    # ── torrc Okuma/Yazma ────────────────────────────────────────────────────

    def torrc_oku(self) -> str:
        if os.path.exists(self.torrc_yolu):
            with open(self.torrc_yolu) as f:
                return f.read()
        return ""

    def torrc_kaydet(self, icerik: str) -> bool:
        try:
            with open(self.torrc_yolu, "w") as f:
                f.write(icerik)
            return True
        except Exception as e:
            self.log.hata(KAYNAK, f"torrc kaydetme hatası: {e}")
            return False

    # ── Güncelleme ───────────────────────────────────────────────────────────

    def guncelleme_kontrol(self, guncelleme_url: str) -> dict:
        try:
            import requests
            proxies = {
                "https": f"socks5h://127.0.0.1:{self.socks_port}",
                "http":  f"socks5h://127.0.0.1:{self.socks_port}",
            }
            r = requests.get(
                guncelleme_url.rstrip("/") + "/version.json",
                proxies=proxies, timeout=20
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            self.log.uyari(KAYNAK, f"Güncelleme kontrolü hatası: {e}")
        return {}

    def guncelleme_indir(self, guncelleme_url: str, hedef_dizin: str) -> bool:
        try:
            import requests
            import zipfile
            import io
            proxies = {
                "https": f"socks5h://127.0.0.1:{self.socks_port}",
                "http":  f"socks5h://127.0.0.1:{self.socks_port}",
            }
            r = requests.get(
                guncelleme_url.rstrip("/") + "/update.zip",
                proxies=proxies, timeout=120, stream=True
            )
            if r.status_code == 200:
                z = zipfile.ZipFile(io.BytesIO(r.content))
                z.extractall(hedef_dizin)
                self._bildir("Güncelleme uygulandı.")
                return True
        except Exception as e:
            self.log.hata(KAYNAK, f"Güncelleme indirme hatası: {e}")
        return False
