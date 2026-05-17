"""
Zihin Köprüsü v6.0 – Otomasyon Motoru
GUI otomasyonu: uygulama açma/kapama, web navigasyonu,
metin yazma, tıklama, kaydırma, medya kontrolü.
xdotool + wmctrl + subprocess tabanlı, Linux/X11.

"""
from __future__ import annotations

import shutil
import subprocess
import time

from .logcu import Logcu
from .niyet_motoru import Niyet, NiyetTipi

KAYNAK = "OTOMASYON"

# Uygulama başlatma komutları
UYGULAMA_KOMUTLARI = {
    "chrome":           ["google-chrome", "chromium-browser", "chromium"],
    "firefox":          ["firefox"],
    "youtube":          ["xdg-open", "https://www.youtube.com"],
    "spotify":          ["spotify"],
    "vscode":           ["code"],
    "terminal":         ["gnome-terminal", "xterm", "konsole", "xfce4-terminal"],
    "dosya_yoneticisi": ["nautilus", "thunar", "nemo", "dolphin"],
    "not_defteri":      ["gedit", "kate", "mousepad", "pluma"],
    "hesap_makinesi":   ["gnome-calculator", "kcalc", "galculator"],
    "vlc":              ["vlc"],
    "whatsapp":         ["xdg-open", "https://web.whatsapp.com"],
    "telegram":         ["telegram-desktop"],
    "discord":          ["discord"],
}


