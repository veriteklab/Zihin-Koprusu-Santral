"""
Zihin Köprüsü v7.0 – Komut Veritabanı  (DÜZELTİLMİŞ v2)

Düzeltmeler v2:
  - kaydet(): os.makedirs dirname boş string çökmesi düzeltildi
  - _kabuk(): executable parametresi /bin/bash değilse graceful fallback
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field, asdict
from enum import Enum
from difflib import SequenceMatcher

from .logcu import Logcu

KAYNAK = "KOMUT_DB"


class HedefOS(str, Enum):
    HEPSI   = "hepsi"
    LINUX   = "linux"
    WINDOWS = "windows"
    ANDROID = "android"


@dataclass
class Komut:
    id: str
    kategori: str
    ad: str
    tetikleyiciler: list[str] = field(default_factory=list)
    tur: str = "kabuk"          # "kabuk" | "konusma" | "uzuv" | "sistem_bilgi" | "hafiza" | "hava" | "takvim" | "makro" | "web_arama"
    yanit_alternatif: list = field(default_factory=list)
    komut: str = ""
    komut_windows: str = ""
    komut_android: str = ""
    yanit: str = ""
    yetkili_bilincler: list[str] = field(default_factory=list)
    hedef_os: str = HedefOS.HEPSI
    uzuv_id: str = ""
    aciklama: str = ""
    aktif: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Komut":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class KomutVeritabani:
    def __init__(self, logcu: Logcu, db_dosyasi: str):
        self.log = logcu
        self.db_dosyasi = db_dosyasi
        self.komutlar: dict[str, Komut] = {}
        self._tetik_indeksi: list[tuple[str, int, Komut]] = []
        self._yukle()

    # ── Disk ─────────────────────────────────────────────────────────────────

    def _yukle(self):
        if os.path.exists(self.db_dosyasi):
            try:
                with open(self.db_dosyasi, "r", encoding="utf-8") as f:
                    data = json.load(f)
                hatali = 0
                for kid, d in data.items():
                    if kid.startswith("__"):
                        continue
                    if not isinstance(d, dict):
                        hatali += 1
                        self.log.uyari(KAYNAK, f"Komut kaydı atlandı ({kid}): dict değil")
                        continue
                    try:
                        komut = Komut.from_dict(d)
                    except TypeError as e:
                        hatali += 1
                        self.log.uyari(KAYNAK, f"Komut kaydı atlandı ({kid}): {e}")
                        continue
                    self.komutlar[kid] = komut
                mesaj = f"{len(self.komutlar)} komut yüklendi."
                if hatali:
                    mesaj += f" {hatali} hatalı kayıt atlandı."
                self._indeks_yenile()
                self.log.bilgi(KAYNAK, mesaj)
            except Exception as e:
                self.log.hata(KAYNAK, f"Komut DB yüklenemedi: {e}")
        else:
            self._varsayilan_yukle()
            self._indeks_yenile()
            self.kaydet()

    def kaydet(self):
        # DÜZELTME: dirname boş string olunca makedirs çöküyordu
        dizin = os.path.dirname(self.db_dosyasi)
        if dizin:
            os.makedirs(dizin, exist_ok=True)
        with open(self.db_dosyasi, "w", encoding="utf-8") as f:
            json.dump({kid: k.to_dict() for kid, k in self.komutlar.items()},
                      f, ensure_ascii=False, indent=2)

    def komut_ekle(self, komut: Komut):
        self.komutlar[komut.id] = komut
        self._indeks_yenile()
        self.kaydet()

    def komut_guncelle(self, komut: Komut):
        self.komutlar[komut.id] = komut
        self._indeks_yenile()
        self.kaydet()

    def komut_sil(self, kid: str):
        self.komutlar.pop(kid, None)
        self._indeks_yenile()
        self.kaydet()

    def _indeks_yenile(self):
        indeks: list[tuple[str, int, Komut]] = []
        for komut in self.komutlar.values():
            for tetik in komut.tetikleyiciler:
                tetik_l = self._normalize(tetik)
                if tetik_l:
                    indeks.append((tetik_l, len(tetik_l), komut))
        indeks.sort(key=lambda item: item[1], reverse=True)
        self._tetik_indeksi = indeks

    # ── Eşleştirme ───────────────────────────────────────────────────────────

    def esles(self, bilinc: str, metin: str, hedef_os: str = HedefOS.LINUX) -> Komut | None:
        metin_l = self._normalize(metin)
        for tetik_l, _uzunluk, komut in self._tetik_indeksi:
            if not komut.aktif:
                continue
            if komut.yetkili_bilincler and bilinc not in komut.yetkili_bilincler:
                continue
            if komut.hedef_os not in (HedefOS.HEPSI, hedef_os):
                continue
            if len(tetik_l) <= 3 and " " not in tetik_l:
                if re.search(rf"(?<!\w){re.escape(tetik_l)}(?!\w)", metin_l):
                    return komut
            elif tetik_l in metin_l:
                return komut

        en_iyi: tuple[float, int, Komut] | None = None
        for komut in self.komutlar.values():
            if not komut.aktif:
                continue
            if komut.yetkili_bilincler and bilinc not in komut.yetkili_bilincler:
                continue
            if komut.hedef_os not in (HedefOS.HEPSI, hedef_os):
                continue
            for tetik in komut.tetikleyiciler:
                skor = self._tetik_skoru(metin_l, tetik)
                if skor >= 0.78:
                    uzunluk = len(self._normalize(tetik))
                    if en_iyi is None or (skor, uzunluk) > (en_iyi[0], en_iyi[1]):
                        en_iyi = (skor, uzunluk, komut)
        return en_iyi[2] if en_iyi else None

    @classmethod
    def _tetik_eslesir(cls, metin_l: str, tetik: str) -> bool:
        return cls._tetik_skoru(metin_l, tetik) >= 0.78

    @classmethod
    def _tetik_skoru(cls, metin_l: str, tetik: str) -> float:
        tetik_l = cls._normalize(tetik)
        if not tetik_l:
            return 0.0
        # "sa" gibi kısa tetikler "saat" içinde eşleşmemeli.
        if len(tetik_l) <= 3 and " " not in tetik_l:
            return 1.0 if re.search(rf"(?<!\w){re.escape(tetik_l)}(?!\w)", metin_l) else 0.0
        if tetik_l in metin_l:
            return 1.0
        metin_ilk = metin_l.split()[0] if metin_l.split() else ""
        tetik_ilk = tetik_l.split()[0] if tetik_l.split() else ""
        if metin_ilk and tetik_ilk and (len(metin_ilk) <= 3 or len(tetik_ilk) <= 3) and metin_ilk != tetik_ilk:
            return 0.0
        if (
            metin_ilk and tetik_ilk and " " in tetik_l
            and len(metin_ilk) >= 4 and len(tetik_ilk) >= 4
            and metin_ilk[0] != tetik_ilk[0]
            and SequenceMatcher(None, metin_ilk, tetik_ilk).ratio() < 0.82
        ):
            return 0.0
        # STT küçük sapmaları için kelime sıralı benzerlik.
        if abs(len(metin_l) - len(tetik_l)) <= max(6, int(len(tetik_l) * 0.35)):
            return SequenceMatcher(None, metin_l, tetik_l).ratio()
        # Uzun cümlede tetikleyici kadar pencere gezdir.
        kelimeler = metin_l.split()
        t_kelimeler = tetik_l.split()
        if len(t_kelimeler) > 1 and len(kelimeler) >= len(t_kelimeler):
            en = 0.0
            pencere = len(t_kelimeler)
            for i in range(0, len(kelimeler) - pencere + 1):
                parca = " ".join(kelimeler[i:i + pencere])
                en = max(en, SequenceMatcher(None, parca, tetik_l).ratio())
            return en
        return 0.0

    @staticmethod
    def _normalize(metin: str) -> str:
        try:
            from .niyet_motoru import normalize_tr
            return normalize_tr(metin)
        except Exception:
            pass
        ceviri = str.maketrans({
            "ç": "c", "Ç": "c",
            "ğ": "g", "Ğ": "g",
            "ı": "i", "I": "i", "İ": "i",
            "ö": "o", "Ö": "o",
            "ş": "s", "Ş": "s",
            "ü": "u", "Ü": "u",
        })
        return metin.translate(ceviri).lower().strip()

    def calistir(self, bilinc: str, metin: str,
                 hedef_os: str = HedefOS.LINUX,
                 uzuv_yoneticisi=None) -> str | None:
        komut = self.esles(bilinc, metin, hedef_os)
        if not komut:
            return None

        if komut.tur == "konusma":
            # Alternatif yanıt varsa rastgele seç
            if komut.yanit_alternatif:
                import random
                secenekler = [komut.yanit] + komut.yanit_alternatif
                return random.choice(secenekler)
            return komut.yanit

        # Özel türler — cekirdek seviyesinde işlenir
        if komut.tur in ("sistem_bilgi", "hafiza", "hava", "takvim", "makro"):
            return f"__TUR:{komut.tur}:{komut.komut}__"

        if komut.tur == "web_arama":
            return f"__WEB:{komut.komut}__"

        if komut.tur == "uzuv" and uzuv_yoneticisi and komut.uzuv_id:
            return uzuv_yoneticisi.komut_calistir(komut.uzuv_id, komut.komut)

        # kabuk
        cmd = komut.komut
        if hedef_os == HedefOS.WINDOWS and komut.komut_windows:
            cmd = komut.komut_windows
        elif hedef_os == HedefOS.ANDROID and komut.komut_android:
            cmd = komut.komut_android

        sonuc = self._kabuk(cmd)
        if komut.yanit and sonuc == "Komut tamamlandı.":
            return komut.yanit
        return sonuc

    def _kabuk(self, cmd: str) -> str:
        self.log.bilgi(KAYNAK, f"Çalıştırılıyor: {cmd}")
        try:
            # DÜZELTME: /bin/bash yoksa (Windows vb.) shell=True ile devam
            import shutil as _sh
            exec_shell = "/bin/bash" if _sh.which("bash") else None
            if self._arkaplan_komutu_mu(cmd):
                subprocess.Popen(
                    cmd, shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **({"executable": exec_shell} if exec_shell else {}),
                )
                return "Komut tamamlandı."
            cikti = subprocess.check_output(
                cmd, shell=True, stderr=subprocess.STDOUT,
                timeout=30,
                **({"executable": exec_shell} if exec_shell else {}),
            ).decode("utf-8", errors="replace").strip()
            return cikti or "Komut tamamlandı."
        except subprocess.TimeoutExpired:
            return "Zaman aşımı."
        except subprocess.CalledProcessError as e:
            return (e.output.decode("utf-8", errors="replace").strip()
                    if e.output else "Komut hata verdi.")
        except Exception as e:
            return f"Hata: {e}"

    @staticmethod
    def _arkaplan_komutu_mu(cmd: str) -> bool:
        """GUI/URL açıcı komutlarda shell çıktısı bekleyip zaman aşımına düşme."""
        metin = (cmd or "").lower()
        arkaplan_isaretleri = (
            "xdg-open ", "gnome-calculator", "kcalc", "galculator", "xcalc",
            "gnome-terminal", "xfce4-terminal", "konsole", "xterm",
            "nautilus", "thunar", "nemo", "dolphin", "gedit", "kate",
            "mousepad", "pluma", "vlc", "spotify", "discord",
            "google-chrome", "chromium", "firefox", "notify-send ",
        )
        return any(isaret in metin for isaret in arkaplan_isaretleri)

    # ── Kategoriler ──────────────────────────────────────────────────────────

    def kategoriler(self) -> list[str]:
        return sorted(set(k.kategori for k in self.komutlar.values()))

    def kategoriye_gore(self, kategori: str) -> list[Komut]:
        return [k for k in self.komutlar.values() if k.kategori == kategori]

    # ── Varsayılan Komut Seti ─────────────────────────────────────────────────

    def _varsayilan_yukle(self):
        def ekle(kategori, ad, tetikler, komut="", komut_w="", komut_a="",
                 yanit="", tur="kabuk", yetki=None, os_=HedefOS.HEPSI,
                 aciklama="", yanit_alt=None):
            kid = f"{kategori}_{ad}".lower().replace(" ", "_")[:40]
            self.komutlar[kid] = Komut(
                id=kid, kategori=kategori, ad=ad,
                tetikleyiciler=tetikler, tur=tur,
                komut=komut, komut_windows=komut_w, komut_android=komut_a,
                yanit=yanit,
                yanit_alternatif=yanit_alt or [],
                yetkili_bilincler=yetki or [],
                hedef_os=os_, aciklama=aciklama,
            )

        # ════════════════════════════════════════════════════════════════════
        # SOHBET & KİŞİLİK
        # ════════════════════════════════════════════════════════════════════
        ekle("Sohbet", "Merhaba",
             ["merhaba","selam","günaydın","iyi günler","hayırlı sabahlar","hayırlı akşamlar"],
             yanit="Merhaba Sahip! Her şey emrinizde.", tur="konusma",
             yanit_alt=["Merhaba! Sizi bekledim Sahip.",
                        "Selam Sahip! Söyleyin, dinliyorum.",
                        "Günaydın! Bugün ne yapmamı istersiniz?"])
        ekle("Sohbet", "İyi Geceler",
             ["iyi geceler","tünaydın","hoşça kal","görüşürüz","bay bay"],
             yanit="İyi geceler Sahip. Gerekirse buradayım.", tur="konusma")
        ekle("Sohbet", "Nasılsın",
             ["nasılsın","nasıl gidiyor","ne haber","naber","nasıl gidiyorsunuz"],
             yanit="İyiyim teşekkür ederim Sahip. Siz nasılsınız?", tur="konusma",
             yanit_alt=["Harika durumdayım Sahip, teşekkürler!",
                        "Çalışır durumdayım ve emrinizdeyim."])
        ekle("Sohbet", "Teşekkür",
             ["teşekkür ederim","teşekkürler","sağ ol","eyvallah","çok sağ ol"],
             yanit="Rica ederim Sahip, her zaman.", tur="konusma",
             yanit_alt=["Ne demek Sahip, görevim bu.",
                        "Bir şey değil, başka bir şey var mı?"])
        ekle("Sohbet", "Tamam",
             ["anlaşıldı","anladım","peki o zaman","olur tamam"],
             yanit="Anlaşıldı Sahip.", tur="konusma")
        ekle("Sohbet", "Sen Kimsin",
             ["sen kimsin","ne yapabilirsin","yeteneklerin neler","hakkında bilgi"],
             yanit="Ben Zihin Köprüsü v7.0 — sesinizle bilgisayarınızı, uzak cihazlarınızı ve web'i yönetmenizi sağlayan yapay zeka destekli asistanınızım.",
             tur="konusma")
        ekle("Sohbet", "Saçmalama",
             ["saçmalıyorsun","yanlış söyledin","hata yaptın","anlayamadın"],
             yanit="Özür dilerim Sahip, tekrar söyler misiniz?", tur="konusma")
        ekle("Sohbet", "Evet",
             ["evet","doğru","aynen","kesinlikle","tabii ki","haklısın"],
             yanit="Anlaşıldı Sahip.", tur="konusma")
        ekle("Sohbet", "Hayır",
             ["hayır","yok","olmaz","istemiyorum","vazgeç"],
             yanit="Peki Sahip, başka bir şey emreder misiniz?", tur="konusma")
        ekle("Sohbet", "Yardım",
             ["yardım et","ne yapabilirim","komutları söyle","nasıl kullanacağım"],
             yanit="Ses, medya, pencere, dosya, web, sistem ve çok daha fazlası için sesli komut verebilirsiniz. 'Komutları listele' deyin tam listeyi alın.",
             tur="konusma")
        ekle("Sohbet", "Komutları Listele",
             ["komutları listele","hangi komutlar var","ne diyebilirim"],
             komut="echo 'Komut listesi GUI panelinden görüntülenebilir.'",
             yanit="Kategoriler: Ses, Medya, Pencere, Klavye, Fare, Uygulama, Tarayıcı, Dosya, Sistem, Ağ, Güvenlik ve daha fazlası. GUI panelinden tam listeyi görebilirsiniz.",
             tur="konusma")
        ekle("Sohbet", "Kaç Komut",
             ["kaç komutun var","komut sayısı","toplam komut"],
             yanit="Yüzlerce sesli komutum var Sahip. Hepsini GUI'deki komut veritabanı panelinden görebilirsiniz.",
             tur="konusma")
        ekle("Sohbet", "Aferin",
             ["aferin","bravo","helal olsun","süpersin","harika iş","iyi iş"],
             yanit="Teşekkür ederim Sahip!", tur="konusma",
             yanit_alt=["Memnun olduğunuza sevindim!",
                        "Elimden geleni yapıyorum Sahip."])
        ekle("Sohbet", "Dur",
             ["dur","bekle","şimdi değil","bir saniye"],
             yanit="Bekliyorum Sahip.", tur="konusma")
        ekle("Sohbet", "Devam Et",
             ["devam et","dinliyorum","söyle"],
             yanit="Buyurun Sahip.", tur="konusma")

        # ════════════════════════════════════════════════════════════════════
        # SES KONTROLİ
        # ════════════════════════════════════════════════════════════════════
        ekle("Ses", "Ses Yükselt",
             ["sesi yükselt","sesi artır","daha yüksek ses","ses açık olsun","volumü artır"],
             komut="pactl set-sink-volume @DEFAULT_SINK@ +10%",
             komut_w="nircmd.exe changesysvolume 6554",
             os_=HedefOS.HEPSI)
        ekle("Ses", "Ses Alçalt",
             ["sesi alçalt","sesi azalt","sesi kıs","daha kısık ses","volumü azalt"],
             komut="pactl set-sink-volume @DEFAULT_SINK@ -10%",
             komut_w="nircmd.exe changesysvolume -6554",
             os_=HedefOS.HEPSI)
        ekle("Ses", "Ses Yüzde Elli",
             ["sesi yüzde elliye ayarla","ses yarıya","orta ses"],
             komut="pactl set-sink-volume @DEFAULT_SINK@ 50%", os_=HedefOS.LINUX)
        ekle("Ses", "Ses Yüzde Yüz",
             ["sesi tam aç","ses yüzde yüz","maksimum ses"],
             komut="pactl set-sink-volume @DEFAULT_SINK@ 100%", os_=HedefOS.LINUX)
        ekle("Ses", "Sessiz",
             ["sesi kapat","sessiz moda al","sesi kes","mute yap","zil sesini kapat"],
             komut="pactl set-sink-mute @DEFAULT_SINK@ 1",
             komut_w="nircmd.exe mutesysvolume 1",
             os_=HedefOS.HEPSI)
        ekle("Ses", "Sessizliği Kaldır",
             ["sesi geri aç","sessizden çık","mute kaldır","sesi aç unmute"],
             komut="pactl set-sink-mute @DEFAULT_SINK@ 0",
             komut_w="nircmd.exe mutesysvolume 0",
             os_=HedefOS.HEPSI)
        ekle("Ses", "Ses Durumu",
             ["ses seviyesi kaç","ses kaçta","ses yüzdesi nedir"],
             komut=r"pactl get-sink-volume @DEFAULT_SINK@ | grep -oP '\d+%' | head -1",
             os_=HedefOS.LINUX)
        ekle("Ses", "Mikrofon Kapat",
             ["mikrofonu kapat","mikrofon sessiz","mic kapat"],
             komut="pactl set-source-mute @DEFAULT_SOURCE@ 1", os_=HedefOS.LINUX)
        ekle("Ses", "Mikrofon Aç",
             ["mikrofonu aç","mic aç","mikrofon aktif"],
             komut="pactl set-source-mute @DEFAULT_SOURCE@ 0", os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # MEDYA KONTROLÜ
        # ════════════════════════════════════════════════════════════════════
        ekle("Medya", "Oynat Duraklat",
             ["müziği oynat","müziği duraklat","medyayı başlat","müzik durdur"],
             komut="playerctl play-pause", os_=HedefOS.LINUX)
        ekle("Medya", "Sonraki Parça",
             ["sonraki şarkı","sonraki parça","ileri şarkı","müziği geç"],
             komut="playerctl next", os_=HedefOS.LINUX)
        ekle("Medya", "Önceki Parça",
             ["önceki şarkı","önceki parça","geri şarkı","başa al"],
             komut="playerctl previous", os_=HedefOS.LINUX)
        ekle("Medya", "Medyayı Durdur",
             ["medyayı tamamen durdur","müziği kapat","playerı durdur"],
             komut="playerctl stop", os_=HedefOS.LINUX)
        ekle("Medya", "Şu An Ne Çalıyor",
             ["şu an ne çalıyor","hangi şarkı","müzik bilgisi","ne oynuyor"],
             komut="playerctl metadata --format '{{ artist }} - {{ title }}' 2>/dev/null || echo 'Çalan müzik yok'",
             os_=HedefOS.LINUX)
        ekle("Medya", "Ses Çıkışı",
             ["ses çıkışları","hoparlörler","çıkış cihazları"],
             komut="pactl list sinks short", os_=HedefOS.LINUX)
        ekle("Medya", "VLC Aç",
             ["vlc aç","video oynatıcı aç","medya oynatıcı"],
             komut="vlc &", os_=HedefOS.LINUX)
        ekle("Medya", "Spotify Aç",
             ["spotify aç","spotify başlat","müzik uygulaması"],
             komut="spotify & 2>/dev/null || flatpak run com.spotify.Client &",
             os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # PENCERE YÖNETİMİ
        # ════════════════════════════════════════════════════════════════════
        ekle("Pencere", "Tam Ekran",
             ["tam ekrana al","pencereyi büyüt","maximize et","pencere büyüsün"],
             komut="xdotool getactivewindow windowstate --add MAXIMIZED_VERT,MAXIMIZED_HORZ",
             os_=HedefOS.LINUX)
        ekle("Pencere", "Pencere Küçült",
             ["pencereyi küçült","simge durumuna al","minimize et","görev çubuğuna at"],
             komut="xdotool getactivewindow windowminimize", os_=HedefOS.LINUX)
        ekle("Pencere", "Pencere Kapat",
             ["pencereyi kapat","uygulamayı kapat","bu programı kapat"],
             komut="xdotool key alt+F4", os_=HedefOS.LINUX)
        ekle("Pencere", "Pencere Normale Al",
             ["pencereyi normale al","tam ekrandan çık","restore et"],
             komut="xdotool getactivewindow windowstate --remove MAXIMIZED_VERT,MAXIMIZED_HORZ",
             os_=HedefOS.LINUX)
        ekle("Pencere", "Bir Sonraki Pencere",
             ["bir sonraki pencere","diğer pencereye geç","alt tab"],
             komut="xdotool key alt+Tab", os_=HedefOS.LINUX)
        ekle("Pencere", "Önceki Pencere",
             ["önceki pencereye geç","alt shift tab","geri pencere"],
             komut="xdotool key alt+shift+Tab", os_=HedefOS.LINUX)
        ekle("Pencere", "Masaüstünü Göster",
             ["masaüstünü göster","tüm pencereleri küçült","masaüstüne git"],
             komut="xdotool key super+d", os_=HedefOS.LINUX)
        ekle("Pencere", "Pencereleri Listele",
             ["açık pencereleri listele","hangi pencereler açık","pencere listesi"],
             komut="wmctrl -l 2>/dev/null | awk '{for(i=4;i<=NF;i++) printf $i\" \"; print \"\"}'",
             os_=HedefOS.LINUX)
        ekle("Pencere", "Ekranı Böl Sol",
             ["pencereyi sola taşı","sol yarıya al","ekranı böl sol"],
             komut="xdotool key super+Left", os_=HedefOS.LINUX)
        ekle("Pencere", "Ekranı Böl Sağ",
             ["pencereyi sağa taşı","sağ yarıya al","ekranı böl sağ"],
             komut="xdotool key super+Right", os_=HedefOS.LINUX)
        ekle("Pencere", "Tüm Uygulamalar",
             ["uygulama menüsü","tüm uygulamalar","launcher aç"],
             komut="xdotool key super", os_=HedefOS.LINUX)
        ekle("Pencere", "Görev Değiştirici",
             ["görev değiştirici","uygulama listesi","açık programlar"],
             komut="xdotool key super+Tab", os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # KLAVYE & KISA YOLLAR
        # ════════════════════════════════════════════════════════════════════
        ekle("Klavye", "Kopyala",
             ["kopyala","kopyalamak istiyorum","seçileni kopyala"],
             komut="xdotool key ctrl+c", os_=HedefOS.LINUX)
        ekle("Klavye", "Yapıştır",
             ["yapıştır","panodan yapıştır","kopyaladığını yapıştır"],
             komut="xdotool key ctrl+v", os_=HedefOS.LINUX)
        ekle("Klavye", "Kes",
             ["kes ve kopyala","seçileni kes","taşımak için kes"],
             komut="xdotool key ctrl+x", os_=HedefOS.LINUX)
        ekle("Klavye", "Tümünü Seç",
             ["tümünü seç","hepsini seç","her şeyi seç"],
             komut="xdotool key ctrl+a", os_=HedefOS.LINUX)
        ekle("Klavye", "Geri Al",
             ["geri al","son işlemi geri al","undo"],
             komut="xdotool key ctrl+z", os_=HedefOS.LINUX)
        ekle("Klavye", "Yinele",
             ["yinele","ileri al","redo","geri alınanı geri al"],
             komut="xdotool key ctrl+y", os_=HedefOS.LINUX)
        ekle("Klavye", "Kaydet",
             ["kaydet","dosyayı kaydet","değişiklikleri kaydet"],
             komut="xdotool key ctrl+s", os_=HedefOS.LINUX)
        ekle("Klavye", "Farklı Kaydet",
             ["farklı kaydet","yeni isimle kaydet","ctrl shift s"],
             komut="xdotool key ctrl+shift+s", os_=HedefOS.LINUX)
        ekle("Klavye", "Yazdır",
             ["yazdır","print","yazıcıya gönder"],
             komut="xdotool key ctrl+p", os_=HedefOS.LINUX)
        ekle("Klavye", "Bul",
             ["bul","ara","ctrl f","arama yap","içinde ara"],
             komut="xdotool key ctrl+f", os_=HedefOS.LINUX)
        ekle("Klavye", "Bul Değiştir",
             ["bul değiştir","ctrl h","bul ve değiştir"],
             komut="xdotool key ctrl+h", os_=HedefOS.LINUX)
        ekle("Klavye", "Yeni Dosya",
             ["yeni dosya","yeni belgeler","ctrl n"],
             komut="xdotool key ctrl+n", os_=HedefOS.LINUX)
        ekle("Klavye", "Aç",
             ["dosya aç","ctrl o","klasör aç"],
             komut="xdotool key ctrl+o", os_=HedefOS.LINUX)
        ekle("Klavye", "Yeni Sekme",
             ["yeni sekme aç","yeni tab aç"],
             komut="xdotool key ctrl+t", os_=HedefOS.LINUX)
        ekle("Klavye", "Sekmeyi Kapat",
             ["sekmeyi kapat","aktif sekmeyi kapat","tabı kapat"],
             komut="xdotool key ctrl+w", os_=HedefOS.LINUX)
        ekle("Klavye", "Bir Sonraki Sekme",
             ["bir sonraki sekme","sağdaki sekme","sonraki tab"],
             komut="xdotool key ctrl+Tab", os_=HedefOS.LINUX)
        ekle("Klavye", "Bir Önceki Sekme",
             ["bir önceki sekme","soldaki sekme","önceki tab"],
             komut="xdotool key ctrl+shift+Tab", os_=HedefOS.LINUX)
        ekle("Klavye", "Sayfayı Yenile",
             ["sayfayı yenile","yenile f5","refresh yap"],
             komut="xdotool key F5", os_=HedefOS.LINUX)
        ekle("Klavye", "Sert Yenile",
             ["önbelleği temizle yenile","sert yenile","ctrl f5"],
             komut="xdotool key ctrl+F5", os_=HedefOS.LINUX)
        ekle("Klavye", "Tarayıcı Tam Ekran",
             ["tarayıcıyı tam ekran yap","f11 bas","tam ekran tarayıcı"],
             komut="xdotool key F11", os_=HedefOS.LINUX)
        ekle("Klavye", "İptal",
             ["iptal et","esc bas","işlemi iptal et"],
             komut="xdotool key Escape", os_=HedefOS.LINUX)
        ekle("Klavye", "Onayla",
             ["onay ver","enter bas","onayla"],
             komut="xdotool key Return", os_=HedefOS.LINUX)
        ekle("Klavye", "Tab Tuşu",
             ["tab bas","sekme tuşuna bas","tab tuşu"],
             komut="xdotool key Tab", os_=HedefOS.LINUX)
        ekle("Klavye", "Boşluk",
             ["boşluk bas","space bas","boşluk tuşu"],
             komut="xdotool key space", os_=HedefOS.LINUX)
        ekle("Klavye", "Yukarı Ok",
             ["yukarı ok tuşu","yukarı bas"],
             komut="xdotool key Up", os_=HedefOS.LINUX)
        ekle("Klavye", "Aşağı Ok",
             ["aşağı ok tuşu","aşağı bas"],
             komut="xdotool key Down", os_=HedefOS.LINUX)
        ekle("Klavye", "Sola Ok",
             ["sola ok tuşu","sol ok bas"],
             komut="xdotool key Left", os_=HedefOS.LINUX)
        ekle("Klavye", "Sağa Ok",
             ["sağa ok tuşu","sağ ok bas"],
             komut="xdotool key Right", os_=HedefOS.LINUX)
        ekle("Klavye", "Sil Delete",
             ["delete bas","del tuşu","ileri sil"],
             komut="xdotool key Delete", os_=HedefOS.LINUX)
        ekle("Klavye", "Backspace",
             ["geri sil","backspace bas","son karakteri sil"],
             komut="xdotool key BackSpace", os_=HedefOS.LINUX)
        ekle("Klavye", "Satır Başı",
             ["satır başına git","home tuşu","başa git"],
             komut="xdotool key Home", os_=HedefOS.LINUX)
        ekle("Klavye", "Satır Sonu",
             ["satır sonuna git","end tuşu","sona git"],
             komut="xdotool key End", os_=HedefOS.LINUX)
        ekle("Klavye", "Sayfa Yukarı",
             ["sayfa yukarı","page up","bir sayfa yukarı"],
             komut="xdotool key Page_Up", os_=HedefOS.LINUX)
        ekle("Klavye", "Sayfa Aşağı",
             ["sayfa aşağı","page down","bir sayfa aşağı"],
             komut="xdotool key Page_Down", os_=HedefOS.LINUX)
        ekle("Klavye", "Ekran Görüntüsü Kısayol",
             ["ekran görüntüsü kısayol","print screen","prt scr"],
             komut="xdotool key Print", os_=HedefOS.LINUX)
        ekle("Klavye", "Zoom Artır",
             ["yaklaştır","zoom artır","büyüt ctrl artı"],
             komut="xdotool key ctrl+plus", os_=HedefOS.LINUX)
        ekle("Klavye", "Zoom Azalt",
             ["uzaklaştır","zoom azalt","küçült ctrl eksi"],
             komut="xdotool key ctrl+minus", os_=HedefOS.LINUX)
        ekle("Klavye", "Zoom Sıfırla",
             ["zoom sıfırla","normal boyut","ctrl sıfır"],
             komut="xdotool key ctrl+0", os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # FARE / MOUSE KONTROLÜ
        # ════════════════════════════════════════════════════════════════════
        ekle("Fare", "Sol Tıkla",
             ["sol tıkla","fareye tıkla","tıkla","click"],
             komut="xdotool click 1", os_=HedefOS.LINUX)
        ekle("Fare", "Sağ Tıkla",
             ["sağ tıkla","sağ click","sağ tuş","menü aç fare"],
             komut="xdotool click 3", os_=HedefOS.LINUX)
        ekle("Fare", "Çift Tıkla",
             ["çift tıkla","double click","iki kez tıkla"],
             komut="xdotool click --repeat 2 1", os_=HedefOS.LINUX)
        ekle("Fare", "Yukarı Kaydır",
             ["yukarı kaydır","sayfayı yukarı kaydır","scroll up"],
             komut="xdotool click 4", os_=HedefOS.LINUX)
        ekle("Fare", "Aşağı Kaydır",
             ["aşağı kaydır","sayfayı aşağı kaydır","scroll down"],
             komut="xdotool click 5", os_=HedefOS.LINUX)
        ekle("Fare", "Fare Ortaya",
             ["fareyi ortaya taşı","fare ekran ortası","mouse ortala"],
             komut="xdotool mousemove --sync $(xdotool getdisplaygeometry | awk '{print int($1/2), int($2/2)}')",
             os_=HedefOS.LINUX)
        ekle("Fare", "Fare Konumu",
             ["fare nerede","mouse konumu","fare koordinatları"],
             komut="xdotool getmouselocation --shell | grep -E 'X=|Y='",
             os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # TARAYICI KONTROLÜ
        # ════════════════════════════════════════════════════════════════════
        ekle("Tarayıcı", "Geri Git",
             ["geri git","önceki sayfaya git","tarayıcıda geri"],
             komut="xdotool key alt+Left", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "İleri Git",
             ["ileri git","sonraki sayfaya git","tarayıcıda ileri"],
             komut="xdotool key alt+Right", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "Adresi Kopyala",
             ["adresi kopyala","url kopyala","sayfa linkini kopyala"],
             komut="xdotool key ctrl+l ctrl+c", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "Gizli Sekme",
             ["gizli sekme","incognito","özel sekme","private mod"],
             komut="xdotool key ctrl+shift+n", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "Yer İmi Ekle",
             ["yer imi ekle","favorilere ekle","bookmark ekle"],
             komut="xdotool key ctrl+d", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "Yer İmleri",
             ["yer imlerini aç","favorilerim","bookmark listesi"],
             komut="xdotool key ctrl+shift+b", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "Geçmiş",
             ["tarayıcı geçmişi","ziyaret geçmişi","history aç"],
             komut="xdotool key ctrl+h", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "İndirmeler",
             ["indirmeler","downloads","indirilen dosyalar"],
             komut="xdotool key ctrl+j", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "Geliştirici Araçları",
             ["geliştirici araçları","developer tools","f12"],
             komut="xdotool key F12", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "Sayfayı Bul",
             ["sayfada bul","sayfa içi arama","ctrl f ara"],
             komut="xdotool key ctrl+f", os_=HedefOS.LINUX)
        ekle("Tarayıcı", "Kapalı Sekmeyi Geri Al",
             ["kapalı sekmeyi geri getir","son sekmeyi geri al","ctrl shift t"],
             komut="xdotool key ctrl+shift+t", os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # WEB SİTELERİ AÇMA
        # ════════════════════════════════════════════════════════════════════
        ekle("Web", "YouTube",
             ["youtube aç","youtubeye git","youtube'a git"],
             komut="xdg-open https://youtube.com", os_=HedefOS.LINUX)
        ekle("Web", "Gmail",
             ["gmail aç","maile git","gmail'e git","e-postayı aç"],
             komut="xdg-open https://mail.google.com", os_=HedefOS.LINUX)
        ekle("Web", "Google",
             ["google aç","google'a git","arama motorunu aç"],
             komut="xdg-open https://google.com", os_=HedefOS.LINUX)
        ekle("Web", "GitHub",
             ["github aç","github'a git","kod deposu"],
             komut="xdg-open https://github.com", os_=HedefOS.LINUX)
        ekle("Web", "Wikipedia",
             ["wikipedia aç","vikipediye git","ansiklopedi aç"],
             komut="xdg-open https://tr.wikipedia.org", os_=HedefOS.LINUX)
        ekle("Web", "Google Drive",
             ["google drive aç","bulut dosyaları","drive'a git"],
             komut="xdg-open https://drive.google.com", os_=HedefOS.LINUX)
        ekle("Web", "Google Haritalar",
             ["haritayı aç","google maps","haritalar"],
             komut="xdg-open https://maps.google.com", os_=HedefOS.LINUX)
        ekle("Web", "Google Takvim",
             ["google takvim","takvibi aç","etkinliklerim"],
             komut="xdg-open https://calendar.google.com", os_=HedefOS.LINUX)
        ekle("Web", "Google Çeviri",
             ["çeviri aç","google çeviri","translate"],
             komut="xdg-open https://translate.google.com", os_=HedefOS.LINUX)
        ekle("Web", "Haber",
             ["haberlere git","haberler","gündem"],
             komut="xdg-open https://news.google.com", os_=HedefOS.LINUX)
        ekle("Web", "ChatGPT",
             ["chatgpt aç","chatgpt'ye git","yapay zeka sohbet"],
             komut="xdg-open https://chat.openai.com", os_=HedefOS.LINUX)
        ekle("Web", "Claude",
             ["claude aç","claude'a git","anthropic"],
             komut="xdg-open https://claude.ai", os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # WEB ARAMA
        # ════════════════════════════════════════════════════════════════════
        ekle("Arama", "Google Ara",
             ["google'da ara","internette ara","web'de ara"],
             tur="web_arama", komut="google")
        ekle("Arama", "YouTube Ara",
             ["youtube'da ara","video ara","youtube'da bul"],
             tur="web_arama", komut="youtube")
        ekle("Arama", "Wikipedia Ara",
             ["vikipedide ara","ansiklopedide ara","wikipedia'da bul"],
             tur="web_arama", komut="wikipedia")
        ekle("Arama", "Hava Durumu",
             ["hava durumu","bugün hava nasıl","hava durumunu öğren","yarın hava"],
             tur="hava", komut="")
        ekle("Arama", "Takvim",
             ["bugün gündem","takvime bak","etkinlikler","ajandayı aç"],
             tur="takvim", komut="")

        # ════════════════════════════════════════════════════════════════════
        # UYGULAMA AÇMA
        # ════════════════════════════════════════════════════════════════════
        ekle("Uygulama", "Firefox",
             ["firefox aç","firefox başlat","mozilla aç"],
             komut="firefox &",
             komut_w="start firefox",
             os_=HedefOS.HEPSI)
        ekle("Uygulama", "Chrome",
             ["chrome aç","google chrome aç","chromium aç"],
             komut="google-chrome & 2>/dev/null || chromium-browser & 2>/dev/null || chromium &",
             komut_w="start chrome",
             os_=HedefOS.HEPSI)
        ekle("Uygulama", "Terminal",
             ["terminal aç","konsol aç","komut satırı aç"],
             komut="x-terminal-emulator & 2>/dev/null || gnome-terminal & 2>/dev/null || xterm &",
             os_=HedefOS.LINUX)
        ekle("Uygulama", "VSCode",
             ["vscode aç","visual studio code","kod editörünü aç"],
             komut="code . &",
             komut_w="code .",
             os_=HedefOS.HEPSI)
        ekle("Uygulama", "Dosya Yöneticisi",
             ["dosya yöneticisi aç","klasör penceresi","ev klasörünü aç"],
             komut="nautilus & 2>/dev/null || thunar & 2>/dev/null || nemo &",
             os_=HedefOS.LINUX)
        ekle("Uygulama", "Metin Editörü",
             ["metin editörü aç","not defterini aç","yazı editörü"],
             komut="gedit & 2>/dev/null || mousepad & 2>/dev/null || kate &",
             os_=HedefOS.LINUX)
        ekle("Uygulama", "Hesap Makinesi",
             ["hesap makinesini aç","hesap makinesi","kalkülator aç"],
             komut="gnome-calculator & 2>/dev/null || kcalc &",
             os_=HedefOS.LINUX)
        ekle("Uygulama", "Sistem Ayarları",
             ["sistem ayarlarını aç","ayarları aç","kontrol paneli aç"],
             komut="gnome-control-center & 2>/dev/null || xfce4-settings-manager &",
             komut_w="control",
             os_=HedefOS.HEPSI)
        ekle("Uygulama", "Görev Yöneticisi",
             ["görev yöneticisini aç","sistem monitörünü aç","cpu kullanımını göster"],
             komut="gnome-system-monitor & 2>/dev/null || htop &",
             komut_w="taskmgr",
             os_=HedefOS.HEPSI)
        ekle("Uygulama", "Disk Aracı",
             ["disk aracını aç","disk yöneticisi","diskleri göster"],
             komut="gnome-disks &", os_=HedefOS.LINUX)
        ekle("Uygulama", "Müzik Çalar",
             ["müzik çaları aç","rhythmbox","müzik yöneticisi"],
             komut="rhythmbox & 2>/dev/null || audacious &",
             os_=HedefOS.LINUX)
        ekle("Uygulama", "Resim Görüntüleyici",
             ["resim görüntüleyici","fotoğraf izleyici","resim aç"],
             komut="eog & 2>/dev/null || shotwell & 2>/dev/null || viewnior &",
             os_=HedefOS.LINUX)
        ekle("Uygulama", "PDF Okuyucu",
             ["pdf oku","pdf görüntüleyici aç","belge okuyucu"],
             komut="evince & 2>/dev/null || okular &",
             os_=HedefOS.LINUX)
        ekle("Uygulama", "Ofis Programı",
             ["libreoffice aç","ofis programı","word benzeri program"],
             komut="libreoffice &",
             os_=HedefOS.LINUX)
        ekle("Uygulama", "Kelime İşlemci",
             ["kelime işlemci aç","libreoffice writer","yazı programı"],
             komut="libreoffice --writer &", os_=HedefOS.LINUX)
        ekle("Uygulama", "Hesap Tablosu",
             ["hesap tablosu","libreoffice calc","excel benzeri"],
             komut="libreoffice --calc &", os_=HedefOS.LINUX)
        ekle("Uygulama", "Sunum",
             ["sunum programı aç","libreoffice impress","powerpoint benzeri"],
             komut="libreoffice --impress &", os_=HedefOS.LINUX)
        ekle("Uygulama", "GIMP",
             ["gimp aç","resim editörü","fotoğraf düzenleyici"],
             komut="gimp &", os_=HedefOS.LINUX)
        ekle("Uygulama", "E-posta İstemcisi",
             ["e-posta programı aç","thunderbird aç","mail istemcisi"],
             komut="thunderbird & 2>/dev/null || evolution &",
             os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # EKRAN & GÖRÜNTÜ
        # ════════════════════════════════════════════════════════════════════
        ekle("Ekran", "Ekran Görüntüsü",
             ["ekran görüntüsü al","screenshot al","ekranı yakala"],
             komut="gnome-screenshot & 2>/dev/null || scrot ~/Masaüstü/ekran_$(date +%Y%m%d_%H%M%S).png &",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Seçili Alan Görüntüsü",
             ["seçili alan ekran görüntüsü","bölge ekran görüntüsü","alan seç screenshot"],
             komut="gnome-screenshot -a & 2>/dev/null || scrot -s ~/Masaüstü/alan_$(date +%Y%m%d_%H%M%S).png &",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Parlaklık Artır",
             ["parlaklığı artır","ekranı daha parlak yap","daha aydınlık"],
             komut="brightnessctl set +10% 2>/dev/null || xrandr --output $(xrandr | grep ' connected' | awk '{print $1}' | head -1) --brightness 1.0",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Parlaklık Azalt",
             ["parlaklığı azalt","ekranı karart","daha loş","daha karanlık"],
             komut="brightnessctl set 10%- 2>/dev/null || xrandr --output $(xrandr | grep ' connected' | awk '{print $1}' | head -1) --brightness 0.5",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Gece Modu",
             ["gece modunu aç","ekranı ısıt","gözleri koru","mavi ışık filtresi"],
             komut="redshift -O 3500 & 2>/dev/null || xrandr --output $(xrandr | grep ' connected' | awk '{print $1}' | head -1) --brightness 0.7",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Gece Modunu Kapat",
             ["gece modunu kapat","normal renge dön","redshift kapat"],
             komut="redshift -x 2>/dev/null; pkill redshift 2>/dev/null || true",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Ekranı Kilitle",
             ["ekranı kilitle","bilgisayarı kilitle","oturumu kilitle"],
             komut="loginctl lock-session 2>/dev/null || xdg-screensaver lock",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Ekranı Kapat",
             ["ekranı kapat","monitörü kapat","display kapat"],
             komut="xset dpms force off", os_=HedefOS.LINUX)
        ekle("Ekran", "Ekranı Aç",
             ["ekranı uyandır","monitörü aç","display aç"],
             komut="xset dpms force on && xset -dpms",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Çözünürlük Listesi",
             ["ekran çözünürlükleri","mevcut çözünürlükler","hangi çözünürlükler var"],
             komut=r"xrandr | grep -E '^\s+[0-9]'", os_=HedefOS.LINUX)
        ekle("Ekran", "Ekran Kaydı Başlat",
             ["ekranı kaydet","ekran kaydını başlat","ekran videosu al"],
             komut="ffmpeg -video_size $(xdpyinfo | grep dimensions | awk '{print $2}') -framerate 25 -f x11grab -i :0.0 ~/Masaüstü/kayit_$(date +%Y%m%d_%H%M%S).mp4 &",
             os_=HedefOS.LINUX)
        ekle("Ekran", "Ekran Kaydı Durdur",
             ["ekran kaydını durdur","kaydı bitir","ffmpeg durdur"],
             komut="pkill -INT ffmpeg", os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # DOSYA & KLASÖR İŞLEMLERİ
        # ════════════════════════════════════════════════════════════════════
        ekle("Dosya", "Ev Klasörü",
             ["ev klasörümü aç","ana dizine git","home klasörü"],
             komut="nautilus ~ & 2>/dev/null || xdg-open ~",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Masaüstü",
             ["masaüstüne git","masaüstü klasörü","desktop aç"],
             komut="nautilus ~/Masaüstü & 2>/dev/null || xdg-open ~/Desktop 2>/dev/null || xdg-open ~/Masaüstü &",
             os_=HedefOS.LINUX)
        ekle("Dosya", "İndirilenler",
             ["indirilenler klasörü","downloads klasörü","indirilen dosyalar"],
             komut="nautilus ~/İndirilenler & 2>/dev/null || xdg-open ~/Downloads &",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Belgeler",
             ["belgeler klasörü","documents klasörü","dokümanlar"],
             komut="nautilus ~/Belgeler & 2>/dev/null || xdg-open ~/Documents &",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Resimler",
             ["resimler klasörü","fotoğraflar klasörü","pictures"],
             komut="nautilus ~/Resimler & 2>/dev/null || xdg-open ~/Pictures &",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Müzikler",
             ["müzikler klasörü","müzik dosyaları","music klasörü"],
             komut="nautilus ~/Müzik & 2>/dev/null || xdg-open ~/Music &",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Videolar",
             ["videolar klasörü","video dosyaları","videos klasörü"],
             komut="nautilus ~/Videolar & 2>/dev/null || xdg-open ~/Videos &",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Çöp Kutusu",
             ["çöp kutusunu aç","silinen dosyalar","trash aç"],
             komut="nautilus trash: &", os_=HedefOS.LINUX)
        ekle("Dosya", "Çöp Kutusunu Boşalt",
             ["çöp kutusunu boşalt","kalıcı olarak sil","trash temizle"],
             komut="gio trash --empty", yetki=["ABİ","DAYI"], os_=HedefOS.LINUX)
        ekle("Dosya", "Son Dosyalar",
             ["son açılan dosyalar","son dosyalar","recent files"],
             komut="ls -lt ~/Belgeler ~/Masaüstü ~/İndirilenler 2>/dev/null | head -15",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Büyük Dosyalar",
             ["büyük dosyaları bul","en büyük dosyalar","disk dolduran dosyalar"],
             komut="du -ah ~ 2>/dev/null | sort -rh | head -10",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Gizli Dosyalar",
             ["gizli dosyaları göster","noktalı dosyalar","hidden files"],
             komut="ls -la ~ | grep '^\\.\\|/\\.'", os_=HedefOS.LINUX)
        ekle("Dosya", "Disk Alanı",
             ["disk alanı","boş disk alanı","depolama durumu"],
             komut="df -h --output=source,size,used,avail,pcent | head -6",
             os_=HedefOS.LINUX)
        ekle("Dosya", "Klasör Boyutu",
             ["ev klasörünün boyutu","home dizin boyutu","klasör kaç mb"],
             komut="du -sh ~ 2>/dev/null", os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # SİSTEM BİLGİSİ
        # ════════════════════════════════════════════════════════════════════
        ekle("SistemBilgi", "Saat",
             ["saat kaç","şu an saat kaç","saati söyle","zaman nedir"],
             komut="date '+Saat %H:%M'", tur="sistem_bilgi", os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Tarih",
             ["bugün tarih nedir","tarih söyle","günün tarihi","kaçıncısı"],
             komut="date '+%A %d %B %Y'", tur="sistem_bilgi", os_=HedefOS.LINUX)
        ekle("SistemBilgi", "RAM Durumu",
             ["ram durumu","bellek durumu","ram ne kadar dolu"],
             komut="free -h | awk '/^Mem:/ {print \"Toplam: \"$2\"  Kullanılan: \"$3\"  Boş: \"$4}'",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "CPU Kullanımı",
             ["cpu kullanımı","işlemci kullanımı","cpu yüzdesi"],
             komut="top -bn1 | grep 'Cpu(s)' | awk '{print \"CPU Kullanımı: \"$2+$4\"%\"}'",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Disk Doluluk",
             ["disk doluluk","disk yüzdesi","disk ne kadar dolu"],
             komut="df -h / | awk 'NR==2{print \"Disk: \"$3\" kullanıldı / \"$2\" toplam (\"$5\")\"}'",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Çalışma Süresi",
             ["bilgisayar ne zamandır açık","çalışma süresi","uptime"],
             komut="uptime -p", os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Kullanıcı Adı",
             ["kullanıcı adım ne","kim olarak giriş yaptım","hangi kullanıcıyım"],
             komut="whoami", os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Sistem Sürümü",
             ["işletim sistemi sürümü","linux sürümü","ubuntu sürümü","os versiyonu"],
             komut="lsb_release -d 2>/dev/null | cut -d: -f2 || cat /etc/os-release | grep PRETTY_NAME",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Kernel Sürümü",
             ["kernel sürümü","çekirdek versiyonu","linux kernel"],
             komut="uname -r", os_=HedefOS.LINUX)
        ekle("SistemBilgi", "CPU Bilgisi",
             ["işlemci bilgisi","cpu model","hangi işlemci"],
             komut="grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "GPU Bilgisi",
             ["ekran kartı bilgisi","gpu model","grafik kartı"],
             komut="lspci | grep -i 'vga\\|3d\\|display' | head -3",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Sıcaklık",
             ["sıcaklık ölç","cpu sıcaklığı nedir","ısı sensörü"],
             komut="sensors 2>/dev/null | grep -E 'Core|temp|CPU' | head -5 || cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000 \" °C\"}'",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Pil Durumu",
             ["pil durumu","laptop pil","batarya yüzdesi","şarj ne kadar"],
             komut="cat /sys/class/power_supply/BAT*/capacity 2>/dev/null | head -1 | xargs -I{} echo 'Pil: {}%' || upower -i /org/freedesktop/UPower/devices/battery_BAT0 2>/dev/null | grep -E 'state|to full|percentage'",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Aktif Süreçler",
             ["çalışan programlar","aktif süreçler","işlemler listesi"],
             komut="ps aux --sort=-%cpu | awk 'NR<=11{print $1, $2, $3\"%\", $11}' | column -t",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Bellek Yoğun",
             ["en çok ram kullanan","bellek yoğun programlar","ram kim kullanıyor"],
             komut="ps aux --sort=-%mem | awk 'NR<=6{print $4\"%\", $11}'",
             os_=HedefOS.LINUX)
        ekle("SistemBilgi", "Sistem Logu",
             ["sistem logları","son loglar","hata logları","journal"],
             komut="journalctl -n 20 --no-pager 2>/dev/null || tail -20 /var/log/syslog",
             yetki=["ABİ"], os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # AĞ & İNTERNET
        # ════════════════════════════════════════════════════════════════════
        ekle("Ağ", "IP Adresim",
             ["ip adresim nedir","yerel ip","ağ adresim"],
             komut="ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \\K[^ ]+' || hostname -I | awk '{print $1}'",
             os_=HedefOS.LINUX)
        ekle("Ağ", "Dış IP",
             ["dışarıdan görünen ip","genel ip adresim","public ip"],
             komut="curl -s --max-time 5 ifconfig.me || curl -s --max-time 5 icanhazip.com",
             os_=HedefOS.LINUX)
        ekle("Ağ", "İnternet Testi",
             ["internet bağlantısı var mı","internete bağlı mıyım","ping testi"],
             komut="ping -c 3 -W 2 8.8.8.8 | tail -2", os_=HedefOS.LINUX)
        ekle("Ağ", "DNS Testi",
             ["dns çalışıyor mu","alan adı çözümü","name resolution"],
             komut="nslookup google.com 2>/dev/null | grep 'Address:' | tail -1",
             os_=HedefOS.LINUX)
        ekle("Ağ", "WiFi Aç",
             ["wifi aç","kablosuz ağı aç","wireless aç"],
             komut="nmcli radio wifi on", os_=HedefOS.LINUX)
        ekle("Ağ", "WiFi Kapat",
             ["wifi kapat","kablosuz ağı kapat","wireless kapat"],
             komut="nmcli radio wifi off", os_=HedefOS.LINUX)
        ekle("Ağ", "WiFi Ağları",
             ["çevredeki wifi ağları","mevcut ağlar","wifi listesi"],
             komut="nmcli dev wifi list 2>/dev/null | head -10", os_=HedefOS.LINUX)
        ekle("Ağ", "WiFi Durumu",
             ["wifi durumu","bağlı olduğum ağ","hangi wifi"],
             komut="nmcli connection show --active 2>/dev/null | head -5 || iwconfig 2>/dev/null | grep ESSID",
             os_=HedefOS.LINUX)
        ekle("Ağ", "Açık Portlar",
             ["açık portlar","dinlenen portlar","ağ portları"],
             komut="ss -tulnp | grep LISTEN", os_=HedefOS.LINUX)
        ekle("Ağ", "Ağ Hızı",
             ["ağ hızı","internet hızı","bant genişliği"],
             komut="vnstat -tr 3 2>/dev/null | tail -5 || cat /proc/net/dev | grep -v lo | awk 'NR>2{print $1, \"RX:\", $2, \"TX:\", $10}'",
             os_=HedefOS.LINUX)
        ekle("Ağ", "Ağ Arayüzleri",
             ["ağ arayüzleri","network kartları","ethernet wifi bilgisi"],
             komut="ip link show | grep -E '^[0-9]+:' | awk '{print $2}' | tr -d ':'",
             os_=HedefOS.LINUX)
        ekle("Ağ", "MAC Adresi",
             ["mac adresim","donanım adresi","network mac"],
             komut="ip link show | grep 'link/ether' | awk '{print $2}' | head -3",
             os_=HedefOS.LINUX)
        ekle("Ağ", "Route Tablosu",
             ["yönlendirme tablosu","routing table","gateway nedir"],
             komut="ip route show | head -10", os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # GÜVENLİK & TOR
        # ════════════════════════════════════════════════════════════════════
        ekle("Güvenlik", "Tor Başlat",
             ["tor başlat","tor servisini başlat","toru çalıştır"],
             komut="sudo systemctl start tor && echo 'Tor başlatıldı'",
             yetki=["ABİ","DAYI"], os_=HedefOS.LINUX)
        ekle("Güvenlik", "Tor Durdur",
             ["tor durdur","tor servisini durdur","toru kapat"],
             komut="sudo systemctl stop tor && echo 'Tor durduruldu'",
             yetki=["ABİ","DAYI"], os_=HedefOS.LINUX)
        ekle("Güvenlik", "Tor Durumu",
             ["tor durumu nedir","tor çalışıyor mu","tor aktif mi"],
             komut="systemctl is-active tor 2>/dev/null && echo 'Tor aktif' || echo 'Tor inaktif'",
             os_=HedefOS.LINUX)
        ekle("Güvenlik", "Tor IP",
             ["tor ip adresim","anonim ip","tor kimliğim"],
             komut="curl -s --socks5-hostname 127.0.0.1:9050 --max-time 10 ifconfig.me",
             os_=HedefOS.LINUX)
        ekle("Güvenlik", "Yeni Tor Kimliği",
             ["yeni tor kimliği al","kimliği değiştir","tor identity değiştir"],
             komut="sudo killall -HUP tor 2>/dev/null && sleep 2 && echo 'Tor kimliği yenilendi'",
             yetki=["ABİ"], os_=HedefOS.LINUX)
        ekle("Güvenlik", "Güvenlik Duvarı",
             ["güvenlik duvarı durumu","firewall durumu","ufw durumu"],
             komut="sudo ufw status 2>/dev/null || iptables -L INPUT --line-numbers 2>/dev/null | head -10",
             yetki=["ABİ"], os_=HedefOS.LINUX)
        ekle("Güvenlik", "SSH Durumu",
             ["ssh durumu","ssh çalışıyor mu","ssh servisi"],
             komut="systemctl is-active ssh 2>/dev/null || systemctl is-active sshd 2>/dev/null",
             os_=HedefOS.LINUX)
        ekle("Güvenlik", "Şifre Üret",
             ["güçlü şifre üret","rastgele şifre oluştur","şifre öner"],
             komut="cat /dev/urandom | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c 16; echo",
             os_=HedefOS.LINUX)
        ekle("Güvenlik", "Sisteme Giriş Yapanlar",
             ["kim giriş yaptı","son girişler","login geçmişi"],
             komut="last | head -10", yetki=["ABİ"], os_=HedefOS.LINUX)
        ekle("Güvenlik", "Sudo Logları",
             ["sudo logları","yönetici komutları","root komut geçmişi"],
             komut="grep sudo /var/log/auth.log 2>/dev/null | tail -10 || journalctl _COMM=sudo -n 10 --no-pager",
             yetki=["ABİ"], os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # SİSTEM YÖNETİMİ
        # ════════════════════════════════════════════════════════════════════
        ekle("Sistem", "Bilgisayarı Kapat",
             ["bilgisayarı kapat","sistemi kapat","shutdown"],
             komut="sudo shutdown -h now",
             komut_w="shutdown /s /t 0",
             yetki=["ABİ","DAYI"], os_=HedefOS.HEPSI)
        ekle("Sistem", "Yeniden Başlat",
             ["yeniden başlat","sistemi yeniden başlat","reboot"],
             komut="sudo reboot",
             komut_w="shutdown /r /t 0",
             yetki=["ABİ","DAYI"], os_=HedefOS.HEPSI)
        ekle("Sistem", "Uyku Modu",
             ["uyku moduna al","sistemi uyut","sleep moda al","suspend"],
             komut="systemctl suspend",
             yetki=["ABİ","DAYI"], os_=HedefOS.LINUX)
        ekle("Sistem", "Hazırda Beklet",
             ["hazırda beklet","hibernate","derin uyku"],
             komut="systemctl hibernate",
             yetki=["ABİ","DAYI"], os_=HedefOS.LINUX)
        ekle("Sistem", "5 Dakika Sonra Kapat",
             ["5 dakika sonra kapat","beş dakika sonra kapat","zamanlı kapat"],
             komut="sudo shutdown -h +5 && echo '5 dakika sonra kapanacak'",
             yetki=["ABİ","DAYI"], os_=HedefOS.LINUX)
        ekle("Sistem", "Kapanışı İptal",
             ["kapanışı iptal et","shutdown iptal","zamanlayıcıyı iptal et"],
             komut="sudo shutdown -c && echo 'Kapanış iptal edildi'",
             yetki=["ABİ","DAYI"], os_=HedefOS.LINUX)
        ekle("Sistem", "Oturumu Kapat",
             ["oturumu kapat","çıkış yap","logout"],
             komut="gnome-session-quit --no-prompt 2>/dev/null || loginctl terminate-session $(loginctl | grep $(whoami) | awk '{print $1}' | head -1)",
             yetki=["ABİ","DAYI"], os_=HedefOS.LINUX)
        ekle("Sistem", "Güncellemeleri Kontrol",
             ["güncelleme var mı","paket güncellemesi","apt güncelleme kontrol"],
             komut="apt list --upgradable 2>/dev/null | head -10",
             os_=HedefOS.LINUX)
        ekle("Sistem", "Sistemi Güncelle",
             ["sistemi güncelle","apt güncelle","paketleri güncelle"],
             komut="sudo apt update && sudo apt upgrade -y",
             yetki=["ABİ"], os_=HedefOS.LINUX)
        ekle("Sistem", "Paket Kur",
             ["paket kur","program yükle","apt install"],
             komut="echo 'Kurmak istediğiniz paketi belirtin: sudo apt install PAKET_ADI'",
             tur="konusma", yetki=["ABİ"], os_=HedefOS.LINUX)
        ekle("Sistem", "Gereksiz Dosyalar Temizle",
             ["gereksiz dosyaları temizle","apt temizle","önbellek temizle"],
             komut="sudo apt autoremove -y && sudo apt autoclean",
             yetki=["ABİ"], os_=HedefOS.LINUX)
        ekle("Sistem", "Aktif Servisler",
             ["aktif servisler listesi","çalışan daemon","systemd servisleri"],
             komut="systemctl list-units --state=running --no-pager --type=service | head -15",
             os_=HedefOS.LINUX)
        ekle("Sistem", "Servis Başlat",
             ["servis başlat","systemctl start","servisi çalıştır"],
             yanit="Hangi servisi başlatmamı istiyorsunuz? Örnek: 'ssh servisini başlat'",
             tur="konusma", yetki=["ABİ"], os_=HedefOS.LINUX)
        ekle("Sistem", "Ortam Değişkenleri",
             ["ortam değişkenleri","environment variables","env listesi"],
             komut="env | sort | head -20", os_=HedefOS.LINUX)
        ekle("Sistem", "Kernel Mesajları",
             ["kernel mesajları","dmesg","sistem donanım mesajları"],
             komut="dmesg | tail -15 2>/dev/null",
             yetki=["ABİ"], os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # PANO (CLİPBOARD)
        # ════════════════════════════════════════════════════════════════════
        ekle("Pano", "Pano İçeriği",
             ["panoda ne var","pano içeriğini göster","kopyalanan metin nedir"],
             komut="xclip -o -selection clipboard 2>/dev/null || xsel --clipboard --output 2>/dev/null || wl-paste 2>/dev/null || echo 'Pano boş veya desteklenmiyor'",
             os_=HedefOS.LINUX)
        ekle("Pano", "Pano Temizle",
             ["panoyu temizle","kopyalanı sil","clipboard temizle"],
             komut="printf '' | xclip -selection clipboard 2>/dev/null || printf '' | xsel --clipboard --input 2>/dev/null || wl-copy '' 2>/dev/null || true",
             os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # HAFIZA & NOTLAR
        # ════════════════════════════════════════════════════════════════════
        ekle("Hafıza", "Notları Göster",
             ["notlarımı göster","kaydettiğim notlar","ne not aldım","notlarım"],
             tur="hafiza", komut="notlar_listele")
        ekle("Hafıza", "Not Al",
             ["not al","bunu not et","hatırlat","kaydet şunu"],
             tur="hafiza", komut="not_ekle")
        ekle("Hafıza", "Not Sil",
             ["notu sil","son notu kaldır","notu unut"],
             tur="hafiza", komut="not_sil")
        ekle("Hafıza", "Hatırlatıcılar",
             ["hatırlatıcılarım","ne hatırlatacaktım","alarm listesi"],
             tur="hafiza", komut="hatirlaticilar")

        # ════════════════════════════════════════════════════════════════════
        # BLUETOOTh
        # ════════════════════════════════════════════════════════════════════
        ekle("Bluetooth", "Bluetooth Aç",
             ["bluetooth aç","bluetooth başlat","bluetooth aktif yap"],
             komut="bluetoothctl power on && echo 'Bluetooth açıldı'",
             os_=HedefOS.LINUX)
        ekle("Bluetooth", "Bluetooth Kapat",
             ["bluetooth kapat","bluetooth deaktif","bluetoothu kapat"],
             komut="bluetoothctl power off && echo 'Bluetooth kapatıldı'",
             os_=HedefOS.LINUX)
        ekle("Bluetooth", "Bluetooth Cihazları",
             ["bluetooth cihazları","eşleşmiş cihazlar","bluetooth listesi"],
             komut="bluetoothctl devices 2>/dev/null | head -10",
             os_=HedefOS.LINUX)
        ekle("Bluetooth", "Bluetooth Durumu",
             ["bluetooth durumu","bluetooth açık mı","bluetooth aktif mi"],
             komut="bluetoothctl show 2>/dev/null | grep -E 'Powered|Discoverable' | head -2",
             os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # WINDOWS UZUV KOMUTLARı
        # ════════════════════════════════════════════════════════════════════
        ekle("Windows", "Sistem Bilgisi",
             ["windows sistem bilgisi","windows bilgisi"],
             komut_w="systeminfo", os_=HedefOS.WINDOWS)
        ekle("Windows", "IP Adresi",
             ["windows ip adresi","windows ağ"],
             komut_w="ipconfig /all", os_=HedefOS.WINDOWS)
        ekle("Windows", "Disk Durumu",
             ["windows disk durumu","windows depolama"],
             komut_w="wmic logicaldisk get Caption,Size,FreeSpace",
             os_=HedefOS.WINDOWS)
        ekle("Windows", "İşlemler",
             ["windows süreçler","windows işlemler"],
             komut_w="tasklist /fo table | findstr /v \"Image Name\"",
             os_=HedefOS.WINDOWS)
        ekle("Windows", "Ağ Bağlantıları",
             ["windows ağ bağlantıları","windows portlar"],
             komut_w="netstat -ano", os_=HedefOS.WINDOWS)
        ekle("Windows", "Reboot",
             ["windows yeniden başlat","windows reboot"],
             komut_w="shutdown /r /t 0",
             yetki=["ABİ","DAYI"], os_=HedefOS.WINDOWS)
        ekle("Windows", "Kapat",
             ["windows kapat","windows shutdown"],
             komut_w="shutdown /s /t 0",
             yetki=["ABİ","DAYI"], os_=HedefOS.WINDOWS)
        ekle("Windows", "Uyku",
             ["windows uyut","windows uyku modu"],
             komut_w="rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
             yetki=["ABİ","DAYI"], os_=HedefOS.WINDOWS)
        ekle("Windows", "Ekran Görüntüsü",
             ["windows ekran görüntüsü"],
             komut_w="powershell -command \"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('%{PRTSC}')\"",
             os_=HedefOS.WINDOWS)

        # ════════════════════════════════════════════════════════════════════
        # ANDROID / TERMUX UZUV KOMUTLARı
        # ════════════════════════════════════════════════════════════════════
        ekle("Android", "Pil Durumu",
             ["telefon pil durumu","android batarya","şarj yüzdesi"],
             komut_a="termux-battery-status", os_=HedefOS.ANDROID)
        ekle("Android", "Konum",
             ["telefon konumu","android konum","gps bilgisi"],
             komut_a="termux-location", os_=HedefOS.ANDROID)
        ekle("Android", "Fotoğraf Çek",
             ["telefonla fotoğraf çek","android kamera","fotoğraf al"],
             komut_a="termux-camera-photo -c 0 /sdcard/zk_foto_$(date +%Y%m%d_%H%M%S).jpg",
             os_=HedefOS.ANDROID)
        ekle("Android", "Depolama",
             ["telefon depolama alanı","android disk","sdcard doluluk"],
             komut_a="df -h /sdcard", os_=HedefOS.ANDROID)
        ekle("Android", "WiFi Bilgisi",
             ["telefon wifi bilgisi","android ağ bilgisi","telefon bağlantısı"],
             komut_a="termux-wifi-connectioninfo", os_=HedefOS.ANDROID)
        ekle("Android", "Bildirim Gönder",
             ["telefonuma bildirim gönder","android bildirim","telefona mesaj"],
             komut_a="termux-notification --title 'Zihin Köprüsü' --content 'Merhaba Sahip!'",
             os_=HedefOS.ANDROID)
        ekle("Android", "Titreşim",
             ["telefonu titret","android vibrasyon","vibrate"],
             komut_a="termux-vibrate -d 500", os_=HedefOS.ANDROID)
        ekle("Android", "Ekran Parlaklığı",
             ["telefon ekranı aydınlat","android parlaklık","telefon ekranı"],
             komut_a="termux-brightness 200", os_=HedefOS.ANDROID)
        ekle("Android", "Kişiler",
             ["telefon rehberi","android kişiler","kontaklar"],
             komut_a="termux-contact-list | head -20", os_=HedefOS.ANDROID)
        ekle("Android", "SMS Gönder",
             ["sms gönder","mesaj gönder android","kısa mesaj"],
             yanit="SMS göndermek için Telegram botu üzerinden komut verin.",
             tur="konusma", os_=HedefOS.ANDROID)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / CHROME & FİREFOX DETAYLI
        # ════════════════════════════════════════════════════════════════════
        ekle("Chrome","Adres Çubuğu Odakla",["chrome adres çubuğuna git","url kutusuna tıkla","chrome ctrl l"],komut="xdotool key ctrl+l",os_=HedefOS.LINUX)
        ekle("Chrome","Yeni Pencere",["chrome yeni pencere aç","tarayıcı yeni pencere","ctrl n chrome"],komut="xdotool key ctrl+n",os_=HedefOS.LINUX)
        ekle("Chrome","Gizli Pencere",["chrome gizli pencere","incognito pencere aç","private pencere"],komut="xdotool key ctrl+shift+n",os_=HedefOS.LINUX)
        ekle("Chrome","Sekmeyi Sabitle",["sekmeyi sabitle","pin tab","sekme sabitleme"],komut="xdotool key ctrl+shift+p",os_=HedefOS.LINUX)
        ekle("Chrome","Sekmeyi Kopyala",["sekmeyi kopyala","duplicate tab","sekme çoğalt"],komut="xdotool key ctrl+shift+k",os_=HedefOS.LINUX)
        ekle("Chrome","Sekmeyi Taşı Sol",["sekmeyi sola taşı","tab sola kaydır"],komut="xdotool key ctrl+shift+Page_Up",os_=HedefOS.LINUX)
        ekle("Chrome","Sekmeyi Taşı Sağ",["sekmeyi sağa taşı","tab sağa kaydır"],komut="xdotool key ctrl+shift+Page_Down",os_=HedefOS.LINUX)
        ekle("Chrome","1. Sekme",["birinci sekme","ilk sekmeye git","sekme bir"],komut="xdotool key ctrl+1",os_=HedefOS.LINUX)
        ekle("Chrome","2. Sekme",["ikinci sekme","ikinci sekmeye git","sekme iki"],komut="xdotool key ctrl+2",os_=HedefOS.LINUX)
        ekle("Chrome","3. Sekme",["üçüncü sekme","üçüncü sekmeye git","sekme üç"],komut="xdotool key ctrl+3",os_=HedefOS.LINUX)
        ekle("Chrome","4. Sekme",["dördüncü sekme","sekme dört"],komut="xdotool key ctrl+4",os_=HedefOS.LINUX)
        ekle("Chrome","5. Sekme",["beşinci sekme","sekme beş"],komut="xdotool key ctrl+5",os_=HedefOS.LINUX)
        ekle("Chrome","6. Sekme",["altıncı sekme","sekme altı"],komut="xdotool key ctrl+6",os_=HedefOS.LINUX)
        ekle("Chrome","7. Sekme",["yedinci sekme","sekme yedi"],komut="xdotool key ctrl+7",os_=HedefOS.LINUX)
        ekle("Chrome","8. Sekme",["sekizinci sekme","sekme sekiz"],komut="xdotool key ctrl+8",os_=HedefOS.LINUX)
        ekle("Chrome","Son Sekme",["son sekme","en sağdaki sekme","sekme dokuz"],komut="xdotool key ctrl+9",os_=HedefOS.LINUX)
        ekle("Chrome","Kaynağı Görüntüle",["sayfa kaynağını görüntüle","html kaynağı","view source"],komut="xdotool key ctrl+u",os_=HedefOS.LINUX)
        ekle("Chrome","Konsol Aç",["js konsolu aç","javascript konsolu","browser konsolu"],komut="xdotool key ctrl+shift+j",os_=HedefOS.LINUX)
        ekle("Chrome","Ağ İzleyici",["ağ trafiğini izle","network tab","network monitor aç"],komut="xdotool key ctrl+shift+i",os_=HedefOS.LINUX)
        ekle("Chrome","Sayfayı Kaydet",["sayfayı kaydet","web sayfasını indir","save page as"],komut="xdotool key ctrl+s",os_=HedefOS.LINUX)
        ekle("Chrome","Baskı Önizleme",["baskı önizleme","print preview","yazdırma önizleme"],komut="xdotool key ctrl+p",os_=HedefOS.LINUX)
        ekle("Chrome","Zoom Yüzde Yüz",["tarayıcı zoom sıfırla","normal boyut tarayıcı","zoom resetle"],komut="xdotool key ctrl+0",os_=HedefOS.LINUX)
        ekle("Chrome","Adres Çubuğu Seç Tümü",["url yi seç","adres çubuğunu seç","tüm url seç"],komut="xdotool key ctrl+l ctrl+a",os_=HedefOS.LINUX)
        ekle("Chrome","Yer İmi Yöneticisi",["yer imleri yöneticisi","bookmark manager","favoriler yönet"],komut="xdotool key ctrl+shift+o",os_=HedefOS.LINUX)
        ekle("Chrome","Şifre Yöneticisi",["tarayıcı şifre yöneticisi","kayıtlı şifreler","passwords chrome"],komut="xdotool key ctrl+shift+comma",os_=HedefOS.LINUX)
        ekle("Chrome","Oturum Açma",["google hesabına gir","chrome oturum aç","sign in chrome"],komut="xdg-open https://accounts.google.com",os_=HedefOS.LINUX)
        ekle("Chrome","Uzantılar",["chrome uzantıları","eklentileri aç","extensions chrome"],komut="xdg-open chrome://extensions",os_=HedefOS.LINUX)
        ekle("Chrome","Chrome Ayarları",["chrome ayarlarına git","tarayıcı ayarları","settings chrome"],komut="xdg-open chrome://settings",os_=HedefOS.LINUX)
        ekle("Chrome","Çerezleri Temizle",["çerezleri temizle","tarayıcı verileri sil","browsing data temizle"],komut="xdg-open chrome://settings/clearBrowserData",os_=HedefOS.LINUX)
        ekle("Chrome","Görev Yöneticisi",["chrome görev yöneticisi","tarayıcı süreçleri","chrome task manager"],komut="xdotool key shift+Escape",os_=HedefOS.LINUX)
        ekle("Chrome","İndirme Klasörünü Aç",["chrome indirme klasörü","indirilen dosyaları bul","download folder aç"],komut="xdg-open ~/İndirilenler 2>/dev/null || xdg-open ~/Downloads",os_=HedefOS.LINUX)
        ekle("Chrome","Odağı İçeriğe Al",["odağı sayfaya ver","içerik alanına git","escape adres çubuğu"],komut="xdotool key Escape",os_=HedefOS.LINUX)
        ekle("Chrome","Sonraki Eşleşme",["sonraki bul","bir sonraki sonuç","find next"],komut="xdotool key ctrl+g",os_=HedefOS.LINUX)
        ekle("Chrome","Önceki Eşleşme",["önceki bul","bir önceki sonuç","find previous"],komut="xdotool key ctrl+shift+g",os_=HedefOS.LINUX)
        ekle("Chrome","Sayfanın Başına Git",["sayfanın başına git","en üste scroll","üste çık"],komut="xdotool key ctrl+Home",os_=HedefOS.LINUX)
        ekle("Chrome","Sayfanın Sonuna Git",["sayfanın sonuna git","en alta scroll","aşağıya git"],komut="xdotool key ctrl+End",os_=HedefOS.LINUX)
        ekle("Chrome","Okuma Modu",["okuma modunu aç","reader mode","dağınıksız oku"],komut="xdotool key F9 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("Chrome","Çevrimdışı Sayfa",["çevrimdışı sayfaları göster","cached sayfalar","offline pages"],komut="xdg-open chrome://downloads",os_=HedefOS.LINUX)
        ekle("Chrome","Performans",["chrome performansı","tarayıcı hızı","chrome performance"],komut="xdg-open chrome://settings/performance",os_=HedefOS.LINUX)
        ekle("Chrome","Güvenlik Kontrol",["chrome güvenlik kontrolü","safety check","güvenlik tara"],komut="xdg-open chrome://settings/safetyCheck",os_=HedefOS.LINUX)
        ekle("Chrome","Arama Motoru Değiştir",["arama motorunu değiştir","varsayılan arama","search engine"],komut="xdg-open chrome://settings/searchEngines",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Yeni Pencere",["firefox yeni pencere","yeni firefox açılır"],komut="firefox --new-window &",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Gizli",["firefox gizli pencere","firefox private","firefox incognito"],komut="firefox --private-window &",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Yer İmleri",["firefox yer imleri","firefox bookmarks","firefox favoriler"],komut="xdotool key ctrl+shift+b",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Kütüphane",["firefox kütüphane","firefox library","geçmiş ve yer imleri"],komut="xdotool key ctrl+shift+h",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Eklentiler",["firefox eklentileri","firefox uzantıları","add-ons firefox"],komut="xdotool key ctrl+shift+a",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Tarama Geçmişi Sil",["firefox geçmişi temizle","firefox verileri sil","firefox privacy"],komut="xdotool key ctrl+shift+Delete",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Okuyucu Görünümü",["firefox okuyucu modu","reader view firefox","f9 firefox"],komut="xdotool key F9",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Sync",["firefox sync","firefox hesabı","firefox cloud"],komut="xdg-open about:preferences#sync",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Kod Düzenleyici",["firefox kodu aç","firefox scratchpad","browser araçlar"],komut="xdotool key shift+F4",os_=HedefOS.LINUX)
        ekle("Firefox","Firefox Hata Ayıklama",["firefox hata ayıklama","firefox debugger","firefox debug"],komut="xdotool key F12",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / VS CODE DETAYLI
        # ════════════════════════════════════════════════════════════════════
        ekle("VSCode","Komut Paleti",["vscode komut paleti","komut paletini aç","ctrl shift p vscode"],komut="xdotool key ctrl+shift+p",os_=HedefOS.LINUX)
        ekle("VSCode","Hızlı Dosya Aç",["vscode dosya aç hızlı","ctrl p vscode","quick open"],komut="xdotool key ctrl+p",os_=HedefOS.LINUX)
        ekle("VSCode","Yan Panel",["vscode yan panel","sidebar aç kapat","explorer panel"],komut="xdotool key ctrl+b",os_=HedefOS.LINUX)
        ekle("VSCode","Entegre Terminal",["vscode terminali aç","entegre terminal","vscode terminal"],komut="xdotool key ctrl+grave",os_=HedefOS.LINUX)
        ekle("VSCode","Yeni Terminal",["vscode yeni terminal penceresi","terminal split vscode"],komut="xdotool key ctrl+shift+grave",os_=HedefOS.LINUX)
        ekle("VSCode","Arama Paneli",["vscode arama paneli","dosyalarda ara","search panel"],komut="xdotool key ctrl+shift+f",os_=HedefOS.LINUX)
        ekle("VSCode","Değiştir Paneli",["vscode değiştir","dosyalarda değiştir","replace all vscode"],komut="xdotool key ctrl+shift+h",os_=HedefOS.LINUX)
        ekle("VSCode","Git Paneli",["vscode git paneli","source control aç","versiyon kontrol"],komut="xdotool key ctrl+shift+g",os_=HedefOS.LINUX)
        ekle("VSCode","Hata Ayıklama",["vscode debug","hata ayıklamayı başlat","debug panel"],komut="xdotool key ctrl+shift+d",os_=HedefOS.LINUX)
        ekle("VSCode","Uzantılar Paneli",["vscode uzantılar","extensions panel","marketplace aç"],komut="xdotool key ctrl+shift+x",os_=HedefOS.LINUX)
        ekle("VSCode","Satıra Git",["satıra git vscode","belirli satır","ctrl g vscode"],komut="xdotool key ctrl+g",os_=HedefOS.LINUX)
        ekle("VSCode","Sembol Bul",["vscode sembol bul","fonksiyon bul","class bul vscode"],komut="xdotool key ctrl+shift+o",os_=HedefOS.LINUX)
        ekle("VSCode","Tanıma Git",["tanıma git vscode","go to definition","f12 vscode"],komut="xdotool key F12",os_=HedefOS.LINUX)
        ekle("VSCode","Referansları Bul",["referansları bul","nerede kullanılıyor","shift f12"],komut="xdotool key shift+F12",os_=HedefOS.LINUX)
        ekle("VSCode","Yeniden Adlandır",["vscode yeniden adlandır","rename symbol","f2 vscode"],komut="xdotool key F2",os_=HedefOS.LINUX)
        ekle("VSCode","Kod Biçimlendir",["kodu biçimlendir","format document","prettier çalıştır"],komut="xdotool key ctrl+shift+i",os_=HedefOS.LINUX)
        ekle("VSCode","Seçimi Biçimlendir",["seçili kodu biçimlendir","format selection vscode"],komut="xdotool key ctrl+k ctrl+f",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Yoruma Al",["satırı yoruma al","comment out","ctrl slash"],komut="xdotool key ctrl+slash",os_=HedefOS.LINUX)
        ekle("VSCode","Blok Yorum",["blok yorum ekle","block comment","ctrl shift a"],komut="xdotool key ctrl+shift+a",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Taşı Yukarı",["satırı yukarı taşı","move line up","alt up"],komut="xdotool key alt+Up",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Taşı Aşağı",["satırı aşağı taşı","move line down","alt down"],komut="xdotool key alt+Down",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Kopyala Yukarı",["satırı yukarı kopyala","copy line up","alt shift up"],komut="xdotool key alt+shift+Up",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Kopyala Aşağı",["satırı aşağı kopyala","copy line down","alt shift down"],komut="xdotool key alt+shift+Down",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Sil",["satırı sil vscode","delete line","ctrl shift k"],komut="xdotool key ctrl+shift+k",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Sonuna Atla",["satır sonuna atla vscode","end of line vscode"],komut="xdotool key End",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Başına Atla",["satır başına atla vscode","başa git vscode"],komut="xdotool key Home",os_=HedefOS.LINUX)
        ekle("VSCode","Tümünü Katla",["tüm kodu katla","fold all","collapse all"],komut="xdotool key ctrl+k ctrl+0",os_=HedefOS.LINUX)
        ekle("VSCode","Tümünü Aç",["tüm kodu aç","unfold all","expand all"],komut="xdotool key ctrl+k ctrl+j",os_=HedefOS.LINUX)
        ekle("VSCode","Yan Yana Aç",["dosyayı yan yana aç","split editor","ctrl backslash"],komut="xdotool key ctrl+backslash",os_=HedefOS.LINUX)
        ekle("VSCode","Sol Editöre Geç",["sol editöre geç","ctrl k sol","önceki editör"],komut="xdotool key ctrl+k ctrl+Left",os_=HedefOS.LINUX)
        ekle("VSCode","Sağ Editöre Geç",["sağ editöre geç","ctrl k sağ","sonraki editör"],komut="xdotool key ctrl+k ctrl+Right",os_=HedefOS.LINUX)
        ekle("VSCode","Kırılma Noktası",["kırılma noktası ekle","breakpoint koy","f9 breakpoint"],komut="xdotool key F9",os_=HedefOS.LINUX)
        ekle("VSCode","Debug Başlat",["debugı başlat","programı debug et","f5 debug"],komut="xdotool key F5",os_=HedefOS.LINUX)
        ekle("VSCode","Debug Durdur",["debugı durdur","debug kapat","shift f5"],komut="xdotool key shift+F5",os_=HedefOS.LINUX)
        ekle("VSCode","Adım İçine",["adım içine gir","step into","f11 debug"],komut="xdotool key F11",os_=HedefOS.LINUX)
        ekle("VSCode","Adım Dışına",["adım dışına çık","step out","shift f11"],komut="xdotool key shift+F11",os_=HedefOS.LINUX)
        ekle("VSCode","Sonraki Adım",["sonraki adım debug","step over","f10 debug"],komut="xdotool key F10",os_=HedefOS.LINUX)
        ekle("VSCode","Git Commit",["vscode git commit","değişiklikleri commit et","git commit mesajı"],komut="xdotool key ctrl+Enter",os_=HedefOS.LINUX)
        ekle("VSCode","Zen Modu",["zen modu aç","dikkat dağıtmasız mod","fullscreen edit"],komut="xdotool key ctrl+k z",os_=HedefOS.LINUX)
        ekle("VSCode","Minimap",["minimap aç kapat","vscode minimap","kod haritası"],komut="xdotool key ctrl+k ctrl+m 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("VSCode","Satır Numaraları",["satır numarasını göster","line numbers","satır numarası toggle"],komut="xdotool key ctrl+shift+p",os_=HedefOS.LINUX)
        ekle("VSCode","Kelime Kaydırma",["kelime kaydırma aç","word wrap","alt z vscode"],komut="xdotool key alt+z",os_=HedefOS.LINUX)
        ekle("VSCode","Çoklu Seçim",["çoklu imleç ekle","multi cursor","ctrl alt aşağı"],komut="xdotool key ctrl+alt+Down",os_=HedefOS.LINUX)
        ekle("VSCode","Tüm Eşleşmeleri Seç",["tüm eşleşmeleri seç","select all occurrences","ctrl shift l"],komut="xdotool key ctrl+shift+l",os_=HedefOS.LINUX)
        ekle("VSCode","Kelimeyi Seç Genişlet",["kelimeyi seç vscode","sonraki eşleşmeyi seç","ctrl d"],komut="xdotool key ctrl+d",os_=HedefOS.LINUX)
        ekle("VSCode","Dosya Değişiklikleri",["dosyada ne değişti","git diff vscode","değişiklikleri göster"],komut="xdotool key ctrl+shift+g",os_=HedefOS.LINUX)
        ekle("VSCode","Sorunlar Paneli",["vscode sorunlar","hatalar ve uyarılar","problems panel"],komut="xdotool key ctrl+shift+m",os_=HedefOS.LINUX)
        ekle("VSCode","Çıktı Paneli",["vscode çıktı","output panel","terminal çıktısı"],komut="xdotool key ctrl+shift+u",os_=HedefOS.LINUX)
        ekle("VSCode","Önerilen Düzeltme",["hata düzeltme öner","quick fix","ctrl nokta"],komut="xdotool key ctrl+period",os_=HedefOS.LINUX)
        ekle("VSCode","Otomatik Tamamlama",["otomatik tamamla","autocomplete tetikle","ctrl space"],komut="xdotool key ctrl+space",os_=HedefOS.LINUX)
        ekle("VSCode","İmza Yardımı",["parametre yardımı","imza bilgisi","ctrl shift space"],komut="xdotool key ctrl+shift+space",os_=HedefOS.LINUX)
        ekle("VSCode","Hover Bilgisi",["hover bilgisi","tip göster","ctrl k ctrl i"],komut="xdotool key ctrl+k ctrl+i",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / TERMİNAL & BASH DETAYLI
        # ════════════════════════════════════════════════════════════════════
        ekle("Terminal","Terminal Temizle",["terminali temizle","ekranı temizle","clear terminal"],komut="xdotool type 'clear' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Son Komutu Tekrar",["son komutu tekrar çalıştır","yukarı ok terminal","history son"],komut="xdotool key Up Return",os_=HedefOS.LINUX)
        ekle("Terminal","Terminal Çıkış",["terminalden çık","exit terminal","terminal kapat"],komut="xdotool type 'exit' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Terminal Kopyala",["terminalde kopyala","terminal ctrl shift c","seçimi kopyala terminal"],komut="xdotool key ctrl+shift+c",os_=HedefOS.LINUX)
        ekle("Terminal","Terminal Yapıştır",["terminale yapıştır","terminal ctrl shift v","panoya yapıştır terminal"],komut="xdotool key ctrl+shift+v",os_=HedefOS.LINUX)
        ekle("Terminal","Yeni Terminal Sekmesi",["yeni terminal sekmesi","terminal tab ekle","terminal split"],komut="xdotool key ctrl+shift+t",os_=HedefOS.LINUX)
        ekle("Terminal","Terminal Büyüt",["terminal fontunu büyüt","yazıyı büyüt terminal","ctrl artı terminal"],komut="xdotool key ctrl+plus",os_=HedefOS.LINUX)
        ekle("Terminal","Terminal Küçült",["terminal fontunu küçült","yazıyı küçült terminal","ctrl eksi terminal"],komut="xdotool key ctrl+minus",os_=HedefOS.LINUX)
        ekle("Terminal","Çalışan Prosesi Kes",["çalışan komutu durdur","ctrl c terminal","prosesi kes"],komut="xdotool key ctrl+c",os_=HedefOS.LINUX)
        ekle("Terminal","Arka Plana Al",["prosesi arka plana al","ctrl z terminal","suspend process"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)
        ekle("Terminal","Çıkış Sinyali",["terminal eof","ctrl d terminal","giriş sonu"],komut="xdotool key ctrl+d",os_=HedefOS.LINUX)
        ekle("Terminal","Satırı Temizle",["komut satırını temizle","ctrl u terminal","satırı sil terminal"],komut="xdotool key ctrl+u",os_=HedefOS.LINUX)
        ekle("Terminal","Kelimeyi Sil",["kelimeyi sil terminal","ctrl w terminal","son kelimeyi kaldır"],komut="xdotool key ctrl+w",os_=HedefOS.LINUX)
        ekle("Terminal","Satır Başına Git",["terminal satır başı","ctrl a terminal","başa git terminal"],komut="xdotool key ctrl+a",os_=HedefOS.LINUX)
        ekle("Terminal","Satır Sonuna Git",["terminal satır sonu","ctrl e terminal","sona git terminal"],komut="xdotool key ctrl+e",os_=HedefOS.LINUX)
        ekle("Terminal","Geçmişte Ara",["terminal geçmişinde ara","ctrl r terminal","history arama"],komut="xdotool key ctrl+r",os_=HedefOS.LINUX)
        ekle("Terminal","Tab Tamamlama",["tab ile tamamla","otomatik tamamla terminal","tab terminal"],komut="xdotool key Tab",os_=HedefOS.LINUX)
        ekle("Terminal","Ev Dizinine Git",["ev dizinine git terminal","cd home","home dizini"],komut="xdotool type 'cd ~' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Masaüstüne Git",["masaüstüne git terminal","cd desktop terminal"],komut="xdotool type 'cd ~/Masaüstü 2>/dev/null || cd ~/Desktop' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Git Durumu",["git durumu göster","git status terminal","repo durumu"],komut="xdotool type 'git status' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Git Log",["git log göster","commit geçmişi","git log terminal"],komut="xdotool type 'git log --oneline -10' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Git Diff",["git diff göster","değişiklikleri göster terminal","git fark"],komut="xdotool type 'git diff' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Git Add All",["tüm değişiklikleri ekle","git add all","git stage all"],komut="xdotool type 'git add .' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Git Push",["git push yap","değişiklikleri gönder","uzağa yükle"],komut="xdotool type 'git push' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Git Pull",["git pull yap","son değişiklikleri çek","repo güncelle"],komut="xdotool type 'git pull' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Dosya İzinleri",["dosya izinlerini göster","ls la","gizli dosyalar listele"],komut="xdotool type 'ls -la' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Disk Kullanımı",["disk kullanımı terminalde","du sh","klasör boyutları"],komut="xdotool type 'du -sh */ 2>/dev/null | sort -rh | head -10' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Süreçleri Göster",["htop başlat","süreç izleyici terminal","top komutu"],komut="xdotool type 'htop 2>/dev/null || top' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Ağ Bağlantılarını Göster",["netstat terminalde","ss tulnp","bağlantıları listele"],komut="xdotool type 'ss -tulnp' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Python Başlat",["python başlat terminal","python yorumlayıcı","python shell"],komut="xdotool type 'python3' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Node Başlat",["node başlat terminal","nodejs shell","node repl"],komut="xdotool type 'node' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","SSH Bağlan",["ssh bağlantısı kur","uzak sunucuya bağlan terminal"],komut="xdotool type 'ssh '",os_=HedefOS.LINUX)
        ekle("Terminal","Ping Yap",["ping at terminal","bağlantı test et","network ping"],komut="xdotool type 'ping -c 4 8.8.8.8' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Nano Editör",["nano aç","metin düzenle terminalde","nano editor"],komut="xdotool type 'nano ' ",os_=HedefOS.LINUX)
        ekle("Terminal","Vim Aç",["vim aç","vim editör","vi terminal"],komut="xdotool type 'vim ' ",os_=HedefOS.LINUX)
        ekle("Terminal","Systemctl Durum",["servis durumunu kontrol et","systemctl status terminal"],komut="xdotool type 'systemctl status ' ",os_=HedefOS.LINUX)
        ekle("Terminal","Journalctl",["journal logları","systemd logları","journalctl terminal"],komut="xdotool type 'journalctl -n 50 --no-pager' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Wget İndir",["wget ile indir","dosya indir terminal","wget download"],komut="xdotool type 'wget ' ",os_=HedefOS.LINUX)
        ekle("Terminal","Curl İstek",["curl isteği yap","api isteği terminal","curl get"],komut="xdotool type 'curl -s ' ",os_=HedefOS.LINUX)
        ekle("Terminal","Tar Çıkart",["tar dosyasını çıkart","arşivi aç terminal","tar extract"],komut="xdotool type 'tar -xzf ' ",os_=HedefOS.LINUX)
        ekle("Terminal","Zip Oluştur",["zip arşivi oluştur","dosyaları sıkıştır","zip terminal"],komut="xdotool type 'zip -r arsiv.zip . ' && xdotool key Return",os_=HedefOS.LINUX)
        ekle("Terminal","Chmod Yürütülebilir",["dosyayı yürütülebilir yap","chmod 755","execute izni ver"],komut="xdotool type 'chmod +x ' ",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / LİBREOFFİCE WRITER
        # ════════════════════════════════════════════════════════════════════
        ekle("Writer","Kalın",["yazıyı kalın yap","bold yap","ctrl b writer"],komut="xdotool key ctrl+b",os_=HedefOS.LINUX)
        ekle("Writer","İtalik",["yazıyı italik yap","eğik yazı","ctrl i writer"],komut="xdotool key ctrl+i",os_=HedefOS.LINUX)
        ekle("Writer","Altı Çizili",["altını çiz","underline yap","ctrl u writer"],komut="xdotool key ctrl+u",os_=HedefOS.LINUX)
        ekle("Writer","Üstü Çizili",["üstünü çiz","strikethrough","yazıyı çiz"],komut="xdotool key alt+h",os_=HedefOS.LINUX)
        ekle("Writer","Sola Hizala",["metni sola hizala","left align","ctrl l writer"],komut="xdotool key ctrl+l",os_=HedefOS.LINUX)
        ekle("Writer","Sağa Hizala",["metni sağa hizala","right align","ctrl r writer"],komut="xdotool key ctrl+r",os_=HedefOS.LINUX)
        ekle("Writer","Ortala",["metni ortala","center align","ctrl e writer"],komut="xdotool key ctrl+e",os_=HedefOS.LINUX)
        ekle("Writer","İki Yana Yasla",["iki yana yasla","justify","ctrl j writer"],komut="xdotool key ctrl+j",os_=HedefOS.LINUX)
        ekle("Writer","Madde İşareti",["madde işareti ekle","bullet list","liste oluştur"],komut="xdotool key F12",os_=HedefOS.LINUX)
        ekle("Writer","Numaralı Liste",["numaralı liste","ordered list","numaralı madde"],komut="xdotool key F12",os_=HedefOS.LINUX)
        ekle("Writer","Girinti Artır",["girintiyi artır","tab ile girinti","indent artır"],komut="xdotool key ctrl+m",os_=HedefOS.LINUX)
        ekle("Writer","Girinti Azalt",["girintiyi azalt","outdent","girinti geri al"],komut="xdotool key ctrl+shift+m",os_=HedefOS.LINUX)
        ekle("Writer","Üst Simge",["üst simge yap","superscript","üssü al"],komut="xdotool key ctrl+shift+p",os_=HedefOS.LINUX)
        ekle("Writer","Alt Simge",["alt simge yap","subscript","alt index"],komut="xdotool key ctrl+shift+b",os_=HedefOS.LINUX)
        ekle("Writer","Başlık 1",["başlık bir stilini uygula","h1 yap","heading one"],komut="xdotool key ctrl+1",os_=HedefOS.LINUX)
        ekle("Writer","Başlık 2",["başlık iki stilini uygula","h2 yap","heading two"],komut="xdotool key ctrl+2",os_=HedefOS.LINUX)
        ekle("Writer","Başlık 3",["başlık üç stilini uygula","h3 yap","heading three"],komut="xdotool key ctrl+3",os_=HedefOS.LINUX)
        ekle("Writer","Sayfa Sonu",["sayfa sonu ekle","page break","yeni sayfa başlat"],komut="xdotool key ctrl+Return",os_=HedefOS.LINUX)
        ekle("Writer","Tablo Ekle",["tablo ekle writer","yeni tablo oluştur","insert table"],komut="xdotool key ctrl+F12",os_=HedefOS.LINUX)
        ekle("Writer","Tablo Sonraki Hücre",["tablo sonraki hücre","tab tablo","next cell"],komut="xdotool key Tab",os_=HedefOS.LINUX)
        ekle("Writer","Tablo Önceki Hücre",["tablo önceki hücre","shift tab tablo","previous cell"],komut="xdotool key shift+Tab",os_=HedefOS.LINUX)
        ekle("Writer","Resim Ekle",["belgeye resim ekle","görsel ekle writer","insert image"],komut="xdotool key ctrl+shift+i",os_=HedefOS.LINUX)
        ekle("Writer","Köprü Ekle",["bağlantı ekle writer","köprü bağlantısı","insert link writer"],komut="xdotool key ctrl+k",os_=HedefOS.LINUX)
        ekle("Writer","Sayfa Numarası",["sayfa numarası ekle","page number insert","numara ekle writer"],komut="xdotool key ctrl+F2",os_=HedefOS.LINUX)
        ekle("Writer","Üst Bilgi",["üst bilgi ekle","header writer","sayfa başlığı"],komut="xdotool key ctrl+F8 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("Writer","Alt Bilgi",["alt bilgi ekle","footer writer","sayfa alt başlığı"],komut="xdotool key ctrl+F9 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("Writer","Dipnot",["dipnot ekle","footnote","altta not ekle"],komut="xdotool key ctrl+alt+f",os_=HedefOS.LINUX)
        ekle("Writer","Kelime Sayısı",["kelime sayısını göster","word count","kaç kelime var"],komut="xdotool key ctrl+shift+g",os_=HedefOS.LINUX)
        ekle("Writer","Yazım Denetimi",["yazım denetimi yap","spell check","imla kontrolü"],komut="xdotool key F7",os_=HedefOS.LINUX)
        ekle("Writer","PDF Dışa Aktar",["pdf olarak kaydet","pdf export","belgeyi pdf yap"],komut="xdotool key ctrl+shift+s",os_=HedefOS.LINUX)
        ekle("Writer","Tam Ekran Yazı",["tam ekran yazı modu","writer fullscreen","yazı odak modu"],komut="xdotool key ctrl+shift+j",os_=HedefOS.LINUX)
        ekle("Writer","Bul ve Değiştir",["writer bul değiştir","metni değiştir","ctrl h writer"],komut="xdotool key ctrl+h",os_=HedefOS.LINUX)
        ekle("Writer","Satırbaşı Karakteri",["satır sonu göster","görünmez karakterler","formatting marks"],komut="xdotool key ctrl+F10",os_=HedefOS.LINUX)
        ekle("Writer","Belge Başına Git",["belgenin başına git","ctrl home writer","ilk sayfaya git"],komut="xdotool key ctrl+Home",os_=HedefOS.LINUX)
        ekle("Writer","Belge Sonuna Git",["belgenin sonuna git","ctrl end writer","son sayfaya git"],komut="xdotool key ctrl+End",os_=HedefOS.LINUX)
        ekle("Writer","Otomatik Düzelt",["autocorrect kapat","otomatik düzelt","yazım otomatik"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)
        ekle("Writer","Stiller Paneli",["stiller panelini aç","paragraph styles","stiller sidebar"],komut="xdotool key F11",os_=HedefOS.LINUX)
        ekle("Writer","Renk Seç",["metin rengini değiştir","font color","yazı rengi"],komut="xdotool key alt+h c",os_=HedefOS.LINUX)
        ekle("Writer","Vurgu Rengi",["arka plan rengi değiştir","highlight text","vurgula"],komut="xdotool key alt+h i",os_=HedefOS.LINUX)
        ekle("Writer","Navigator",["navigator aç writer","belgede gezinim","outline navigator"],komut="xdotool key F5",os_=HedefOS.LINUX)
        ekle("Writer","Makro Çalıştır",["makro çalıştır writer","libreoffice macro","basic makro"],komut="xdotool key alt+F8",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / LİBREOFFİCE CALC
        # ════════════════════════════════════════════════════════════════════
        ekle("Calc","Hücreye Git",["calc hücreye git","belirli hücre","name box calc"],komut="xdotool key ctrl+Home",os_=HedefOS.LINUX)
        ekle("Calc","Hücre Düzenle",["hücreyi düzenle","f2 calc","cell edit"],komut="xdotool key F2",os_=HedefOS.LINUX)
        ekle("Calc","Formül Gir",["formül gir calc","eşittir formül","formula bar"],komut="xdotool type '='",os_=HedefOS.LINUX)
        ekle("Calc","Toplam Formülü",["toplam formülü","sum formülü","autosum calc"],komut="xdotool key ctrl+shift+Return",os_=HedefOS.LINUX)
        ekle("Calc","Sütun Otomatik Genişlik",["sütunu otomatik genişlet","best fit column","column autofit"],komut="xdotool key ctrl+1",os_=HedefOS.LINUX)
        ekle("Calc","Satır Ekle",["satır ekle calc","yeni satır tablo","insert row"],komut="xdotool key ctrl+plus",os_=HedefOS.LINUX)
        ekle("Calc","Sütun Ekle",["sütun ekle calc","yeni sütun","insert column"],komut="xdotool key ctrl+plus",os_=HedefOS.LINUX)
        ekle("Calc","Satır Sil",["satır sil calc","delete row","satırı kaldır"],komut="xdotool key ctrl+minus",os_=HedefOS.LINUX)
        ekle("Calc","Filtre Uygula",["calc filtre uygula","autofilter","veri filtrele"],komut="xdotool key ctrl+shift+l",os_=HedefOS.LINUX)
        ekle("Calc","Sırala",["verileri sırala","sort data calc","sort ascending"],komut="xdotool key ctrl+shift+F9",os_=HedefOS.LINUX)
        ekle("Calc","Grafik Ekle",["grafik ekle calc","chart insert","veri grafiği"],komut="xdotool key ctrl+F3",os_=HedefOS.LINUX)
        ekle("Calc","Yeni Sayfa",["yeni çalışma sayfası","new sheet calc","sayfa ekle calc"],komut="xdotool key ctrl+shift+plus",os_=HedefOS.LINUX)
        ekle("Calc","Sayfa Sil",["çalışma sayfasını sil","sheet delete calc"],komut="xdotool key ctrl+shift+minus",os_=HedefOS.LINUX)
        ekle("Calc","Sonraki Sayfa",["sonraki sayfa calc","next sheet","sağdaki sayfa"],komut="xdotool key ctrl+Page_Down",os_=HedefOS.LINUX)
        ekle("Calc","Önceki Sayfa",["önceki sayfa calc","previous sheet","soldaki sayfa"],komut="xdotool key ctrl+Page_Up",os_=HedefOS.LINUX)
        ekle("Calc","Hücre Biçimi",["hücre biçimi aç","cell format","ctrl 1 calc"],komut="xdotool key ctrl+1",os_=HedefOS.LINUX)
        ekle("Calc","Para Birimi",["para birimi biçimi","currency format","tl formatı"],komut="xdotool key ctrl+shift+4",os_=HedefOS.LINUX)
        ekle("Calc","Yüzde Biçim",["yüzde biçimi","percent format","yüzde calc"],komut="xdotool key ctrl+shift+5",os_=HedefOS.LINUX)
        ekle("Calc","Tarih Biçim",["tarih biçimi","date format calc","tarih formatı"],komut="xdotool key ctrl+shift+3",os_=HedefOS.LINUX)
        ekle("Calc","Sütun Gizle",["sütun gizle","hide column","sütunu gizle calc"],komut="xdotool key ctrl+0",os_=HedefOS.LINUX)
        ekle("Calc","Sütun Göster",["gizli sütunları göster","unhide column","sütun açık"],komut="xdotool key ctrl+shift+9",os_=HedefOS.LINUX)
        ekle("Calc","Bölmeleri Dondur",["satırları dondur","freeze panes","başlıkları sabitle"],komut="xdotool key ctrl+F2 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("Calc","Koşullu Biçimlendirme",["koşullu biçimlendirme","conditional format","kural ekle"],komut="xdotool key ctrl+shift+F7",os_=HedefOS.LINUX)
        ekle("Calc","Pivot Tablo",["pivot tablo","data pilot","özet tablo"],komut="xdotool key ctrl+shift+F1 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("Calc","Alan Adla Git",["calc alana git","belirli hücreye atla","ctrl f5 calc"],komut="xdotool key ctrl+F5",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / VLC MEDYA OYNATICI
        # ════════════════════════════════════════════════════════════════════
        ekle("VLC","VLC Oynat Durdur",["vlc oynat","vlc durdur","vlc play pause"],komut="xdotool key space",os_=HedefOS.LINUX)
        ekle("VLC","VLC İleri Sar",["vlc ileri sar","vlc fast forward","vlc on saniye ileri"],komut="xdotool key ctrl+Right",os_=HedefOS.LINUX)
        ekle("VLC","VLC Geri Sar",["vlc geri sar","vlc rewind","vlc on saniye geri"],komut="xdotool key ctrl+Left",os_=HedefOS.LINUX)
        ekle("VLC","VLC Bir Dakika İleri",["vlc bir dakika ileri","vlc dakika ileri","vlc uzun ileri"],komut="xdotool key alt+Right",os_=HedefOS.LINUX)
        ekle("VLC","VLC Bir Dakika Geri",["vlc bir dakika geri","vlc uzun geri","vlc dakika geri"],komut="xdotool key alt+Left",os_=HedefOS.LINUX)
        ekle("VLC","VLC Tam Ekran",["vlc tam ekran","vlc fullscreen","f tuşu vlc"],komut="xdotool key f",os_=HedefOS.LINUX)
        ekle("VLC","VLC Altyazı",["vlc altyazı","vlc subtitle","altyazı aç kapat"],komut="xdotool key v",os_=HedefOS.LINUX)
        ekle("VLC","VLC Ses Artır",["vlc ses artır","vlc volume up","vlc daha yüksek"],komut="xdotool key ctrl+Up",os_=HedefOS.LINUX)
        ekle("VLC","VLC Ses Azalt",["vlc ses azalt","vlc volume down","vlc daha kısık"],komut="xdotool key ctrl+Down",os_=HedefOS.LINUX)
        ekle("VLC","VLC Sessiz",["vlc sessiz","vlc mute","vlc sesi kes"],komut="xdotool key m",os_=HedefOS.LINUX)
        ekle("VLC","VLC Playlist Aç",["vlc playlist","vlc oynatma listesi","l tuşu vlc"],komut="xdotool key ctrl+l",os_=HedefOS.LINUX)
        ekle("VLC","VLC Sonraki Medya",["vlc sonraki","vlc next","vlc next track"],komut="xdotool key n",os_=HedefOS.LINUX)
        ekle("VLC","VLC Önceki Medya",["vlc önceki","vlc previous","vlc previous track"],komut="xdotool key p",os_=HedefOS.LINUX)
        ekle("VLC","VLC Döngü",["vlc döngü","vlc loop","vlc tekrar et"],komut="xdotool key l",os_=HedefOS.LINUX)
        ekle("VLC","VLC Karıştır",["vlc karıştır","vlc shuffle","vlc rastgele çal"],komut="xdotool key r",os_=HedefOS.LINUX)
        ekle("VLC","VLC Medya Bilgisi",["vlc medya bilgisi","vlc meta","vlc dosya bilgisi"],komut="xdotool key ctrl+i",os_=HedefOS.LINUX)
        ekle("VLC","VLC Hızı Artır",["vlc oynatma hızı artır","vlc faster","vlc hızlandır"],komut="xdotool key plus",os_=HedefOS.LINUX)
        ekle("VLC","VLC Hızı Azalt",["vlc oynatma hızı azalt","vlc slower","vlc yavaşlat"],komut="xdotool key minus",os_=HedefOS.LINUX)
        ekle("VLC","VLC Normal Hız",["vlc normal hız","vlc 1x speed","vlc hız sıfırla"],komut="xdotool key equal",os_=HedefOS.LINUX)
        ekle("VLC","VLC Ekran Görüntüsü",["vlc ekran görüntüsü","vlc screenshot","vlc frame yakala"],komut="xdotool key shift+s",os_=HedefOS.LINUX)
        ekle("VLC","VLC Görüntü Uzatma",["vlc görüntüyü uzat","vlc video uzat","vlc tam doldur"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)
        ekle("VLC","VLC Ses Kanalı",["vlc ses kanalı değiştir","vlc audio track","ses kanalı vlc"],komut="xdotool key b",os_=HedefOS.LINUX)
        ekle("VLC","VLC Program Kapat",["vlc kapat","vlc programı kapat","vlc çıkış"],komut="xdotool key ctrl+q",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / GIMP GÖRÜNTÜ EDİTÖRÜ
        # ════════════════════════════════════════════════════════════════════
        ekle("GIMP","GIMP Yeni Görüntü",["gimp yeni görüntü","yeni resim oluştur","ctrl n gimp"],komut="xdotool key ctrl+n",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Aç",["gimp resim aç","gimp dosya aç","ctrl o gimp"],komut="xdotool key ctrl+o",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Kaydet",["gimp dışa aktar","gimp kaydet","ctrl shift e gimp"],komut="xdotool key ctrl+shift+e",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Dışa Aktar",["gimp png kaydet","gimp jpg kaydet","export as gimp"],komut="xdotool key ctrl+shift+e",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Geri Al",["gimp geri al","gimp undo","ctrl z gimp"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Geçmişi Göster",["gimp geçmişi","gimp undo history","edit history"],komut="xdotool key ctrl+shift+z",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Tümünü Seç",["gimp tümünü seç","select all gimp","ctrl a gimp"],komut="xdotool key ctrl+a",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Seçimi Kaldır",["gimp seçimi kaldır","deselect gimp","ctrl shift a gimp"],komut="xdotool key ctrl+shift+a",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Tersine Seç",["seçimi tersine çevir","invert selection gimp","ctrl i gimp"],komut="xdotool key ctrl+i",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Kopyala",["gimp kopyala","katmanı kopyala","ctrl c gimp"],komut="xdotool key ctrl+c",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Yapıştır Yeni",["yapıştır yeni katman","paste as new layer","ctrl shift v gimp"],komut="xdotool key ctrl+shift+v",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Görüntü Boyutu",["görüntü boyutunu değiştir","gimp resize","scale image"],komut="xdotool key ctrl+shift+e",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Tuval Boyutu",["tuval boyutunu değiştir","canvas size","gimp canvas"],komut="xdotool key ctrl+shift+c",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Döndür",["görüntüyü döndür","rotate image","gimp rotate"],komut="xdotool key ctrl+shift+r 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Ayna Yatay",["yatay aynala","flip horizontal","gimp mirror"],komut="xdotool key ctrl+shift+h 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Renk Dengesi",["renk dengesi gimp","color balance","renkler ayarla"],komut="xdotool key ctrl+b",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Parlaklık Kontrast",["parlaklık kontrast gimp","brightness contrast","gimp brightness"],komut="xdotool key ctrl+shift+b",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Eğriler",["eğriler ayarı gimp","gimp curves","color curves"],komut="xdotool key ctrl+m",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Seviyeler",["gimp seviyeler","levels adjustment","gimp levels"],komut="xdotool key ctrl+l",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Ton Doygunluk",["gimp ton doygunluk","hue saturation","renk tonu gimp"],komut="xdotool key ctrl+shift+s",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Filtre Uygula",["son filtreyi tekrar uygula","gimp son filtre","ctrl f gimp"],komut="xdotool key ctrl+f",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Zoom Fit",["gimp ekrana sığdır","fit image window","görüntüyü sığdır"],komut="xdotool key shift+ctrl+e",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Tam Ekran",["gimp tam ekran","fullscreen gimp","gimp büyük görünüm"],komut="xdotool key F11",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Araç Kutusu",["araç kutusunu göster","toolbox gimp","gimp araçlar"],komut="xdotool key ctrl+b",os_=HedefOS.LINUX)
        ekle("GIMP","GIMP Katmanlar",["katmanlar paneli","layers panel gimp","gimp layers"],komut="xdotool key ctrl+l",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / NAUTILUS DOSYA YÖNETİCİSİ
        # ════════════════════════════════════════════════════════════════════
        ekle("Nautilus","Gizli Dosyaları Göster",["gizli dosyaları göster nautilus","ctrl h nautilus","noktalı dosyalar göster"],komut="xdotool key ctrl+h",os_=HedefOS.LINUX)
        ekle("Nautilus","Adresi Göster",["adres çubuğunu aç nautilus","ctrl l nautilus","konum çubuğu"],komut="xdotool key ctrl+l",os_=HedefOS.LINUX)
        ekle("Nautilus","Yukarı Klasöre Git",["üst klasöre git","parent folder","geri nautilus"],komut="xdotool key alt+Up",os_=HedefOS.LINUX)
        ekle("Nautilus","Önceki Klasöre Git",["önceki klasöre git","geri nautilus history","alt sol nautilus"],komut="xdotool key alt+Left",os_=HedefOS.LINUX)
        ekle("Nautilus","Sonraki Klasöre Git",["sonraki klasöre git","ileri nautilus","alt sağ nautilus"],komut="xdotool key alt+Right",os_=HedefOS.LINUX)
        ekle("Nautilus","Ev Klasörüne Git",["ev klasörüne git nautilus","alt home nautilus"],komut="xdotool key alt+Home",os_=HedefOS.LINUX)
        ekle("Nautilus","Yeni Klasör",["yeni klasör oluştur","create folder","ctrl shift n nautilus"],komut="xdotool key ctrl+shift+n",os_=HedefOS.LINUX)
        ekle("Nautilus","Dosya Özellikler",["dosya özelliklerini aç","file properties","alt enter nautilus"],komut="xdotool key alt+Return",os_=HedefOS.LINUX)
        ekle("Nautilus","Liste Görünümü",["liste görünümüne geç","list view nautilus","ctrl 1 nautilus"],komut="xdotool key ctrl+1",os_=HedefOS.LINUX)
        ekle("Nautilus","Izgara Görünümü",["izgara görünümüne geç","icon view nautilus","ctrl 2 nautilus"],komut="xdotool key ctrl+2",os_=HedefOS.LINUX)
        ekle("Nautilus","Yeni Sekme Nautilus",["yeni sekme nautilus","dosya yöneticisi tab","ctrl t nautilus"],komut="xdotool key ctrl+t",os_=HedefOS.LINUX)
        ekle("Nautilus","Arama Nautilus",["nautilus içinde ara","dosya ara","ctrl f nautilus"],komut="xdotool key ctrl+f",os_=HedefOS.LINUX)
        ekle("Nautilus","Tüm Seç Nautilus",["tüm dosyaları seç","select all nautilus","ctrl a nautilus"],komut="xdotool key ctrl+a",os_=HedefOS.LINUX)
        ekle("Nautilus","Yenile Nautilus",["nautilus yenile","dizini yenile","ctrl r nautilus"],komut="xdotool key ctrl+r",os_=HedefOS.LINUX)
        ekle("Nautilus","Panelı Aç Kapat",["yan paneli aç kapat","nautilus panel","f9 nautilus"],komut="xdotool key F9",os_=HedefOS.LINUX)
        ekle("Nautilus","Dosya Adını Değiştir",["dosya adını değiştir","rename file","f2 nautilus"],komut="xdotool key F2",os_=HedefOS.LINUX)
        ekle("Nautilus","Sıkıştır",["dosyaları sıkıştır","archive files","nautilus zip"],komut="xdotool key ctrl+shift+z 2>/dev/null; true",os_=HedefOS.LINUX)
        ekle("Nautilus","Terminal Burada Aç",["burada terminal aç","nautilus terminali","open terminal here"],komut="xdotool key ctrl+alt+t",os_=HedefOS.LINUX)
        ekle("Nautilus","Yer İmi Ekle Nautilus",["yer imi ekle nautilus","bookmark folder","ctrl d nautilus"],komut="xdotool key ctrl+d",os_=HedefOS.LINUX)
        ekle("Nautilus","Kopyala Nautilus",["dosyayı kopyala nautilus","ctrl c nautilus"],komut="xdotool key ctrl+c",os_=HedefOS.LINUX)
        ekle("Nautilus","Kes Nautilus",["dosyayı kes nautilus","ctrl x nautilus"],komut="xdotool key ctrl+x",os_=HedefOS.LINUX)
        ekle("Nautilus","Yapıştır Nautilus",["dosyayı yapıştır nautilus","ctrl v nautilus"],komut="xdotool key ctrl+v",os_=HedefOS.LINUX)
        ekle("Nautilus","Çöpe At",["dosyayı çöpe at","delete to trash","sil nautilus"],komut="xdotool key Delete",os_=HedefOS.LINUX)
        ekle("Nautilus","Kalıcı Sil",["kalıcı olarak sil","permanently delete","shift delete nautilus"],komut="xdotool key shift+Delete",os_=HedefOS.LINUX)
        ekle("Nautilus","Geri Döndür",["silindi geri döndür","restore from trash","ctrl z nautilus"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / THUNDERBIRD E-POSTA
        # ════════════════════════════════════════════════════════════════════
        ekle("Thunderbird","Yeni Mesaj",["yeni e-posta yaz","thunderbird yeni mesaj","mail yaz"],komut="xdotool key ctrl+n",os_=HedefOS.LINUX)
        ekle("Thunderbird","Mesajı Gönder",["e-postayı gönder","ctrl enter thunderbird","send mail"],komut="xdotool key ctrl+Return",os_=HedefOS.LINUX)
        ekle("Thunderbird","Postaları Al",["yeni postaları al","thunderbird refresh","get mail"],komut="xdotool key ctrl+t",os_=HedefOS.LINUX)
        ekle("Thunderbird","Yanıtla",["e-postayı yanıtla","reply mail","ctrl r thunderbird"],komut="xdotool key ctrl+r",os_=HedefOS.LINUX)
        ekle("Thunderbird","Hepsini Yanıtla",["hepsini yanıtla","reply all","ctrl shift r"],komut="xdotool key ctrl+shift+r",os_=HedefOS.LINUX)
        ekle("Thunderbird","İlet",["e-postayı ilet","forward mail","ctrl l thunderbird"],komut="xdotool key ctrl+l",os_=HedefOS.LINUX)
        ekle("Thunderbird","Sil",["e-postayı sil","delete message","thunderbird delete"],komut="xdotool key Delete",os_=HedefOS.LINUX)
        ekle("Thunderbird","Arşivle",["e-postayı arşivle","archive message","a tuşu thunderbird"],komut="xdotool key a",os_=HedefOS.LINUX)
        ekle("Thunderbird","Okundu İşaretle",["okundu olarak işaretle","mark as read","m tuşu"],komut="xdotool key m",os_=HedefOS.LINUX)
        ekle("Thunderbird","Önemli İşaretle",["yıldız ekle thunderbird","flag message","star mail"],komut="xdotool key s",os_=HedefOS.LINUX)
        ekle("Thunderbird","Sonraki Mesaj",["sonraki e-posta","next message","f tuşu thunderbird"],komut="xdotool key f",os_=HedefOS.LINUX)
        ekle("Thunderbird","Önceki Mesaj",["önceki e-posta","previous message","b tuşu thunderbird"],komut="xdotool key b",os_=HedefOS.LINUX)
        ekle("Thunderbird","Arama",["thunderbird arama","mail içinde ara","ctrl k thunderbird"],komut="xdotool key ctrl+k",os_=HedefOS.LINUX)
        ekle("Thunderbird","Filtreler",["mesaj filtreleri","filter rules","thunderbird filtre"],komut="xdotool key ctrl+shift+l",os_=HedefOS.LINUX)
        ekle("Thunderbird","Ek Ekle",["dosya ekle thunderbird","attachment ekle","ctrl shift a mail"],komut="xdotool key ctrl+shift+a",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / GENEL SİSTEM & SÜREÇ YÖNETİMİ
        # ════════════════════════════════════════════════════════════════════
        ekle("Süreç","Süreci Sonlandır",["programı zorla kapat","süreci sonlandır","kill process"],komut="xdotool key ctrl+c",os_=HedefOS.LINUX)
        ekle("Süreç","PID İle Öldür",["pid ile süreci sonlandır","kill pid","force kill"],komut="kill -9 $(xdotool getactivewindow getwindowpid) 2>/dev/null || echo 'PID bulunamadı'",os_=HedefOS.LINUX)
        ekle("Süreç","Donmuş Programı Kapat",["donmuş programı kapat","xkill kullan","force quit dondu"],komut="xkill &",os_=HedefOS.LINUX)
        ekle("Süreç","En Çok CPU Kullanan",["en çok cpu kullanan ne","top cpu process","cpu hangi program"],komut="ps aux --sort=-%cpu | awk 'NR==2{print $11, \"CPU:\", $3\"%\", \"PID:\", $2}'",os_=HedefOS.LINUX)
        ekle("Süreç","Arka Plan Süreçleri",["arka planda çalışanlar","background jobs","jobs listele"],komut="jobs -l 2>/dev/null || ps aux | grep -v grep | grep -v bash | tail -5",os_=HedefOS.LINUX)
        ekle("Süreç","Süreç Ağacı",["süreç ağacını göster","process tree","pstree"],komut="pstree -p 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("Süreç","Firefox'u Yeniden Başlat",["firefox'u yeniden başlat","firefox restart","firefox yeni"],komut="pkill firefox; sleep 1; firefox &",os_=HedefOS.LINUX)
        ekle("Süreç","Chrome'u Yeniden Başlat",["chrome'u yeniden başlat","chrome restart"],komut="pkill google-chrome; sleep 1; google-chrome &",os_=HedefOS.LINUX)
        ekle("Süreç","Tüm Tarayıcıları Kapat",["tüm tarayıcıları kapat","browser kapat","firefox chrome kapat"],komut="pkill firefox 2>/dev/null; pkill google-chrome 2>/dev/null; pkill chromium 2>/dev/null; echo 'Tarayıcılar kapatıldı'",os_=HedefOS.LINUX)
        ekle("Süreç","Uygulama Başlangıca Ekle",["başlangıca ekle","autostart ekle","startup program"],yanit="Başlangıca eklemek istediğiniz uygulamanın tam adını belirtin.",tur="konusma",os_=HedefOS.LINUX)
        ekle("Süreç","Cron Listesi",["cron listesi","zamanlanmış görevler","crontab l"],komut="crontab -l 2>/dev/null || echo 'Cron görevi yok'",os_=HedefOS.LINUX)
        ekle("Süreç","RAM Önbelleğini Temizle",["ram önbelleğini temizle","cache temizle","sync drop caches"],komut="sync && sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches' && echo 'Önbellek temizlendi'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Süreç","Swap Kullanımı",["swap kullanımı","takas alanı","swap ne kadar dolu"],komut="swapon --show 2>/dev/null || free -h | grep Swap",os_=HedefOS.LINUX)
        ekle("Süreç","Açık Dosyalar",["açık dosyalar listesi","lsof","hangi dosyalar açık"],komut="lsof 2>/dev/null | wc -l | xargs echo 'Açık dosya sayısı:'",os_=HedefOS.LINUX)
        ekle("Süreç","Sinyal Gönder",["sürece sinyal gönder","sigusr1","process signal"],yanit="Hangi sürece sinyal göndermek istiyorsunuz?",tur="konusma",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-1 / METİN GİRİŞİ (SESLE YAZMA)
        # ════════════════════════════════════════════════════════════════════
        ekle("Metin","URL Yaz",["url yaz","adres çubuğuna yaz","link gir"],komut="xdotool type --clearmodifiers --delay 50 ' '",os_=HedefOS.LINUX)
        ekle("Metin","İmza Ekle",["imzamı ekle","e-posta imzası","signature yaz"],yanit="İmzanızı ayarlar üzerinden yapılandırabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("Metin","Tarih Yaz",["bugünün tarihini yaz","tarihi gir","date type"],komut=r"xdotool type --clearmodifiers $(date '+%d/%m/%Y')",os_=HedefOS.LINUX)
        ekle("Metin","Saat Yaz",["saati yaz","şu anki saati gir","time type"],komut=r"xdotool type --clearmodifiers $(date '+%H:%M')",os_=HedefOS.LINUX)
        ekle("Metin","Kullanıcı Adını Yaz",["kullanıcı adını yaz","username type","giriş adı yaz"],komut=r"xdotool type --clearmodifiers $(whoami)",os_=HedefOS.LINUX)
        ekle("Metin","IP Adresini Yaz",["ip adresini yaz","ip adresini gir","type ip address"],komut=r"xdotool type --clearmodifiers $(hostname -I | awk '{print $1}')",os_=HedefOS.LINUX)
        ekle("Metin","Hostname Yaz",["hostname yaz","bilgisayar adını gir","makine adını yaz"],komut=r"xdotool type --clearmodifiers $(hostname)",os_=HedefOS.LINUX)
        ekle("Metin","Büyük Harfe Çevir",["büyük harfe çevir","uppercase","caps lock aç"],komut="xdotool key Caps_Lock",os_=HedefOS.LINUX)
        ekle("Metin","Kelime Sil",["son kelimeyi sil","backspace word","ctrl backspace"],komut="xdotool key ctrl+BackSpace",os_=HedefOS.LINUX)
        ekle("Metin","Satır Sil",["satırı tamamen sil","satır temizle","ctrl shift k metin"],komut="xdotool key ctrl+Home ctrl+shift+End Delete",os_=HedefOS.LINUX)
        ekle("Metin","Panoya Kopyala Seç",["panodaki metni seç","clipboard seç","paste select"],komut="xdotool key ctrl+a ctrl+c",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / INKSCAPE VEKTÖR EDİTÖRÜ
        # ════════════════════════════════════════════════════════════════════
        ekle("Inkscape","Inkscape Aç",["inkscape aç","vektör editörü aç","inkscape başlat"],komut="inkscape &",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Yeni",["inkscape yeni belge","yeni svg","inkscape new"],komut="xdotool key ctrl+n",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Dosya Aç",["inkscape dosya aç","svg aç","inkscape open"],komut="xdotool key ctrl+o",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Kaydet",["inkscape kaydet","svg kaydet","inkscape save"],komut="xdotool key ctrl+s",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Farklı Kaydet",["inkscape farklı kaydet","save as inkscape"],komut="xdotool key ctrl+shift+s",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Dışa Aktar",["inkscape dışa aktar","png olarak aktar","inkscape export"],komut="xdotool key ctrl+shift+e",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Geri Al",["inkscape geri al","undo inkscape"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape İleri Al",["inkscape ileri al","redo inkscape"],komut="xdotool key ctrl+y",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Tümünü Seç",["tümünü seç inkscape","select all inkscape"],komut="xdotool key ctrl+a",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Grupla",["nesneleri grupla inkscape","group inkscape"],komut="xdotool key ctrl+g",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Grubu Çöz",["grubu çöz inkscape","ungroup inkscape"],komut="xdotool key ctrl+shift+g",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Öne Getir",["öne getir inkscape","bring to front inkscape"],komut="xdotool key Home",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Arkaya Gönder",["arkaya gönder inkscape","send to back inkscape"],komut="xdotool key End",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Zoom Fit",["inkscape sayfayı sığdır","fit page inkscape"],komut="xdotool key 3",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Seçim Aracı",["seçim aracı inkscape","select tool inkscape"],komut="xdotool key F1",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Kalem Aracı",["kalem aracı inkscape","bezier inkscape"],komut="xdotool key b",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Metin Aracı",["metin aracı inkscape","text tool inkscape"],komut="xdotool key t",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Dikdörtgen",["dikdörtgen çiz inkscape","rectangle inkscape"],komut="xdotool key r",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Daire",["daire çiz inkscape","ellipse inkscape"],komut="xdotool key e",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Transform",["nesne boyutu inkscape","transform inkscape"],komut="xdotool key ctrl+shift+m",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Hizala",["nesneleri hizala inkscape","align inkscape"],komut="xdotool key ctrl+shift+a",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape XML",["xml editörü inkscape","edit xml inkscape"],komut="xdotool key ctrl+shift+x",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Katmanlar",["katmanlar inkscape","layers inkscape"],komut="xdotool key ctrl+shift+l",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Bul Değiştir",["bul değiştir inkscape","find replace inkscape"],komut="xdotool key ctrl+f",os_=HedefOS.LINUX)
        ekle("Inkscape","Inkscape Kapat",["inkscape kapat","inkscape çıkış"],komut="xdotool key ctrl+q",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / KDENLİVE VIDEO EDİTÖR
        # ════════════════════════════════════════════════════════════════════
        ekle("Kdenlive","Kdenlive Aç",["kdenlive aç","video editörü aç","kdenlive başlat"],komut="kdenlive &",os_=HedefOS.LINUX)
        ekle("Kdenlive","Kdenlive Yeni Proje",["kdenlive yeni proje","yeni video projesi"],komut="xdotool key ctrl+n",os_=HedefOS.LINUX)
        ekle("Kdenlive","Kdenlive Kaydet",["kdenlive kaydet","video projesini kaydet"],komut="xdotool key ctrl+s",os_=HedefOS.LINUX)
        ekle("Kdenlive","Kdenlive Geri Al",["kdenlive geri al","undo kdenlive"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)
        ekle("Kdenlive","Kdenlive Oynat Durdur",["kdenlive oynat durdur","play pause kdenlive"],komut="xdotool key space",os_=HedefOS.LINUX)
        ekle("Kdenlive","Kdenlive Dışa Aktar",["kdenlive render","kdenlive export","videoyu aktar"],komut="xdotool key ctrl+Return",os_=HedefOS.LINUX)
        ekle("Kdenlive","Kdenlive Kırp",["kdenlive kırp","timeline cut kdenlive"],komut="xdotool key x",os_=HedefOS.LINUX)
        ekle("Kdenlive","Kdenlive Tam Ekran",["kdenlive tam ekran","fullscreen preview kdenlive"],komut="xdotool key F11",os_=HedefOS.LINUX)
        ekle("Kdenlive","OpenShot Aç",["openshot aç","openshot video editörü"],komut="openshot-qt &",os_=HedefOS.LINUX)
        ekle("Kdenlive","OpenShot Kaydet",["openshot kaydet","openshot projesi kaydet"],komut="xdotool key ctrl+s",os_=HedefOS.LINUX)
        ekle("Kdenlive","OpenShot Dışa Aktar",["openshot export","openshot video aktar"],komut="xdotool key ctrl+e",os_=HedefOS.LINUX)
        ekle("Kdenlive","OpenShot Oynat",["openshot oynat","play openshot"],komut="xdotool key space",os_=HedefOS.LINUX)
        ekle("Kdenlive","OpenShot Geri Al",["openshot geri al","undo openshot"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)
        ekle("Kdenlive","Kdenlive Kapat",["kdenlive kapat","video editörü kapat"],komut="xdotool key ctrl+q",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / AUDACITY SES EDİTÖRÜ
        # ════════════════════════════════════════════════════════════════════
        ekle("Audacity","Audacity Aç",["audacity aç","ses editörü aç","audacity başlat"],komut="audacity &",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Dosya Aç",["audacity dosya aç","ses dosyası aç"],komut="xdotool key ctrl+o",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Kaydet",["audacity kaydet","ses projesi kaydet"],komut="xdotool key ctrl+s",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Dışa Aktar",["audacity export","ses dışa aktar","mp3 kaydet audacity"],komut="xdotool key ctrl+shift+e",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Oynat",["audacity oynat","ses oynat audacity"],komut="xdotool key space",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Kayıt",["audacity kayıt başlat","mikrofon kaydet audacity"],komut="xdotool key r",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Geri Al",["audacity geri al","undo audacity"],komut="xdotool key ctrl+z",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Tümünü Seç",["audacity tümünü seç","select all audacity"],komut="xdotool key ctrl+a",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Kes",["audacity kes","audio kes"],komut="xdotool key ctrl+x",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Sil",["ses bölümünü sil","delete audacity"],komut="xdotool key Delete",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Zoom Fit",["audacity tüm projeyi göster","fit window audacity"],komut="xdotool key ctrl+shift+f",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Parça Ekle",["yeni ses parçası ekle audacity","add track audacity"],komut="xdotool key ctrl+shift+n",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Soldur",["sesi soldur audacity","fade out audacity"],komut="xdotool key ctrl+shift+l",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Gürültü Gider",["gürültüyü gider audacity","noise reduction"],yanit="Sessiz bölüm seçip Efekt > Gürültü Azaltma adımlarını izleyin.",tur="konusma",os_=HedefOS.LINUX)
        ekle("Audacity","Audacity Kapat",["audacity kapat","ses editörü kapat"],komut="xdotool key ctrl+q",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / OBS STUDIO
        # ════════════════════════════════════════════════════════════════════
        ekle("OBS","OBS Aç",["obs aç","obs studio aç","obs başlat","ekran yayın programı"],komut="obs &",os_=HedefOS.LINUX)
        ekle("OBS","OBS Kayıt Başlat",["obs kayıt başlat","ekran kaydet obs"],komut="xdotool key ctrl+F9",os_=HedefOS.LINUX)
        ekle("OBS","OBS Kayıt Durdur",["obs kayıt durdur","ekran kayıt bitir"],komut="xdotool key ctrl+F9",os_=HedefOS.LINUX)
        ekle("OBS","OBS Yayın Başlat",["obs yayın başlat","stream başlat obs"],komut="xdotool key ctrl+F12",os_=HedefOS.LINUX)
        ekle("OBS","OBS Yayın Durdur",["obs yayın durdur","stream bitir obs"],komut="xdotool key ctrl+F12",os_=HedefOS.LINUX)
        ekle("OBS","OBS Sanal Kamera",["obs sanal kamera aç","virtual camera obs"],komut="xdotool key ctrl+shift+F10",os_=HedefOS.LINUX)
        ekle("OBS","OBS Ekran Görüntüsü",["obs ekran görüntüsü al","screenshot obs"],komut="xdotool key ctrl+F10",os_=HedefOS.LINUX)
        ekle("OBS","OBS Studio Mode",["obs studio mode","obs önizleme modu"],komut="xdotool key ctrl+shift+s",os_=HedefOS.LINUX)
        ekle("OBS","OBS Ses Ayarları",["obs ses ayarları","obs audio settings"],yanit="OBS Ayarlar > Ses bölümünden mikrofon ve masaüstü sesini ayarlayın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("OBS","OBS Çözünürlük",["obs video ayarları","obs çözünürlük ayarla","obs fps"],yanit="OBS Ayarlar > Video bölümünden çözünürlük ve FPS seçin.",tur="konusma",os_=HedefOS.LINUX)
        ekle("OBS","OBS Çıkış Ayarı",["obs çıkış ayarları","obs kayıt kalitesi","obs bitrate"],yanit="OBS Ayarlar > Çıkış bölümünden kalite ve format seçin.",tur="konusma",os_=HedefOS.LINUX)
        ekle("OBS","OBS Kapat",["obs kapat","obs studio kapat"],komut="xdotool key ctrl+q",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / DOCKER
        # ════════════════════════════════════════════════════════════════════
        ekle("Docker","Docker Durum",["docker durumu","docker ps","çalışan konteynerler"],komut="docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'Docker çalışmıyor'",os_=HedefOS.LINUX)
        ekle("Docker","Docker Tüm Konteyner",["tüm docker konteynerleri","docker ps a"],komut="docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker İmajlar",["docker imajları","docker images"],komut="docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Up",["docker compose başlat","docker compose up","docker up"],komut="docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Down",["docker compose durdur","docker compose down","docker down"],komut="docker compose down 2>/dev/null || docker-compose down 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Log",["docker compose logları","docker compose log"],komut="docker compose logs --tail=50 2>/dev/null || docker-compose logs --tail=50 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Tüm Durdur",["tüm konteynerleri durdur","docker stop all"],komut="docker stop $(docker ps -q) 2>/dev/null && echo 'Tüm konteynerler durduruldu' || echo 'Çalışan konteyner yok'",os_=HedefOS.LINUX)
        ekle("Docker","Docker Temizlik",["docker temizlik","kullanılmayan docker temizle","docker prune"],komut="docker system prune -f 2>/dev/null && echo 'Docker temizlendi'",os_=HedefOS.LINUX)
        ekle("Docker","Docker Disk",["docker disk kullanımı","docker df"],komut="docker system df 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Ağlar",["docker ağları listele","docker network ls"],komut="docker network ls 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Volumler",["docker volume listele","docker volumes"],komut="docker volume ls 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Stats",["docker kaynak kullanımı","docker stats"],komut="docker stats --no-stream 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Versiyon",["docker versiyonu","docker version"],komut="docker --version 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Build",["docker compose derle","docker compose build"],komut="docker compose build 2>/dev/null || docker-compose build 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Restart",["docker compose yeniden başlat","docker compose restart"],komut="docker compose restart 2>/dev/null || docker-compose restart 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Docker","Docker Orphan Temizle",["docker orphan kaldır","kullanılmayan konteyner sil"],komut="docker container prune -f 2>/dev/null && docker volume prune -f 2>/dev/null && echo 'Temizlendi'",os_=HedefOS.LINUX)
        ekle("Docker","Docker Pull",["docker imaj indir","docker pull"],yanit="docker pull imaj_adi komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("Docker","Docker Exec",["docker konteynere gir","docker bash","docker exec"],yanit="docker exec -it konteyner_adi bash komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("Docker","Docker Log",["konteyner logu","docker log konteyner"],yanit="docker logs -f konteyner_adi komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("Docker","Docker Info",["docker bilgisi","docker info"],komut="docker info 2>/dev/null | head -20",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / VIRTUALBOX / QEMU
        # ════════════════════════════════════════════════════════════════════
        ekle("VirtualBox","VirtualBox Aç",["virtualbox aç","sanal makine yöneticisi","vm yöneticisi"],komut="virtualbox &",os_=HedefOS.LINUX)
        ekle("VirtualBox","VirtualBox Listele",["sanal makineleri listele","vboxmanage list vms"],komut="vboxmanage list vms 2>/dev/null || echo 'VirtualBox kurulu değil'",os_=HedefOS.LINUX)
        ekle("VirtualBox","VirtualBox Çalışanlar",["çalışan sanal makineler","running vms"],komut="vboxmanage list runningvms 2>/dev/null || echo 'Çalışan VM yok'",os_=HedefOS.LINUX)
        ekle("VirtualBox","VirtualBox Başlat",["sanal makineyi başlat","vm start"],yanit="vboxmanage startvm 'vm_adi' --type headless komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("VirtualBox","VirtualBox Durdur",["sanal makineyi durdur","vm stop"],yanit="vboxmanage controlvm 'vm_adi' poweroff komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("VirtualBox","VirtualBox Snapshot",["vm snapshot al","sanal makine anlık görüntü"],yanit="vboxmanage snapshot 'vm_adi' take 'ad' komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("VirtualBox","QEMU KVM Kontrol",["kvm destekli mi","qemu kvm kontrol"],komut="lsmod | grep kvm && echo 'KVM aktif' || echo 'KVM yüklü değil'",os_=HedefOS.LINUX)
        ekle("VirtualBox","Virt Manager",["virt manager aç","virt-manager","gnome vm yöneticisi"],komut="virt-manager &",os_=HedefOS.LINUX)
        ekle("VirtualBox","Virsh Listesi",["virsh vm listesi","libvirt vm listesi","virsh list"],komut="virsh list --all 2>/dev/null || echo 'libvirt çalışmıyor'",os_=HedefOS.LINUX)
        ekle("VirtualBox","VM Ağ Bilgisi",["vm ağ bilgisi","sanal makine ağ"],komut="virsh net-list --all 2>/dev/null || vboxmanage list hostonlyifs 2>/dev/null",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / TELEGRAM DESKTOP
        # ════════════════════════════════════════════════════════════════════
        ekle("TelegramDesktop","Telegram Desktop Aç",["telegram masaüstü aç","telegram desktop aç","telegram app aç"],komut="telegram-desktop &",os_=HedefOS.LINUX)
        ekle("TelegramDesktop","Telegram Yeni Mesaj",["telegram yeni mesaj yaz","ctrl n telegram desktop"],komut="xdotool key ctrl+n",os_=HedefOS.LINUX)
        ekle("TelegramDesktop","Telegram Ara",["telegram içinde ara","ctrl f telegram desktop"],komut="xdotool key ctrl+f",os_=HedefOS.LINUX)
        ekle("TelegramDesktop","Telegram Profil",["telegram profil","telegram ayarları aç","telegram settings"],komut="xdotool key ctrl+comma",os_=HedefOS.LINUX)
        ekle("TelegramDesktop","Telegram Sonraki Sohbet",["telegram sonraki","alt aşağı telegram"],komut="xdotool key alt+Down",os_=HedefOS.LINUX)
        ekle("TelegramDesktop","Telegram Önceki Sohbet",["telegram önceki","alt yukarı telegram"],komut="xdotool key alt+Up",os_=HedefOS.LINUX)
        ekle("TelegramDesktop","Telegram Dosya Gönder",["telegram dosya gönder","attach file telegram"],komut="xdotool key ctrl+o",os_=HedefOS.LINUX)
        ekle("TelegramDesktop","Telegram Emoji",["telegram emoji","ctrl i telegram desktop"],komut="xdotool key ctrl+i",os_=HedefOS.LINUX)
        ekle("TelegramDesktop","Telegram Kapat",["telegram desktop kapat","telegram masaüstü kapat"],komut="pkill telegram-desktop 2>/dev/null; echo 'Telegram kapatıldı'",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / DISCORD
        # ════════════════════════════════════════════════════════════════════
        ekle("Discord","Discord Aç",["discord aç","discord başlat","discord uygulaması aç"],komut="discord &",os_=HedefOS.LINUX)
        ekle("Discord","Discord Sessize Al",["discord sustur","discord mute mikrofon","ctrl shift m discord"],komut="xdotool key ctrl+shift+m",os_=HedefOS.LINUX)
        ekle("Discord","Discord Video Kapat",["discord kamera kapat","video kapat discord"],komut="xdotool key ctrl+shift+v",os_=HedefOS.LINUX)
        ekle("Discord","Discord Kanaldan Çık",["discord sesli kanaldan çık","voice channel çık"],komut="xdotool key ctrl+shift+d",os_=HedefOS.LINUX)
        ekle("Discord","Discord Ara",["discord arama","ctrl k discord"],komut="xdotool key ctrl+k",os_=HedefOS.LINUX)
        ekle("Discord","Discord Sunucu Geç",["discord sonraki sunucu","ctrl alt Down discord"],komut="xdotool key ctrl+alt+Down",os_=HedefOS.LINUX)
        ekle("Discord","Discord DM",["discord dm aç","direct mesaj discord"],komut="xdotool key ctrl+shift+t",os_=HedefOS.LINUX)
        ekle("Discord","Discord Emoji",["discord emoji ekle","ctrl e discord"],komut="xdotool key ctrl+e",os_=HedefOS.LINUX)
        ekle("Discord","Discord Güncelle",["discord güncelle","discord yeniden başlat"],komut="pkill discord; sleep 1; discord &",os_=HedefOS.LINUX)
        ekle("Discord","Discord Kapat",["discord kapat","discord çıkış"],komut="pkill discord 2>/dev/null; echo 'Discord kapatıldı'",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / ZOOM / TEAMS
        # ════════════════════════════════════════════════════════════════════
        ekle("Zoom","Zoom Aç",["zoom aç","zoom toplantı başlat"],komut="zoom &",os_=HedefOS.LINUX)
        ekle("Zoom","Zoom Sessize Al",["zoom mikrofon kapat","zoom mute","alt a zoom"],komut="xdotool key alt+a",os_=HedefOS.LINUX)
        ekle("Zoom","Zoom Video Kapat",["zoom kamera kapat","video kapat zoom","alt v zoom"],komut="xdotool key alt+v",os_=HedefOS.LINUX)
        ekle("Zoom","Zoom Ekran Paylaş",["zoom ekran paylaş","screen share zoom"],komut="xdotool key alt+shift+s",os_=HedefOS.LINUX)
        ekle("Zoom","Zoom El Kaldır",["zoom el kaldır","raise hand zoom","alt y zoom"],komut="xdotool key alt+y",os_=HedefOS.LINUX)
        ekle("Zoom","Zoom Katılımcılar",["zoom katılımcıları göster","participants zoom"],komut="xdotool key alt+u",os_=HedefOS.LINUX)
        ekle("Zoom","Zoom Sohbet",["zoom sohbet aç","chat zoom"],komut="xdotool key alt+h",os_=HedefOS.LINUX)
        ekle("Zoom","Zoom Kayıt",["zoom toplantı kaydet","record zoom","alt r zoom"],komut="xdotool key alt+r",os_=HedefOS.LINUX)
        ekle("Zoom","Zoom Bitir",["zoom toplantıyı bitir","end meeting zoom"],komut="xdotool key alt+q",os_=HedefOS.LINUX)
        ekle("Zoom","Teams Aç",["teams aç","microsoft teams başlat","ms teams"],komut="teams &",os_=HedefOS.LINUX)
        ekle("Zoom","Teams Sessize Al",["teams mikrofon kapat","teams mute"],komut="xdotool key ctrl+shift+m",os_=HedefOS.LINUX)
        ekle("Zoom","Teams Video Kapat",["teams kamera kapat","video kapat teams"],komut="xdotool key ctrl+shift+o",os_=HedefOS.LINUX)
        ekle("Zoom","Teams Ekran Paylaş",["teams ekran paylaş","screen share teams"],komut="xdotool key ctrl+shift+e",os_=HedefOS.LINUX)
        ekle("Zoom","Teams El Kaldır",["teams el kaldır","raise hand teams"],komut="xdotool key ctrl+shift+k",os_=HedefOS.LINUX)
        ekle("Zoom","Teams Sohbet",["teams sohbet aç","teams chat"],komut="xdotool key ctrl+shift+c",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / GELİŞTİRME ARAÇLARI
        # ════════════════════════════════════════════════════════════════════
        ekle("Geliştirme","Python Versiyon",["python versiyonu","python version","python sürüm"],komut="python3 --version 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Geliştirme","Pip Listele",["pip paketleri listele","pip list","python paketleri"],komut="pip3 list 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("Geliştirme","Node Versiyon",["node versiyonu","nodejs version","npm version"],komut="node --version 2>/dev/null; npm --version 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Geliştirme","NPM Global Paketler",["npm global paketleri","npm list global"],komut="npm list -g --depth=0 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Geliştirme","Venv Oluştur",["python venv oluştur","virtualenv kur","sanal ortam oluştur"],komut="python3 -m venv venv && echo 'Venv oluşturuldu: ./venv'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Git Status",["git durumu","git status","git değişiklikler"],komut="git status 2>/dev/null || echo 'Git deposu yok'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Git Log",["git log göster","commit geçmişi","git log kısa"],komut="git log --oneline -10 2>/dev/null || echo 'Git deposu yok'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Git Branch",["git dallar","git branch listele","hangi git branch"],komut="git branch -a 2>/dev/null || echo 'Git deposu yok'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Git Stash",["git stash yap","değişiklikleri sakla git"],komut="git stash 2>/dev/null && echo 'Saklandı' || echo 'Git deposu yok'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Git Stash Pop",["git stash geri al","saklananı geri yükle git"],komut="git stash pop 2>/dev/null && echo 'Geri yüklendi' || echo 'Stash yok'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Git Diff",["git farkları","git diff göster","değişiklik farkı"],komut="git diff --stat 2>/dev/null || echo 'Git deposu yok'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Git Pull",["git pull yap","son commitleri çek","git güncelle"],komut="git pull 2>/dev/null || echo 'Git deposu yok'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Git Remote",["git remote listele","git uzak depolar"],komut="git remote -v 2>/dev/null || echo 'Git deposu yok'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Jupyter Başlat",["jupyter başlat","jupyter notebook aç","jupyter lab"],komut="jupyter notebook &",os_=HedefOS.LINUX)
        ekle("Geliştirme","Pytest Çalıştır",["testleri çalıştır","pytest","python testleri çalıştır"],komut="python3 -m pytest -v 2>/dev/null || echo 'pytest kurulu değil'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Go Versiyon",["go versiyonu","golang version"],komut="go version 2>/dev/null || echo 'Go kurulu değil'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Rust Versiyon",["rust versiyonu","rustc version","cargo version"],komut="rustc --version 2>/dev/null; cargo --version 2>/dev/null",os_=HedefOS.LINUX)
        ekle("Geliştirme","Java Versiyon",["java versiyonu","java version","jdk sürüm"],komut="java --version 2>/dev/null || java -version 2>&1 | head -1",os_=HedefOS.LINUX)
        ekle("Geliştirme","HTTP Server",["basit http server","python web server","localhost başlat"],komut="python3 -m http.server 8000 &",os_=HedefOS.LINUX)
        ekle("Geliştirme","Kodu Formatla",["kodu formatla python","black çalıştır","python formatter"],komut="black . 2>/dev/null && echo 'Formatlandı' || echo 'Black kurulu değil'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Linter Çalıştır",["python linter çalıştır","flake8","kod kalite kontrol"],komut="flake8 . 2>/dev/null | head -20 || echo 'Linter kurulu değil'",os_=HedefOS.LINUX)
        ekle("Geliştirme","Make Çalıştır",["make çalıştır","makefile build"],komut="make 2>/dev/null || echo 'Makefile bulunamadı'",os_=HedefOS.LINUX)
        ekle("Geliştirme","DBeaver Aç",["dbeaver aç","veritabanı arayüzü aç","dbeaver başlat"],komut="dbeaver &",os_=HedefOS.LINUX)
        ekle("Geliştirme","pgAdmin Aç",["pgadmin aç","postgresql arayüzü"],komut="pgadmin4 &",os_=HedefOS.LINUX)
        ekle("Geliştirme","Postman Aç",["postman aç","api test aracı","postman başlat"],komut="postman &",os_=HedefOS.LINUX)
        ekle("Geliştirme","Insomnia Aç",["insomnia aç","api client aç"],komut="insomnia &",os_=HedefOS.LINUX)
        ekle("Geliştirme","SQLite Aç",["sqlite aç","sqlite3 başlat"],yanit="sqlite3 veritabani.db komutuyla SQLite konsolunu açabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("Geliştirme","Redis Durum",["redis durumu","redis server kontrol"],komut="redis-cli ping 2>/dev/null || echo 'Redis çalışmıyor'",os_=HedefOS.LINUX)
        ekle("Geliştirme","PostgreSQL Bağlan",["postgresql bağlan","psql aç","postgres konsol"],komut="psql -U postgres 2>/dev/null || echo 'PostgreSQL bağlantısı kurulamadı'",os_=HedefOS.LINUX)
        ekle("Geliştirme","MySQL Durum",["mysql durumu","mysql bağlantı kontrol"],komut="mysqladmin -u root ping 2>/dev/null || echo 'MySQL çalışmıyor'",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / SİSTEM YÖNETİMİ GENİŞLETİLMİŞ
        # ════════════════════════════════════════════════════════════════════
        ekle("SistemYönetim","Servis Listesi",["servis listesi","çalışan servisler","systemd aktif"],komut="systemctl list-units --type=service --state=running 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Başarısız Servisler",["başarısız servisler","failed services"],komut="systemctl --failed 2>/dev/null",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Sistem Journalı",["journal log","journalctl","system log"],komut="journalctl -n 30 --no-pager 2>/dev/null | tail -20",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Kernel Versiyonu",["kernel versiyonu","çekirdek sürüm","uname r"],komut="uname -r",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Sistem Çalışma Süresi",["sistem ne kadar açık","uptime süre","sistem uptime"],komut="uptime -p 2>/dev/null || uptime",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Aktif Kullanıcılar",["aktif kullanıcılar","who komutu","kim giriş yapmış"],komut="who",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Son Girişler",["son giriş kayıtları","last login","giriş geçmişi"],komut="last -n 10 2>/dev/null",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Görev Monitörü",["görev monitörü aç","gnome system monitor","sistem monitörü aç"],komut="gnome-system-monitor &",os_=HedefOS.LINUX)
        ekle("SistemYönetim","GNOME Ayarları",["gnome ayarları aç","sistem ayarları","gnome control center"],komut="gnome-control-center &",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Yazılım Merkezi",["yazılım merkezi aç","gnome software","uygulama yöneticisi aç"],komut="gnome-software &",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Snap Listesi",["snap paketleri listele","snap list"],komut="snap list 2>/dev/null || echo 'Snap kurulu değil'",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Flatpak Listesi",["flatpak uygulamalar","flatpak list"],komut="flatpak list 2>/dev/null || echo 'Flatpak kurulu değil'",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Donanım Bilgisi",["donanım bilgisi","hardware info","sistem donanımı"],komut="lshw -short 2>/dev/null | head -20 || inxi -b 2>/dev/null | head -15",os_=HedefOS.LINUX)
        ekle("SistemYönetim","PCI Aygıtlar",["pci aygıtları","lspci listesi","donanım listesi"],komut="lspci 2>/dev/null | head -15",os_=HedefOS.LINUX)
        ekle("SistemYönetim","USB Aygıtlar",["usb aygıtları","lsusb","bağlı usb cihazlar"],komut="lsusb 2>/dev/null",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Ekran Kartı Bilgisi",["ekran kartı bilgisi","gpu bilgisi","nvidia bilgisi"],komut="lspci | grep -i vga 2>/dev/null; nvidia-smi 2>/dev/null | head -10 || echo 'NVIDIA sürücü yok'",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Ortam Değişkenleri",["ortam değişkenleri","env listele","environment vars"],komut="env | sort | head -20",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Disk Boyutu Klasör",["en büyük klasörler","disk hangi klasör","du büyük"],komut="du -sh /* 2>/dev/null | sort -rh | head -10",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Mount Listesi",["bağlı dosya sistemleri","mount listesi","df dosya sistemi"],komut="mount | grep -v 'type tmpfs\\|type cgroup\\|type proc\\|type sysfs' | head -10",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Kullanıcı Listesi",["sistem kullanıcıları listele","yerel kullanıcılar","cat passwd"],komut="cut -d: -f1 /etc/passwd | head -20",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Grup Listesi",["grupları listele","cat group","kullanıcı grupları"],komut="cut -d: -f1 /etc/group | head -20",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Kullanıcı Ekle",["yeni kullanıcı ekle","adduser","useradd"],yanit="sudo adduser kullanici_adi komutuyla yeni kullanıcı ekleyebilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Sudo Yetkisi Ver",["kullanıcıya sudo yetkisi ver","usermod sudo"],yanit="sudo usermod -aG sudo kullanici_adi komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Cron Listesi",["cron listesi","zamanlanmış görevler","crontab -l"],komut="crontab -l 2>/dev/null || echo 'Cron görevi yok'",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Cron Düzenle",["cron görevi ekle","crontab düzenle","crontab e"],yanit="crontab -e komutuyla cron görevlerini düzenleyebilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("SistemYönetim","At Komutu",["zamanlanmış tek seferlik görev","at komutu","at job"],yanit="echo 'komut' | at SAAT komutunu kullanın. Örnek: at 15:30",tur="konusma",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Servis Aktif Et",["servisi otomatik başlat","systemctl enable"],yanit="sudo systemctl enable servis_adi komutuyla otomatik başlatmayı aktif edin.",tur="konusma",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Servis Devre Dışı",["servisi devre dışı bırak","systemctl disable"],yanit="sudo systemctl disable servis_adi komutuyla otomatik başlatmayı kapatın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("SistemYönetim","Sistem Mimarisi",["sistem mimarisi","cpu mimarisi","uname m"],komut="uname -m && uname -o",os_=HedefOS.LINUX)
        ekle("SistemYönetim","IRQ Listesi",["irq listesi","kesme vektörleri"],komut="cat /proc/interrupts 2>/dev/null | head -15",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / AĞ ARAÇLARI GENİŞLETİLMİŞ
        # ════════════════════════════════════════════════════════════════════
        ekle("AğAraçları","WiFi Tarama",["wifi ağlarını tara","yakındaki wifi","nmcli wifi list"],komut="nmcli dev wifi list 2>/dev/null | head -15",os_=HedefOS.LINUX)
        ekle("AğAraçları","WiFi Bağlan",["wifi ağına bağlan","nmcli wifi connect"],yanit="nmcli dev wifi connect 'SSID' password 'şifre' komutuyla bağlanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("AğAraçları","Ağ Arayüzleri",["ağ arayüzleri listesi","ip link show","network interfaces"],komut="ip link show 2>/dev/null | grep -E '^[0-9]+:' | awk '{print $2}'",os_=HedefOS.LINUX)
        ekle("AğAraçları","Ping Test",["ping testi","internet ping","google ping at"],komut="ping -c 4 8.8.8.8 2>/dev/null",os_=HedefOS.LINUX)
        ekle("AğAraçları","Traceroute",["traceroute yap","paket yolu izle"],komut="traceroute -m 10 8.8.8.8 2>/dev/null || tracepath 8.8.8.8 2>/dev/null | head -15",os_=HedefOS.LINUX)
        ekle("AğAraçları","Açık Portlar",["açık portları göster","port listesi","ss portlar"],komut="ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("AğAraçları","Ağ Trafiği",["ağ trafiği anlık","network bandwidth","ağ hız"],komut="cat /proc/net/dev 2>/dev/null | grep -v lo | awk 'NR>2{print $1, \"RX:\", int($2/1024/1024)\"MB\", \"TX:\", int($10/1024/1024)\"MB\"}'",os_=HedefOS.LINUX)
        ekle("AğAraçları","DNS Sorgula",["dns sorgula","nslookup","dig komutu"],komut="nslookup google.com 2>/dev/null | head -6 || dig google.com +short 2>/dev/null",os_=HedefOS.LINUX)
        ekle("AğAraçları","ARP Tablosu",["arp tablosu","yerel ağ cihazları","arp -a"],komut="arp -a 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("AğAraçları","Route Tablosu",["yönlendirme tablosu","ip route show"],komut="ip route show 2>/dev/null",os_=HedefOS.LINUX)
        ekle("AğAraçları","Hosts Dosyası",["hosts dosyası","etc hosts","hostname eşleşmeleri"],komut="cat /etc/hosts 2>/dev/null",os_=HedefOS.LINUX)
        ekle("AğAraçları","DNS Sunucu",["dns sunucusu","resolv conf","nameserver nedir"],komut="cat /etc/resolv.conf 2>/dev/null",os_=HedefOS.LINUX)
        ekle("AğAraçları","Aktif Bağlantılar",["aktif tcp bağlantıları","ss established","bağlı hostlar"],komut="ss -tnp state established 2>/dev/null | head -15",os_=HedefOS.LINUX)
        ekle("AğAraçları","Ağ Gecikme",["ağ gecikme testi","ping gecikme","latency ms"],komut="ping -c 5 8.8.8.8 2>/dev/null | tail -2",os_=HedefOS.LINUX)
        ekle("AğAraçları","IP Konum",["dış ip konumu","ip geolocation","ip nereden gelir"],komut="curl -s https://ipinfo.io/json 2>/dev/null | python3 -c \"import json,sys; d=json.load(sys.stdin); print(d.get('ip','?'), d.get('city','?'), d.get('country','?'))\" 2>/dev/null || echo 'Bağlantı kurulamadı'",os_=HedefOS.LINUX)
        ekle("AğAraçları","Network Manager Restart",["network manager yeniden başlat","wifi servisi yenile"],komut="sudo systemctl restart NetworkManager 2>/dev/null && echo 'Network Manager yeniden başlatıldı'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("AğAraçları","Ağ İstatistikleri",["ağ istatistikleri","ss summary","network stats"],komut="ss -s 2>/dev/null",os_=HedefOS.LINUX)
        ekle("AğAraçları","Curl Test",["curl ile test et","http request test","url içeriği"],yanit="curl -I URL ile HTTP başlıklarını, curl URL ile içeriği alabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("AğAraçları","Wget İndir",["wget ile indir","dosya indir terminal","wget download"],yanit="wget URL komutuyla dosyayı indirebilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("AğAraçları","MTU Boyutu",["mtu boyutu","ağ paket boyutu"],komut="ip link show 2>/dev/null | grep mtu",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / GÜVENLİK GENİŞLETİLMİŞ
        # ════════════════════════════════════════════════════════════════════
        ekle("GüvenlikAraç","Güvenlik Duvarı Durum",["güvenlik duvarı durumu","ufw status","firewall durum"],komut="sudo ufw status verbose 2>/dev/null || iptables -L -n 2>/dev/null | head -20",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Güvenlik Duvarı Aç",["güvenlik duvarını aç","ufw enable","firewall aktif"],komut="sudo ufw enable 2>/dev/null && echo 'Güvenlik duvarı açıldı'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Güvenlik Duvarı Kapat",["güvenlik duvarını kapat","ufw disable","firewall kapat"],komut="sudo ufw disable 2>/dev/null && echo 'Güvenlik duvarı kapatıldı'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Port İzin Ver",["porta izin ver güvenlik duvarı","ufw allow port"],yanit="sudo ufw allow PORT_NO komutuyla port açabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","SSH Anahtar Oluştur",["ssh anahtarı oluştur","generate ssh key","ssh keygen"],komut="ssh-keygen -t ed25519 -C \"$(whoami)@$(hostname)\" -N '' -f ~/.ssh/id_ed25519 2>/dev/null && echo 'Anahtar: ~/.ssh/id_ed25519.pub'",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","SSH Genel Anahtar",["ssh public key göster","ssh anahtarını göster"],komut="cat ~/.ssh/id_ed25519.pub 2>/dev/null || cat ~/.ssh/id_rsa.pub 2>/dev/null || echo 'SSH anahtarı bulunamadı'",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","GPG Anahtarları",["gpg anahtarları listele","gpg list keys"],komut="gpg --list-keys 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Güçlü Şifre",["güçlü şifre oluştur","random password","şifre üret güvenli"],komut="python3 -c \"import secrets; print(secrets.token_urlsafe(16))\"",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Nmap Tarama",["nmap port tarama","yerel port tara","nmap localhost"],komut="nmap -sT localhost 2>/dev/null | head -20 || ss -tlnp 2>/dev/null",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Sudo Yetkileri",["sudo yetkileri göster","sudoers liste","sudo -l"],komut="sudo -l 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","SUID Dosyaları",["suid dosyaları bul","setuid binary","suid tarama"],komut="find /usr -perm -4000 -type f 2>/dev/null | head -15",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Fail2ban Durum",["fail2ban durumu","brute force engel","başarısız giriş"],komut="sudo fail2ban-client status 2>/dev/null || echo 'Fail2ban kurulu değil'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Antivirus Tarama",["antivirus tara","clamav tarama","virüs tara"],komut="clamscan --quick ~ 2>/dev/null | tail -5 || echo 'ClamAV kurulu değil'",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Dosya Hash",["dosya hash hesapla","sha256 hesapla","md5 kontrol"],yanit="sha256sum dosya veya md5sum dosya komutlarını kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","SSL Sertifika",["ssl sertifika kontrol","tls sertifikası","openssl check"],yanit="openssl s_client -connect site.com:443 </dev/null 2>/dev/null | openssl x509 -noout -dates",tur="konusma",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Şifreli Arşiv",["şifreli zip oluştur","encrypted archive","gpg şifrele"],yanit="gpg -c dosya veya zip -e arsiv.zip dosyalar ile şifreli arşiv oluşturun.",tur="konusma",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","MAC Değiştir",["mac adresini değiştir","macchanger kullan"],yanit="sudo macchanger -r ARAYUZ komutuyla rastgele MAC atayabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Açık Dosyalar",["açık dosyalar lsof","hangi dosyalar açık"],komut="lsof 2>/dev/null | wc -l | xargs echo 'Açık dosya:'",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Denetim Logu",["audit log","sistem denetim log","auditd"],komut="journalctl -u auditd --no-pager -n 20 2>/dev/null || echo 'auditd çalışmıyor'",os_=HedefOS.LINUX)
        ekle("GüvenlikAraç","Çekirdek Güvenlik",["apparmor durumu","selinux durum","linux güvenlik modülü"],komut="apparmor_status 2>/dev/null | head -5 || sestatus 2>/dev/null | head -5 || echo 'Güvenlik modülü bilgisi alınamadı'",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / ERİŞİLEBİLİRLİK
        # ════════════════════════════════════════════════════════════════════
        ekle("Erişilebilirlik","Ekran Okuyucu Aç",["ekran okuyucu aç","orca başlat","screen reader"],komut="orca &",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Ekran Okuyucu Kapat",["ekran okuyucu kapat","orca durdur"],komut="pkill orca 2>/dev/null; echo 'Ekran okuyucu kapatıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Yüksek Kontrast Aç",["yüksek kontrast aç","high contrast tema"],komut="gsettings set org.gnome.desktop.interface gtk-theme HighContrast 2>/dev/null && echo 'Yüksek kontrast açıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Yüksek Kontrast Kapat",["yüksek kontrast kapat","normal temaya dön"],komut="gsettings set org.gnome.desktop.interface gtk-theme Adwaita 2>/dev/null && echo 'Normal tema geri yüklendi'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Yazı Büyüt",["yazı tipi büyüt","font büyüklüğü artır","erişilebilirlik font büyüt"],komut="gsettings set org.gnome.desktop.interface text-scaling-factor 1.5 2>/dev/null && echo 'Yazı büyütüldü'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Yazı Normal",["yazı tipi normal boyut","font sıfırla"],komut="gsettings set org.gnome.desktop.interface text-scaling-factor 1.0 2>/dev/null && echo 'Yazı boyutu sıfırlandı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Büyüteç Aç",["büyüteç aç","screen magnifier","ekran büyüteç"],komut="gsettings set org.gnome.desktop.a11y.applications screen-magnifier-enabled true 2>/dev/null && echo 'Büyüteç açıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Büyüteç Kapat",["büyüteç kapat","magnifier kapat"],komut="gsettings set org.gnome.desktop.a11y.applications screen-magnifier-enabled false 2>/dev/null && echo 'Büyüteç kapatıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Yapışkan Tuşlar",["yapışkan tuşlar aç","sticky keys aç"],komut="gsettings set org.gnome.desktop.a11y.keyboard stickykeys-enable true 2>/dev/null && echo 'Yapışkan tuşlar açıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Animasyonları Kapat",["sistem animasyonları kapat","gnome animasyon kapat"],komut="gsettings set org.gnome.desktop.interface enable-animations false 2>/dev/null && echo 'Animasyonlar kapatıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Animasyonları Aç",["sistem animasyonları aç","gnome animasyon aç"],komut="gsettings set org.gnome.desktop.interface enable-animations true 2>/dev/null && echo 'Animasyonlar açıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","İmleç Büyüt",["imleci büyüt","cursor büyük yap"],komut="gsettings set org.gnome.desktop.interface cursor-size 48 2>/dev/null && echo 'İmleç büyütüldü'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","İmleç Normal",["imleci normalleştir","cursor normal boyut"],komut="gsettings set org.gnome.desktop.interface cursor-size 24 2>/dev/null && echo 'İmleç sıfırlandı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Ekran Klavyesi",["ekran klavyesi aç","sanal klavye aç","onscreen keyboard"],komut="onboard &",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Koyu Tema",["koyu temaya geç","dark mode aç","dark theme gnome"],komut="gsettings set org.gnome.desktop.interface color-scheme prefer-dark 2>/dev/null; gsettings set org.gnome.desktop.interface gtk-theme Adwaita-dark 2>/dev/null && echo 'Koyu tema açıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Açık Tema",["açık temaya geç","light mode aç","normal tema"],komut="gsettings set org.gnome.desktop.interface color-scheme prefer-light 2>/dev/null; gsettings set org.gnome.desktop.interface gtk-theme Adwaita 2>/dev/null && echo 'Açık tema açıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Touchpad Aç",["dokunmatik yüzey aç","touchpad enable"],komut="gsettings set org.gnome.desktop.peripherals.touchpad send-events enabled 2>/dev/null && echo 'Touchpad açıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Touchpad Kapat",["dokunmatik yüzey kapat","touchpad disable"],komut="gsettings set org.gnome.desktop.peripherals.touchpad send-events disabled 2>/dev/null && echo 'Touchpad kapatıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Otomatik Kilit Kapat",["otomatik ekran kilidi kapat","screen lock kapat","auto lock kapat"],komut="gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null && echo 'Otomatik kilit kapatıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Ekran Zaman Aşımı Kapat",["ekran kapanma süresi kapat","monitor timeout kapat","ekran açık kalsın"],komut="gsettings set org.gnome.settings-daemon.plugins.power idle-dim false 2>/dev/null; xset s off 2>/dev/null; xset -dpms 2>/dev/null && echo 'Ekran zaman aşımı kapatıldı'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Erişilebilirlik Ayarları",["erişilebilirlik ayarları aç","a11y settings","universal access"],komut="gnome-control-center universal-access &",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Zil Sesi Kapat",["sistem zil sesini kapat","bell kapat","beep kapat"],komut="gsettings set org.gnome.desktop.wm.preferences audible-bell false 2>/dev/null && echo 'Zil sesi kapatıldı'",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / PAKET YÖNETİMİ GENİŞLETİLMİŞ
        # ════════════════════════════════════════════════════════════════════
        ekle("PaketYönetim","APT Güncelle",["apt güncelle","paket listesi güncelle","apt update"],komut="sudo apt update 2>/dev/null && echo 'Paket listesi güncellendi'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Yükselt",["sistem güncelle apt","apt upgrade","tüm paketleri güncelle"],komut="sudo apt upgrade -y 2>/dev/null && echo 'Sistem güncellendi'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Ara",["apt paket ara","apt search","paket bul"],yanit="apt search paket_adi komutuyla arama yapabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Kur",["apt ile kur","paket yükle apt","apt install"],yanit="sudo apt install paket_adi komutuyla kurabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Kaldır",["apt ile kaldır","paket sil apt","apt remove"],yanit="sudo apt remove paket_adi veya sudo apt purge paket_adi komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Otomatik Temizle",["kullanılmayan paketleri temizle","apt autoremove","apt clean"],komut="sudo apt autoremove -y 2>/dev/null && sudo apt clean 2>/dev/null && echo 'Temizlendi'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Yükseltilecekler",["yükseltilecek paketler","apt list upgradable","güncellenecek paket"],komut="apt list --upgradable 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Kur",["snap ile kur","snap install","snap yükle"],yanit="sudo snap install paket_adi komutuyla kurabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Güncelle",["snap paketleri güncelle","snap refresh"],komut="sudo snap refresh 2>/dev/null && echo 'Snap güncellendi'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Kaldır",["snap paketi kaldır","snap remove"],yanit="sudo snap remove paket_adi komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Kur",["flatpak ile kur","flatpak install"],yanit="flatpak install flathub uygulama_adi komutuyla kurabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Güncelle",["flatpak güncelle","flatpak update"],komut="flatpak update -y 2>/dev/null && echo 'Flatpak güncellendi'",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Kaldır",["flatpak kaldır","flatpak remove"],yanit="flatpak remove uygulama_adi komutunu kullanın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Paket Bilgisi",["paket bilgisi apt","apt show","paket detayları"],yanit="apt show paket_adi komutuyla bilgi alabilirsiniz.",tur="konusma",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Kurulu Paketler",["kurulu paketler listele","dpkg list","yüklü paketler"],komut="dpkg -l 2>/dev/null | grep '^ii' | head -20",os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # BATCH-2 / GNOME MASAÜSTÜ ÖZELLEŞTİRME
        # ════════════════════════════════════════════════════════════════════
        ekle("GNOMEÖzelleştir","Dock Konum Sol",["dock'u sola taşı","taskbar sol","görev çubuğu sola"],komut="gsettings set org.gnome.shell.extensions.dash-to-dock dock-position LEFT 2>/dev/null && echo 'Dock sola taşındı'",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Dock Konum Alt",["dock'u alta taşı","taskbar alt","görev çubuğu alta"],komut="gsettings set org.gnome.shell.extensions.dash-to-dock dock-position BOTTOM 2>/dev/null && echo 'Dock alta taşındı'",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Dock Otogizle",["dock otomatik gizle","auto hide dock","taskbar gizle"],komut="gsettings set org.gnome.shell.extensions.dash-to-dock autohide true 2>/dev/null && echo 'Dock otogizle açıldı'",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Duvar Kağıdı Değiştir",["duvar kağıdını değiştir","masaüstü arka plan","wallpaper değiştir"],komut="gnome-control-center background &",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","GNOME Uzantılar",["gnome uzantıları aç","extensions manager","gnome-extensions"],komut="gnome-extensions-app &",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","GNOME Tweak",["gnome tweak aç","gnome ayar aracı","gnome-tweaks"],komut="gnome-tweaks &",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Saat Formatı",["saati 24 saat yap","24h format","saat formatı değiştir"],komut="gsettings set org.gnome.desktop.interface clock-format 24h 2>/dev/null && echo 'Saat 24h formatına alındı'",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Pil Yüzdesi Göster",["pil yüzdesini göster","battery percentage","batarya yüzde"],komut="gsettings set org.gnome.desktop.interface show-battery-percentage true 2>/dev/null && echo 'Pil yüzdesi gösterilecek'",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Ekran Çözünürlüğü",["ekran çözünürlüğü ayarla","monitor resolution","xrandr çözünürlük"],komut="xrandr 2>/dev/null | grep '*' | head -5",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Çoklu Monitör",["çoklu monitör ayarı","display settings","xrandr çoklu ekran"],komut="gnome-control-center display &",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Klavye Kısayol Ayarla",["klavye kısayolları","keyboard shortcuts","gnome kısayol ayarla"],komut="gnome-control-center keyboard &",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Fare Ayarları",["fare ayarları","mouse settings","dokunmatik ayarları"],komut="gnome-control-center mouse &",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Ses Ayarları GNOME",["gnome ses ayarları","sound settings","hoparlör ayarları"],komut="gnome-control-center sound &",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Yazı Tipi Ayarı",["yazı tipi ayarla","font settings","sistem fontu değiştir"],komut="gnome-tweaks &",os_=HedefOS.LINUX)
        ekle("GNOMEÖzelleştir","Başlangıç Uygulamaları",["başlangıç uygulamaları","startup applications","gnome otomatik başlatma"],komut="gnome-session-properties &",os_=HedefOS.LINUX)

        # ── Batch-3: Git Detaylı ──────────────────────────────────────────
        ekle("Git","Git Durumu",["git durumu","git status","git ne değişti"],komut="git status",os_=HedefOS.LINUX)
        ekle("Git","Git Log",["git log","git geçmişi","commit geçmişi"],komut="git log --oneline -20",os_=HedefOS.LINUX)
        ekle("Git","Git Log Detaylı",["git log detaylı","git log graph","git dal grafiği"],komut="git log --oneline --graph --all -30",os_=HedefOS.LINUX)
        ekle("Git","Git Diff",["git diff","git fark","değişiklikleri göster"],komut="git diff",os_=HedefOS.LINUX)
        ekle("Git","Git Staged Diff",["git staged diff","git hazır fark","index farkı"],komut="git diff --staged",os_=HedefOS.LINUX)
        ekle("Git","Git Add All",["git add all","git hepsini ekle","git tümünü hazırla"],komut="git add -A",os_=HedefOS.LINUX)
        ekle("Git","Git Commit",["git commit","değişiklikleri kaydet","commit yap"],komut='git commit -m "$(date +\"%Y-%m-%d %H:%M:%S\")"',os_=HedefOS.LINUX)
        ekle("Git","Git Push",["git push","git yükle","uzaktaki repoya gönder"],komut="git push",os_=HedefOS.LINUX)
        ekle("Git","Git Pull",["git pull","git çek","uzaktan güncelle"],komut="git pull",os_=HedefOS.LINUX)
        ekle("Git","Git Fetch",["git fetch","git getir","uzak değişimleri getir"],komut="git fetch --all",os_=HedefOS.LINUX)
        ekle("Git","Git Branch Listesi",["git branch listesi","git dalları","hangi dallar var"],komut="git branch -a",os_=HedefOS.LINUX)
        ekle("Git","Git Yeni Branch",["git yeni dal","git branch oluştur","yeni branch aç"],komut="git checkout -b yeni-dal",os_=HedefOS.LINUX)
        ekle("Git","Git Dal Değiştir",["git dal değiştir","git checkout","başka dala geç"],komut="git checkout main",os_=HedefOS.LINUX)
        ekle("Git","Git Merge",["git merge","git birleştir","dalı birleştir"],komut="git merge --no-ff",os_=HedefOS.LINUX)
        ekle("Git","Git Rebase",["git rebase","git yeniden tabanlı","commit'leri düzenle"],komut="git rebase -i HEAD~5",os_=HedefOS.LINUX)
        ekle("Git","Git Stash",["git stash","git geçici kaydet","değişiklikleri sakla"],komut="git stash",os_=HedefOS.LINUX)
        ekle("Git","Git Stash Pop",["git stash pop","git saklananı geri al","stash geri yükle"],komut="git stash pop",os_=HedefOS.LINUX)
        ekle("Git","Git Stash Listesi",["git stash listesi","saklananları göster","git stash list"],komut="git stash list",os_=HedefOS.LINUX)
        ekle("Git","Git Tag",["git tag","git etiket","sürüm etiketi"],komut="git tag -l",os_=HedefOS.LINUX)
        ekle("Git","Git Yeni Tag",["git yeni tag","git etiket oluştur","sürüm etiketi ekle"],komut='git tag -a v1.0 -m "v1.0"',os_=HedefOS.LINUX)
        ekle("Git","Git Clone",["git clone","depoyu klonla","repo kopyala"],komut="git clone",os_=HedefOS.LINUX)
        ekle("Git","Git Remote Listesi",["git remote","uzak depo listesi","git remote list"],komut="git remote -v",os_=HedefOS.LINUX)
        ekle("Git","Git Remote Ekle",["git remote ekle","uzak depo ekle","origin ekle"],komut='git remote add origin ""',os_=HedefOS.LINUX)
        ekle("Git","Git Reset Soft",["git reset soft","son commiti geri al","commit'i geri al"],komut="git reset --soft HEAD~1",os_=HedefOS.LINUX)
        ekle("Git","Git Reset Hard",["git reset hard","tüm değişiklikleri geri al","çalışmayı sil"],komut="git reset --hard HEAD",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Git","Git Clean",["git clean","izlenmeyen dosyaları sil","git temizle"],komut="git clean -fd",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Git","Git Blame",["git blame","satırı kim yazdı","değişikliği kim yaptı"],komut="git blame",os_=HedefOS.LINUX)
        ekle("Git","Git Bisect",["git bisect","git ikili arama","hatalı commit bul"],komut="git bisect start",os_=HedefOS.LINUX)
        ekle("Git","Git Shortlog",["git shortlog","katkıcı özeti","kim ne kadar commit yaptı"],komut="git shortlog -sn",os_=HedefOS.LINUX)
        ekle("Git","Git Patch",["git patch oluştur","diff dosyası kaydet","patch al"],komut="git diff > degisiklik.patch",os_=HedefOS.LINUX)

        # ── Batch-3: Python / pip ─────────────────────────────────────────
        ekle("Python","Python Versiyonu",["python versiyonu","python version","hangi python"],komut="python3 --version",os_=HedefOS.LINUX)
        ekle("Python","Python Çalıştır",["python çalıştır","python dosya çalıştır","py dosya aç"],komut="python3",os_=HedefOS.LINUX)
        ekle("Python","Python Shell",["python shell","python konsolu","interaktif python"],komut="python3 -i",os_=HedefOS.LINUX)
        ekle("Python","pip Listesi",["pip listesi","pip paketler","kurulu paketler"],komut="pip3 list",os_=HedefOS.LINUX)
        ekle("Python","pip Güncelle",["pip güncelle","pip update","pip yükselt"],komut="pip3 install --upgrade pip",os_=HedefOS.LINUX)
        ekle("Python","pip Paket Kur",["pip kur","pip install","paket yükle"],komut="pip3 install",os_=HedefOS.LINUX)
        ekle("Python","pip Paket Kaldır",["pip kaldır","pip uninstall","paket sil"],komut="pip3 uninstall -y",os_=HedefOS.LINUX)
        ekle("Python","pip Freeze",["pip freeze","gereksinimleri dışa aktar","requirements kaydet"],komut="pip3 freeze > requirements.txt",os_=HedefOS.LINUX)
        ekle("Python","pip Gereksinimler Kur",["requirements kur","pip requirements","gereksinimleri yükle"],komut="pip3 install -r requirements.txt",os_=HedefOS.LINUX)
        ekle("Python","pip Güncelleme Listesi",["pip güncel değil","pip outdated","güncellenecek paketler"],komut="pip3 list --outdated",os_=HedefOS.LINUX)
        ekle("Python","pip Paket Ara",["pip ara","pip search","paket ara pip"],komut="pip3 index versions",os_=HedefOS.LINUX)
        ekle("Python","Sanal Ortam Oluştur",["sanal ortam oluştur","venv oluştur","virtualenv kur"],komut="python3 -m venv venv",os_=HedefOS.LINUX)
        ekle("Python","Sanal Ortam Aktif Et",["sanal ortam aktifleştir","venv aktif","virtualenv aktifleştir"],komut="source venv/bin/activate",os_=HedefOS.LINUX)
        ekle("Python","Sanal Ortam Kapat",["sanal ortam kapat","venv kapat","deactivate"],komut="deactivate",os_=HedefOS.LINUX)
        ekle("Python","Python Lint",["python lint","flake8 çalıştır","kod kontrol python"],komut="flake8 .",os_=HedefOS.LINUX)
        ekle("Python","Python Format",["python formatla","black çalıştır","kodu otomatik düzenle"],komut="black .",os_=HedefOS.LINUX)
        ekle("Python","Python Test",["python test","pytest çalıştır","testleri çalıştır"],komut="pytest -v",os_=HedefOS.LINUX)
        ekle("Python","Python Test Coverage",["test kapsam","pytest coverage","kod kapsama testi"],komut="pytest --cov=. --cov-report=html",os_=HedefOS.LINUX)
        ekle("Python","Python Derleme",["python derle","pyc oluştur","python bytecode"],komut="python3 -m compileall .",os_=HedefOS.LINUX)
        ekle("Python","Python Profil",["python profil","cProfile çalıştır","performans ölç python"],komut="python3 -m cProfile -s cumulative",os_=HedefOS.LINUX)

        # ── Batch-3: Node.js / npm ────────────────────────────────────────
        ekle("NodeJS","Node Versiyonu",["node versiyonu","node version","hangi node"],komut="node --version",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Versiyonu",["npm versiyonu","npm version","hangi npm"],komut="npm --version",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Paket Listesi",["npm listesi","npm paketler","node paketler"],komut="npm list",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Küresel Paketler",["npm global listesi","npm -g listesi","küresel node paketleri"],komut="npm list -g --depth=0",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Paket Kur",["npm kur","npm install","node paket yükle"],komut="npm install",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Dev Paket Kur",["npm dev kur","npm install dev","geliştirme bağımlılığı ekle"],komut="npm install --save-dev",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Paket Kaldır",["npm kaldır","npm uninstall","node paket sil"],komut="npm uninstall",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Güncelle",["npm güncelle","npm update","node paketleri güncelle"],komut="npm update",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Outdated",["npm güncel değil","npm outdated","güncellenecek paketler node"],komut="npm outdated",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Başlat",["npm başlat","npm start","node uygulaması başlat"],komut="npm start",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Build",["npm build","npm derleme","node derleme"],komut="npm run build",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Test",["npm test","npm testler","node testleri"],komut="npm test",os_=HedefOS.LINUX)
        ekle("NodeJS","npm Temizle",["npm cache temizle","npm cache clean","node cache sil"],komut="npm cache clean --force",os_=HedefOS.LINUX)
        ekle("NodeJS","npx Komutu",["npx çalıştır","npx komut","geçici paket çalıştır"],komut="npx",os_=HedefOS.LINUX)
        ekle("NodeJS","yarn Versiyonu",["yarn versiyonu","yarn version","hangi yarn"],komut="yarn --version",os_=HedefOS.LINUX)
        ekle("NodeJS","yarn Kur",["yarn kur","yarn install","yarn bağımlılıkları yükle"],komut="yarn install",os_=HedefOS.LINUX)
        ekle("NodeJS","yarn Başlat",["yarn başlat","yarn start","yarn uygulaması başlat"],komut="yarn start",os_=HedefOS.LINUX)
        ekle("NodeJS","yarn Build",["yarn build","yarn derleme","yarn derle"],komut="yarn build",os_=HedefOS.LINUX)
        ekle("NodeJS","nvm Listesi",["nvm listesi","nvm list","kurulu node versiyonları"],komut="nvm list",os_=HedefOS.LINUX)
        ekle("NodeJS","nvm Versiyon Yükle",["nvm install","node versiyonu kur","nvm yeni versiyon"],komut="nvm install --lts",os_=HedefOS.LINUX)

        # ── Batch-3: Jupyter Notebook ─────────────────────────────────────
        ekle("Jupyter","Jupyter Başlat",["jupyter başlat","jupyter notebook aç","notebook sunucu"],komut="jupyter notebook",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Lab Başlat",["jupyter lab başlat","jupyterlab aç","jupyter lab aç"],komut="jupyter lab",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Listesi",["jupyter listesi","çalışan jupyter","jupyter server list"],komut="jupyter server list",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Dönüştür HTML",["jupyter html dönüştür","notebook html","nbconvert html"],komut="jupyter nbconvert --to html",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Dönüştür PDF",["jupyter pdf dönüştür","notebook pdf","nbconvert pdf"],komut="jupyter nbconvert --to pdf",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Dönüştür Script",["jupyter script dönüştür","notebook py","nbconvert script"],komut="jupyter nbconvert --to script",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Kernel Listesi",["jupyter kernel listesi","mevcut kerneller","jupyter kernels"],komut="jupyter kernelspec list",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Kernel Ekle",["jupyter kernel ekle","ipykernel kur","venv kernel ekle"],komut="python3 -m ipykernel install --user --name=venv",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Çalıştır",["jupyter notebook çalıştır","notebook çalıştır","ipynb çalıştır"],komut="jupyter nbconvert --to notebook --execute",os_=HedefOS.LINUX)
        ekle("Jupyter","Jupyter Kapat",["jupyter kapat","notebook kapat","jupyter sunucu durdur"],komut="jupyter notebook stop",os_=HedefOS.LINUX)

        # ── Batch-3: Systemd Servis Yönetimi ──────────────────────────────
        ekle("Systemd","Servis Başlat",["servis başlat","service start","servisi çalıştır"],komut="sudo systemctl start",os_=HedefOS.LINUX)
        ekle("Systemd","Servis Durdur",["servis durdur","service stop","servisi kapat"],komut="sudo systemctl stop",os_=HedefOS.LINUX)
        ekle("Systemd","Servis Yeniden Başlat",["servis yeniden başlat","service restart","servisi resetle"],komut="sudo systemctl restart",os_=HedefOS.LINUX)
        ekle("Systemd","Servis Reload",["servis reload","service reload","servisi yenile"],komut="sudo systemctl reload",os_=HedefOS.LINUX)
        ekle("Systemd","Servis Durumu",["servis durumu","service status","servis çalışıyor mu"],komut="systemctl status",os_=HedefOS.LINUX)
        ekle("Systemd","Tüm Servisleri Listele",["tüm servisler","service list","aktif servisler"],komut="systemctl list-units --type=service",os_=HedefOS.LINUX)
        ekle("Systemd","Başlangıçta Aktif Et",["servis otomatik başlat","enable service","servis etkinleştir"],komut="sudo systemctl enable",os_=HedefOS.LINUX)
        ekle("Systemd","Başlangıçtan Kaldır",["servis otomatik başlatma kapat","disable service","servis devre dışı"],komut="sudo systemctl disable",os_=HedefOS.LINUX)
        ekle("Systemd","Başlangıç Servisleri",["başlangıçta ne çalışıyor","enabled services","otomatik başlayan servisler"],komut="systemctl list-unit-files --state=enabled",os_=HedefOS.LINUX)
        ekle("Systemd","Başarısız Servisler",["başarısız servisler","failed services","çalışmayan servisler"],komut="systemctl --failed",os_=HedefOS.LINUX)
        ekle("Systemd","Systemd Log",["systemd log","systemd günlük","servis logu"],komut="journalctl -xe",os_=HedefOS.LINUX)
        ekle("Systemd","Servis Log",["servis log","journalctl servis","belirli servis logu"],komut="journalctl -u",os_=HedefOS.LINUX)
        ekle("Systemd","Canlı Log",["canlı log izle","log stream","journalctl follow"],komut="journalctl -f",os_=HedefOS.LINUX)
        ekle("Systemd","Son 100 Log",["son loglar","son yüz satır log","journalctl son"],komut="journalctl -n 100",os_=HedefOS.LINUX)
        ekle("Systemd","Boot Log",["boot logu","önyükleme logu","sistemin açılış logu"],komut="journalctl -b",os_=HedefOS.LINUX)
        ekle("Systemd","Servis Dosyası Oluştur",["servis dosyası oluştur","yeni systemd unit","unit dosyası aç"],komut="sudo nano /etc/systemd/system/yeni.service",os_=HedefOS.LINUX)
        ekle("Systemd","Daemon Reload",["systemd daemon reload","unit dosyaları yenile","systemctl daemon-reload"],komut="sudo systemctl daemon-reload",os_=HedefOS.LINUX)
        ekle("Systemd","Timer Listesi",["systemd timer listesi","zamanlı görevler","timer units"],komut="systemctl list-timers",os_=HedefOS.LINUX)
        ekle("Systemd","Hedef Görüntüle",["systemd hedef","runlevel","default target"],komut="systemctl get-default",os_=HedefOS.LINUX)
        ekle("Systemd","Grafik Hedef",["grafik moduna geç","graphical target","masaüstü başlat"],komut="sudo systemctl set-default graphical.target",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ── Batch-3: Kullanıcı Yönetimi ───────────────────────────────────
        ekle("KullanıcıYönetim","Kullanıcı Listesi",["kullanıcı listesi","kullanıcıları göster","who is logged in"],komut="cut -d: -f1 /etc/passwd | sort",os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Giriş Yapanlar",["kim giriş yaptı","aktif kullanıcılar","who logged in"],komut="w",os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Mevcut Kullanıcı",["ben kimim","mevcut kullanıcı","şu anki kullanıcı"],komut="whoami",os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Kullanıcı Bilgisi",["kullanıcı bilgisi","id komutu","uid gid göster"],komut="id",os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Gruplar",["hangi gruplardayım","grup listesi","groups komutu"],komut="groups",os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Yeni Kullanıcı",["yeni kullanıcı ekle","kullanıcı oluştur","adduser"],komut="sudo adduser",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Kullanıcı Sil",["kullanıcı sil","kullanıcıyı kaldır","deluser"],komut="sudo deluser --remove-home",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Kullanıcı Gruba Ekle",["kullanıcıyı gruba ekle","usermod gruba ekle","sudo grubuna ekle"],komut="sudo usermod -aG sudo",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Şifre Değiştir",["şifre değiştir","parola güncelle","passwd komutu"],komut="passwd",os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Root Şifre",["root şifresi değiştir","sudo passwd root","root parola"],komut="sudo passwd root",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Hesabı Kilitle",["kullanıcıyı kilitle","hesabı devre dışı bırak","lock user"],komut="sudo passwd -l",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Hesabı Aç",["kullanıcıyı aç","hesabı etkinleştir","unlock user"],komut="sudo passwd -u",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Sudo Yetkisi",["sudo yetkisi ver","sudoers ekle","yönetici yap"],komut="sudo visudo",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Giriş Geçmişi",["giriş geçmişi","last komutu","kim ne zaman giriş yaptı"],komut="last -20",os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Başarısız Girişler",["başarısız giriş","lastb komutu","hatalı şifre girişleri"],komut="sudo lastb -20",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Yeni Grup Oluştur",["yeni grup oluştur","grup ekle","addgroup"],komut="sudo addgroup",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Grup Sil",["grubu sil","group kaldır","delgroup"],komut="sudo delgroup",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Kullanıcı Kabuk Değiştir",["varsayılan kabuk değiştir","shell değiştir","chsh komutu"],komut="chsh -s /bin/bash",os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Oturumu Sonlandır",["oturumu kapat","kullanıcıyı kick","pkill kullanıcı"],komut="sudo pkill -u",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("KullanıcıYönetim","Kullanıcı Ana Dizin",["kullanıcı ev dizini","home dizini göster","echo HOME"],komut="echo $HOME",os_=HedefOS.LINUX)

        # ── Batch-3: Disk ve Dosya Sistemi ────────────────────────────────
        ekle("DiskYönetim","Disk Kullanımı",["disk kullanımı","df -h","ne kadar disk var"],komut="df -h",os_=HedefOS.LINUX)
        ekle("DiskYönetim","Klasör Boyutu",["klasör boyutu","du -sh","dizin ne kadar yer kaplıyor"],komut="du -sh *",os_=HedefOS.LINUX)
        ekle("DiskYönetim","Büyük Dosyalar",["büyük dosyalar","en çok yer kaplayan","disk dolduran dosyalar"],komut="du -ah / 2>/dev/null | sort -rh | head -20",os_=HedefOS.LINUX)
        ekle("DiskYönetim","Disk Listesi",["disk listesi","blk listesi","bağlı diskler"],komut="lsblk",os_=HedefOS.LINUX)
        ekle("DiskYönetim","Disk Detayı",["disk detayı","fdisk listele","disk bilgisi"],komut="sudo fdisk -l",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","Bağlı Sistemler",["bağlı dosya sistemleri","mount listesi","mount noktaları"],komut="mount | column -t",os_=HedefOS.LINUX)
        ekle("DiskYönetim","Disk Bağla",["disk bağla","mount disk","harici diski bağla"],komut="sudo mount",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","Disk Ayır",["disk ayır","umount disk","harici diski ayır"],komut="sudo umount",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","Dosya Sistemi Kontrol",["disk kontrol","fsck çalıştır","bozuk disk onar"],komut="sudo fsck -n",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","Disk UUID",["disk uuid","blkid komutu","disk kimliği"],komut="blkid",os_=HedefOS.LINUX)
        ekle("DiskYönetim","fstab Düzenle",["fstab düzenle","disk otomatik bağ","mount tablosu"],komut="sudo nano /etc/fstab",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","Bölüm Oluştur",["yeni disk bölümü","bölüm oluştur","gdisk bölümle"],komut="sudo gdisk",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","Ext4 Biçimlendir",["ext4 formatla","ext4 biçimlendir","diski biçimlendir"],komut="sudo mkfs.ext4",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","NTFS Biçimlendir",["ntfs formatla","ntfs biçimlendir","windows disk formatla"],komut="sudo mkfs.ntfs",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","FAT32 Biçimlendir",["fat32 formatla","usb formatla","fat biçimlendir"],komut="sudo mkfs.vfat -F32",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","Disk Sağlık",["disk sağlığı","smartctl","disk ömrü"],komut="sudo smartctl -a /dev/sda",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","inode Kullanımı",["inode kullanımı","df inode","dosya sayısı sınırı"],komut="df -i",os_=HedefOS.LINUX)
        ekle("DiskYönetim","Swap Durumu",["swap durumu","swap alanı","sanal bellek"],komut="swapon --show",os_=HedefOS.LINUX)
        ekle("DiskYönetim","Swap Oluştur",["swap dosyası oluştur","swap ekle","sanal bellek ekle"],komut="sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DiskYönetim","ISO Yaz",["iso yaz","usb bootable yap","dd iso"],komut="sudo dd if=dosya.iso of=/dev/sdX bs=4M status=progress",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ── Batch-3: Cron / Zamanlayıcı ───────────────────────────────────
        ekle("Cron","Cron Listesi",["cron listesi","crontab listele","zamanlanmış görevler"],komut="crontab -l",os_=HedefOS.LINUX)
        ekle("Cron","Cron Düzenle",["cron düzenle","crontab düzenle","zamanlanmış görev ekle"],komut="crontab -e",os_=HedefOS.LINUX)
        ekle("Cron","Cron Sil",["cron sil","crontab temizle","tüm cronjobları sil"],komut="crontab -r",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Cron","Sistem Cron",["sistem cron","sistem cronjob","root zamanlanmış görevler"],komut="sudo crontab -l",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Cron","Cron Log",["cron logu","cron hatası","zamanlanmış görev logu"],komut="grep CRON /var/log/syslog | tail -20",os_=HedefOS.LINUX)
        ekle("Cron","At Komutu",["at komutu","tek seferlik görev","at zamanla"],komut="at now + 5 minutes",os_=HedefOS.LINUX)
        ekle("Cron","At Listesi",["at listesi","bekleyen at görevleri","atq komutu"],komut="atq",os_=HedefOS.LINUX)
        ekle("Cron","At İptal",["at iptal","görev sil at","atrm komutu"],komut="atrm",os_=HedefOS.LINUX)
        ekle("Cron","Her Dakika Çalıştır",["her dakika çalıştır","cron dakikada","1 dakikada bir"],yanit="Crontab formatı: * * * * * /path/to/script.sh",tur="konusma",os_=HedefOS.LINUX)
        ekle("Cron","Her Gün Çalıştır",["her gün çalıştır","günlük cron","sabah çalışsın"],yanit="Crontab formatı: 0 8 * * * /path/to/script.sh (her gün 08:00)",tur="konusma",os_=HedefOS.LINUX)
        ekle("Cron","Her Hafta Çalıştır",["her hafta çalıştır","haftalık cron","pazartesi çalışsın"],yanit="Crontab formatı: 0 9 * * 1 /path/to/script.sh (her Pazartesi 09:00)",tur="konusma",os_=HedefOS.LINUX)
        ekle("Cron","Anacron Çalıştır",["anacron çalıştır","kaçırılan görev çalıştır","anacron -n"],komut="sudo anacron -n",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ── Batch-3: SSH Anahtar Yönetimi ─────────────────────────────────
        ekle("SSHAnahtar","SSH Anahtar Oluştur",["ssh anahtar oluştur","ssh keygen","yeni ssh key"],komut="ssh-keygen -t ed25519 -C \"$(whoami)@$(hostname)\"",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH RSA Anahtar",["ssh rsa anahtar","rsa keygen","4096 bit ssh key"],komut="ssh-keygen -t rsa -b 4096",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Anahtar Listesi",["ssh anahtar listesi","mevcut ssh keyler","authorized keys"],komut="ls -la ~/.ssh/",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Public Key Göster",["public key göster","ssh pub key","id_ed25519.pub"],komut="cat ~/.ssh/id_ed25519.pub",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH RSA Public Key",["rsa public key göster","id_rsa.pub","ssh rsa pub"],komut="cat ~/.ssh/id_rsa.pub",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Yetkili Anahtarlar",["yetkili anahtarlar","authorized_keys","ssh yetkili listesi"],komut="cat ~/.ssh/authorized_keys",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Anahtar Ekle",["ssh anahtar ekle","authorized_keys ekle","ssh key yetkilendir"],komut="ssh-copy-id -i ~/.ssh/id_ed25519.pub",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Agent Başlat",["ssh agent başlat","ssh-agent","anahtar ajanı"],komut="eval $(ssh-agent -s)",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Agent Ekle",["ssh agent ekle","ssh-add","anahtar yükle agent"],komut="ssh-add ~/.ssh/id_ed25519",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Agent Listesi",["ssh agent listesi","yüklü anahtarlar","ssh-add -l"],komut="ssh-add -l",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Config Düzenle",["ssh config düzenle","ssh yapılandırma","~/.ssh/config"],komut="nano ~/.ssh/id_ed25519",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Bağlantı Test",["ssh bağlantı test","ssh github test","ssh ping"],komut="ssh -T git@github.com",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Known Hosts Temizle",["known hosts temizle","ssh host sil","eski ssh host kaldır"],komut="ssh-keygen -R",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH Tunnel Oluştur",["ssh tunnel","ssh tünel","port forward ssh"],komut="ssh -L 8080:localhost:80",os_=HedefOS.LINUX)
        ekle("SSHAnahtar","SSH SOCKS Proxy",["ssh proxy","ssh socks","ssh üzerinden proxy"],komut="ssh -D 1080 -N",os_=HedefOS.LINUX)

        # ── Batch-3: GPG Şifreleme ────────────────────────────────────────
        ekle("GPG","GPG Anahtar Oluştur",["gpg anahtar oluştur","gpg keygen","yeni gpg key"],komut="gpg --full-generate-key",os_=HedefOS.LINUX)
        ekle("GPG","GPG Anahtar Listesi",["gpg anahtar listesi","gpg anahtarlar","gpg keyring"],komut="gpg --list-keys",os_=HedefOS.LINUX)
        ekle("GPG","GPG Gizli Anahtarlar",["gpg gizli anahtarlar","gpg private keys","gpg secret keyring"],komut="gpg --list-secret-keys",os_=HedefOS.LINUX)
        ekle("GPG","GPG Dosya Şifrele",["gpg dosya şifrele","gpg encrypt","dosyayı şifrele gpg"],komut="gpg --encrypt --recipient",os_=HedefOS.LINUX)
        ekle("GPG","GPG Dosya Çöz",["gpg dosya çöz","gpg decrypt","şifreyi aç gpg"],komut="gpg --decrypt",os_=HedefOS.LINUX)
        ekle("GPG","GPG İmzala",["gpg imzala","dosyayı imzala","gpg sign"],komut="gpg --sign",os_=HedefOS.LINUX)
        ekle("GPG","GPG İmza Doğrula",["gpg imzayı doğrula","gpg verify","imza kontrol"],komut="gpg --verify",os_=HedefOS.LINUX)
        ekle("GPG","GPG Anahtar Dışa Aktar",["gpg anahtar dışa aktar","gpg export","public key çıkar"],komut="gpg --export --armor",os_=HedefOS.LINUX)
        ekle("GPG","GPG Anahtar İçe Al",["gpg anahtar içe al","gpg import","public key yükle"],komut="gpg --import",os_=HedefOS.LINUX)
        ekle("GPG","GPG Anahtar Sil",["gpg anahtar sil","gpg delete key","gpg anahtarı kaldır"],komut="gpg --delete-key",os_=HedefOS.LINUX)
        ekle("GPG","GPG Anahtar Sunucusu",["gpg keyserver","anahtar sunucusu gönder","gpg upload key"],komut="gpg --keyserver keyserver.ubuntu.com --send-keys",os_=HedefOS.LINUX)
        ekle("GPG","GPG Anahtar İndir",["gpg anahtar indir","keyserver ara","gpg search key"],komut="gpg --keyserver keyserver.ubuntu.com --search-keys",os_=HedefOS.LINUX)
        ekle("GPG","GPG Symmetric Şifrele",["simetrik şifrele","parola ile şifrele","gpg symmetric"],komut="gpg --symmetric",os_=HedefOS.LINUX)
        ekle("GPG","GPG Parola Yöneticisi",["gpg pass","gpg parola","pass komutu"],komut="pass",os_=HedefOS.LINUX)

        # ── Batch-3: Network Manager Detaylı ──────────────────────────────
        ekle("NetworkManager","WiFi Ağları Tara",["wifi ağları tara","nmcli wifi listesi","kablosuz ağlar"],komut="nmcli device wifi list",os_=HedefOS.LINUX)
        ekle("NetworkManager","WiFi Bağlan",["wifi bağlan","ağa bağlan","ssid bağlan"],komut="nmcli device wifi connect",os_=HedefOS.LINUX)
        ekle("NetworkManager","WiFi Şifre",["wifi şifresini göster","kayıtlı wifi şifresi","nmcli wifi şifre"],komut='nmcli -show-secrets connection show "$(nmcli -t -f NAME connection show --active | head -1)"',os_=HedefOS.LINUX)
        ekle("NetworkManager","Bağlantı Listesi",["nmcli bağlantı listesi","kayıtlı ağlar","network bağlantıları"],komut="nmcli connection show",os_=HedefOS.LINUX)
        ekle("NetworkManager","Aktif Bağlantı",["aktif bağlantı","şu an bağlı ağ","nmcli active"],komut="nmcli connection show --active",os_=HedefOS.LINUX)
        ekle("NetworkManager","Bağlantı Sil",["ağ bağlantısı sil","nmcli bağlantı kaldır","kayıtlı ağ sil"],komut="nmcli connection delete",os_=HedefOS.LINUX)
        ekle("NetworkManager","Bağlantıyı Kapat",["ağı kapat","bağlantıyı kapat","nmcli down"],komut="nmcli connection down",os_=HedefOS.LINUX)
        ekle("NetworkManager","Bağlantıyı Aç",["ağı aç","bağlantıyı başlat","nmcli up"],komut="nmcli connection up",os_=HedefOS.LINUX)
        ekle("NetworkManager","Arayüz Durumu",["ağ arayüzü durumu","nmcli device","network interface"],komut="nmcli device status",os_=HedefOS.LINUX)
        ekle("NetworkManager","Hotspot Oluştur",["hotspot oluştur","mobil hotspot","wifi paylaş"],komut='nmcli device wifi hotspot ifname wlan0 ssid "ZihinKoprusu" password "güçlüşifre123"',os_=HedefOS.LINUX)
        ekle("NetworkManager","DNS Sunucusu Değiştir",["dns değiştir","dns sunucu ayarla","nameserver güncelle"],komut="nmcli connection modify $(nmcli -t -f NAME connection show --active | head -1) ipv4.dns 1.1.1.1",os_=HedefOS.LINUX)
        ekle("NetworkManager","Statik IP",["statik ip ayarla","ip adresi sabitle","fixed ip"],komut="nmcli connection modify",os_=HedefOS.LINUX)
        ekle("NetworkManager","DHCP IP",["dhcp ip al","otomatik ip","dynamic ip"],komut="nmcli connection modify $(nmcli -t -f NAME connection show --active | head -1) ipv4.method auto",os_=HedefOS.LINUX)
        ekle("NetworkManager","Proxy Ayarla",["proxy ayarla","nmcli proxy","ağ proxy"],komut="gsettings set org.gnome.system.proxy mode 'manual'",os_=HedefOS.LINUX)
        ekle("NetworkManager","VPN Listesi",["vpn listesi","nmcli vpn","kayıtlı vpn"],komut="nmcli connection show | grep vpn",os_=HedefOS.LINUX)

        # ── Batch-3: iptables / Güvenlik Duvarı ───────────────────────────
        ekle("Firewall","UFW Durumu",["ufw durumu","firewall durumu","güvenlik duvarı aktif mi"],komut="sudo ufw status verbose",os_=HedefOS.LINUX)
        ekle("Firewall","UFW Etkinleştir",["ufw etkinleştir","firewall aç","güvenlik duvarını aktif et"],komut="sudo ufw enable",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","UFW Devre Dışı",["ufw kapat","firewall kapat","güvenlik duvarını kapat"],komut="sudo ufw disable",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","UFW Kural İzin Ver",["ufw port izin","bağlantıya izin ver","ufw allow"],komut="sudo ufw allow",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","UFW Kural Engelle",["ufw port engelle","bağlantıyı engelle","ufw deny"],komut="sudo ufw deny",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","UFW Kural Sil",["ufw kural sil","kuralı kaldır","ufw delete"],komut="sudo ufw delete",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","UFW SSH İzin",["ufw ssh izin","ssh portunu aç","22 portunu aç"],komut="sudo ufw allow 22/tcp",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","UFW HTTP İzin",["ufw http izin","80 portunu aç","web server izin"],komut="sudo ufw allow 80/tcp",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","UFW HTTPS İzin",["ufw https izin","443 portunu aç","ssl port aç"],komut="sudo ufw allow 443/tcp",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","iptables Listele",["iptables listele","iptables kuralları","firewall kuralları listesi"],komut="sudo iptables -L -n -v",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","iptables Sıfırla",["iptables sıfırla","firewall kurallarını sil","iptables flush"],komut="sudo iptables -F",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","iptables Kural Kaydet",["iptables kaydet","firewall kurallarını kaydet","iptables-save"],komut="sudo iptables-save > /etc/iptables/rules.v4",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Firewall","Port Tara",["port tara","açık portlar","nmap localhost"],komut="nmap -sT localhost",os_=HedefOS.LINUX)
        ekle("Firewall","Dinleyen Portlar",["dinleyen portlar","ss komutu","açık soketler"],komut="ss -tlnp",os_=HedefOS.LINUX)
        ekle("Firewall","Fail2ban Durumu",["fail2ban durumu","fail2ban status","brute force koruması"],komut="sudo fail2ban-client status",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ── Batch-3: Wireguard / OpenVPN ──────────────────────────────────
        ekle("VPN","WireGuard Başlat",["wireguard başlat","wg up","vpn aç wireguard"],komut="sudo wg-quick up wg0",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("VPN","WireGuard Durdur",["wireguard durdur","wg down","vpn kapat wireguard"],komut="sudo wg-quick down wg0",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("VPN","WireGuard Durumu",["wireguard durumu","wg show","vpn durumu wireguard"],komut="sudo wg show",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("VPN","OpenVPN Başlat",["openvpn başlat","openvpn bağlan","vpn aç openvpn"],komut="sudo openvpn --config client.ovpn",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("VPN","VPN IP Kontrol",["vpn ip kontrol","vpn ile ip ne","tunnel ip"],komut="curl -s ifconfig.me",os_=HedefOS.LINUX)
        ekle("VPN","ProtonVPN Bağlan",["protonvpn bağlan","proton vpn aç","proton en hızlı"],komut="protonvpn-cli connect --fastest",os_=HedefOS.LINUX)
        ekle("VPN","ProtonVPN Kes",["protonvpn kes","proton vpn kapat","protonvpn disconnect"],komut="protonvpn-cli disconnect",os_=HedefOS.LINUX)
        ekle("VPN","ProtonVPN Durumu",["protonvpn durumu","proton vpn status","protonvpn status"],komut="protonvpn-cli status",os_=HedefOS.LINUX)
        ekle("VPN","NordVPN Bağlan",["nordvpn bağlan","nord vpn aç","nordvpn connect"],komut="nordvpn connect",os_=HedefOS.LINUX)
        ekle("VPN","NordVPN Kes",["nordvpn kes","nord vpn kapat","nordvpn disconnect"],komut="nordvpn disconnect",os_=HedefOS.LINUX)

        # ── Batch-3: Android ADB Detaylı ──────────────────────────────────
        ekle("ADB","ADB Cihaz Listesi",["adb cihazlar","bağlı android cihazlar","adb devices"],komut="adb devices",os_=HedefOS.LINUX)
        ekle("ADB","ADB Bağlan Wi-Fi",["adb wifi bağlan","adb kablosuz","android wireless adb"],komut="adb connect 192.168.1.x:5555",os_=HedefOS.LINUX)
        ekle("ADB","ADB Kes",["adb kes","adb disconnect","android bağlantısını kes"],komut="adb disconnect",os_=HedefOS.LINUX)
        ekle("ADB","ADB Shell",["adb shell","android terminal","android konsolu adb"],komut="adb shell",os_=HedefOS.LINUX)
        ekle("ADB","ADB Dosya Gönder",["adb dosya gönder","android dosya kopyala","adb push"],komut="adb push",os_=HedefOS.LINUX)
        ekle("ADB","ADB Dosya Al",["adb dosya al","android dosya çek","adb pull"],komut="adb pull",os_=HedefOS.LINUX)
        ekle("ADB","ADB APK Kur",["adb apk kur","android uygulama yükle","adb install"],komut="adb install",os_=HedefOS.LINUX)
        ekle("ADB","ADB APK Kaldır",["adb apk kaldır","android uygulama sil","adb uninstall"],komut="adb uninstall",os_=HedefOS.LINUX)
        ekle("ADB","ADB Ekran Görüntüsü",["adb ekran görüntüsü","android screenshot","adb screencap"],komut='adb exec-out screencap -p > ekran_$(date +%s).png',os_=HedefOS.LINUX)
        ekle("ADB","ADB Ekran Kaydı",["adb ekran kaydı","android screenrecord","adb video kayıt"],komut="adb shell screenrecord /sdcard/video.mp4",os_=HedefOS.LINUX)
        ekle("ADB","ADB Log",["adb log","android logcat","android sistem logu"],komut="adb logcat",os_=HedefOS.LINUX)
        ekle("ADB","ADB Reboot",["adb yeniden başlat","android reboot adb","telefonu yeniden başlat"],komut="adb reboot",os_=HedefOS.LINUX)
        ekle("ADB","ADB Reboot Recovery",["adb recovery","android recovery modu","adb reboot recovery"],komut="adb reboot recovery",os_=HedefOS.LINUX)
        ekle("ADB","ADB Reboot Bootloader",["adb bootloader","android bootloader","fastboot modu"],komut="adb reboot bootloader",os_=HedefOS.LINUX)
        ekle("ADB","ADB TCP Modu Aç",["adb tcp modu","android adb port aç","tcpip 5555"],komut="adb tcpip 5555",os_=HedefOS.LINUX)
        ekle("ADB","ADB Pil Durumu",["android pil durumu","telefon batarya","adb battery"],komut="adb shell dumpsys battery",os_=HedefOS.LINUX)
        ekle("ADB","ADB Uygulama Listesi",["android uygulama listesi","adb package list","yüklü apklar"],komut="adb shell pm list packages -3",os_=HedefOS.LINUX)
        ekle("ADB","ADB Ekran Kilidi Aç",["adb ekran kilidi aç","android unlock","adb input keyevent"],komut="adb shell input keyevent 82",os_=HedefOS.LINUX)
        ekle("ADB","ADB Metin Gönder",["android metin gönder","adb text input","adb yazı yaz"],komut='adb shell input text ""',os_=HedefOS.LINUX)
        ekle("ADB","scrcpy Başlat",["scrcpy başlat","android ekran yansıt","telefon ekranını göster"],komut="scrcpy",os_=HedefOS.LINUX)
        ekle("ADB","scrcpy Kaydet",["scrcpy kaydet","android ekranı kaydet scrcpy","scrcpy video"],komut="scrcpy --record kayit.mp4",os_=HedefOS.LINUX)
        ekle("ADB","scrcpy Ses",["scrcpy ses","android ses yansıt","scrcpy audio"],komut="scrcpy --audio-codec=aac",os_=HedefOS.LINUX)
        ekle("ADB","scrcpy WiFi",["scrcpy wifi","kablosuz ekran yansıt","scrcpy wireless"],komut="scrcpy --tcpip",os_=HedefOS.LINUX)

        # ── Batch-4: xrandr / Ekran Yönetimi ─────────────────────────────
        ekle("xrandr","Ekranları Listele",["ekranları listele","xrandr listesi","monitörler"],komut="xrandr --listmonitors",os_=HedefOS.LINUX)
        ekle("xrandr","Çözünürlük Listesi",["çözünürlük listesi","desteklenen çözünürlükler","xrandr modları"],komut="xrandr",os_=HedefOS.LINUX)
        ekle("xrandr","Çözünürlük Değiştir",["çözünürlük değiştir","xrandr çözünürlük","ekran boyutu değiştir"],komut="xrandr --output eDP-1 --mode 1920x1080",os_=HedefOS.LINUX)
        ekle("xrandr","Yenileme Hızı",["yenileme hızı","hz değiştir","ekran hz"],komut="xrandr --output eDP-1 --rate 144",os_=HedefOS.LINUX)
        ekle("xrandr","İkinci Ekran Sağ",["ikinci ekranı sağa ekle","çift monitör","second monitor right"],komut="xrandr --output HDMI-1 --auto --right-of eDP-1",os_=HedefOS.LINUX)
        ekle("xrandr","İkinci Ekran Sol",["ikinci ekranı sola ekle","monitörü sola al","second monitor left"],komut="xrandr --output HDMI-1 --auto --left-of eDP-1",os_=HedefOS.LINUX)
        ekle("xrandr","İkinci Ekran Üst",["ikinci ekranı üste ekle","monitörü üste al","second monitor above"],komut="xrandr --output HDMI-1 --auto --above eDP-1",os_=HedefOS.LINUX)
        ekle("xrandr","Yansıt Ekran",["ekranları yansıt","mirror display","duplicate screen"],komut="xrandr --output HDMI-1 --same-as eDP-1",os_=HedefOS.LINUX)
        ekle("xrandr","Ekranı Kapat",["hdmi ekranı kapat","ikinci monitörü kapat","xrandr off"],komut="xrandr --output HDMI-1 --off",os_=HedefOS.LINUX)
        ekle("xrandr","Sadece Harici Ekran",["sadece harici ekran","laptop ekranı kapat","sadece hdmi"],komut="xrandr --output eDP-1 --off --output HDMI-1 --auto",os_=HedefOS.LINUX)
        ekle("xrandr","Sadece Dahili Ekran",["sadece dahili ekran","laptop ekranına dön","hdmi kapat dahili aç"],komut="xrandr --output HDMI-1 --off --output eDP-1 --auto",os_=HedefOS.LINUX)
        ekle("xrandr","Ekran Döndür",["ekranı döndür","monitor rotate","ekran döndürme"],komut="xrandr --output eDP-1 --rotate left",os_=HedefOS.LINUX)
        ekle("xrandr","Ekran Normal",["ekranı düzelt","monitor normal","ekranı normale al"],komut="xrandr --output eDP-1 --rotate normal",os_=HedefOS.LINUX)
        ekle("xrandr","DPI Ayarla",["ekran dpi ayarla","yüksek dpi","xrandr dpi"],komut="xrandr --dpi 120",os_=HedefOS.LINUX)
        ekle("xrandr","Özel Mod Ekle",["özel çözünürlük ekle","xrandr newmode","custom resolution"],komut="xrandr --newmode",os_=HedefOS.LINUX)
        ekle("xrandr","Parlaklık xrandr",["xrandr parlaklık","ekran parlaklığı ayarla","brightness xrandr"],komut="xrandr --output eDP-1 --brightness 0.8",os_=HedefOS.LINUX)
        ekle("xrandr","Gamma Ayarla",["gamma ayarla","renk dengesi","xrandr gamma"],komut="xrandr --output eDP-1 --gamma 1.0:1.0:0.8",os_=HedefOS.LINUX)
        ekle("xrandr","Ölçekleme",["ekran ölçekle","xrandr scale","monitor zoom"],komut="xrandr --output eDP-1 --scale 1.5x1.5",os_=HedefOS.LINUX)
        ekle("xrandr","DisplayPort Bağlantı",["displayport ekle","dp monitör","xrandr dp"],komut="xrandr --output DP-1 --auto --right-of eDP-1",os_=HedefOS.LINUX)
        ekle("xrandr","Tüm Ekranlar Açık",["tüm ekranlar açık","all monitors on","tüm monitörler"],komut="xrandr --auto",os_=HedefOS.LINUX)

        # ── Batch-4: APT / Snap / Flatpak Tam ────────────────────────────
        ekle("PaketYönetim","APT Güncelle",["apt güncelle","paket listesini güncelle","apt update"],komut="sudo apt update",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Yükselt",["apt yükselt","paketleri yükselt","apt upgrade"],komut="sudo apt upgrade -y",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Tam Yükselt",["apt full upgrade","tam yükseltme","apt dist-upgrade"],komut="sudo apt full-upgrade -y",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Kur",["apt kur","apt install","paket yükle apt"],komut="sudo apt install -y",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Kaldır",["apt kaldır","apt remove","paket sil apt"],komut="sudo apt remove",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Temizle",["apt temizle","apt autoremove","gereksiz paketleri kaldır"],komut="sudo apt autoremove -y && sudo apt autoclean",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Ara",["apt ara","paket ara","apt search"],komut="apt search",os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Bilgi",["apt bilgi","paket bilgisi","apt show"],komut="apt show",os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Yüklü Listesi",["yüklü paketler","kurulu paketler apt","dpkg listesi"],komut="dpkg -l | grep '^ii'",os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Cache Temizle",["apt cache temizle","apt-get clean","paket cache sil"],komut="sudo apt-get clean",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT PPA Ekle",["ppa ekle","repository ekle","apt ppa"],komut="sudo add-apt-repository ppa:",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT PPA Kaldır",["ppa kaldır","repository kaldır","apt ppa sil"],komut="sudo add-apt-repository --remove ppa:",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","APT Kaynak Listesi",["apt kaynak listesi","sources.list","apt repository listesi"],komut="cat /etc/apt/sources.list",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Listesi",["snap listesi","snap paketler","kurulu snapler"],komut="snap list",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Kur",["snap kur","snap install","snap paketi yükle"],komut="sudo snap install",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Kaldır",["snap kaldır","snap remove","snap paketi sil"],komut="sudo snap remove",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Güncelle",["snap güncelle","snap refresh","snap yükselt"],komut="sudo snap refresh",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Ara",["snap ara","snap find","snap paket ara"],komut="snap find",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Snap Bilgi",["snap bilgi","snap info","snap paket bilgisi"],komut="snap info",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Listesi",["flatpak listesi","flatpak uygulamalar","kurulu flatpakler"],komut="flatpak list",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Kur",["flatpak kur","flatpak install","flatpak paketi yükle"],komut="flatpak install",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Kaldır",["flatpak kaldır","flatpak remove","flatpak paketi sil"],komut="flatpak uninstall",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Güncelle",["flatpak güncelle","flatpak update","flatpak yükselt"],komut="flatpak update",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Ara",["flatpak ara","flatpak search","flatpak paket ara"],komut="flatpak search",os_=HedefOS.LINUX)
        ekle("PaketYönetim","Flatpak Remote Ekle",["flathub ekle","flatpak repository ekle","flatpak remote"],komut="flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo",os_=HedefOS.LINUX)
        ekle("PaketYönetim","dpkg Kur",["dpkg kur","deb dosyası kur","dpkg -i"],komut="sudo dpkg -i",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","dpkg Bağımlılık Düzelt",["dpkg bağımlılık düzelt","broken packages","apt fix broken"],komut="sudo apt install -f",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("PaketYönetim","AppImage Çalıştır",["appimage çalıştır","appimage aç","appimage executable"],komut="chmod +x *.AppImage && ./*.AppImage",os_=HedefOS.LINUX)

        # ── Batch-4: LVM / RAID ───────────────────────────────────────────
        ekle("LVM","LVM Fiziksel Birimler",["lvm fiziksel birimler","pvdisplay","pv listesi"],komut="sudo pvdisplay",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("LVM","LVM Grup Listesi",["lvm grup listesi","vgdisplay","volume group"],komut="sudo vgdisplay",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("LVM","LVM Mantıksal Birimler",["lvm mantıksal birimler","lvdisplay","logical volume"],komut="sudo lvdisplay",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("LVM","LVM PV Oluştur",["lvm pv oluştur","pvcreate","fiziksel birim oluştur"],komut="sudo pvcreate",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("LVM","LVM VG Oluştur",["lvm vg oluştur","vgcreate","volume group oluştur"],komut="sudo vgcreate",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("LVM","LVM LV Oluştur",["lvm lv oluştur","lvcreate","mantıksal birim oluştur"],komut="sudo lvcreate -L 10G -n",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("LVM","LVM Genişlet",["lvm genişlet","lvextend","mantıksal birimi büyüt"],komut="sudo lvextend -L +5G",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("LVM","LVM Küçült",["lvm küçült","lvreduce","mantıksal birimi küçült"],komut="sudo lvreduce -L -2G",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("LVM","RAID Durumu",["raid durumu","mdadm status","raid array"],komut="cat /proc/mdstat",os_=HedefOS.LINUX)
        ekle("LVM","RAID Detayı",["raid detayı","mdadm detail","raid dizisi bilgisi"],komut="sudo mdadm --detail /dev/md0",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ── Batch-4: Kabuk Betik Yönetimi ────────────────────────────────
        ekle("KabukBetik","Yeni Script Oluştur",["yeni script oluştur","bash script yaz","shell script aç"],komut='echo "#!/bin/bash" > script.sh && chmod +x script.sh && nano script.sh',os_=HedefOS.LINUX)
        ekle("KabukBetik","Script Çalıştır",["script çalıştır","bash dosya çalıştır","sh dosya çalıştır"],komut="bash script.sh",os_=HedefOS.LINUX)
        ekle("KabukBetik","Script Hata Ayıkla",["script debug","bash debug","betik hata ayıkla"],komut="bash -x script.sh",os_=HedefOS.LINUX)
        ekle("KabukBetik","Script Sözdizimi Kontrol",["script syntax","bash -n","betik sözdizimi"],komut="bash -n script.sh",os_=HedefOS.LINUX)
        ekle("KabukBetik","Çalıştırılabilir Yap",["dosyayı çalıştırılabilir yap","chmod +x","executable yap"],komut="chmod +x",os_=HedefOS.LINUX)
        ekle("KabukBetik","PATH Göster",["path göster","echo PATH","hangi dizinler path"],komut="echo $PATH | tr ':' '\n'",os_=HedefOS.LINUX)
        ekle("KabukBetik","PATH Ekle",["path ekle","dizini path'e ekle","export PATH"],yanit="~/.bashrc veya ~/.zshrc dosyasına: export PATH=$PATH:/yeni/dizin",tur="konusma",os_=HedefOS.LINUX)
        ekle("KabukBetik","Alias Listesi",["alias listesi","takma adlar","tanımlı aliaslar"],komut="alias",os_=HedefOS.LINUX)
        ekle("KabukBetik","Yeni Alias",["yeni alias ekle","takma ad tanımla","alias oluştur"],yanit="~/.bashrc dosyasına: alias kısayol='uzun komut'",tur="konusma",os_=HedefOS.LINUX)
        ekle("KabukBetik","Ortam Değişkenleri",["ortam değişkenleri","env değişkenler","printenv"],komut="printenv | sort",os_=HedefOS.LINUX)
        ekle("KabukBetik","Değişken Export",["değişken dışa aktar","export variable","env var ekle"],komut='export DEGISKEN="deger"',os_=HedefOS.LINUX)
        ekle("KabukBetik","bashrc Düzenle",["bashrc düzenle","bash ayarları","bash profil"],komut="nano ~/.bashrc",os_=HedefOS.LINUX)
        ekle("KabukBetik","bashrc Yenile",["bashrc yenile","bash yenile","source bashrc"],komut="source ~/.bashrc",os_=HedefOS.LINUX)
        ekle("KabukBetik","zshrc Düzenle",["zshrc düzenle","zsh ayarları","zsh profil"],komut="nano ~/.zshrc",os_=HedefOS.LINUX)
        ekle("KabukBetik","Komut Geçmişi",["komut geçmişi","history komutu","son komutlar"],komut="history | tail -30",os_=HedefOS.LINUX)
        ekle("KabukBetik","Geçmişi Temizle",["geçmişi temizle","history temizle","komut geçmişini sil"],komut="history -c && history -w",os_=HedefOS.LINUX)
        ekle("KabukBetik","Komut Bul",["hangi komut","which komutu","komut nerede"],komut="which",os_=HedefOS.LINUX)
        ekle("KabukBetik","Tüm Konumlar",["komutun tüm yolları","whereis komutu","man sayfası nerede"],komut="whereis",os_=HedefOS.LINUX)
        ekle("KabukBetik","Komut Hakkında",["komut hakkında bilgi","man sayfası","manual page"],komut="man",os_=HedefOS.LINUX)
        ekle("KabukBetik","Kısa Yardım",["kısa yardım","tldr komutu","komut özeti"],komut="tldr",os_=HedefOS.LINUX)
        ekle("KabukBetik","Betik Zamanlayıcı",["betik ne kadar sürdü","time komutu","komut süresi"],komut="time",os_=HedefOS.LINUX)
        ekle("KabukBetik","Paralel Çalıştır",["paralel çalıştır","xargs paralel","parallel komutu"],komut="parallel -j4",os_=HedefOS.LINUX)
        ekle("KabukBetik","Betik Şablon",["bash şablon","script template","bash boilerplate"],yanit="#!/bin/bash\nset -euo pipefail\nmain() { echo 'başlıyor'; }\nmain \"$@\"",tur="konusma",os_=HedefOS.LINUX)

        # ── Batch-4: Metin İşleme Araçları ───────────────────────────────
        ekle("MetinAraç","Dosya Ara grep",["dosyada ara","grep komutu","kelime ara dosyada"],komut='grep -r "" .',os_=HedefOS.LINUX)
        ekle("MetinAraç","Büyük/Küçük Harf grep",["büyük küçük harf ara","grep -i","harf duyarsız ara"],komut='grep -ri "" .',os_=HedefOS.LINUX)
        ekle("MetinAraç","Satır Numaralı grep",["satır numaralı ara","grep -n","grep satır numarası"],komut='grep -rn "" .',os_=HedefOS.LINUX)
        ekle("MetinAraç","Regex grep",["regex ile ara","grep regex","düzenli ifade ara"],komut='grep -rE "" .',os_=HedefOS.LINUX)
        ekle("MetinAraç","Ters grep",["içermeyenleri bul","grep -v","satırı dışla"],komut='grep -v ""',os_=HedefOS.LINUX)
        ekle("MetinAraç","sed Değiştir",["sed komutu","metin değiştir sed","sed replace"],komut="sed -i 's/eski/yeni/g'",os_=HedefOS.LINUX)
        ekle("MetinAraç","awk Sütun",["awk sütun","awk komutu","sütun seç"],komut="awk '{print $1}'",os_=HedefOS.LINUX)
        ekle("MetinAraç","Satır Say",["satır say","wc -l","kaç satır"],komut="wc -l",os_=HedefOS.LINUX)
        ekle("MetinAraç","Kelime Say",["kelime say","wc -w","kaç kelime"],komut="wc -w",os_=HedefOS.LINUX)
        ekle("MetinAraç","Sırala",["dosyayı sırala","sort komutu","alfabetik sırala"],komut="sort",os_=HedefOS.LINUX)
        ekle("MetinAraç","Tekrarsız Sırala",["tekrarsız sırala","sort -u","benzersiz satırlar"],komut="sort -u",os_=HedefOS.LINUX)
        ekle("MetinAraç","Ters Sırala",["ters sırala","sort -r","azalan sıra"],komut="sort -r",os_=HedefOS.LINUX)
        ekle("MetinAraç","Tekrarları Kaldır",["tekrarları kaldır","uniq komutu","yinelenen satırları sil"],komut="sort | uniq",os_=HedefOS.LINUX)
        ekle("MetinAraç","Tekrar Sayısı",["tekrar sayısı","uniq -c","kaç kez tekrar"],komut="sort | uniq -c | sort -rn",os_=HedefOS.LINUX)
        ekle("MetinAraç","Kesim Sütun",["sütun kes","cut komutu","alan seç"],komut="cut -d',' -f1",os_=HedefOS.LINUX)
        ekle("MetinAraç","Baş Satırlar",["baş satırlar","head komutu","ilk 10 satır"],komut="head -20",os_=HedefOS.LINUX)
        ekle("MetinAraç","Son Satırlar",["son satırlar","tail komutu","son 10 satır"],komut="tail -20",os_=HedefOS.LINUX)
        ekle("MetinAraç","Canlı İzle",["dosyayı canlı izle","tail -f","log izle"],komut="tail -f",os_=HedefOS.LINUX)
        ekle("MetinAraç","Hex Görüntüle",["hex görüntüle","xxd komutu","binary dosya incele"],komut="xxd",os_=HedefOS.LINUX)
        ekle("MetinAraç","Karakter Değiştir",["karakter değiştir","tr komutu","char replace"],komut="tr 'a-z' 'A-Z'",os_=HedefOS.LINUX)
        ekle("MetinAraç","Sütunla Hizala",["sütunla hizala","column komutu","tablo görünümü"],komut="column -t",os_=HedefOS.LINUX)
        ekle("MetinAraç","JSON Format",["json formatla","jq komutu","json güzelleştir"],komut="jq '.'",os_=HedefOS.LINUX)
        ekle("MetinAraç","JSON Sorgula",["json sorgula","jq filtre","json değer al"],komut='jq ".alan"',os_=HedefOS.LINUX)
        ekle("MetinAraç","CSV'yi JSON'a",["csv json dönüştür","csv to json","csvjson"],komut="python3 -c \"import csv,json,sys; print(json.dumps(list(csv.DictReader(sys.stdin))))\"",os_=HedefOS.LINUX)
        ekle("MetinAraç","Fark Göster",["iki dosya farkı","diff komutu","dosyaları karşılaştır"],komut="diff",os_=HedefOS.LINUX)
        ekle("MetinAraç","Renkli Fark",["renkli fark","colordiff","diff renkli"],komut="colordiff",os_=HedefOS.LINUX)
        ekle("MetinAraç","Yama Uygula",["yama uygula","patch komutu","diff uygula"],komut="patch < degisiklik.patch",os_=HedefOS.LINUX)
        ekle("MetinAraç","Base64 Kodla",["base64 kodla","base64 encode","metin şifrele base64"],komut='echo -n "metin" | base64',os_=HedefOS.LINUX)
        ekle("MetinAraç","Base64 Çöz",["base64 çöz","base64 decode","base64 metin çöz"],komut='echo "encoded" | base64 -d',os_=HedefOS.LINUX)
        ekle("MetinAraç","MD5 Hash",["md5 hash","dosya md5","md5sum"],komut="md5sum",os_=HedefOS.LINUX)
        ekle("MetinAraç","SHA256 Hash",["sha256 hash","dosya sha256","sha256sum"],komut="sha256sum",os_=HedefOS.LINUX)

        # ── Batch-4: Sıkıştırma ve Arşiv ─────────────────────────────────
        ekle("Arşiv","Tar Oluştur",["tar oluştur","tar arşivi","klasörü sıkıştır tar"],komut="tar -czvf arşiv.tar.gz",os_=HedefOS.LINUX)
        ekle("Arşiv","Tar Aç",["tar aç","tar dosyası aç","tar extract"],komut="tar -xzvf arşiv.tar.gz",os_=HedefOS.LINUX)
        ekle("Arşiv","Tar Listele",["tar içeriği","tar listele","tar dosyasını göster"],komut="tar -tzvf arşiv.tar.gz",os_=HedefOS.LINUX)
        ekle("Arşiv","ZIP Oluştur",["zip oluştur","zip arşiv","dosyaları zip yap"],komut="zip -r arşiv.zip",os_=HedefOS.LINUX)
        ekle("Arşiv","ZIP Aç",["zip aç","zip dosyası aç","unzip"],komut="unzip",os_=HedefOS.LINUX)
        ekle("Arşiv","ZIP Listele",["zip içeriği","zip listele","zip dosyasını göster"],komut="unzip -l",os_=HedefOS.LINUX)
        ekle("Arşiv","7zip Oluştur",["7zip oluştur","7z arşiv","7zip sıkıştır"],komut="7z a arşiv.7z",os_=HedefOS.LINUX)
        ekle("Arşiv","7zip Aç",["7zip aç","7z extract","7z dosyası aç"],komut="7z x",os_=HedefOS.LINUX)
        ekle("Arşiv","GZIP Sıkıştır",["gzip sıkıştır","dosyayı gzip","gz oluştur"],komut="gzip",os_=HedefOS.LINUX)
        ekle("Arşiv","GZIP Aç",["gzip aç","gunzip","gz dosyası aç"],komut="gunzip",os_=HedefOS.LINUX)
        ekle("Arşiv","BZIP2 Sıkıştır",["bzip2 sıkıştır","bz2 oluştur","bzip kompres"],komut="bzip2",os_=HedefOS.LINUX)
        ekle("Arşiv","BZIP2 Aç",["bzip2 aç","bunzip2","bz2 dosyası aç"],komut="bunzip2",os_=HedefOS.LINUX)
        ekle("Arşiv","XZ Sıkıştır",["xz sıkıştır","xz kompres","en iyi sıkıştırma"],komut="xz",os_=HedefOS.LINUX)
        ekle("Arşiv","XZ Aç",["xz aç","unxz","xz dosyası aç"],komut="unxz",os_=HedefOS.LINUX)
        ekle("Arşiv","rar Aç",["rar aç","rar dosyası aç","unrar"],komut="unrar x",os_=HedefOS.LINUX)
        ekle("Arşiv","Sıkıştırma Oranı Karşılaştır",["sıkıştırma karşılaştır","hangi format daha iyi","kompresyon testi"],yanit="Sıkıştırma gücü sıralaması: xz > bzip2 > gzip > zip > tar. Hız sıralaması tersi.",tur="konusma",os_=HedefOS.LINUX)

        # ── Batch-4: İndirme / Ağ Araçları ───────────────────────────────
        ekle("İndirme","wget İndir",["wget indir","dosya indir wget","url indir"],komut="wget",os_=HedefOS.LINUX)
        ekle("İndirme","wget Arkaplan",["arkaplan indir","wget arka planda","wget background"],komut="wget -b",os_=HedefOS.LINUX)
        ekle("İndirme","wget Devam",["yarım indirmeyi devam ettir","wget -c","indirmeye devam"],komut="wget -c",os_=HedefOS.LINUX)
        ekle("İndirme","wget Ayna İndir",["web sitesini kopyala","wget mirror","site indir"],komut="wget --mirror -p --convert-links",os_=HedefOS.LINUX)
        ekle("İndirme","curl İndir",["curl indir","curl dosya","curl get"],komut="curl -O",os_=HedefOS.LINUX)
        ekle("İndirme","curl POST",["curl post","curl veri gönder","curl -X POST"],komut='curl -X POST -H "Content-Type: application/json" -d \'{"key":"value"}\'',os_=HedefOS.LINUX)
        ekle("İndirme","curl Başlık",["curl başlık","curl header","http başlık gör"],komut="curl -I",os_=HedefOS.LINUX)
        ekle("İndirme","curl API Test",["curl api test","api endpoint test","curl json api"],komut='curl -s | jq "."',os_=HedefOS.LINUX)
        ekle("İndirme","YouTube İndir",["youtube indir","yt-dlp","video indir youtube"],komut="yt-dlp",os_=HedefOS.LINUX)
        ekle("İndirme","YouTube Ses İndir",["youtube ses indir","mp3 indir youtube","yt-dlp ses"],komut="yt-dlp -x --audio-format mp3",os_=HedefOS.LINUX)
        ekle("İndirme","YouTube Liste İndir",["youtube playlist indir","oynatma listesi indir","yt-dlp playlist"],komut="yt-dlp --yes-playlist",os_=HedefOS.LINUX)
        ekle("İndirme","aria2 İndir",["aria2 indir","hızlı indir aria2","multi-connection download"],komut="aria2c -x16 -s16",os_=HedefOS.LINUX)
        ekle("İndirme","rsync Dosya Kopyala",["rsync kopyala","dosya senkronize et","rsync sync"],komut="rsync -avz",os_=HedefOS.LINUX)
        ekle("İndirme","rsync Uzaktan Kopyala",["rsync uzak kopyala","ssh ile kopyala","rsync ssh"],komut="rsync -avz -e ssh",os_=HedefOS.LINUX)
        ekle("İndirme","scp Kopyala",["scp kopyala","ssh ile dosya kopyala","scp upload"],komut="scp",os_=HedefOS.LINUX)
        ekle("İndirme","sftp Bağlan",["sftp bağlan","sftp sunucu","dosya transfer sftp"],komut="sftp",os_=HedefOS.LINUX)
        ekle("İndirme","FTP Bağlan",["ftp bağlan","ftp sunucu","dosya transfer ftp"],komut="ftp",os_=HedefOS.LINUX)
        ekle("İndirme","Torrent İndir",["torrent indir","qbittorrent cli","transmission cli"],komut="transmission-remote --add",os_=HedefOS.LINUX)

        # ── Batch-4: İzleme ve Performans ─────────────────────────────────
        ekle("İzleme","htop İzle",["htop aç","sistem izle htop","process izle"],komut="htop",os_=HedefOS.LINUX)
        ekle("İzleme","btop İzle",["btop aç","gelişmiş sistem izle","btop monitor"],komut="btop",os_=HedefOS.LINUX)
        ekle("İzleme","Gerçek Zamanlı CPU",["cpu kullanımı canlı","top komutu","cpu izle"],komut="top -d 1",os_=HedefOS.LINUX)
        ekle("İzleme","CPU Frekansı",["cpu frekansı","işlemci hızı","mhz göster"],komut="watch -n1 'cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq | sort -n | tail -1'",os_=HedefOS.LINUX)
        ekle("İzleme","GPU İzle",["gpu izle","nvidia gpu","gpu kullanımı"],komut="watch -n1 nvidia-smi",os_=HedefOS.LINUX)
        ekle("İzleme","RAM Detaylı",["ram detaylı","bellek detayı","free -h"],komut="free -h",os_=HedefOS.LINUX)
        ekle("İzleme","vmstat",["vmstat","sanal bellek istatistik","sistem istatistik"],komut="vmstat 1 5",os_=HedefOS.LINUX)
        ekle("İzleme","iostat",["iostat","disk io istatistik","depolama hızı"],komut="iostat -xz 1 5",os_=HedefOS.LINUX)
        ekle("İzleme","netstat Bağlantılar",["netstat bağlantılar","açık bağlantılar","aktif soketler"],komut="netstat -tuln",os_=HedefOS.LINUX)
        ekle("İzleme","Ağ Trafiği",["ağ trafiği izle","nethogs","hangi uygulama bant kullanıyor"],komut="sudo nethogs",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("İzleme","Ağ Bant Genişliği",["bant genişliği izle","iftop","network bandwidth"],komut="sudo iftop",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("İzleme","Sistem Yükü",["sistem yükü","load average","uptime komutu"],komut="uptime",os_=HedefOS.LINUX)
        ekle("İzleme","Sistem Bilgisi Detaylı",["sistem bilgisi detaylı","neofetch","sistem özeti"],komut="neofetch",os_=HedefOS.LINUX)
        ekle("İzleme","Donanım Listesi",["donanım listesi","lshw","sistem donanımı"],komut="sudo lshw -short",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("İzleme","PCI Aygıtlar",["pci aygıtlar","lspci","pci kartlar"],komut="lspci",os_=HedefOS.LINUX)
        ekle("İzleme","USB Aygıtlar",["usb aygıtlar","lsusb","bağlı usb"],komut="lsusb",os_=HedefOS.LINUX)
        ekle("İzleme","Kesintiler",["cpu kesintileri","proc interrupts","irq listesi"],komut="cat /proc/interrupts",os_=HedefOS.LINUX)
        ekle("İzleme","Çekirdek Mesajları",["çekirdek mesajları","dmesg","kernel log"],komut="dmesg | tail -30",os_=HedefOS.LINUX)
        ekle("İzleme","Canlı Çekirdek Log",["canlı kernel log","dmesg -w","kernel canlı izle"],komut="dmesg -w",os_=HedefOS.LINUX)
        ekle("İzleme","Watchdog",["belirli aralıkta çalıştır","watch komutu","komutu izle"],komut="watch -n2",os_=HedefOS.LINUX)

        # ── Batch-4: Güvenlik Tarama ──────────────────────────────────────
        ekle("GüvenlikTarama","Virüs Tara",["virüs tara","clamav","malware tara"],komut="clamscan -r --bell",os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","ClamAV Güncelle",["clamav güncelle","virüs veritabanı güncelle","freshclam"],komut="sudo freshclam",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Rootkit Tara",["rootkit tara","rkhunter","gizli zararlı tara"],komut="sudo rkhunter --check",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Chkrootkit",["chkrootkit tara","rootkit kontrol","chkrootkit"],komut="sudo chkrootkit",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Lynis Denetim",["lynis denetim","güvenlik denetimi","lynis audit"],komut="sudo lynis audit system",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Açık Port Tara",["açık portları tara","nmap port scan","port tarama"],komut="nmap -sV localhost",os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Zafiyet Tara",["zafiyet tara","nmap zafiyet","güvenlik açığı tara"],komut="nmap --script vuln localhost",os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","SUID Dosyalar",["suid dosyalar","suid bit arama","yetki yükseltme riski"],komut="find / -perm -4000 -type f 2>/dev/null",os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","World Writable",["herkes yazabilir","world writable","yanlış izin dosyalar"],komut="find / -perm -0002 -type f 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","AppArmor Durumu",["apparmor durumu","apparmor status","uygulama güvenlik profili"],komut="sudo aa-status",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","SELinux Durumu",["selinux durumu","getenforce","zorunlu erişim kontrolü"],komut="getenforce",os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Aide Kontrol",["aide kontrol","dosya bütünlüğü","aide --check"],komut="sudo aide --check",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Şüpheli Süreçler",["şüpheli süreçler","olağandışı süreçler","gizli process"],komut="ps aux | awk '{print $11}' | sort | uniq -c | sort -rn | head -20",os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Ağ Bağlantı Analiz",["ağ bağlantı analiz","dışa bağlantılar","olağandışı bağlantılar"],komut="ss -tunapl | grep ESTABLISHED",os_=HedefOS.LINUX)
        ekle("GüvenlikTarama","Log Analiz",["güvenlik log analizi","auth log incele","giriş denemeleri"],komut="grep 'Failed password' /var/log/auth.log | tail -20",os_=HedefOS.LINUX)

        # ── Batch-5: Medya İşleme ─────────────────────────────────────────
        ekle("Medyaİşleme","FFmpeg Video Dönüştür",["video dönüştür","ffmpeg convert","mp4 dönüştür"],komut="ffmpeg -i girdi.avi çıktı.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Ses Çıkar",["videodan ses çıkar","ffmpeg ses çıkar","mp3 çıkar videodan"],komut="ffmpeg -i video.mp4 -q:a 0 -map a ses.mp3",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Video Kes",["videoyu kes","ffmpeg trim","bölüm kes video"],komut="ffmpeg -i girdi.mp4 -ss 00:01:00 -to 00:02:00 -c copy çıktı.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Birleştir",["videoları birleştir","ffmpeg concat","video yapıştır"],komut="ffmpeg -f concat -safe 0 -i liste.txt -c copy çıktı.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Boyutlandır",["video boyutlandır","ffmpeg resize","çözünürlük değiştir video"],komut="ffmpeg -i girdi.mp4 -vf scale=1280:720 çıktı.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg GIF Oluştur",["videoyü gif yap","ffmpeg gif","animasyon gif oluştur"],komut="ffmpeg -i girdi.mp4 -vf 'fps=10,scale=480:-1' çıktı.gif",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Ekran Kaydı",["ffmpeg ekran kaydet","screencast ffmpeg","masaüstü kaydet"],komut="ffmpeg -f x11grab -r 25 -s 1920x1080 -i :0.0 -c:v libx264 kayıt.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Webcam",["webcam kaydet","ffmpeg kamera","kamerayı kaydet"],komut="ffmpeg -f v4l2 -i /dev/video0 webcam.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Ses Hızlandır",["ses hızlandır","ffmpeg tempo","sesi hızlı çal"],komut="ffmpeg -i ses.mp3 -af atempo=1.5 hızlı.mp3",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Video Bilgisi",["video bilgisi","ffprobe","video meta veri"],komut="ffprobe -v quiet -print_format json -show_format -show_streams",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Küçük Resim",["video thumbnail","ffmpeg ekran görüntüsü","videoya küçük resim"],komut="ffmpeg -i video.mp4 -ss 00:00:05 -vframes 1 thumbnail.jpg",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Sıkıştır",["videoyu sıkıştır","ffmpeg compress","video boyutu küçült"],komut="ffmpeg -i girdi.mp4 -vcodec libx265 -crf 28 çıktı.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Altyazı Ekle",["altyazı ekle","ffmpeg subtitle","srt göm video"],komut="ffmpeg -i video.mp4 -vf subtitles=altyazi.srt çıktı.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Ses Normalize",["ses normalize et","ffmpeg normalize","ses seviyesi düzenle"],komut="ffmpeg -i ses.mp3 -af loudnorm çıktı.mp3",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","FFmpeg Filigran Ekle",["filigran ekle","ffmpeg watermark","video logo ekle"],komut="ffmpeg -i video.mp4 -i logo.png -filter_complex overlay=10:10 çıktı.mp4",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Dönüştür",["resim dönüştür","imagemagick convert","jpg png dönüştür"],komut="convert girdi.jpg çıktı.png",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Yeniden Boyutlandır",["resmi boyutlandır","imagemagick resize","fotoğraf küçült"],komut="convert -resize 800x600 girdi.jpg çıktı.jpg",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Toplu Dönüştür",["toplu resim dönüştür","imagemagick batch","tüm resimleri dönüştür"],komut="mogrify -format png *.jpg",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Kalite",["resim kalitesi ayarla","jpeg kalite","imagemagick quality"],komut="convert -quality 85 girdi.jpg çıktı.jpg",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Birleştir",["resimleri birleştir","imagemagick append","fotoğraf yanyana"],komut="convert +append resim1.jpg resim2.jpg birlesik.jpg",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Metin Ekle",["resme metin ekle","imagemagick text","fotoğrafa yazı yaz"],komut='convert girdi.jpg -font DejaVu-Sans -pointsize 36 -fill white -annotate +10+40 "Metin" çıktı.jpg',os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Gri Ton",["resmi gri yap","imagemagick grayscale","siyah beyaz çevir"],komut="convert -colorspace Gray girdi.jpg çıktı.jpg",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Döndür",["resmi döndür","imagemagick rotate","fotoğrafı çevir"],komut="convert -rotate 90 girdi.jpg çıktı.jpg",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick Kırp",["resmi kırp","imagemagick crop","fotoğraf kırpma"],komut="convert -crop 800x600+0+0 girdi.jpg çıktı.jpg",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","ImageMagick PDF'e",["resimden pdf","imagemagick pdf","jpg pdf çevir"],komut="convert *.jpg çıktı.pdf",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","Ses Dosyası Bilgisi",["ses bilgisi","soxi","ses süresi format"],komut="soxi",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","SoX Ses Dönüştür",["sox dönüştür","ses formatı değiştir","wav mp3 çevir"],komut="sox girdi.wav çıktı.mp3",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","SoX Gürültü Azalt",["gürültü azalt","sox noise","ses temizle"],komut="sox girdi.wav çıktı.wav noisered profil.prof 0.21",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","Exiftool Meta",["exiftool meta","dosya meta verisi","fotoğraf bilgisi exif"],komut="exiftool",os_=HedefOS.LINUX)
        ekle("Medyaİşleme","Exiftool Meta Sil",["meta veri sil","exiftool temizle","fotoğraf gizliliği"],komut="exiftool -all= ",os_=HedefOS.LINUX)

        # ── Batch-5: Veritabanı ───────────────────────────────────────────
        ekle("Veritabanı","PostgreSQL Bağlan",["postgresql bağlan","psql bağlan","postgres konsolu"],komut="psql -U postgres",os_=HedefOS.LINUX)
        ekle("Veritabanı","PostgreSQL Servis",["postgresql başlat","postgres servis","psql servis"],komut="sudo systemctl start postgresql",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Veritabanı","PostgreSQL DB Listesi",["postgres veritabanı listesi","psql list db","hangi veritabanları var"],komut='psql -U postgres -c "\\l"',os_=HedefOS.LINUX)
        ekle("Veritabanı","PostgreSQL Tablo Listesi",["postgres tablo listesi","psql tablolar","veritabanı tabloları"],komut='psql -U postgres -c "\\dt"',os_=HedefOS.LINUX)
        ekle("Veritabanı","PostgreSQL Yedek Al",["postgres yedek","pg_dump","veritabanı yedekle"],komut="pg_dump -U postgres veritabani > yedek.sql",os_=HedefOS.LINUX)
        ekle("Veritabanı","PostgreSQL Yedek Yükle",["postgres yedek yükle","psql restore","veritabanı geri yükle"],komut="psql -U postgres veritabani < yedek.sql",os_=HedefOS.LINUX)
        ekle("Veritabanı","MySQL Bağlan",["mysql bağlan","mysql konsolu","mysql veritabanı"],komut="mysql -u root -p",os_=HedefOS.LINUX)
        ekle("Veritabanı","MySQL Servis",["mysql başlat","mysql servis","mysql sunucu"],komut="sudo systemctl start mysql",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Veritabanı","MySQL DB Listesi",["mysql veritabanı listesi","show databases","mysql hangi db"],komut='mysql -u root -p -e "SHOW DATABASES;"',os_=HedefOS.LINUX)
        ekle("Veritabanı","MySQL Yedek Al",["mysql yedek","mysqldump","mysql veritabanı yedekle"],komut="mysqldump -u root -p veritabani > yedek.sql",os_=HedefOS.LINUX)
        ekle("Veritabanı","SQLite Aç",["sqlite aç","sqlite3 konsolu","sqlite veritabanı"],komut="sqlite3",os_=HedefOS.LINUX)
        ekle("Veritabanı","SQLite Tablo Listesi",["sqlite tablolar","sqlite schema",".tables sqlite"],komut='sqlite3 veritabani.db ".tables"',os_=HedefOS.LINUX)
        ekle("Veritabanı","SQLite Yedek Al",["sqlite yedek","sqlite dump","sqlite export"],komut='sqlite3 veritabani.db ".dump" > yedek.sql',os_=HedefOS.LINUX)
        ekle("Veritabanı","Redis Başlat",["redis başlat","redis servis","redis sunucu"],komut="sudo systemctl start redis",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Veritabanı","Redis CLI",["redis cli","redis konsolu","redis komutları"],komut="redis-cli",os_=HedefOS.LINUX)
        ekle("Veritabanı","Redis Ping",["redis ping","redis çalışıyor mu","redis bağlantı test"],komut="redis-cli ping",os_=HedefOS.LINUX)
        ekle("Veritabanı","Redis Tüm Anahtarlar",["redis anahtarlar","redis keys","redis key listesi"],komut='redis-cli KEYS "*"',os_=HedefOS.LINUX)
        ekle("Veritabanı","MongoDB Başlat",["mongodb başlat","mongo servis","mongodb sunucu"],komut="sudo systemctl start mongod",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Veritabanı","MongoDB Shell",["mongo shell","mongodb konsolu","mongosh"],komut="mongosh",os_=HedefOS.LINUX)
        ekle("Veritabanı","MongoDB DB Listesi",["mongodb veritabanı listesi","show dbs mongo","mongo hangi db"],komut='mongosh --eval "show dbs"',os_=HedefOS.LINUX)

        # ── Batch-5: Web Sunucu / Nginx / Apache ─────────────────────────
        ekle("WebSunucu","Nginx Başlat",["nginx başlat","nginx servis","web sunucu başlat nginx"],komut="sudo systemctl start nginx",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Nginx Durdur",["nginx durdur","nginx kapat","nginx servis durdur"],komut="sudo systemctl stop nginx",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Nginx Yeniden Başlat",["nginx yeniden başlat","nginx restart","nginx resetle"],komut="sudo systemctl restart nginx",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Nginx Reload",["nginx reload","nginx yenile","nginx config uygula"],komut="sudo systemctl reload nginx",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Nginx Durum",["nginx durum","nginx status","nginx çalışıyor mu"],komut="sudo systemctl status nginx",os_=HedefOS.LINUX)
        ekle("WebSunucu","Nginx Config Test",["nginx config test","nginx syntax","nginx yapılandırma kontrol"],komut="sudo nginx -t",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Nginx Log",["nginx log","nginx erişim logu","nginx error log"],komut="sudo tail -f /var/log/nginx/error.log",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Apache Başlat",["apache başlat","apache2 servis","httpd başlat"],komut="sudo systemctl start apache2",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Apache Durdur",["apache durdur","apache2 kapat","httpd durdur"],komut="sudo systemctl stop apache2",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Apache Yeniden Başlat",["apache yeniden başlat","apache restart","httpd restart"],komut="sudo systemctl restart apache2",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Apache Config Test",["apache config test","apache2ctl configtest","httpd syntax"],komut="sudo apache2ctl configtest",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Apache Log",["apache log","apache erişim logu","httpd error log"],komut="sudo tail -f /var/log/apache2/error.log",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Certbot Sertifika",["ssl sertifika al","certbot","lets encrypt"],komut="sudo certbot --nginx",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Certbot Yenile",["ssl yenile","certbot renew","sertifika yenile"],komut="sudo certbot renew --dry-run",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("WebSunucu","Basit HTTP Sunucu",["basit http sunucu","python http server","hızlı web sunucu"],komut="python3 -m http.server 8080",os_=HedefOS.LINUX)
        ekle("WebSunucu","Gunicorn Başlat",["gunicorn başlat","python wsgi","flask üretim"],komut="gunicorn -w 4 -b 0.0.0.0:8000 app:app",os_=HedefOS.LINUX)
        ekle("WebSunucu","uWSGI Başlat",["uwsgi başlat","uwsgi django","python uwsgi"],komut="uwsgi --ini uwsgi.ini",os_=HedefOS.LINUX)

        # ── Batch-5: Docker Genişletilmiş ────────────────────────────────
        ekle("Docker","Docker Versiyon",["docker versiyonu","docker version","hangi docker"],komut="docker --version && docker compose version",os_=HedefOS.LINUX)
        ekle("Docker","Docker Çalışanlar",["çalışan containerlar","docker ps","aktif docker"],komut="docker ps",os_=HedefOS.LINUX)
        ekle("Docker","Docker Hepsi",["tüm containerlar","docker ps -a","tüm docker"],komut="docker ps -a",os_=HedefOS.LINUX)
        ekle("Docker","Docker Image Listesi",["docker image listesi","docker images","imajlar"],komut="docker images",os_=HedefOS.LINUX)
        ekle("Docker","Docker Pull",["docker image indir","docker pull","imaj çek"],komut="docker pull",os_=HedefOS.LINUX)
        ekle("Docker","Docker Run",["docker çalıştır","docker run","container başlat"],komut="docker run -d",os_=HedefOS.LINUX)
        ekle("Docker","Docker Run İnteraktif",["docker interaktif","docker bash","container içine gir"],komut="docker run -it --rm",os_=HedefOS.LINUX)
        ekle("Docker","Docker Exec",["docker exec","çalışan containera gir","docker shell"],komut="docker exec -it",os_=HedefOS.LINUX)
        ekle("Docker","Docker Stop",["docker durdur","docker stop","container durdur"],komut="docker stop",os_=HedefOS.LINUX)
        ekle("Docker","Docker Kaldır",["docker container sil","docker rm","container kaldır"],komut="docker rm",os_=HedefOS.LINUX)
        ekle("Docker","Docker Image Sil",["docker image sil","docker rmi","imajı kaldır"],komut="docker rmi",os_=HedefOS.LINUX)
        ekle("Docker","Docker Temizle",["docker temizle","docker prune","kullanılmayanları sil"],komut="docker system prune -f",os_=HedefOS.LINUX)
        ekle("Docker","Docker Log",["docker log","container logu","docker çıktısı"],komut="docker logs -f",os_=HedefOS.LINUX)
        ekle("Docker","Docker Build",["docker build","dockerfile derle","imaj oluştur"],komut="docker build -t",os_=HedefOS.LINUX)
        ekle("Docker","Docker Push",["docker push","imajı yükle","docker registry"],komut="docker push",os_=HedefOS.LINUX)
        ekle("Docker","Docker Tag",["docker tag","imajı etiketle","docker versiyon etiketi"],komut="docker tag",os_=HedefOS.LINUX)
        ekle("Docker","Docker Volume Listesi",["docker volume listesi","docker volumes","kalıcı depolama"],komut="docker volume ls",os_=HedefOS.LINUX)
        ekle("Docker","Docker Network Listesi",["docker network listesi","docker networks","konteyner ağları"],komut="docker network ls",os_=HedefOS.LINUX)
        ekle("Docker","Docker Stats",["docker istatistik","docker stats","container kaynak kullanımı"],komut="docker stats --no-stream",os_=HedefOS.LINUX)
        ekle("Docker","Docker Inspect",["docker inspect","container bilgisi","docker detay"],komut="docker inspect",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Başlat",["docker compose başlat","compose up","servisleri başlat"],komut="docker compose up -d",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Durdur",["docker compose durdur","compose down","servisleri durdur"],komut="docker compose down",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Log",["docker compose log","compose logs","servis logları"],komut="docker compose logs -f",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Build",["docker compose build","compose derleme","servisleri derle"],komut="docker compose build",os_=HedefOS.LINUX)
        ekle("Docker","Docker Compose Ölçekle",["docker compose ölçekle","compose scale","replika sayısı"],komut="docker compose up -d --scale",os_=HedefOS.LINUX)
        ekle("Docker","Docker Hub Login",["docker hub login","docker registry giriş","docker login"],komut="docker login",os_=HedefOS.LINUX)
        ekle("Docker","Docker Portainer",["docker portainer","docker web arayüz","container yönetim paneli"],komut="docker run -d -p 9000:9000 --restart=always -v /var/run/docker.sock:/var/run/docker.sock portainer/portainer-ce",os_=HedefOS.LINUX)

        # ── Batch-5: Kubernetes ───────────────────────────────────────────
        ekle("Kubernetes","kubectl Versiyon",["kubectl versiyonu","kubernetes version","hangi kubectl"],komut="kubectl version --short",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Pod Listesi",["pod listesi","kubectl pods","çalışan podlar"],komut="kubectl get pods",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Tüm Namespace",["tüm namespace podlar","kubectl pods all","kubectl -A"],komut="kubectl get pods -A",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Servisler",["kubernetes servisler","kubectl services","k8s hizmetler"],komut="kubectl get services",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Deployments",["kubernetes deployments","kubectl deploy","k8s dağıtımlar"],komut="kubectl get deployments",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Nodes",["kubernetes nodes","kubectl node","k8s düğümler"],komut="kubectl get nodes",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Describe Pod",["pod detayı","kubectl describe","pod bilgisi"],komut="kubectl describe pod",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Log",["kubernetes log","kubectl logs","pod logu"],komut="kubectl logs -f",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Exec",["kubectl exec","pod içine gir","kubernetes shell"],komut="kubectl exec -it -- /bin/bash",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Apply",["kubectl uygula","kubernetes yaml uygula","k8s deploy"],komut="kubectl apply -f",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Delete",["kubectl sil","kubernetes kaynak sil","k8s delete"],komut="kubectl delete -f",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Scale",["kubernetes ölçekle","kubectl scale","replica sayısı değiştir"],komut="kubectl scale deployment --replicas=3",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Port Forward",["kubernetes port forward","kubectl tunnel","pod porta yönlendir"],komut="kubectl port-forward",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Namespace Listesi",["namespace listesi","kubectl namespaces","k8s namespaceler"],komut="kubectl get namespaces",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Config",["kubectl config","kubeconfig","k8s bağlam"],komut="kubectl config get-contexts",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Rollout",["kubernetes rollout","kubectl rollout status","dağıtım durumu"],komut="kubectl rollout status deployment",os_=HedefOS.LINUX)
        ekle("Kubernetes","kubectl Rollback",["kubernetes geri al","kubectl rollback","önceki versiyona dön"],komut="kubectl rollout undo deployment",os_=HedefOS.LINUX)
        ekle("Kubernetes","Minikube Başlat",["minikube başlat","yerel kubernetes","minikube start"],komut="minikube start",os_=HedefOS.LINUX)
        ekle("Kubernetes","Minikube Durdur",["minikube durdur","minikube stop","yerel k8s kapat"],komut="minikube stop",os_=HedefOS.LINUX)
        ekle("Kubernetes","Helm Listesi",["helm listesi","helm charts","kubernetes paketler"],komut="helm list",os_=HedefOS.LINUX)

        # ── Batch-5: CI/CD ve DevOps ──────────────────────────────────────
        ekle("DevOps","GitHub Actions Log",["github actions log","ci cd log","pipeline logu"],komut="gh run list",os_=HedefOS.LINUX)
        ekle("DevOps","GitHub Actions İzle",["github actions izle","gh run watch","pipeline izle"],komut="gh run watch",os_=HedefOS.LINUX)
        ekle("DevOps","Terraform Init",["terraform init","terraform başlat","infra başlat"],komut="terraform init",os_=HedefOS.LINUX)
        ekle("DevOps","Terraform Plan",["terraform plan","infra planı","terraform ne yapacak"],komut="terraform plan",os_=HedefOS.LINUX)
        ekle("DevOps","Terraform Apply",["terraform uygula","terraform apply","infra oluştur"],komut="terraform apply",os_=HedefOS.LINUX)
        ekle("DevOps","Terraform Destroy",["terraform sil","terraform destroy","infra kaldır"],komut="terraform destroy",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DevOps","Ansible Playbook",["ansible çalıştır","ansible playbook","otomasyon çalıştır"],komut="ansible-playbook",os_=HedefOS.LINUX)
        ekle("DevOps","Ansible Ping",["ansible ping","sunucu bağlantı test","ansible host test"],komut="ansible all -m ping",os_=HedefOS.LINUX)
        ekle("DevOps","Jenkins Başlat",["jenkins başlat","jenkins servis","ci sunucu başlat"],komut="sudo systemctl start jenkins",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DevOps","SonarQube Tara",["sonarqube tara","kod kalite tara","sonar analiz"],komut="sonar-scanner",os_=HedefOS.LINUX)
        ekle("DevOps","Makefile Çalıştır",["make çalıştır","makefile","make komutu"],komut="make",os_=HedefOS.LINUX)
        ekle("DevOps","Make Build",["make build","projeyi derle make","make ile derleme"],komut="make build",os_=HedefOS.LINUX)
        ekle("DevOps","Make Test",["make test","make ile test","makefile testler"],komut="make test",os_=HedefOS.LINUX)
        ekle("DevOps","Make Clean",["make clean","make temizle","derleme dosyalarını sil"],komut="make clean",os_=HedefOS.LINUX)
        ekle("DevOps","CMake Kur",["cmake kur","cmake build","c++ derle cmake"],komut="cmake -B build && cmake --build build",os_=HedefOS.LINUX)
        ekle("DevOps","Cargo Build",["cargo build","rust derle","rust proje"],komut="cargo build --release",os_=HedefOS.LINUX)
        ekle("DevOps","Cargo Test",["cargo test","rust test","rust testler"],komut="cargo test",os_=HedefOS.LINUX)
        ekle("DevOps","Go Build",["go build","golang derle","go proje"],komut="go build ./...",os_=HedefOS.LINUX)
        ekle("DevOps","Go Test",["go test","golang test","go testler"],komut="go test ./...",os_=HedefOS.LINUX)
        ekle("DevOps","Maven Build",["maven build","mvn build","java maven derle"],komut="mvn package",os_=HedefOS.LINUX)
        ekle("DevOps","Gradle Build",["gradle build","gradle derle","java gradle"],komut="./gradlew build",os_=HedefOS.LINUX)

        # ── Batch-5: Ofis ve PDF ──────────────────────────────────────────
        ekle("OfisAraç","LibreOffice Dönüştür PDF",["pdf dönüştür libreoffice","libreoffice headless","docx pdf yap"],komut="libreoffice --headless --convert-to pdf",os_=HedefOS.LINUX)
        ekle("OfisAraç","LibreOffice Dönüştür DOCX",["odt docx çevir","libreoffice docx","word formatına çevir"],komut="libreoffice --headless --convert-to docx",os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF Birleştir",["pdf birleştir","pdfunite","pdf dosyalarını birleştir"],komut="pdfunite dosya1.pdf dosya2.pdf çıktı.pdf",os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF Böl",["pdf böl","pdfseparate","pdf sayfa ayır"],komut="pdfseparate kaynak.pdf sayfa-%d.pdf",os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF Sayfa Çıkar",["pdf sayfa çıkar","pdf belirli sayfa","pdftk extract"],komut="pdftk girdi.pdf cat 1-5 output çıktı.pdf",os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF Metin Çıkar",["pdf metin çıkar","pdftotext","pdf içeriği oku"],komut="pdftotext dosya.pdf -",os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF Sıkıştır",["pdf sıkıştır","gs compress pdf","pdf boyutu küçült"],komut="gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook -dNOPAUSE -dQUIET -dBATCH -sOutputFile=çıktı.pdf girdi.pdf",os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF Şifrele",["pdf şifrele","pdftk encrypt","pdf parola koy"],komut='pdftk girdi.pdf output şifreli.pdf user_pw "şifre"',os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF Şifre Kaldır",["pdf şifre kaldır","pdftk decrypt","pdf kilidi aç"],komut='pdftk şifreli.pdf input_pw "şifre" output açık.pdf',os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF Görüntüle",["pdf görüntüle","evince pdf","pdf aç"],komut="evince",os_=HedefOS.LINUX)
        ekle("OfisAraç","PDF OCR",["pdf ocr","tesseract pdf","pdf metin tanı"],komut="tesseract girdi.png çıktı -l tur pdf",os_=HedefOS.LINUX)
        ekle("OfisAraç","Görüntüden Metin",["resimden metin çıkar","ocr tesseract","fotoğrafı metne çevir"],komut="tesseract görüntü.png çıktı",os_=HedefOS.LINUX)
        ekle("OfisAraç","Pandoc Dönüştür",["pandoc dönüştür","markdown html","belge formatı değiştir"],komut="pandoc -f markdown -t html dosya.md -o çıktı.html",os_=HedefOS.LINUX)
        ekle("OfisAraç","Pandoc Word",["pandoc word","markdown docx","pandoc docx"],komut="pandoc dosya.md -o çıktı.docx",os_=HedefOS.LINUX)
        ekle("OfisAraç","Pandoc PDF",["pandoc pdf","markdown pdf","pandoc pdf oluştur"],komut="pandoc dosya.md -o çıktı.pdf",os_=HedefOS.LINUX)
        ekle("OfisAraç","Onlyoffice Aç",["onlyoffice aç","onlyoffice belge","online office"],komut="onlyoffice-desktopeditors &",os_=HedefOS.LINUX)
        ekle("OfisAraç","Okular PDF",["okular aç","kde pdf görüntüle","okular belge"],komut="okular",os_=HedefOS.LINUX)
        ekle("OfisAraç","Foxit PDF",["foxit aç","foxit pdf","foxit reader"],komut="FoxitReader",os_=HedefOS.LINUX)

        # ── Batch-5: Bulut Hizmetleri ─────────────────────────────────────
        ekle("BulutHizmet","AWS CLI Versiyon",["aws cli versiyonu","aws version","hangi aws"],komut="aws --version",os_=HedefOS.LINUX)
        ekle("BulutHizmet","AWS S3 Listele",["aws s3 listele","s3 bucket listesi","aws dosyalar"],komut="aws s3 ls",os_=HedefOS.LINUX)
        ekle("BulutHizmet","AWS S3 Kopyala",["aws s3 kopyala","s3 upload","dosyayı s3 ye yükle"],komut="aws s3 cp",os_=HedefOS.LINUX)
        ekle("BulutHizmet","AWS EC2 Listele",["aws ec2 listele","ec2 sunucuları","aws instances"],komut="aws ec2 describe-instances --output table",os_=HedefOS.LINUX)
        ekle("BulutHizmet","AWS Profil",["aws profil listesi","aws configure list","aws kimlik"],komut="aws configure list",os_=HedefOS.LINUX)
        ekle("BulutHizmet","GCloud Versiyon",["gcloud versiyonu","google cloud version","hangi gcloud"],komut="gcloud --version",os_=HedefOS.LINUX)
        ekle("BulutHizmet","GCloud Auth",["gcloud giriş","gcloud auth","google cloud login"],komut="gcloud auth login",os_=HedefOS.LINUX)
        ekle("BulutHizmet","GCloud Proje Listesi",["gcloud proje listesi","google cloud projeler","gcloud projects"],komut="gcloud projects list",os_=HedefOS.LINUX)
        ekle("BulutHizmet","GCloud Compute Listesi",["gcloud vm listesi","compute engine listesi","google vm"],komut="gcloud compute instances list",os_=HedefOS.LINUX)
        ekle("BulutHizmet","Azure CLI Versiyon",["azure cli versiyonu","az version","hangi azure"],komut="az --version",os_=HedefOS.LINUX)
        ekle("BulutHizmet","Azure Login",["azure giriş","az login","microsoft cloud login"],komut="az login",os_=HedefOS.LINUX)
        ekle("BulutHizmet","Rclone Listele",["rclone listele","bulut dosyaları","rclone ls"],komut="rclone ls",os_=HedefOS.LINUX)
        ekle("BulutHizmet","Rclone Kopyala",["rclone kopyala","bulut yedek","rclone copy"],komut="rclone copy",os_=HedefOS.LINUX)
        ekle("BulutHizmet","Rclone Senkronize",["rclone senkronize","bulut sync","rclone sync"],komut="rclone sync",os_=HedefOS.LINUX)
        ekle("BulutHizmet","Nextcloud Senkronize",["nextcloud senkronize","nextcloud sync","özel bulut sync"],komut="nextcloudcmd -u kullanici -p sifre /yerel https://nextcloud.sunucu.com",os_=HedefOS.LINUX)

        # ── Batch-5: Programlama Dil Araçları ────────────────────────────
        ekle("ProgramlamaDil","Java Versiyonu",["java versiyonu","java version","hangi java"],komut="java --version",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Java Derle",["java derle","javac","java compile"],komut="javac",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Java Çalıştır",["java çalıştır","java run","jar çalıştır"],komut="java -jar",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","PHP Versiyonu",["php versiyonu","php version","hangi php"],komut="php --version",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","PHP Sunucu",["php sunucu","php -S","php dev server"],komut="php -S localhost:8000",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","PHP Composer",["composer kur","php composer install","bağımlılıkları kur composer"],komut="composer install",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Ruby Versiyonu",["ruby versiyonu","ruby version","hangi ruby"],komut="ruby --version",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Gem Kur",["gem kur","ruby gem install","ruby paket yükle"],komut="gem install",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Bundle Kur",["bundle kur","bundler install","ruby bağımlılıkları"],komut="bundle install",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Rails Sunucu",["rails sunucu","rails server","ruby on rails başlat"],komut="rails server",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Kotlin Derle",["kotlin derle","kotlinc","kotlin compile"],komut="kotlinc",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Swift Çalıştır",["swift çalıştır","swift run","swift dosya"],komut="swift",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Perl Çalıştır",["perl çalıştır","perl run","perl dosya"],komut="perl",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Lua Çalıştır",["lua çalıştır","lua run","lua dosya"],komut="lua",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","R Çalıştır",["r çalıştır","rscript","r dilinde çalıştır"],komut="Rscript",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","R Studio Aç",["r studio aç","rstudio","r ide"],komut="rstudio &",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Octave Çalıştır",["octave çalıştır","matlab alternatif","gnu octave"],komut="octave",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Scala Çalıştır",["scala çalıştır","scala repl","scala konsolu"],komut="scala",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Elixir Çalıştır",["elixir çalıştır","iex","elixir repl"],komut="iex",os_=HedefOS.LINUX)
        ekle("ProgramlamaDil","Haskell GHCi",["haskell çalıştır","ghci","haskell repl"],komut="ghci",os_=HedefOS.LINUX)

        # ── Batch-6: Ağ Teşhis Araçları ──────────────────────────────────
        ekle("AğTeşhis","Ping",["ping at","ping komutu","sunucu erişilebilir mi"],komut="ping -c 4",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Sürekli Ping",["sürekli ping","ping -i","ping durma"],komut="ping -i 0.5",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Traceroute",["traceroute","paketi izle","yol izle"],komut="traceroute",os_=HedefOS.LINUX)
        ekle("AğTeşhis","MTR",["mtr","ağ yol analizi","ping traceroute birlikte"],komut="mtr",os_=HedefOS.LINUX)
        ekle("AğTeşhis","DNS Sorgula",["dns sorgula","nslookup","alan adı çöz"],komut="nslookup",os_=HedefOS.LINUX)
        ekle("AğTeşhis","dig DNS",["dig komutu","dns detaylı sorgula","dns kayıt"],komut="dig",os_=HedefOS.LINUX)
        ekle("AğTeşhis","dig MX",["mx kaydı sorgula","dig mx","mail sunucu sorgula"],komut="dig MX",os_=HedefOS.LINUX)
        ekle("AğTeşhis","dig AAAA",["ipv6 adresi sorgula","dig aaaa","ipv6 dns"],komut="dig AAAA",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Ters DNS",["ters dns","reverse dns","ip adresinden alan adı"],komut="dig -x",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Hosts Dosyası",["hosts dosyası","etc hosts","dns lokal"],komut="cat /etc/hosts",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Hosts Düzenle",["hosts dosyası düzenle","dns lokal düzenle","etc hosts ekle"],komut="sudo nano /etc/hosts",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("AğTeşhis","Resolv Conf",["dns sunucusu","resolv.conf","nameserver ayarı"],komut="cat /etc/resolv.conf",os_=HedefOS.LINUX)
        ekle("AğTeşhis","IP Yönlendirme",["yönlendirme tablosu","route tablosu","ip route"],komut="ip route show",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Arp Tablosu",["arp tablosu","mac adresi tablosu","yerel ağ cihazlar"],komut="arp -n",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Ağ Tarama",["yerel ağ tara","nmap ağ","hangi cihazlar var"],komut="nmap -sn 192.168.1.0/24",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Hız Testi",["internet hızı","speedtest","bant genişliği test"],komut="speedtest-cli",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Hız Testi curl",["curl hız testi","indirme hızı test","wget hız"],komut="curl -o /dev/null https://speed.cloudflare.com/__down?bytes=10000000 -w '%{speed_download}'",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Paket Yakala",["paket yakala","tcpdump","ağ trafiği yakala"],komut="sudo tcpdump -i any -n",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("AğTeşhis","Wireshark Aç",["wireshark aç","ağ analizi wireshark","paket analizörü"],komut="wireshark &",os_=HedefOS.LINUX)
        ekle("AğTeşhis","IP Değiştir",["ip adresi değiştir","ip komutu","arayüze ip ata"],komut="sudo ip addr add 192.168.1.100/24 dev eth0",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("AğTeşhis","MAC Değiştir",["mac adresi değiştir","mac spoof","mac adresini değiştir"],komut="sudo ip link set eth0 address 02:01:02:03:04:05",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("AğTeşhis","Port Bağlantı Test",["porta bağlan","nc komutu","port erişilebilir mi"],komut="nc -zv 127.0.0.1 80",os_=HedefOS.LINUX)
        ekle("AğTeşhis","HTTP Test",["http test","curl http","site çalışıyor mu"],komut="curl -Is --max-time 5",os_=HedefOS.LINUX)
        ekle("AğTeşhis","Latans Ölç",["gecikme ölç","ping latency","ms ölç"],komut="ping -c 10 8.8.8.8 | tail -2",os_=HedefOS.LINUX)

        # ── Batch-6: Grafik / Tasarım ─────────────────────────────────────
        ekle("Grafik","GIMP Aç",["gimp aç","gimp resim düzenle","gimp başlat"],komut="gimp &",os_=HedefOS.LINUX)
        ekle("Grafik","Inkscape Aç",["inkscape aç","vektör çiz","svg düzenle"],komut="inkscape &",os_=HedefOS.LINUX)
        ekle("Grafik","Inkscape SVG Aç",["inkscape svg","svg dosyası aç","inkscape dosya"],komut="inkscape dosya.svg &",os_=HedefOS.LINUX)
        ekle("Grafik","Inkscape PNG Dışa Aktar",["inkscape png export","svg png çevir","inkscape export"],komut="inkscape --export-type=png --export-filename=çıktı.png girdi.svg",os_=HedefOS.LINUX)
        ekle("Grafik","Inkscape PDF Dışa Aktar",["inkscape pdf export","svg pdf çevir","inkscape pdf"],komut="inkscape --export-type=pdf --export-filename=çıktı.pdf girdi.svg",os_=HedefOS.LINUX)
        ekle("Grafik","Inkscape Boyutlandır",["inkscape boyutlandır","svg yeniden boyutlandır","inkscape resize"],komut="inkscape --export-width=800 --export-type=png --export-filename=çıktı.png girdi.svg",os_=HedefOS.LINUX)
        ekle("Grafik","Krita Aç",["krita aç","dijital çizim","krita başlat"],komut="krita &",os_=HedefOS.LINUX)
        ekle("Grafik","Darktable Aç",["darktable aç","raw fotoğraf düzenle","darktable"],komut="darktable &",os_=HedefOS.LINUX)
        ekle("Grafik","Shotwell Aç",["shotwell aç","fotoğraf galerisi","shotwell"],komut="shotwell &",os_=HedefOS.LINUX)
        ekle("Grafik","gThumb Aç",["gthumb aç","resim görüntüle","gthumb"],komut="gthumb &",os_=HedefOS.LINUX)
        ekle("Grafik","Eye of GNOME",["resim görüntüleyici","eog aç","fotoğraf aç"],komut="eog &",os_=HedefOS.LINUX)
        ekle("Grafik","Feh Resim Göster",["feh resim","terminal resim görüntüle","feh"],komut="feh",os_=HedefOS.LINUX)
        ekle("Grafik","Feh Slayt",["feh slayt","resimleri otomatik göster","feh slideshow"],komut="feh -D 3 -F",os_=HedefOS.LINUX)
        ekle("Grafik","Renk Seçici",["renk seçici","color picker","hex renk kodu al"],komut="zenity --color-selection",os_=HedefOS.LINUX)
        ekle("Grafik","Ekran Rengi Al",["ekrandan renk al","gpick","piksel rengi"],komut="gpick",os_=HedefOS.LINUX)
        ekle("Grafik","Fontları Listele",["yazı tipi listesi","font listesi","fc-list"],komut="fc-list | sort",os_=HedefOS.LINUX)
        ekle("Grafik","Font Önizleme",["font önizleme","font görüntüle","gnome font viewer"],komut="gnome-font-viewer",os_=HedefOS.LINUX)
        ekle("Grafik","SVG Optimize",["svg optimize","svgo","svg boyutu küçült"],komut="svgo girdi.svg -o çıktı.svg",os_=HedefOS.LINUX)
        ekle("Grafik","PNG Optimize",["png optimize","optipng","png boyutu küçült"],komut="optipng -o5",os_=HedefOS.LINUX)
        ekle("Grafik","JPEG Optimize",["jpeg optimize","jpegoptim","jpg boyutu küçült"],komut="jpegoptim --size=500k",os_=HedefOS.LINUX)
        ekle("Grafik","Ekran Paleti",["ekran paleti","paletli ekran","scrot renk"],komut="scrot -s ekran.png && convert ekran.png -colors 8 -unique-colors palet.png",os_=HedefOS.LINUX)

        # ── Batch-6: Oyun / Eğlence ───────────────────────────────────────
        ekle("OyunEğlence","Steam Aç",["steam aç","steam başlat","oyun platformu"],komut="steam &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Lutris Aç",["lutris aç","wine oyun","lutris başlat"],komut="lutris &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Heroic Aç",["heroic aç","epic games linux","heroic launcher"],komut="heroic &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Wine Çalıştır",["wine çalıştır","windows program çalıştır","wine exe"],komut="wine",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Wine Config",["wine ayarları","winecfg","wine yapılandırma"],komut="winecfg",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Winetricks",["winetricks","wine bileşen kur","windows dll kur"],komut="winetricks",os_=HedefOS.LINUX)
        ekle("OyunEğlence","GameMode",["gamemode aktifleştir","oyun modu","gamemoded"],komut="gamemoded -r",os_=HedefOS.LINUX)
        ekle("OyunEğlence","MangoHud",["mangohud","fps göster","oyun overlay"],komut="mangohud",os_=HedefOS.LINUX)
        ekle("OyunEğlence","RetroArch Aç",["retroarch aç","emülatör","retro oyun"],komut="retroarch &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","DOSBox Aç",["dosbox aç","dos oyun","dosbox başlat"],komut="dosbox &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Minecraft Aç",["minecraft aç","minecraft java","minecraft başlat"],komut="minecraft-launcher &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Godot Aç",["godot aç","oyun motoru","godot engine"],komut="godot &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Blender Aç",["blender aç","3d modelleme","blender başlat"],komut="blender &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","FreeCiv Aç",["freeciv aç","civilization oyunu","strateji oyunu"],komut="freeciv-gtk4 &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","0AD Aç",["0ad aç","strateji oyunu açık kaynak","0 ad"],komut="0ad &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","SuperTuxKart",["supertuxkart aç","yarış oyunu","tux kart"],komut="supertuxkart &",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Fortune",["bana bir şey söyle","fortune","rastgele alıntı"],komut="fortune",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Cowsay",["inek ne diyor","cowsay","süslü mesaj"],komut="fortune | cowsay",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Figlet",["büyük yazı","figlet","ascii sanat yazı"],komut="figlet",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Cmatrix",["matrix ekranı","cmatrix","yeşil kod yağmuru"],komut="cmatrix",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Lolcat",["renkli çıktı","lolcat","gökkuşağı renk"],komut="ls | lolcat",os_=HedefOS.LINUX)
        ekle("OyunEğlence","sl Tren",["tren geç","sl komutu","hata tren"],komut="sl",os_=HedefOS.LINUX)
        ekle("OyunEğlence","Espeak Türkçe",["espeak türkçe","hızlı tts","espeak seslendirme"],komut='espeak -v tr "Merhaba"',os_=HedefOS.LINUX)
        ekle("OyunEğlence","xeyes",["gözleri takip et","xeyes","ekran gözleri"],komut="xeyes &",os_=HedefOS.LINUX)

        # ── Batch-6: Akıllı Ev / IoT ──────────────────────────────────────
        ekle("IoT","MQTT Yayınla",["mqtt yayınla","mqtt publish","iot mesaj gönder"],komut='mosquitto_pub -h localhost -t "ev/oda/sıcaklık" -m "22"',os_=HedefOS.LINUX)
        ekle("IoT","MQTT Abone Ol",["mqtt dinle","mqtt subscribe","iot mesaj dinle"],komut='mosquitto_sub -h localhost -t "ev/#"',os_=HedefOS.LINUX)
        ekle("IoT","MQTT Sunucu",["mqtt sunucu","mosquitto başlat","mqtt broker"],komut="sudo systemctl start mosquitto",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("IoT","Home Assistant Başlat",["home assistant başlat","ha servis","akıllı ev başlat"],komut="sudo systemctl start home-assistant",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("IoT","Node-RED Başlat",["node red başlat","node-red otomasyon","iot akış"],komut="node-red &",os_=HedefOS.LINUX)
        ekle("IoT","Arduino IDE",["arduino ide","arduino başlat","mikrodenetleyici"],komut="arduino &",os_=HedefOS.LINUX)
        ekle("IoT","Arduino Yükle",["arduino yükle","arduino upload","koda yükle"],komut="arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:uno",os_=HedefOS.LINUX)
        ekle("IoT","Serial Monitor",["seri port izle","serial monitor","arduino serial"],komut="minicom -D /dev/ttyUSB0 -b 9600",os_=HedefOS.LINUX)
        ekle("IoT","Raspberry Pi SSH",["raspberry ssh","rpi bağlan","raspberry pi erişim"],komut="ssh pi@raspberrypi.local",os_=HedefOS.LINUX)
        ekle("IoT","GPIO Oku",["gpio oku","raspberry gpio","pinout"],komut="gpio readall",os_=HedefOS.LINUX)
        ekle("IoT","I2C Tara",["i2c tara","i2c cihazlar","i2c detect"],komut="sudo i2cdetect -y 1",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("IoT","USB Aygıt İzle",["usb bağlantı izle","usb hotplug","yeni usb"],komut="udevadm monitor",os_=HedefOS.LINUX)

        # ── Batch-6: Yapay Zeka / ML Araçları ────────────────────────────
        ekle("YapayZeka","Ollama Çalıştır",["ollama çalıştır","yerel ai","ollama llm"],komut="ollama run llama3",os_=HedefOS.LINUX)
        ekle("YapayZeka","Ollama Listesi",["ollama listesi","yüklü modeller ollama","ollama models"],komut="ollama list",os_=HedefOS.LINUX)
        ekle("YapayZeka","Ollama Model İndir",["ollama model indir","ollama pull","ai model çek"],komut="ollama pull",os_=HedefOS.LINUX)
        ekle("YapayZeka","Ollama Sunucu",["ollama sunucu","ollama serve","ollama api başlat"],komut="ollama serve &",os_=HedefOS.LINUX)
        ekle("YapayZeka","Stable Diffusion",["stable diffusion","resim üret","ai resim"],komut="python3 scripts/txt2img.py --prompt",os_=HedefOS.LINUX)
        ekle("YapayZeka","Whisper Transkript",["whisper transkript","sesi metne çevir","whisper asr"],komut="whisper ses.mp3 --language Turkish",os_=HedefOS.LINUX)
        ekle("YapayZeka","Hugging Face İndir",["hugging face model indir","hf model","transformers model"],komut="python3 -c \"from huggingface_hub import snapshot_download; snapshot_download(repo_id='')\"",os_=HedefOS.LINUX)
        ekle("YapayZeka","TensorFlow Versiyon",["tensorflow versiyonu","tf version","derin öğrenme versiyon"],komut='python3 -c "import tensorflow as tf; print(tf.__version__)"',os_=HedefOS.LINUX)
        ekle("YapayZeka","PyTorch Versiyon",["pytorch versiyonu","torch version","pytorch gpu"],komut='python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"',os_=HedefOS.LINUX)
        ekle("YapayZeka","GPU Bellek",["gpu bellek kullanımı","vram kullanımı","nvidia memory"],komut="nvidia-smi --query-gpu=memory.used,memory.free --format=csv",os_=HedefOS.LINUX)
        ekle("YapayZeka","Jupyter AI Başlat",["jupyter ai başlat","notebook ai","jupyter gpu"],komut="jupyter lab --ip=0.0.0.0 --no-browser",os_=HedefOS.LINUX)
        ekle("YapayZeka","MLflow Başlat",["mlflow başlat","ml tracking","mlflow ui"],komut="mlflow ui",os_=HedefOS.LINUX)

        # ── Batch-6: Uzak Masaüstü / Ekran Paylaşımı ─────────────────────
        ekle("UzakMasaüstü","VNC Server Başlat",["vnc sunucu başlat","vnc server","uzak masaüstü başlat"],komut="vncserver :1",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","VNC Server Durdur",["vnc sunucu durdur","vnc server kapat","vncserver kill"],komut="vncserver -kill :1",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","VNC Viewer Bağlan",["vnc bağlan","vncviewer","uzak masaüstüne bağlan"],komut="vncviewer",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","RDP Bağlan",["rdp bağlan","rdesktop","windows uzak masaüstü"],komut="xfreerdp /v:",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","xRDP Başlat",["xrdp başlat","rdp sunucu","uzak masaüstü linux sunucu"],komut="sudo systemctl start xrdp",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","Remmina Aç",["remmina aç","uzak bağlantı yöneticisi","remmina başlat"],komut="remmina &",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","TeamViewer Başlat",["teamviewer başlat","teamviewer","uzak destek"],komut="teamviewer &",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","AnyDesk Başlat",["anydesk başlat","anydesk","uzak masaüstü anydesk"],komut="anydesk &",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","SSH X11 Yönlendir",["ssh x11","ssh grafik","uzak gui"],komut="ssh -X",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","SPICE Bağlan",["spice bağlan","virt-viewer","sanal makine ekranı"],komut="virt-viewer --connect qemu:///system",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","Barrier Sunucu",["barrier sunucu","kvm yazılım","klavye fare paylaş"],komut="barriers --enable-crypto &",os_=HedefOS.LINUX)
        ekle("UzakMasaüstü","Barrier İstemci",["barrier istemci","barrier bağlan","kvm istemci"],komut="barrierc",os_=HedefOS.LINUX)

        # ── Batch-6: Klavye / Fare Özelleştirme ──────────────────────────
        ekle("GirişAygıt","xmodmap Listele",["xmodmap listele","tuş haritası","klavye haritası"],komut="xmodmap -pke | head -40",os_=HedefOS.LINUX)
        ekle("GirişAygıt","xmodmap Uygula",["xmodmap uygula","klavye haritası uygula","tuş haritası yükle"],komut="xmodmap ~/.Xmodmap",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Klavye Düzeni",["klavye düzeni","setxkbmap","tr klavye"],komut="setxkbmap tr",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Klavye İngilizce",["klavye ingilizce","setxkbmap us","ingilizce klavye"],komut="setxkbmap us",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Klavye Tekrar Hızı",["klavye tekrar hızı","xset r rate","tuş tekrar"],komut="xset r rate 300 50",os_=HedefOS.LINUX)
        ekle("GirişAygıt","CapsLock Kapat",["caps lock kapat","büyük harf kilidi kapat","caps devre dışı"],komut="setxkbmap -option ctrl:nocaps",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Fare Hızı",["fare hızı ayarla","mouse hızı","xinput fare"],komut="xinput --set-prop 'Mouse' 'libinput Accel Speed' 0.5",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Fare Sol El",["fare sol el","mouse sol el","fare düğmeleri değiştir"],komut="xmodmap -e 'pointer = 3 2 1'",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Fare Normal",["fare normal","mouse sağ el","fare düğmeleri normal"],komut="xmodmap -e 'pointer = 1 2 3'",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Dokunmatik Kapat",["dokunmatik kapat","touchpad devre dışı","dokunmatik fare kapat"],komut="xinput --disable $(xinput list | grep -i touchpad | grep -oP 'id=\\K[0-9]+')",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Dokunmatik Aç",["dokunmatik aç","touchpad aktifleştir","dokunmatik fare aç"],komut="xinput --enable $(xinput list | grep -i touchpad | grep -oP 'id=\\K[0-9]+')",os_=HedefOS.LINUX)
        ekle("GirişAygıt","Giriş Aygıtları",["giriş aygıtları listesi","xinput listesi","bağlı girişler"],komut="xinput list",os_=HedefOS.LINUX)
        ekle("GirişAygıt","xdotool Tık",["xdotool ile tıkla","otomasyon tıklama","xdotool click"],komut="xdotool click 1",os_=HedefOS.LINUX)
        ekle("GirişAygıt","xdotool Yaz",["xdotool ile yaz","otomasyon yazma","xdotool type"],komut='xdotool type "metin"',os_=HedefOS.LINUX)
        ekle("GirişAygıt","Ekran Klavyesi",["ekran klavyesi","sanal klavye","onboard"],komut="onboard &",os_=HedefOS.LINUX)

        # ── Batch-6: Yazı Tipi Yönetimi ───────────────────────────────────
        ekle("YazıTipi","Font Yükle",["font yükle","yazı tipi kur","ttf kur"],komut="sudo cp *.ttf /usr/local/share/fonts/ && sudo fc-cache -f -v",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("YazıTipi","Font Cache Yenile",["font cache yenile","fc-cache","yazı tipi önbellek"],komut="fc-cache -f -v",os_=HedefOS.LINUX)
        ekle("YazıTipi","Font Ara",["font ara","fc-list arama","yazı tipi ara"],komut="fc-list | grep -i",os_=HedefOS.LINUX)
        ekle("YazıTipi","Nerd Font Kur",["nerd font kur","programlama fontu","nerd font"],yanit="https://www.nerdfonts.com/font-downloads adresinden indirip ~/.local/share/fonts/ dizinine kopyalayın.",tur="konusma",os_=HedefOS.LINUX)
        ekle("YazıTipi","Google Font Kur",["google font kur","web fontu kur","google fonts"],komut="sudo apt install fonts-urw-base35",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ── Batch-6: Erişilebilirlik Genişletilmiş ───────────────────────
        ekle("Erişilebilirlik","Orca Ekran Okuyucu",["orca başlat","ekran okuyucu","görme engelli mod"],komut="orca &",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Orca Durdur",["orca durdur","ekran okuyucu kapat","orca kapat"],komut="pkill orca",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Büyüteç Aç",["büyüteç aç","ekran büyüteci","gnome-magnifier"],komut="gsettings set org.gnome.desktop.a11y.magnifier screen-position full-screen && gsettings set org.gnome.desktop.a11y applications screen-magnifier-enabled true",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Büyüteç Kapat",["büyüteç kapat","ekran büyüteci kapat","magnifier off"],komut="gsettings set org.gnome.desktop.a11y.applications screen-magnifier-enabled false",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Kontrast Artır",["kontrast artır","yüksek kontrast","high contrast mod"],komut="gsettings set org.gnome.desktop.interface gtk-theme 'HighContrast'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Kontrast Normal",["kontrast normal","normal tema","high contrast kapat"],komut="gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita'",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Metin Büyüt",["metin büyüt","yazı boyutu artır","dpi büyüt"],komut="gsettings set org.gnome.desktop.interface text-scaling-factor 1.5",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Metin Normal",["metin normal boyut","yazı boyutu sıfırla","dpi normal"],komut="gsettings set org.gnome.desktop.interface text-scaling-factor 1.0",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Yapışkan Tuşlar",["yapışkan tuşlar","sticky keys","erişilebilirlik tuşlar"],komut="gsettings set org.gnome.desktop.a11y.keyboard stickykeys-enable true",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Yavaş Tuşlar",["yavaş tuşlar","slow keys","tuş gecikmesi"],komut="gsettings set org.gnome.desktop.a11y.keyboard slowkeys-enable true",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Zil Sesi Görsel",["zil görsel","görsel uyarı","a11y bell"],komut="gsettings set org.gnome.desktop.a11y.interface visual-bell true",os_=HedefOS.LINUX)
        ekle("Erişilebilirlik","Renk Körlüğü Filtresi",["renk körlüğü filtresi","deuteranopia","renk görme filtresi"],komut="pkexec dbus-send --system --print-reply --dest=org.gnome.ColorManager /org/gnome/ColorManager org.gnome.ColorManager.GetProfilesForDevice",os_=HedefOS.LINUX)

        # ── Batch-6: Sistem Bilgi ve Raporlama ────────────────────────────
        ekle("SistemRapor","Tam Sistem Raporu",["sistem raporu","sistem bilgi raporu","sistem özeti tam"],komut="echo '=== UNAME ===' && uname -a && echo '=== CPU ===' && lscpu | grep 'Model name' && echo '=== RAM ===' && free -h && echo '=== DISK ===' && df -h && echo '=== IP ===' && ip addr | grep 'inet '",os_=HedefOS.LINUX)
        ekle("SistemRapor","Açılış Süresi",["açılış süresi","boot süresi","sistem ne zaman başladı"],komut="systemd-analyze",os_=HedefOS.LINUX)
        ekle("SistemRapor","Açılış Servis Süreleri",["açılış servis süreleri","boot blame","hangi servis ne kadar sürdü"],komut="systemd-analyze blame | head -20",os_=HedefOS.LINUX)
        ekle("SistemRapor","Kritik Loglar",["kritik loglar","hata logları","önemli sistem logları"],komut="journalctl -p 3 -xb",os_=HedefOS.LINUX)
        ekle("SistemRapor","Bellek Sızıntısı",["bellek sızıntısı","valgrind","memory leak"],komut="valgrind --leak-check=full",os_=HedefOS.LINUX)
        ekle("SistemRapor","Strace",["strace","sistem çağrısı izle","process syscall"],komut="strace -p",os_=HedefOS.LINUX)
        ekle("SistemRapor","lsof Açık Dosyalar",["açık dosyalar","lsof","hangi dosya açık"],komut="lsof | head -30",os_=HedefOS.LINUX)
        ekle("SistemRapor","lsof Port",["hangi uygulama portu kullanıyor","lsof port","port kullanan uygulama"],komut="sudo lsof -i :",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("SistemRapor","Kernel Versiyon",["kernel versiyonu","linux çekirdek","uname -r"],komut="uname -r",os_=HedefOS.LINUX)
        ekle("SistemRapor","BIOS/UEFI Bilgisi",["bios bilgisi","uefi versiyon","dmidecode"],komut="sudo dmidecode -t bios",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("SistemRapor","Anakart Bilgisi",["anakart bilgisi","motherboard info","dmidecode board"],komut="sudo dmidecode -t baseboard",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("SistemRapor","RAM Bilgisi",["ram bilgisi","bellek tipi","dmidecode memory"],komut="sudo dmidecode -t memory | grep -E 'Size|Speed|Type'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("SistemRapor","CPU Özellikleri",["cpu özellikleri","işlemci bayrakları","lscpu tam"],komut="lscpu",os_=HedefOS.LINUX)
        ekle("SistemRapor","GPU Bilgisi",["gpu bilgisi","ekran kartı","lspci gpu"],komut="lspci | grep -i vga",os_=HedefOS.LINUX)
        ekle("SistemRapor","Ses Aygıtları",["ses aygıtları","soundcard listesi","aplay -l"],komut="aplay -l",os_=HedefOS.LINUX)
        ekle("SistemRapor","Batarya Sağlığı",["batarya sağlığı","pil kapasitesi","upower pil"],komut="upower -i $(upower -e | grep BAT) | grep -E 'capacity|percentage|state'",os_=HedefOS.LINUX)

        # ── Batch-7: GNOME Masaüstü Tam ───────────────────────────────────
        ekle("GNOME","GNOME Shell Yeniden Başlat",["gnome shell yeniden başlat","masaüstü sıfırla","alt f2 r"],komut="killall -3 gnome-shell",os_=HedefOS.LINUX)
        ekle("GNOME","GNOME Oturum Kapat",["gnome oturum kapat","gnome logout","oturumu kapat"],komut="gnome-session-quit --logout --no-prompt",os_=HedefOS.LINUX)
        ekle("GNOME","GNOME Kilitle",["gnome ekran kilitle","masaüstü kilitle","gnome-screensaver"],komut="gnome-screensaver-command -l",os_=HedefOS.LINUX)
        ekle("GNOME","GNOME Ekran Koruyucu",["ekran koruyucu","screensaver aç","gnome screensaver"],komut="gnome-screensaver-command -a",os_=HedefOS.LINUX)
        ekle("GNOME","Duvar Kağıdı Değiştir",["duvar kağıdı değiştir","masaüstü arkaplanı","wallpaper değiştir"],komut='gsettings set org.gnome.desktop.background picture-uri "file:///yol/resim.jpg"',os_=HedefOS.LINUX)
        ekle("GNOME","Duvar Kağıdı Renk",["arkaplan rengi","masaüstü renk","solid color background"],komut="gsettings set org.gnome.desktop.background primary-color '#1a1a2e'",os_=HedefOS.LINUX)
        ekle("GNOME","Karanlık Tema",["karanlık tema","dark mode gnome","gece teması"],komut="gsettings set org.gnome.desktop.interface color-scheme prefer-dark",os_=HedefOS.LINUX)
        ekle("GNOME","Açık Tema",["açık tema","light mode gnome","beyaz tema"],komut="gsettings set org.gnome.desktop.interface color-scheme prefer-light",os_=HedefOS.LINUX)
        ekle("GNOME","GNOME Tweaks",["gnome tweaks","masaüstü ince ayar","gnome tweak tool"],komut="gnome-tweaks &",os_=HedefOS.LINUX)
        ekle("GNOME","GNOME Uzantılar",["gnome uzantılar","extensions gnome","gnome extension manager"],komut="gnome-extensions-app &",os_=HedefOS.LINUX)
        ekle("GNOME","Uzantı Listesi",["uzantı listesi","etkin uzantılar","gnome-extensions list"],komut="gnome-extensions list --enabled",os_=HedefOS.LINUX)
        ekle("GNOME","Uzantı Etkinleştir",["uzantı etkinleştir","gnome-extensions enable","extension aç"],komut="gnome-extensions enable",os_=HedefOS.LINUX)
        ekle("GNOME","Uzantı Devre Dışı",["uzantı kapat","gnome-extensions disable","extension kapat"],komut="gnome-extensions disable",os_=HedefOS.LINUX)
        ekle("GNOME","Dock Göster",["dock göster","görev çubuğu göster","panel göster"],komut="gsettings set org.gnome.shell.extensions.dash-to-dock dock-fixed true",os_=HedefOS.LINUX)
        ekle("GNOME","Dock Gizle",["dock gizle","görev çubuğu gizle","autohide dock"],komut="gsettings set org.gnome.shell.extensions.dash-to-dock autohide true",os_=HedefOS.LINUX)
        ekle("GNOME","Animasyonlar Kapat",["animasyonlar kapat","gnome animasyon kapat","efektleri kapat"],komut="gsettings set org.gnome.desktop.interface enable-animations false",os_=HedefOS.LINUX)
        ekle("GNOME","Animasyonlar Aç",["animasyonlar aç","gnome animasyon aç","efektleri aç"],komut="gsettings set org.gnome.desktop.interface enable-animations true",os_=HedefOS.LINUX)
        ekle("GNOME","Tuş Bağlantıları Listele",["kısayol listesi","keybindings gnome","gnome kısayollar"],komut="gsettings list-recursively org.gnome.settings-daemon.plugins.media-keys",os_=HedefOS.LINUX)
        ekle("GNOME","Özel Kısayol Ekle",["özel kısayol ekle","gnome custom shortcut","yeni klavye kısayolu"],yanit="dconf-editor ile org.gnome.settings-daemon.plugins.media-keys.custom-keybindings yolunu düzenleyin.",tur="konusma",os_=HedefOS.LINUX)
        ekle("GNOME","Workspace Sayısı",["çalışma alanı sayısı","workspace kaç","gnome workspace"],komut="gsettings set org.gnome.desktop.wm.preferences num-workspaces 4",os_=HedefOS.LINUX)
        ekle("GNOME","Dinamik Workspace",["dinamik çalışma alanı","dynamic workspaces","otomatik workspace"],komut="gsettings set org.gnome.mutter dynamic-workspaces true",os_=HedefOS.LINUX)
        ekle("GNOME","Dosya Yöneticisi Listesi",["nautilus listesi","dosyaları listele","ls ile aç"],komut="nautilus --browser &",os_=HedefOS.LINUX)
        ekle("GNOME","Dosyalar Açık",["dosyalar aç","nautilus başlat","dosya yöneticisi aç"],komut="nautilus &",os_=HedefOS.LINUX)
        ekle("GNOME","dconf Düzenle",["dconf düzenle","gnome ayarları derin","dconf-editor"],komut="dconf-editor &",os_=HedefOS.LINUX)
        ekle("GNOME","gsettings Sıfırla",["gsettings sıfırla","gnome ayarları sıfırla","varsayılan gnome"],komut="dconf reset -f /org/gnome/",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ── Batch-7: KDE Plasma ───────────────────────────────────────────
        ekle("KDE","KDE Plasma Yeniden Başlat",["kde yeniden başlat","plasma restart","plasmashell resetle"],komut="kquitapp5 plasmashell && kstart5 plasmashell",os_=HedefOS.LINUX)
        ekle("KDE","KDE Kilitle",["kde ekran kilitle","plasma kilitle","kscreenlocker"],komut="loginctl lock-session",os_=HedefOS.LINUX)
        ekle("KDE","KDE Oturum Kapat",["kde oturum kapat","plasma logout","kde çıkış"],komut="qdbus org.kde.ksmserver /KSMServer logout 0 0 0",os_=HedefOS.LINUX)
        ekle("KDE","KDE Duvar Kağıdı",["kde duvar kağıdı","plasma wallpaper","kde arkaplan"],komut='qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript \'var allDesktops = desktops(); for (i=0;i<allDesktops.length;i++) { d = allDesktops[i]; d.wallpaperPlugin = "org.kde.image"; d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General"); d.writeConfig("Image", "file:///yol/resim.jpg"); }\'',os_=HedefOS.LINUX)
        ekle("KDE","KDE Tema",["kde tema değiştir","plasma tema","kde görünüm"],komut="lookandfeeltool --apply",os_=HedefOS.LINUX)
        ekle("KDE","KDE Sistem Ayarları",["kde ayarlar","kde system settings","plasma ayarları"],komut="systemsettings5 &",os_=HedefOS.LINUX)
        ekle("KDE","KDE Widget Ekle",["kde widget ekle","plasma widget","panel widget"],komut="plasma-browser-integration-host &",os_=HedefOS.LINUX)
        ekle("KDE","KWin Efektler",["kwin efektler","masaüstü efektleri","kde efekt"],komut="qdbus org.kde.KWin /Effects org.kde.kwin.Effects.isEffectLoaded blur",os_=HedefOS.LINUX)
        ekle("KDE","Dolphin Aç",["dolphin aç","kde dosya yöneticisi","dolphin başlat"],komut="dolphin &",os_=HedefOS.LINUX)
        ekle("KDE","Spectacle Ekran Görüntüsü",["spectacle ekran görüntüsü","kde screenshot","plasma ekran al"],komut="spectacle -b -n -o ekran.png",os_=HedefOS.LINUX)

        # ── Batch-7: Masaüstü Ortamları (Genel) ──────────────────────────
        ekle("Masaüstü","XFCE Başlat",["xfce başlat","xfce masaüstü","xfce4-session"],komut="xfce4-session",os_=HedefOS.LINUX)
        ekle("Masaüstü","XFCE Ayarlar",["xfce ayarları","xfce4-settings-manager","xfce yapılandırma"],komut="xfce4-settings-manager &",os_=HedefOS.LINUX)
        ekle("Masaüstü","LXDE Başlat",["lxde başlat","lxde masaüstü","openbox"],komut="openbox --reconfigure",os_=HedefOS.LINUX)
        ekle("Masaüstü","i3 Config",["i3 config","i3wm yapılandırma","tiling window manager"],komut="nano ~/.config/i3/config",os_=HedefOS.LINUX)
        ekle("Masaüstü","i3 Yeniden Yükle",["i3 yeniden yükle","i3 reload","i3 config uygula"],komut="i3-msg reload",os_=HedefOS.LINUX)
        ekle("Masaüstü","i3 Yeniden Başlat",["i3 yeniden başlat","i3 restart","i3 sıfırla"],komut="i3-msg restart",os_=HedefOS.LINUX)
        ekle("Masaüstü","Sway Config",["sway config","sway yapılandırma","wayland tiling"],komut="nano ~/.config/sway/config",os_=HedefOS.LINUX)
        ekle("Masaüstü","Rofi Başlatıcı",["rofi başlatıcı","uygulama başlatıcı rofi","rofi run"],komut="rofi -show run",os_=HedefOS.LINUX)
        ekle("Masaüstü","dmenu Başlatıcı",["dmenu başlatıcı","dmenu_run","hızlı uygulama başlat"],komut="dmenu_run",os_=HedefOS.LINUX)
        ekle("Masaüstü","Polybar Başlat",["polybar başlat","status bar polybar","polybar"],komut="polybar &",os_=HedefOS.LINUX)
        ekle("Masaüstü","Picom Compositor",["picom compositor","masaüstü compositor","pencere şeffaflığı"],komut="picom --experimental-backends &",os_=HedefOS.LINUX)
        ekle("Masaüstü","Compton Compositor",["compton compositor","compton başlat","eski compositor"],komut="compton &",os_=HedefOS.LINUX)
        ekle("Masaüstü","Nitrogen Duvar Kağıdı",["nitrogen duvar kağıdı","wallpaper nitrogen","masaüstü arkaplan ayarla"],komut="nitrogen &",os_=HedefOS.LINUX)
        ekle("Masaüstü","Feh Duvar Kağıdı",["feh duvar kağıdı","wallpaper feh","feh --bg-scale"],komut="feh --bg-scale ~/Resimler/duvar.jpg",os_=HedefOS.LINUX)
        ekle("Masaüstü","Conky Sistem İzle",["conky başlat","masaüstü sistem bilgisi","conky monitor"],komut="conky &",os_=HedefOS.LINUX)

        # ── Batch-7: Terminal Çoklayıcılar ────────────────────────────────
        ekle("Tmux","tmux Başlat",["tmux başlat","tmux aç","terminal multiplexer"],komut="tmux",os_=HedefOS.LINUX)
        ekle("Tmux","tmux Yeni Oturum",["tmux yeni oturum","tmux new session","tmux session oluştur"],komut="tmux new-session -s ana",os_=HedefOS.LINUX)
        ekle("Tmux","tmux Oturumları Listele",["tmux oturumları","tmux list sessions","tmux sessions"],komut="tmux list-sessions",os_=HedefOS.LINUX)
        ekle("Tmux","tmux Oturuma Bağlan",["tmux oturuma bağlan","tmux attach","tmux resume"],komut="tmux attach-session -t ana",os_=HedefOS.LINUX)
        ekle("Tmux","tmux Oturumu Kapat",["tmux oturumu kapat","tmux kill session","tmux session sil"],komut="tmux kill-session -t ana",os_=HedefOS.LINUX)
        ekle("Tmux","tmux Pencere Böl Yatay",["tmux yatay böl","tmux split horizontal","tmux pane"],komut='tmux split-window -h',os_=HedefOS.LINUX)
        ekle("Tmux","tmux Pencere Böl Dikey",["tmux dikey böl","tmux split vertical","tmux alt panel"],komut='tmux split-window -v',os_=HedefOS.LINUX)
        ekle("Tmux","tmux Yeni Pencere",["tmux yeni pencere","tmux new window","tmux window oluştur"],komut="tmux new-window",os_=HedefOS.LINUX)
        ekle("Tmux","tmux Config",["tmux config","tmux yapılandırma","tmux.conf düzenle"],komut="nano ~/.tmux.conf",os_=HedefOS.LINUX)
        ekle("Tmux","Screen Başlat",["screen başlat","gnu screen","terminal screen"],komut="screen",os_=HedefOS.LINUX)
        ekle("Tmux","Screen Listele",["screen listele","screen oturumları","screen -ls"],komut="screen -ls",os_=HedefOS.LINUX)
        ekle("Tmux","Screen Bağlan",["screen bağlan","screen resume","screen attach"],komut="screen -r",os_=HedefOS.LINUX)
        ekle("Tmux","Zellij Başlat",["zellij başlat","modern terminal multiplexer","zellij"],komut="zellij",os_=HedefOS.LINUX)

        # ── Batch-7: Dosya Arama / Yönetimi ──────────────────────────────
        ekle("DosyaArama","Dosya Bul",["dosya bul","find komutu","dosya ara"],komut='find . -name "*.py" -type f',os_=HedefOS.LINUX)
        ekle("DosyaArama","Yeni Dosyalar",["yeni dosyalar","son değiştirilen","son dosyalar"],komut="find . -newer /tmp -maxdepth 2 -type f | head -20",os_=HedefOS.LINUX)
        ekle("DosyaArama","Büyük Dosya Bul",["büyük dosya bul","100mb üzeri dosya","büyük dosyalar"],komut="find / -size +100M -type f 2>/dev/null | head -20",os_=HedefOS.LINUX)
        ekle("DosyaArama","Boş Dosyalar",["boş dosyalar","sıfır byte dosya","empty files"],komut="find . -empty -type f",os_=HedefOS.LINUX)
        ekle("DosyaArama","İzin Sorunlu Dosyalar",["izin sorunlu dosyalar","dünyaya açık dosya","777 dosyalar"],komut="find . -perm 777 -type f",os_=HedefOS.LINUX)
        ekle("DosyaArama","fd Bul",["fd ile bul","fd komutu","hızlı dosya arama"],komut="fd",os_=HedefOS.LINUX)
        ekle("DosyaArama","fzf Fuzzy Ara",["fzf fuzzy","bulanık dosya arama","fzf"],komut="fzf",os_=HedefOS.LINUX)
        ekle("DosyaArama","fzf ile Aç",["fzf ile dosya aç","fuzzy open","fzf nano"],komut='nano $(fzf)',os_=HedefOS.LINUX)
        ekle("DosyaArama","ripgrep Ara",["ripgrep ara","rg komutu","hızlı kod arama"],komut="rg",os_=HedefOS.LINUX)
        ekle("DosyaArama","locate Bul",["locate bul","locate komutu","hızlı dosya yolu"],komut="locate",os_=HedefOS.LINUX)
        ekle("DosyaArama","locate Güncelle",["locate veritabanı güncelle","updatedb","locate db"],komut="sudo updatedb",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DosyaArama","Dosya Kopyala",["dosya kopyala","cp komutu","copy file"],komut="cp -r",os_=HedefOS.LINUX)
        ekle("DosyaArama","Dosya Taşı",["dosya taşı","mv komutu","move file"],komut="mv",os_=HedefOS.LINUX)
        ekle("DosyaArama","Dosya Sil",["dosya sil","rm komutu","delete file"],komut="rm",os_=HedefOS.LINUX)
        ekle("DosyaArama","Klasör Sil",["klasör sil","rm -rf","dizin sil"],komut="rm -rf",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DosyaArama","Sembolik Link",["sembolik link oluştur","ln -s","symlink"],komut="ln -s kaynak hedef",os_=HedefOS.LINUX)
        ekle("DosyaArama","İzin Değiştir",["izin değiştir","chmod komutu","dosya izni"],komut="chmod 755",os_=HedefOS.LINUX)
        ekle("DosyaArama","Sahip Değiştir",["sahip değiştir","chown komutu","dosya sahibi"],komut="sudo chown -R",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("DosyaArama","Gizli Dosyalar",["gizli dosyalar","ls -la","nokta dosyalar"],komut="ls -la",os_=HedefOS.LINUX)
        ekle("DosyaArama","Ağaç Görünümü",["ağaç görünümü","tree komutu","dizin ağacı"],komut="tree -L 3",os_=HedefOS.LINUX)

        # ── Batch-7: Kablosuz ve Bluetooth Genişletilmiş ──────────────────
        ekle("Kablosuz","WiFi Şifre Göster",["wifi şifre göster","bağlı ağın şifresi","nmcli şifre"],komut='sudo grep -r "psk=" /etc/NetworkManager/system-connections/ | grep -v "psk-flags"',yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Kablosuz","WiFi QR Kodu",["wifi qr kodu","wifi qr","wifi paylaş qr"],komut='qrencode -t ansiutf8 "WIFI:S:$(nmcli -t -f NAME con show --active | head -1);T:WPA;P:şifre;;"',os_=HedefOS.LINUX)
        ekle("Kablosuz","Bluetooth Cihaz Bağlan",["bluetooth bağlan","bluetoothctl connect","bt cihaz bağla"],komut="bluetoothctl connect",os_=HedefOS.LINUX)
        ekle("Kablosuz","Bluetooth Cihaz Kes",["bluetooth kes","bluetoothctl disconnect","bt bağlantı kes"],komut="bluetoothctl disconnect",os_=HedefOS.LINUX)
        ekle("Kablosuz","Bluetooth Eşleştir",["bluetooth eşleştir","bluetoothctl pair","bt pair"],komut="bluetoothctl pair",os_=HedefOS.LINUX)
        ekle("Kablosuz","Bluetooth Tara",["bluetooth tara","bluetoothctl scan","bt cihaz tara"],komut="bluetoothctl scan on",os_=HedefOS.LINUX)
        ekle("Kablosuz","Bluetooth Ses",["bluetooth kulaklık","bluetooth ses","bt audio"],komut="pactl list sinks | grep -i bluetooth",os_=HedefOS.LINUX)
        ekle("Kablosuz","WiFi Kanal Analizi",["wifi kanal analizi","wifi kanal","iwlist kanal"],komut="sudo iwlist scan 2>/dev/null | grep -E 'ESSID|Channel|Signal'",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Kablosuz","WiFi Sinyal Gücü",["wifi sinyal gücü","iwconfig sinyal","kablosuz sinyal"],komut="iwconfig 2>/dev/null | grep -i signal",os_=HedefOS.LINUX)
        ekle("Kablosuz","WiFi Bağlantı Bilgisi",["wifi bağlantı bilgisi","iwconfig","kablosuz bağlantı detayı"],komut="iwconfig",os_=HedefOS.LINUX)

        # ── Batch-7: PulseAudio / PipeWire Ses Yönetimi ───────────────────
        ekle("SesYönetim","PulseAudio Yeniden Başlat",["pulseaudio yeniden başlat","ses sunucu resetle","pulseaudio restart"],komut="pulseaudio -k && pulseaudio --start",os_=HedefOS.LINUX)
        ekle("SesYönetim","PipeWire Yeniden Başlat",["pipewire yeniden başlat","pipewire restart","ses sunucu pipewire"],komut="systemctl --user restart pipewire",os_=HedefOS.LINUX)
        ekle("SesYönetim","Ses Çıkışı Listesi",["ses çıkışları","pactl sink listesi","hoparlör listesi"],komut="pactl list short sinks",os_=HedefOS.LINUX)
        ekle("SesYönetim","Ses Girişi Listesi",["ses girişleri","pactl source listesi","mikrofon listesi"],komut="pactl list short sources",os_=HedefOS.LINUX)
        ekle("SesYönetim","Varsayılan Çıkış",["varsayılan ses çıkışı","pactl default sink","ses çıkışı değiştir"],komut="pactl set-default-sink",os_=HedefOS.LINUX)
        ekle("SesYönetim","Varsayılan Giriş",["varsayılan mikrofon","pactl default source","mikrofon değiştir"],komut="pactl set-default-source",os_=HedefOS.LINUX)
        ekle("SesYönetim","Ses Seviyesi Ayarla",["ses seviyesi yüzde","pactl volume","ses yüzde"],komut="pactl set-sink-volume @DEFAULT_SINK@ 70%",os_=HedefOS.LINUX)
        ekle("SesYönetim","Ses Arttır pactl",["ses artır pactl","ses up pactl","ses yükselt"],komut="pactl set-sink-volume @DEFAULT_SINK@ +5%",os_=HedefOS.LINUX)
        ekle("SesYönetim","Ses Azalt pactl",["ses azalt pactl","ses down pactl","ses kıs"],komut="pactl set-sink-volume @DEFAULT_SINK@ -5%",os_=HedefOS.LINUX)
        ekle("SesYönetim","Sessiz Geçiş",["sessiz geçiş","pactl mute toggle","sesi aç kapat"],komut="pactl set-sink-mute @DEFAULT_SINK@ toggle",os_=HedefOS.LINUX)
        ekle("SesYönetim","Mikrofon Sessiz",["mikrofon sessiz","mikrofon mute","pactl mikrofon"],komut="pactl set-source-mute @DEFAULT_SOURCE@ toggle",os_=HedefOS.LINUX)
        ekle("SesYönetim","pavucontrol Aç",["pavucontrol aç","ses denetim masası","pulseaudio gui"],komut="pavucontrol &",os_=HedefOS.LINUX)
        ekle("SesYönetim","alsamixer Aç",["alsamixer aç","alsa ses","terminal ses kontrolü"],komut="alsamixer",os_=HedefOS.LINUX)
        ekle("SesYönetim","ALSA Kaydet",["alsa kaydet","alsactl store","ses ayarlarını kaydet"],komut="sudo alsactl store",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("SesYönetim","EQ Yükle",["equalizer yükle","easyeffects","ses efekt"],komut="easyeffects &",os_=HedefOS.LINUX)

        # ── Batch-7: Yazıcı Yönetimi ──────────────────────────────────────
        ekle("Yazıcı","Yazıcı Listesi",["yazıcı listesi","lpstat yazıcılar","bağlı yazıcılar"],komut="lpstat -p -d",os_=HedefOS.LINUX)
        ekle("Yazıcı","Yazdır",["yazdır","lp komutu","dosyayı yzdır"],komut="lp",os_=HedefOS.LINUX)
        ekle("Yazıcı","Baskı Kuyruğu",["baskı kuyruğu","lpq komutu","baskı sırası"],komut="lpq",os_=HedefOS.LINUX)
        ekle("Yazıcı","Baskı İptal",["baskı iptal","lprm komutu","yazdırmayı durdur"],komut="lprm",os_=HedefOS.LINUX)
        ekle("Yazıcı","CUPS Yönetim",["cups yönetim","yazıcı web arayüzü","cups admin"],komut="xdg-open http://localhost:631",os_=HedefOS.LINUX)
        ekle("Yazıcı","CUPS Servis",["cups başlat","yazıcı servisi","cups daemon"],komut="sudo systemctl start cups",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Yazıcı","Yazıcı Ekle",["yazıcı ekle","lpadmin","yeni yazıcı kur"],komut="sudo lpadmin -p",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Yazıcı","PDF Yazdır",["pdf yazdır","lp pdf","pdf baskı"],komut="lp dosya.pdf",os_=HedefOS.LINUX)

        # ── Batch-7: Tarama (Scanner) ─────────────────────────────────────
        ekle("Tarayıcı","Tarayıcı Listesi",["tarayıcı listesi","scanimage listesi","bağlı tarayıcılar"],komut="scanimage -L",os_=HedefOS.LINUX)
        ekle("Tarayıcı","Belge Tara",["belge tara","scanimage tara","tarayıcı kullan"],komut="scanimage --format=png > tarama.png",os_=HedefOS.LINUX)
        ekle("Tarayıcı","Basit Tarama",["basit tarama","simple-scan aç","gnome tarayıcı"],komut="simple-scan &",os_=HedefOS.LINUX)
        ekle("Tarayıcı","GIMP ile Tara",["gimp ile tara","gimp scanner","gimp tarayıcı"],komut="gimp --no-splash &",os_=HedefOS.LINUX)
        ekle("Tarayıcı","Tarama DPI",["300 dpi tara","yüksek kalite tara","scanimage dpi"],komut="scanimage --resolution 300 --format=tiff > tarama.tiff",os_=HedefOS.LINUX)

        # ── Batch-7: Enerji Yönetimi ──────────────────────────────────────
        ekle("EnerjiYönetim","TLP Durumu",["tlp durumu","pil optimizasyonu","tlp-stat"],komut="sudo tlp-stat -s",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","TLP Başlat",["tlp başlat","pil tasarrufu aç","tlp start"],komut="sudo tlp start",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","CPU Governor",["cpu governor","işlemci modu","powersave performance"],komut="cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","Powersave Modu",["powersave modu","güç tasarrufu modu","cpu yavaşlat"],komut='echo powersave | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor',yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","Performance Modu",["performance modu","yüksek performans modu","cpu hızlandır"],komut='echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor',yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","Ekran Kapatma Süresi",["ekran kapanma süresi","xset dpms","ekran uyku"],komut="xset dpms 120 300 600",os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","Ekran Uyku Kapat",["ekran uyku kapat","dpms kapat","ekranı uyutma"],komut="xset -dpms && xset s off",os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","Güç Profili",["güç profili","power profile","powerprofilesctl"],komut="powerprofilesctl list",os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","Güç İstatistik",["güç istatistik","powertop","enerji tüketimi"],komut="sudo powertop --time=5",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("EnerjiYönetim","Şarj Limiti",["şarj limiti","batarya şarj sınırı","charge threshold"],komut="cat /sys/class/power_supply/BAT0/charge_control_end_threshold",os_=HedefOS.LINUX)

        # ── Batch-7: Sanal Makine ─────────────────────────────────────────
        ekle("SanalMakine","VirtualBox Aç",["virtualbox aç","vbox başlat","sanal makine aç"],komut="virtualbox &",os_=HedefOS.LINUX)
        ekle("SanalMakine","VBoxManage Listesi",["virtualbox vm listesi","vboxmanage listesi","sanal makineler"],komut="VBoxManage list vms",os_=HedefOS.LINUX)
        ekle("SanalMakine","VBoxManage Başlat",["virtualbox vm başlat","vboxmanage startvm","sanal makine çalıştır"],komut="VBoxManage startvm",os_=HedefOS.LINUX)
        ekle("SanalMakine","VBoxManage Durdur",["virtualbox vm durdur","vboxmanage poweroff","sanal makine kapat"],komut="VBoxManage controlvm poweroff",os_=HedefOS.LINUX)
        ekle("SanalMakine","QEMU Çalıştır",["qemu çalıştır","qemu vm","hızlı sanal makine"],komut="qemu-system-x86_64 -m 2G -enable-kvm",os_=HedefOS.LINUX)
        ekle("SanalMakine","virt-manager Aç",["virt-manager aç","kvm yönetici","libvirt gui"],komut="virt-manager &",os_=HedefOS.LINUX)
        ekle("SanalMakine","Vagrant Başlat",["vagrant başlat","vagrant up","geliştirme vm"],komut="vagrant up",os_=HedefOS.LINUX)
        ekle("SanalMakine","Vagrant SSH",["vagrant ssh","vagrant makineye gir","vagrant shell"],komut="vagrant ssh",os_=HedefOS.LINUX)
        ekle("SanalMakine","Vagrant Durdur",["vagrant durdur","vagrant halt","geliştirme vm kapat"],komut="vagrant halt",os_=HedefOS.LINUX)
        ekle("SanalMakine","Vagrant Destroy",["vagrant sil","vagrant destroy","geliştirme vm sil"],komut="vagrant destroy",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # XFCE — Debian 12 / Ubuntu
        # ════════════════════════════════════════════════════════════════════
        ekle("XFCE","XFCE Paneli Yeniden Başlat",["xfce panel yeniden başlat","xfce4-panel resetle","panel resetle xfce"],komut="xfce4-panel -r",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Panel Ayarları",["xfce panel ayarları","xfce4-panel preferences","panel tercihler"],komut="xfce4-panel --preferences",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Masaüstü Yenile",["xfce masaüstü yenile","xfdesktop reload","xfce reload"],komut="xfdesktop --reload",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Uygulama Bulucu",["xfce uygulama başlatıcı","xfce4-appfinder","uygulama bul xfce"],komut="xfce4-appfinder",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Görev Yöneticisi",["xfce görev yöneticisi","xfce4-taskmanager","xfce sistem izle"],komut="xfce4-taskmanager &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Terminal",["xfce terminali","xfce4-terminal","xfce terminal aç"],komut="xfce4-terminal &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Terminal Drop-Down",["xfce açılır terminal","xfce drop down terminal","xfce4-terminal drop"],komut="xfce4-terminal --drop-down",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Dosya Yöneticisi",["xfce dosya yöneticisi","thunar aç","thunar"],komut="thunar &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Ayarlar Yöneticisi",["xfce ayarlar","xfce4-settings-manager","xfce kontrol paneli"],komut="xfce4-settings-manager &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Görünüm Ayarları",["xfce görünüm","xfce4-appearance-settings","xfce tema ayarı"],komut="xfce4-appearance-settings &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Ekran Ayarları",["xfce ekran ayarları","xfce4-display-settings","xfce monitör"],komut="xfce4-display-settings &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Klavye Ayarları",["xfce klavye ayarları","xfce4-keyboard-settings","xfce klavye"],komut="xfce4-keyboard-settings &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Fare Ayarları",["xfce fare ayarları","xfce4-mouse-settings","xfce mouse"],komut="xfce4-mouse-settings &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Güç Yöneticisi",["xfce güç yöneticisi","xfce4-power-manager","xfce pil ayarı"],komut="xfce4-power-manager-settings &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Oturum Yöneticisi",["xfce oturum yöneticisi","xfce4-session-settings","xfce başlangıç"],komut="xfce4-session-settings &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Duvar Kağıdı",["xfce duvar kağıdı","xfdesktop wallpaper","xfce arka plan"],komut="xfdesktop-settings &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Pencere Yöneticisi",["xfce pencere yöneticisi","xfwm4-settings","xfce window manager"],komut="xfwm4-settings &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Bildirim Ayarları",["xfce bildirim ayarları","xfce4-notifyd-config","xfce notification"],komut="xfce4-notifyd-config &",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Ekran Görüntüsü",["xfce ekran görüntüsü","xfce4-screenshooter","xfce screenshot"],komut="xfce4-screenshooter",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Ekran Görüntüsü Tam",["xfce tam ekran görüntüsü","xfce4-screenshooter fullscreen","xfce screenshot tam ekran"],komut="xfce4-screenshooter -f",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Ekran Görüntüsü Alan",["xfce alan ekran görüntüsü","xfce4-screenshooter region","xfce bölge al"],komut="xfce4-screenshooter -r",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Renk Seçici",["xfce renk seçici","xfce4-colorchooser","xfce renk kodu"],komut="xfce4-colorchooser",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Kilit Ekranı",["xfce kilitle","xfce4-screensaver","xfce ekran kilitle"],komut="xflock4",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Oturumu Kapat",["xfce oturumu kapat","xfce logout","xfce çıkış"],komut="xfce4-session-logout",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Uyku",["xfce uyku","xfce suspend","xfce askıya al"],komut="xfce4-session-logout --suspend",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Kapat",["xfce kapat","xfce shutdown","xfce sistemi kapat"],komut="xfce4-session-logout --halt",os_=HedefOS.LINUX)
        ekle("XFCE","XFCE Yeniden Başlat",["xfce yeniden başlat","xfce reboot","xfce restart"],komut="xfce4-session-logout --reboot",os_=HedefOS.LINUX)
        ekle("XFCE","Mousepad Metin Editörü",["mousepad aç","xfce metin editörü","mousepad"],komut="mousepad &",os_=HedefOS.LINUX)
        ekle("XFCE","Ristretto Resim Görüntüle",["ristretto aç","xfce resim görüntüle","ristretto"],komut="ristretto &",os_=HedefOS.LINUX)
        ekle("XFCE","Parole Medya",["parole aç","xfce medya oynatıcı","parole medya"],komut="parole &",os_=HedefOS.LINUX)
        ekle("XFCE","Gigolo Ağ Bağlantısı",["gigolo aç","xfce ağ sürücüsü","gigolo"],komut="gigolo &",os_=HedefOS.LINUX)
        # Debian 12 spesifik
        ekle("XFCE","Debian Güncelle",["debian güncelle","debian update","debian paket güncelle"],komut="sudo apt update && sudo apt full-upgrade -y",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("XFCE","Debian Kaynak Listesi",["debian kaynak listesi","debian sources.list","debian repo"],komut="cat /etc/apt/sources.list",os_=HedefOS.LINUX)
        ekle("XFCE","Debian Sürümü",["debian sürümü","debian version","hangi debian"],komut="cat /etc/debian_version",os_=HedefOS.LINUX)
        ekle("XFCE","Debian Codename",["debian kod adı","debian codename","bookworm bullseye"],komut="lsb_release -sc",os_=HedefOS.LINUX)
        ekle("XFCE","Debian Katkı Etkinleştir",["debian contrib non-free","debian katkı","non-free etkinleştir"],komut='sudo sed -i "s/main/main contrib non-free non-free-firmware/" /etc/apt/sources.list && sudo apt update',yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("XFCE","Debian Firmware Kur",["debian firmware kur","wifi firmware","sürücü firmware"],komut="sudo apt install firmware-linux firmware-linux-nonfree",yetki=["ABİ"],os_=HedefOS.LINUX)
        # Ubuntu spesifik
        ekle("XFCE","Ubuntu Sürümü",["ubuntu sürümü","ubuntu version","hangi ubuntu"],komut="lsb_release -a",os_=HedefOS.LINUX)
        ekle("XFCE","Ubuntu LTS Yükselt",["ubuntu yükselt","ubuntu upgrade","lts versiyona geç"],komut="sudo do-release-upgrade",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("XFCE","Ubuntu Sürücüler",["ubuntu sürücüler","ubuntu-drivers","önerilen sürücüler"],komut="ubuntu-drivers list",os_=HedefOS.LINUX)
        ekle("XFCE","Ubuntu Sürücü Kur",["ubuntu sürücü kur","nvidia sürücü","ubuntu otomatik sürücü"],komut="sudo ubuntu-drivers install",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("XFCE","Ubuntu Snap Store",["snap store aç","ubuntu yazılım merkezi","snap-store"],komut="snap-store &",os_=HedefOS.LINUX)
        ekle("XFCE","Xubuntu Güncelle",["xubuntu güncelle","xfce ubuntu güncelle","xubuntu update"],komut="sudo apt update && sudo apt dist-upgrade -y",yetki=["ABİ"],os_=HedefOS.LINUX)

        # ════════════════════════════════════════════════════════════════════
        # WINDOWS 10
        # ════════════════════════════════════════════════════════════════════
        ekle("Windows10","Dosya Gezgini Aç",["dosya gezgini aç","windows gezgin","explorer aç"],komut_w="explorer.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Görev Yöneticisi",["windows görev yöneticisi","task manager","ctrl alt del"],komut_w="taskmgr.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Denetim Masası",["denetim masası","control panel","windows ayarlar"],komut_w="control.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Sistem Bilgisi",["windows sistem bilgisi","msinfo32","sistem bilgisi windows"],komut_w="msinfo32.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Aygıt Yöneticisi",["aygıt yöneticisi","device manager","sürücüler windows"],komut_w="devmgmt.msc",os_=HedefOS.WINDOWS)
        ekle("Windows10","Disk Yöneticisi",["windows disk yöneticisi","diskmgmt","disk bölüm windows"],komut_w="diskmgmt.msc",os_=HedefOS.WINDOWS)
        ekle("Windows10","Hizmetler",["windows hizmetler","services.msc","servisler windows"],komut_w="services.msc",os_=HedefOS.WINDOWS)
        ekle("Windows10","Kayıt Defteri",["kayıt defteri","regedit","registry windows"],komut_w="regedit.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Görev Zamanlayıcı",["görev zamanlayıcı","task scheduler","zamanlanmış görev windows"],komut_w="taskschd.msc",os_=HedefOS.WINDOWS)
        ekle("Windows10","Olay Görüntüleyici",["olay görüntüleyici","event viewer","windows log"],komut_w="eventvwr.msc",os_=HedefOS.WINDOWS)
        ekle("Windows10","Sistem Özellikleri",["sistem özellikleri","sysdm.cpl","bilgisayar özellikleri"],komut_w="sysdm.cpl",os_=HedefOS.WINDOWS)
        ekle("Windows10","Windows Güncelleme",["windows güncelle","windows update","windows güncelleme aç"],komut_w="ms-settings:windowsupdate",os_=HedefOS.WINDOWS)
        ekle("Windows10","Windows Ayarları",["windows ayarları aç","settings windows","windows settings"],komut_w="ms-settings:",os_=HedefOS.WINDOWS)
        ekle("Windows10","Windows Güvenlik Duvarı",["windows güvenlik duvarı","firewall windows","wf.msc"],komut_w="wf.msc",os_=HedefOS.WINDOWS)
        ekle("Windows10","Windows Defender",["windows defender","virüs koruması","windows güvenlik"],komut_w="ms-settings:windowsdefender",os_=HedefOS.WINDOWS)
        ekle("Windows10","Ekran Görüntüsü",["windows ekran görüntüsü","win prtsc","snipping tool"],komut_w="snippingtool.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Ekran Kaydı",["windows ekran kaydı","xbox game bar kayıt","win g"],komut_w="ms-gamebar:",os_=HedefOS.WINDOWS)
        ekle("Windows10","Bildirim Merkezi",["bildirim merkezi aç","action center","windows bildirimler"],komut_w="ms-actioncenter:",os_=HedefOS.WINDOWS)
        ekle("Windows10","Sanal Masaüstü",["windows sanal masaüstü","win tab","task view"],komut_w="explorer.exe shell:::{3080F90E-D7AD-11D9-BD98-0000947B0257}",os_=HedefOS.WINDOWS)
        ekle("Windows10","Çalıştır",["çalıştır windows","win r","run dialog"],komut_w="rundll32.exe shell32.dll,#61",os_=HedefOS.WINDOWS)
        ekle("Windows10","Cmd Aç",["cmd aç","komut istemi","command prompt"],komut_w="cmd.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","PowerShell Aç",["powershell aç","ps terminal","windows powershell"],komut_w="powershell.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","PowerShell Yönetici",["powershell yönetici","powershell admin","ps yönetici"],komut_w="powershell -Command \"Start-Process powershell -Verb RunAs\"",os_=HedefOS.WINDOWS)
        ekle("Windows10","Windows Terminal",["windows terminal","wt aç","modern terminal"],komut_w="wt.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","IP Adresi",["windows ip adresi","ipconfig","windows network"],komut_w="ipconfig /all",os_=HedefOS.WINDOWS)
        ekle("Windows10","IP Yenile",["windows ip yenile","ipconfig renew","dhcp yenile"],komut_w="ipconfig /release && ipconfig /renew",os_=HedefOS.WINDOWS)
        ekle("Windows10","DNS Temizle",["windows dns temizle","ipconfig flushdns","dns cache sil"],komut_w="ipconfig /flushdns",os_=HedefOS.WINDOWS)
        ekle("Windows10","Ağ Sıfırla",["windows ağ sıfırla","netsh winsock reset","ağ sorun gider"],komut_w="netsh winsock reset && netsh int ip reset",os_=HedefOS.WINDOWS)
        ekle("Windows10","Wifi Şifre Göster",["windows wifi şifresi","netsh wifi şifre","kablosuz şifre windows"],komut_w="netsh wlan show profile name=\"%SSID%\" key=clear",os_=HedefOS.WINDOWS)
        ekle("Windows10","Disk Temizle",["windows disk temizle","cleanmgr","gereksiz dosya sil"],komut_w="cleanmgr.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Disk Hata Denetle",["disk hata denetle","chkdsk","windows disk kontrol"],komut_w="chkdsk C: /f /r",os_=HedefOS.WINDOWS)
        ekle("Windows10","SFC Tara",["sfc tara","sistem dosyası denetle","sfc /scannow"],komut_w="sfc /scannow",os_=HedefOS.WINDOWS)
        ekle("Windows10","DISM Onar",["dism onar","windows image onar","dism restorehealth"],komut_w="DISM /Online /Cleanup-Image /RestoreHealth",os_=HedefOS.WINDOWS)
        ekle("Windows10","Başlangıç Programları",["başlangıç programları windows","startup programs","msconfig"],komut_w="msconfig.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Performans İzle",["windows performans izle","perfmon","resource monitor"],komut_w="perfmon.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Bağlantı Noktaları",["windows açık portlar","netstat windows","aktif bağlantılar"],komut_w="netstat -ano",os_=HedefOS.WINDOWS)
        ekle("Windows10","Kullanıcı Hesapları",["windows kullanıcılar","netplwiz","kullanıcı hesap yönetimi"],komut_w="netplwiz.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Grup İlkeleri",["grup ilkeleri","gpedit","local policy"],komut_w="gpedit.msc",os_=HedefOS.WINDOWS)
        ekle("Windows10","Yazı Tipi Klasörü",["windows font klasörü","yazı tipleri","fonts windows"],komut_w="explorer C:\\Windows\\Fonts",os_=HedefOS.WINDOWS)
        ekle("Windows10","Geçici Dosyalar",["geçici dosyalar sil","temp klasörü","windows temp"],komut_w="explorer %TEMP%",os_=HedefOS.WINDOWS)
        ekle("Windows10","Prefetch Temizle",["prefetch temizle","windows prefetch","başlangıç önbellek"],komut_w="del /q /f C:\\Windows\\Prefetch\\*",os_=HedefOS.WINDOWS)
        ekle("Windows10","Ses Ayarları",["windows ses ayarları","mmsys.cpl","sound settings"],komut_w="mmsys.cpl",os_=HedefOS.WINDOWS)
        ekle("Windows10","Çözünürlük Ayarları",["windows çözünürlük","desk.cpl","ekran ayarları windows"],komut_w="desk.cpl",os_=HedefOS.WINDOWS)
        ekle("Windows10","Güç Ayarları",["windows güç ayarları","powercfg.cpl","enerji planı"],komut_w="powercfg.cpl",os_=HedefOS.WINDOWS)
        ekle("Windows10","Program Kaldır",["program kaldır windows","appwiz.cpl","uygulama kaldır"],komut_w="appwiz.cpl",os_=HedefOS.WINDOWS)
        ekle("Windows10","Sistem Geri Yükleme",["sistem geri yükleme","rstrui","restore point"],komut_w="rstrui.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","BitLocker",["bitlocker yönet","bitlocker aç","disk şifreleme windows"],komut_w="manage-bde -status",os_=HedefOS.WINDOWS)
        ekle("Windows10","WSL Listesi",["wsl listesi","linux subsystem listesi","wsl -l"],komut_w="wsl --list --verbose",os_=HedefOS.WINDOWS)
        ekle("Windows10","WSL Başlat",["wsl başlat","linux subsystem başlat","wsl ubuntu"],komut_w="wsl",os_=HedefOS.WINDOWS)
        ekle("Windows10","Winget Ara",["winget ara","winget search","windows paket ara"],komut_w="winget search",os_=HedefOS.WINDOWS)
        ekle("Windows10","Winget Kur",["winget kur","winget install","windows paket yükle"],komut_w="winget install",os_=HedefOS.WINDOWS)
        ekle("Windows10","Winget Güncelle",["winget güncelle","winget upgrade","windows paket güncelle"],komut_w="winget upgrade --all",os_=HedefOS.WINDOWS)
        ekle("Windows10","Chocolatey Kur",["chocolatey kur","choco install","choco paket"],komut_w="choco install",os_=HedefOS.WINDOWS)
        ekle("Windows10","Chocolatey Güncelle",["chocolatey güncelle","choco upgrade","choco all"],komut_w="choco upgrade all -y",os_=HedefOS.WINDOWS)
        ekle("Windows10","Hyper-V Başlat",["hyper-v başlat","hyper-v vm","virtmgmt"],komut_w="virtmgmt.msc",os_=HedefOS.WINDOWS)
        ekle("Windows10","Uzak Masaüstü",["uzak masaüstü windows","mstsc","rdp windows"],komut_w="mstsc.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Notepad Aç",["not defteri aç","notepad","windows metin editörü"],komut_w="notepad.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Hesap Makinesi",["hesap makinesi windows","calc","windows calculator"],komut_w="calc.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Paint Aç",["paint aç","mspaint","windows resim"],komut_w="mspaint.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Wordpad Aç",["wordpad aç","wordpad","windows belgeler"],komut_w="wordpad.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Windows Media Player",["windows media player","wmp aç","wmplayer"],komut_w="wmplayer.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Karakter Eşlemesi",["karakter eşlemesi","charmap","özel karakter windows"],komut_w="charmap.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Büyüteç",["büyüteç windows","magnify","windows büyüteç"],komut_w="magnify.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Anlatıcı",["anlatıcı windows","narrator","windows ekran okuyucu"],komut_w="narrator.exe",os_=HedefOS.WINDOWS)
        ekle("Windows10","Ekran Klavyesi Win",["ekran klavyesi windows","osk","on-screen keyboard windows"],komut_w="osk.exe",os_=HedefOS.WINDOWS)

        # ════════════════════════════════════════════════════════════════════
        # ANDROID / TERMUX
        # ════════════════════════════════════════════════════════════════════
        ekle("Android","Termux Paket Güncelle",["termux güncelle","termux update","android paket güncelle"],komut_a="pkg update && pkg upgrade -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux Paket Kur",["termux paket kur","pkg install","android uygulama kur termux"],komut_a="pkg install",os_=HedefOS.ANDROID)
        ekle("Android","Termux Paket Listesi",["termux paket listesi","pkg list-installed","kurulu termux paketler"],komut_a="pkg list-installed",os_=HedefOS.ANDROID)
        ekle("Android","Termux Depolama",["termux depolama izni","termux-setup-storage","dahili depolama eriş"],komut_a="termux-setup-storage",os_=HedefOS.ANDROID)
        ekle("Android","Termux SSH Sunucu",["termux ssh sunucu","sshd başlat android","termux openssh"],komut_a="pkg install openssh -y && sshd",os_=HedefOS.ANDROID)
        ekle("Android","Termux SSH Bağlan",["termux ssh bağlan","android ssh client","termux ssh"],komut_a="ssh",os_=HedefOS.ANDROID)
        ekle("Android","Termux Python",["termux python","android python","python termux"],komut_a="pkg install python -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux Node",["termux node","android nodejs","node termux"],komut_a="pkg install nodejs -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux Git",["termux git","android git","git termux"],komut_a="pkg install git -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux Vim",["termux vim","android vim","vim termux"],komut_a="pkg install vim -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux wget",["termux wget","android wget","wget termux"],komut_a="pkg install wget -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux curl",["termux curl","android curl","curl termux"],komut_a="pkg install curl -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux Nmap",["termux nmap","android nmap","nmap termux"],komut_a="pkg install nmap -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux Metasploit",["termux metasploit","android msf","msfconsole termux"],komut_a="pkg install unstable-repo -y && pkg install metasploit -y",yetki=["ABİ"],os_=HedefOS.ANDROID)
        ekle("Android","Termux Proot Distro",["termux linux kur","proot distro","android linux"],komut_a="pkg install proot-distro -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux Ubuntu Kur",["termux ubuntu kur","proot ubuntu","android ubuntu"],komut_a="proot-distro install ubuntu",os_=HedefOS.ANDROID)
        ekle("Android","Termux Ubuntu Gir",["termux ubuntu gir","proot ubuntu login","android ubuntu shell"],komut_a="proot-distro login ubuntu",os_=HedefOS.ANDROID)
        ekle("Android","Termux Debian Kur",["termux debian kur","proot debian","android debian"],komut_a="proot-distro install debian",os_=HedefOS.ANDROID)
        ekle("Android","Termux Masaüstü",["termux masaüstü","termux-vnc","android xfce"],komut_a="pkg install x11-repo -y && pkg install tigervnc xfce4 -y",os_=HedefOS.ANDROID)
        ekle("Android","Termux VNC Başlat",["termux vnc başlat","vncserver android","android uzak masaüstü"],komut_a="vncserver :1 -geometry 1280x720 -depth 24",os_=HedefOS.ANDROID)
        ekle("Android","Termux Bildirim",["termux bildirim","termux-notification","android bildirim gönder"],komut_a='termux-notification --title "Zihin Köprüsü" --content',os_=HedefOS.ANDROID)
        ekle("Android","Termux Titreşim",["android titreşim","termux-vibrate","telefon titret"],komut_a="termux-vibrate -d 500",os_=HedefOS.ANDROID)
        ekle("Android","Termux Pil Durumu",["android pil termux","termux-battery-status","telefon batarya termux"],komut_a="termux-battery-status",os_=HedefOS.ANDROID)
        ekle("Android","Termux Konum",["android konum termux","termux-location","gps konum termux"],komut_a="termux-location",os_=HedefOS.ANDROID)
        ekle("Android","Termux Kamera",["android kamera termux","termux-camera-photo","fotoğraf çek termux"],komut_a="termux-camera-photo foto.jpg",os_=HedefOS.ANDROID)
        ekle("Android","Termux Mikrofon",["android mikrofon termux","termux-microphone-record","ses kaydet termux"],komut_a="termux-microphone-record -l 10 -f ses.aac",os_=HedefOS.ANDROID)
        ekle("Android","Termux Ses Çal",["android ses çal termux","termux-media-player","müzik çal termux"],komut_a="termux-media-player play",os_=HedefOS.ANDROID)
        ekle("Android","Termux TTS",["android tts termux","termux-tts-speak","android sesli söyle"],komut_a='termux-tts-speak -l tr "Merhaba"',os_=HedefOS.ANDROID)
        ekle("Android","Termux Kopyala",["android panoya kopyala","termux-clipboard-set","termux clipboard"],komut_a='echo "metin" | termux-clipboard-set',os_=HedefOS.ANDROID)
        ekle("Android","Termux Yapıştır",["android panodan yapıştır","termux-clipboard-get","termux paste"],komut_a="termux-clipboard-get",os_=HedefOS.ANDROID)
        ekle("Android","Termux Torch",["android el feneri","termux-torch","telefon feneri"],komut_a="termux-torch on",os_=HedefOS.ANDROID)
        ekle("Android","Termux Torch Kapat",["android el feneri kapat","termux-torch off","telefon feneri kapat"],komut_a="termux-torch off",os_=HedefOS.ANDROID)
        ekle("Android","Termux WiFi Info",["android wifi bilgisi","termux-wifi-connectioninfo","wifi bilgisi termux"],komut_a="termux-wifi-connectioninfo",os_=HedefOS.ANDROID)
        ekle("Android","Termux Telefon Ara",["android arama yap","termux-telephony-call","numara ara termux"],komut_a="termux-telephony-call",os_=HedefOS.ANDROID)
        ekle("Android","Termux SMS Gönder",["android sms gönder","termux-sms-send","mesaj gönder termux"],komut_a='termux-sms-send -n "+905XXXXXXXXX"',os_=HedefOS.ANDROID)
        ekle("Android","Termux SMS Listesi",["android sms listesi","termux-sms-list","mesaj kutusu termux"],komut_a="termux-sms-list",os_=HedefOS.ANDROID)
        ekle("Android","Termux Kişiler",["android kişiler termux","termux-contact-list","rehber termux"],komut_a="termux-contact-list",os_=HedefOS.ANDROID)
        ekle("Android","Termux Açık Uygulamalar",["android açık uygulamalar","termux-app-info","çalışan appler"],komut_a="dumpsys activity activities | grep -i 'mresumedactivity'",os_=HedefOS.ANDROID)
        ekle("Android","Termux Hotspot",["android hotspot","termux hotspot","mobil internet paylaş"],komut_a="su -c 'svc wifi enable && am startservice -n com.android.settings/.wifi.WifiApEnabler'",yetki=["ABİ"],os_=HedefOS.ANDROID)

        # ════════════════════════════════════════════════════════════════════
        # ÇAPRAZ PLATFORM (HEPSI) — Linux / Windows / Android
        # ════════════════════════════════════════════════════════════════════
        ekle("ÇaprazPlatform","Dizin Listele",["dizin listele","ls dir","klasör içeriği"],
             komut="ls -la", komut_w="dir /a", komut_a="ls -la", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Sistem Bilgisi",["sistem bilgisi genel","os bilgisi","işletim sistemi"],
             komut="uname -a", komut_w="systeminfo | findstr /B /C:\"OS\"", komut_a="uname -a", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Ağ Bağlantısı",["ağ bağlantısı kontrol","internet var mı","bağlantı test"],
             komut="ping -c 3 8.8.8.8", komut_w="ping -n 3 8.8.8.8", komut_a="ping -c 3 8.8.8.8", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Dış IP Adresi",["dış ip adresi","public ip","wan ip"],
             komut="curl -s ifconfig.me", komut_w="curl -s ifconfig.me", komut_a="curl -s ifconfig.me", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Python Versiyon",["python versiyonu genel","python version platform","hangi python genel"],
             komut="python3 --version", komut_w="python --version", komut_a="python --version", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Git Versiyon",["git versiyon genel","git version","hangi git"],
             komut="git --version", komut_w="git --version", komut_a="git --version", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Boş Alan",["boş disk alanı","disk ne kadar boş","storage space"],
             komut="df -h /", komut_w="wmic logicaldisk get size,freespace,caption", komut_a="df -h /data", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","RAM Kullanımı",["ram kullanımı genel","bellek genel","memory usage"],
             komut="free -h", komut_w="wmic OS get TotalVisibleMemorySize,FreePhysicalMemory", komut_a="free -h", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","CPU Bilgisi",["cpu bilgisi genel","işlemci genel","processor info"],
             komut="lscpu | grep 'Model name'", komut_w="wmic cpu get name", komut_a="cat /proc/cpuinfo | grep 'model name' | head -1", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Çalışma Dizini",["çalışma dizini","pwd print working","hangi klasördeyim"],
             komut="pwd", komut_w="cd", komut_a="pwd", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Tarih Saat",["tarih saat genel","date time platform","sistem saati"],
             komut="date", komut_w="echo %DATE% %TIME%", komut_a="date", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Ortam Değişkeni",["ortam değişkeni genel","env variable","path değişkeni"],
             komut="printenv PATH", komut_w="echo %PATH%", komut_a="printenv PATH", os_=HedefOS.HEPSI)
        ekle("ÇaprazPlatform","Çıkış",["çıkış terminal","terminali kapat","exit shell"],
             komut="exit", komut_w="exit", komut_a="exit", os_=HedefOS.HEPSI)

        # ── Batch-8: Genel Devam — Güvenlik / Pentest ─────────────────────
        ekle("Pentest","Nmap Tam Tarama",["nmap tam tarama","nmap -A","kapsamlı port tarama"],komut="nmap -A -T4",os_=HedefOS.LINUX)
        ekle("Pentest","Nmap Hızlı",["nmap hızlı","nmap -F","nmap fast scan"],komut="nmap -F",os_=HedefOS.LINUX)
        ekle("Pentest","Nmap UDP",["nmap udp tarama","nmap -sU","udp port tarama"],komut="sudo nmap -sU",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Nmap OS Tespit",["nmap os tespit","işletim sistemi tespiti","nmap -O"],komut="sudo nmap -O",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Nmap Script",["nmap script","nmap nse","nmap --script"],komut="nmap --script=",os_=HedefOS.LINUX)
        ekle("Pentest","Nikto Web Tara",["nikto tara","web güvenlik tara","nikto"],komut="nikto -h",os_=HedefOS.LINUX)
        ekle("Pentest","Gobuster Dizin",["gobuster dizin","web dizin tara","gobuster dir"],komut="gobuster dir -u http://hedef -w /usr/share/wordlists/dirb/common.txt",os_=HedefOS.LINUX)
        ekle("Pentest","Hydra Brute Force",["hydra brute force","hydra şifre kır","hydra ssh"],komut="hydra -l kullanici -P wordlist.txt ssh://hedef",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","John the Ripper",["john the ripper","şifre hash kır","john"],komut="john --wordlist=/usr/share/wordlists/rockyou.txt",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Hashcat",["hashcat","gpu şifre kır","hash crack"],komut="hashcat -m 0 -a 0 hash.txt wordlist.txt",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Sqlmap",["sqlmap","sql injection tara","veritabanı inject"],komut="sqlmap -u",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Metasploit",["metasploit","msfconsole","exploit framework"],komut="msfconsole",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Burp Suite",["burp suite","web proxy","http intercept"],komut="burpsuite &",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Aircrack-ng",["aircrack wifi kır","aircrack-ng","wifi şifre dene"],komut="aircrack-ng",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Ettercap",["ettercap","mitm saldırısı","man in middle"],komut="sudo ettercap -G",yetki=["ABİ"],os_=HedefOS.LINUX)
        ekle("Pentest","Shodan CLI",["shodan arama","shodan cli","internet cihaz ara"],komut="shodan search",os_=HedefOS.LINUX)
        ekle("Pentest","theHarvester",["theharvester","email toplama","osint theharvester"],komut="theHarvester -d example.com -l 100 -b google",os_=HedefOS.LINUX)
        ekle("Pentest","Recon-ng",["recon-ng","osint framework","bilgi toplama recon"],komut="recon-ng",os_=HedefOS.LINUX)
        ekle("Pentest","Maltego",["maltego","görsel osint","link analizi"],komut="maltego &",os_=HedefOS.LINUX)
        ekle("Pentest","Wifite",["wifite","wifi otomatik kır","wifite2"],komut="sudo wifite",yetki=["ABİ"],os_=HedefOS.LINUX)

        self.log.bilgi(KAYNAK, f"Varsayılan {len(self.komutlar)} komut yüklendi.")