class OtomasyonMotoru:
    def __init__(self, logcu: Logcu):
        self.log = logcu
        self._xdotool_var = shutil.which("xdotool") is not None
        self._wmctrl_var  = shutil.which("wmctrl") is not None

    # ── Ana Yürütücü ─────────────────────────────────────────────────────────

    def isle(self, niyet: Niyet) -> str:
        """Niyeti karşılayan eylemi yürütür."""
        self.log.bilgi(KAYNAK, f"Yürütülüyor: {niyet}")

        tip = niyet.tip
        if tip == NiyetTipi.UYGULAMA_AC:
            return self.uygulama_ac(niyet.ozne)
        elif tip == NiyetTipi.UYGULAMA_KAP:
            return self.uygulama_kapat(niyet.ozne)
        elif tip == NiyetTipi.WEB_GEZ:
            return self.web_git(niyet.hedef)
        elif tip == NiyetTipi.WEB_TIKLA:
            return self.ekranda_tikla_metin(niyet.hedef)
        elif tip == NiyetTipi.WEB_KAYDIR:
            return self.sayfa_kaydir(niyet.eylem)
        elif tip == NiyetTipi.MEDYA_OYNAT:
            return self.medya_oynat(niyet.ozne, niyet.hedef)
        elif tip == NiyetTipi.MEDYA_DUR:
            return self.medya_durdur()
        elif tip == NiyetTipi.ARAMA:
            return self.web_ara(niyet.hedef)
        elif tip == NiyetTipi.METIN_YAZ:
            return self.metin_yaz(niyet.hedef)
        elif tip == NiyetTipi.EKRAN_GORUNTU:
            return self.ekran_goruntu_al()
        elif tip == NiyetTipi.HESAP:
            return self.hesap_yap(niyet.hedef)
        else:
            return ""

    # ── Uygulama Kontrolü ────────────────────────────────────────────────────

    def uygulama_ac(self, ozne: str) -> str:
        komutlar = UYGULAMA_KOMUTLARI.get(ozne.lower(), [])
        if not komutlar:
            # Genel denemek: doğrudan isimle başlat
            return self._calistir([ozne])

        # Birden fazla alternatif komut varsa ilki kuruluyu dene
        if len(komutlar) > 1 and komutlar[0] == "xdg-open":
            # URL aç
            return self._calistir(["xdg-open", komutlar[1]])
        for cmd in (komutlar if isinstance(komutlar[0], str) else [komutlar]):
            if shutil.which(cmd if isinstance(cmd, str) else cmd[0]):
                return self._calistir([cmd] if isinstance(cmd, str) else cmd)
        # Fallback: xdg-open
        return self._calistir(["xdg-open", ozne])

    def uygulama_kapat(self, ozne: str) -> str:
        if self._wmctrl_var:
            r = subprocess.run(["wmctrl", "-c", ozne],
                               capture_output=True, text=True)
            if r.returncode == 0:
                return f"{ozne} kapatıldı."
        # pkill fallback
        r = subprocess.run(["pkill", "-f", ozne], capture_output=True)
        return f"{ozne} kapatıldı." if r.returncode == 0 else f"{ozne} bulunamadı."

    # ── Web Navigasyonu ───────────────────────────────────────────────────────

    def web_git(self, url: str) -> str:
        if not url.startswith("http"):
            url = "https://" + url
        self._calistir(["xdg-open", url])
        return f"Açılıyor: {url}"

    def web_ara(self, sorgu: str) -> str:
        import urllib.parse
        url = "https://www.google.com/search?q=" + urllib.parse.quote(sorgu)
        self._calistir(["xdg-open", url])
        return f"Aranıyor: {sorgu}"

    def sayfa_kaydir(self, yon: str = "asagi", miktar: int = 3) -> str:
        if not self._xdotool_var:
            return "xdotool kurulu değil."
        tus = "Down" if yon == "asagi" else "Up"
        for _ in range(miktar):
            subprocess.run(["xdotool", "key", tus], check=False)
            time.sleep(0.05)
        return f"Sayfa {'aşağı' if yon=='asagi' else 'yukarı'} kaydırıldı."

    def ekranda_tikla_metin(self, hedef_metin: str) -> str:
        """
        Ekranda belirtilen metni bulup tıklar.
        xdotool search + click kullanır.
        """
        if not self._xdotool_var:
            return "xdotool kurulu değil."
        # Önce pencere id'sini bul
        r = subprocess.run(
            ["xdotool", "search", "--name", hedef_metin],
            capture_output=True, text=True
        )
        if r.stdout.strip():
            wid = r.stdout.strip().split()[0]
            subprocess.run(["xdotool", "windowactivate", wid])
            time.sleep(0.2)
        # Ekrandaki konumu bulmak için scrot + pytesseract gerekir
        # Basit yol: odaklanmış pencerede Enter'a bas
        subprocess.run(["xdotool", "key", "Return"])
        return f"'{hedef_metin}' için Enter'a basıldı."

    # ── Metin Yazma ───────────────────────────────────────────────────────────

    def metin_yaz(self, metin: str) -> str:
        if not self._xdotool_var:
            return "xdotool kurulu değil."
        # Türkçe karakterler için type --clearmodifiers
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "30", metin])
        return f"Yazıldı: {metin}"

    def not_defteri_ac_ve_yaz(self, metin: str) -> str:
        """Not defterini aç ve içine metin yaz."""
        self.uygulama_ac("not_defteri")
        time.sleep(1.5)
        return self.metin_yaz(metin)

    # ── Medya Kontrolü ───────────────────────────────────────────────────────

    def medya_oynat(self, ozne: str, sorgu: str = "") -> str:
        if ozne == "youtube" and sorgu:
            import urllib.parse
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(sorgu)}"
            self.web_git(url)
            return f"YouTube'da aranıyor: {sorgu}"
        elif ozne == "spotify":
            self.uygulama_ac("spotify")
            return "Spotify açıldı."
        # XF86 medya tuşu simüle et
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "XF86AudioPlay"])
        return "Medya oynatılıyor."

    def medya_durdur(self) -> str:
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "XF86AudioStop"])
        return "Medya durduruldu."

    def medya_ileri(self) -> str:
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "XF86AudioNext"])
        return "Sonraki parça."

    def medya_geri(self) -> str:
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "XF86AudioPrev"])
        return "Önceki parça."

    def ses_yuksel(self) -> str:
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "XF86AudioRaiseVolume"])
        return "Ses yükseltildi."

    def ses_alçalt(self) -> str:
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "XF86AudioLowerVolume"])
        return "Ses alçaltıldı."

    # ── Ekran Görüntüsü ───────────────────────────────────────────────────────

    def ekran_goruntu_al(self, dosya: str = "/tmp/zk_ekran.png") -> str:
        for cmd in [["gnome-screenshot", "-f", dosya],
                    ["scrot", dosya],
                    ["import", "-window", "root", dosya]]:
            if shutil.which(cmd[0]):
                r = subprocess.run(cmd, capture_output=True)
                if r.returncode == 0:
                    return f"Ekran görüntüsü alındı: {dosya}"
        return "Ekran görüntüsü aracı bulunamadı."

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    def hesap_yap(self, ifade: str) -> str:
        try:
            import re
            # Güvenli matematik ifadesi
            temiz = re.sub(r"[^0-9\+\-\*\/\(\)\.\s]", "", ifade)
            if temiz.strip():
                sonuc = eval(temiz)
                return f"{temiz.strip()} = {sonuc}"
        except Exception:
            pass
        return f"Hesaplanamadı: {ifade}"

    def _calistir(self, args: list[str]) -> str:
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return f"Çalıştırıldı: {args[0]}"
        except FileNotFoundError:
            return f"{args[0]} bulunamadı."
        except Exception as e:
            self.log.hata(KAYNAK, f"Çalıştırma hatası: {e}")
            return f"Hata: {e}"

    # ── Sistem Bilgi Handler'ı — Temiz Türkçe Çıktı ────────────────────────

    def yukse(self, niyet):
        """Geriye dönük uyumluluk alias."""
        return self.isle(niyet)

    def sistem_bilgi(self, komut: str) -> str:
        """
        Sistem bilgisi sorgularını işler, temiz sade Türkçe döner.
        Ham Linux çıktısı değil — anlaşılır cümleler.
        """
        import subprocess, re

        def _calistir(cmd, timeout=5):
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=timeout)
                return (r.stdout + r.stderr).strip()
            except Exception:
                return ""

        if komut == "saat":
            from datetime import datetime
            dt = datetime.now()
            return f"Saat {dt.strftime('%H:%M')}."

        elif komut == "tarih":
            from datetime import datetime
            dt = datetime.now()
            gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe",
                      "Cuma", "Cumartesi", "Pazar"]
            aylar = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                     "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            return (f"Bugün {gunler[dt.weekday()]}, "
                    f"{dt.day} {aylar[dt.month]} {dt.year}.")

        elif komut == "cpu":
            cikti = _calistir("top -bn1 | grep -E 'Cpu|cpu'")
            m = re.search(r"([\d.]+)\s*us", cikti)
            if m:
                cpu = float(m.group(1))
                yorum = ("az" if cpu < 30 else
                         "normal" if cpu < 60 else
                         "yüksek" if cpu < 85 else "kritik")
                return f"İşlemci kullanımı yüzde {cpu:.0f} — {yorum}."
            return "İşlemci bilgisi alınamadı."

        elif komut == "ram":
            cikti = _calistir("free -m")
            for satir in cikti.splitlines():
                if satir.startswith("Mem"):
                    p = satir.split()
                    if len(p) >= 3:
                        toplam = int(p[1])
                        kullani = int(p[2])
                        yuzde = int(kullani * 100 / toplam) if toplam else 0
                        yorum = ("bol" if yuzde < 40 else
                                 "normal" if yuzde < 70 else
                                 "az" if yuzde < 85 else "kritik")
                        return (f"Bellek kullanımı yüzde {yuzde}. "
                                f"{kullani} MB kullanılıyor, "
                                f"{toplam - kullani} MB boş. Durum {yorum}.")
            return "Bellek bilgisi alınamadı."

        elif komut == "disk":
            cikti = _calistir("df -h /")
            satirlar = cikti.splitlines()
            if len(satirlar) >= 2:
                p = satirlar[1].split()
                if len(p) >= 5:
                    yuzde = int(p[4].replace("%", ""))
                    yorum = ("rahat" if yuzde < 60 else
                             "dikkat" if yuzde < 80 else
                             "az kaldı" if yuzde < 90 else "dolu neredeyse")
                    return (f"Disk yüzde {yuzde} dolu. "
                            f"Kullanılan {p[2]}, toplam {p[1]}, "
                            f"boş {p[3]}. Durum {yorum}.")
            return "Disk bilgisi alınamadı."

        elif komut == "sicaklik":
            for yol in [
                "/sys/class/thermal/thermal_zone0/temp",
                "/sys/class/thermal/thermal_zone1/temp",
            ]:
                try:
                    with open(yol) as f:
                        sicak = int(f.read().strip()) / 1000
                    yorum = ("soğuk" if sicak < 40 else
                             "normal" if sicak < 60 else
                             "ılık" if sicak < 75 else "sıcak")
                    return f"Sistem sıcaklığı {sicak:.1f} derece — {yorum}."
                except Exception:
                    pass
            # sensors komutu dene
            cikti = _calistir("sensors 2>/dev/null | grep -iE 'core|temp' | head -3")
            if cikti:
                # İlk derece değerini bul
                m = re.search(r"([\d.]+)°C", cikti)
                if m:
                    return f"Sıcaklık {m.group(1)} derece."
            return "Sıcaklık sensörü bulunamadı."

        elif komut == "pil":
            # Linux
            for yol in [
                "/sys/class/power_supply/BAT0/capacity",
                "/sys/class/power_supply/BAT1/capacity",
            ]:
                try:
                    with open(yol) as f:
                        pil = int(f.read().strip())
                    # Şarjda mı?
                    try:
                        with open(yol.replace("capacity","status")) as f:
                            durum = f.read().strip()
                    except Exception:
                        durum = ""
                    sarj_metni = ""
                    if "Charging" in durum:
                        sarj_metni = ", şarj oluyor"
                    elif "Full" in durum:
                        sarj_metni = ", tam dolu"
                    elif "Discharging" in durum:
                        sarj_metni = ", pil kullanılıyor"
                    yorum = ("kritik, hemen şarj et" if pil < 10 else
                             "düşük" if pil < 25 else
                             "orta" if pil < 60 else "iyi")
                    return f"Pil yüzde {pil}{sarj_metni}. Durum {yorum}."
                except Exception:
                    pass
            return "Pil bilgisi bulunamadı, AC adaptörde olabilirsin."

        elif komut == "ag":
            # IP adresi
            ip_cikti = _calistir("ip route get 8.8.8.8 2>/dev/null | grep -oP 'src [^ ]+' | awk '{print $2}'")
            if not ip_cikti:
                ip_cikti = _calistir("hostname -I 2>/dev/null | awk '{print $1}'")
            # Dış IP
            dis_ip = _calistir("curl -s --max-time 4 ifconfig.me 2>/dev/null || wget -qO- ifconfig.me 2>/dev/null")
            if ip_cikti and dis_ip:
                return (f"Yerel IP adresin {ip_cikti.strip()}, "
                        f"dış IP adresin {dis_ip.strip()[:20]}.")
            elif ip_cikti:
                return f"Yerel IP adresin {ip_cikti.strip()}. Dış IP alınamadı."
            return "Ağ bağlantısı bulunamadı."

        elif komut == "wifi":
            cikti = _calistir("nmcli -t -f active,ssid dev wifi 2>/dev/null | grep '^yes'")
            if cikti:
                ssid = cikti.split(":")[-1].strip()
                return f"Bağlı olduğun ağ: {ssid}."
            cikti = _calistir("iwgetid -r 2>/dev/null")
            if cikti.strip():
                return f"Bağlı olduğun WiFi: {cikti.strip()}."
            return "WiFi bağlantısı bulunamadı ya da kablolu bağlısın."

        elif komut == "internet_test":
            r = subprocess.run(
                ["ping", "-c", "2", "-W", "3", "8.8.8.8"],
                capture_output=True, timeout=10)
            if r.returncode == 0:
                m = re.search(r"time=([\d.]+)", r.stdout.decode())
                ms = m.group(1) if m else "?"
                return f"İnternet bağlantısı var. Gecikme {ms} ms."
            return "İnternet bağlantısı yok ya da çok yavaş."

        elif komut == "uptime":
            cikti = _calistir("uptime -p 2>/dev/null || uptime")
            # Türkçeleştir
            cikti = (cikti.replace("up ", "")
                         .replace("hours", "saat")
                         .replace("hour", "saat")
                         .replace("minutes", "dakika")
                         .replace("minute", "dakika")
                         .replace("days", "gün")
                         .replace("day", "gün")
                         .replace("weeks", "hafta")
                         .replace("week", "hafta")
                         .strip())
            return f"Sistem {cikti} süredir açık."

        elif komut == "ozet":
            sonuclar = []
            # CPU
            cikti = _calistir("top -bn1 | grep -E 'Cpu|cpu'")
            m = re.search(r"([\d.]+)\s*us", cikti)
            if m:
                sonuclar.append(f"İşlemci yüzde {float(m.group(1)):.0f}")
            # RAM
            cikti = _calistir("free -m | grep Mem")
            p = cikti.split()
            if len(p) >= 3:
                yuzde = int(p[2]) * 100 // int(p[1]) if int(p[1]) else 0
                sonuclar.append(f"bellek yüzde {yuzde}")
            # Disk
            cikti = _calistir("df -h / | tail -1")
            p = cikti.split()
            if len(p) >= 5:
                sonuclar.append(f"disk yüzde {p[4].replace('%','')}")
            # Pil
            try:
                with open("/sys/class/power_supply/BAT0/capacity") as f:
                    sonuclar.append(f"pil yüzde {f.read().strip()}")
            except Exception:
                pass
            if sonuclar:
                return "Sistem özeti: " + ", ".join(sonuclar) + "."
            return "Sistem özeti alınamadı."

        elif komut == "acik_uygulamalar":
            cikti = _calistir("wmctrl -l 2>/dev/null | awk '{$1=$2=$3=""; print $0}' | sort -u")
            if cikti:
                pencereler = [s.strip() for s in cikti.splitlines() if s.strip()][:8]
                return ("Açık pencereler: "
                        + ", ".join(pencereler) + ".")
            return "Açık pencere bilgisi alınamadı."

        elif komut == "tor_baslat":
            if hasattr(self, '_cekirdek') and self._cekirdek:
                self._cekirdek.tor.baslat()
                return "Tor başlatılıyor."
            return "Tor başlatmak için sistemi yeniden başlatın."

        elif komut == "onion_adres":
            if hasattr(self, '_cekirdek') and self._cekirdek:
                onion = self._cekirdek.tor.onion_adresi_al("ssh")
                if onion:
                    return f"Onion adresin: {onion}"
                return "Henüz onion adresi oluşmadı. Tor çalışıyor mu?"
            return "Sistem bağlantısı yok."

        elif komut == "uzuv_listesi":
            if hasattr(self, '_cekirdek') and self._cekirdek:
                uzuvlar = self._cekirdek.uzuv.uzuvlar
                if not uzuvlar:
                    return "Kayıtlı uzuv yok."
                liste = []
                for u in uzuvlar.values():
                    durum = str(u.durum)
                    liste.append(f"{u.ad} ({durum})")
                return "Bağlı uzuvlar: " + ", ".join(liste) + "."
            return "Sistem bağlantısı yok."

        elif komut == "guvenlik":
            sonuclar = []
            # Açık portlar
            cikti = _calistir("ss -tlnp 2>/dev/null | grep LISTEN | awk '{print $4}' | cut -d: -f2 | sort -n | head -10")
            if cikti:
                portlar = [p.strip() for p in cikti.splitlines() if p.strip()]
                sonuclar.append(f"Açık portlar: {', '.join(portlar)}")
            # Firewall
            fw = _calistir("ufw status 2>/dev/null | head -1")
            if fw:
                fw_tr = fw.replace("Status: active", "güvenlik duvarı açık").replace("Status: inactive", "güvenlik duvarı kapalı")
                sonuclar.append(fw_tr)
            if sonuclar:
                return " | ".join(sonuclar) + "."
            return "Güvenlik bilgisi alınamadı."

        return f"'{komut}' komutu tanınmadı."
