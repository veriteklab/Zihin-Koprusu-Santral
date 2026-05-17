"""
Zihin Köprüsü v7.0 – Hava Durumu & Takvim & Güncelleme

Tamamen AI'sız çalışır — açık API'ler kullanır.

1. Hava Durumu
   - wttr.in (ücretsiz, API key gerekmez)
   - Şehir adıyla veya otomatik IP konumuyla
   - Sesli okunabilir özet

2. Takvim (Google Calendar API opsiyonel)
   - Yerel .ics dosyası desteği
   - Basit etkinlik ekleme/listeleme
   - "Bugün ne var?" sesli komutu

3. Otomatik Güncelleme
   - GitHub Releases'dan versiyon kontrol
   - Yeni sürüm varsa sesli + Telegram bildirimi
   - İndirme + uygulama (opsiyonel)

"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

from .logcu import Logcu

KAYNAK = "HAVA_TAKVIM"
SURUM  = "7.0.0"
GITHUB_REPO = "KULLANICI/zihin-koprusu"


# ─────────────────────────────────────────────────────────────────────────────
# HAVA DURUMU
# ─────────────────────────────────────────────────────────────────────────────

class HavaDurumu:
    def __init__(self, logcu: Logcu):
        self.log = logcu
        self._sehir: str = "Istanbul"
        self._son_veri: Optional[dict] = None
        self._son_guncelleme: float = 0.0
        self._onbellek_sure = 1800   # 30 dakika

    def sehir_ayarla(self, sehir: str):
        self._sehir = sehir
        self._son_guncelleme = 0  # Önbelleği sıfırla

    def _guncel_mi(self) -> bool:
        import time
        return (time.time() - self._son_guncelleme) < self._onbellek_sure

    def hava_al(self, sehir: str = "",
                callback: Optional[Callable[[str], None]] = None) -> str:
        """
        wttr.in'den hava durumu çek.
        Senkron veya async (callback ile).
        """
        if callback:
            threading.Thread(
                target=lambda: callback(self._hava_cek(sehir)),
                daemon=True
            ).start()
            return "Hava durumu alınıyor..."
        return self._hava_cek(sehir)

    def _hava_cek(self, sehir: str = "") -> str:
        hedef = sehir or self._sehir
        try:
            import urllib.request
            # wttr.in JSON formatı
            url = (f"https://wttr.in/{urllib.request.quote(hedef)}"
                   f"?format=j1&lang=tr")
            req = urllib.request.Request(url, headers={
                "User-Agent": "ZihinKoprusu/7.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                veri = json.loads(r.read())

            self._son_veri = veri
            return self._veri_isle(veri, hedef)

        except Exception as e:
            self.log.uyari(KAYNAK, f"Hava verisi alınamadı: {e}")
            # Fallback: basit format
            try:
                import urllib.request
                url = f"https://wttr.in/{urllib.request.quote(hedef)}?format=3&lang=tr"
                req = urllib.request.Request(url, headers={
                    "User-Agent": "ZihinKoprusu/7.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    return r.read().decode("utf-8").strip()
            except Exception as e2:
                return f"Hava durumu alınamadı: {e2}"

    def _veri_isle(self, veri: dict, sehir: str) -> str:
        """JSON verisini okunabilir Türkçe metne çevir."""
        try:
            anlik = veri["current_condition"][0]
            bugun = veri["weather"][0]

            sicaklik   = anlik.get("temp_C", "?")
            hissedilen = anlik.get("FeelsLikeC", "?")
            nem        = anlik.get("humidity", "?")
            ruzgar     = anlik.get("windspeedKmph", "?")
            durum      = anlik.get("lang_tr", [{}])[0].get("value",
                          anlik.get("weatherDesc", [{}])[0].get("value", "?"))

            max_s = bugun.get("maxtempC", "?")
            min_s = bugun.get("mintempC", "?")

            ozet = (
                f"{sehir} hava durumu: {durum}. "
                f"Şu an {sicaklik}°C, hissedilen {hissedilen}°C. "
                f"Nem %{nem}, rüzgar {ruzgar} km/saat. "
                f"Gün içi en yüksek {max_s}°C, en düşük {min_s}°C."
            )
            return ozet
        except Exception as e:
            return f"Hava verisi işlenemedi: {e}"

    def uc_gun_tahmin(self, sehir: str = "") -> str:
        """3 günlük tahmin."""
        hedef = sehir or self._sehir
        if self._son_veri:
            veri = self._son_veri
        else:
            try:
                import urllib.request
                url = (f"https://wttr.in/{urllib.request.quote(hedef)}"
                       f"?format=j1&lang=tr")
                req = urllib.request.Request(url, headers={
                    "User-Agent": "ZihinKoprusu/7.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    veri = json.loads(r.read())
            except Exception as e:
                return f"Tahmin alınamadı: {e}"

        try:
            satirlar = [f"📅 {hedef} — 3 Günlük Tahmin"]
            gun_adlari = ["Bugün", "Yarın", "Öbür gün"]
            for i, gun in enumerate(veri.get("weather", [])[:3]):
                ad = gun_adlari[i] if i < len(gun_adlari) else f"Gün {i+1}"
                max_s = gun.get("maxtempC", "?")
                min_s = gun.get("mintempC", "?")
                durum = (gun.get("hourly", [{}])[4]
                         .get("lang_tr", [{}])[0]
                         .get("value", "?"))
                satirlar.append(
                    f"  {ad}: {durum}, {min_s}°C – {max_s}°C")
            return "\n".join(satirlar)
        except Exception as e:
            return f"Tahmin işlenemedi: {e}"

    def sesli_komut_isle(self, metin: str) -> Optional[str]:
        ml = metin.lower()
        if any(k in ml for k in [
            "hava durumu", "hava nasıl", "dışarıda nasıl",
            "yağmur", "kar", "sıcaklık", "bugün hava"
        ]):
            # Şehir adı var mı?
            sehir = self._sehir
            for tetik in ["hava durumu ", "hava "]:
                if tetik in ml:
                    potansiyel = ml.split(tetik)[-1].strip()
                    if potansiyel and len(potansiyel) > 2:
                        sehir = potansiyel
            return self.hava_al(sehir)

        if any(k in ml for k in ["3 günlük", "üç günlük", "tahmin"]):
            return self.uc_gun_tahmin()

        return None


# ─────────────────────────────────────────────────────────────────────────────
# TAKVİM
# ─────────────────────────────────────────────────────────────────────────────

class Takvim:
    def __init__(self, logcu: Logcu, veri_dosyasi: str):
        self.log = logcu
        self.veri_dosyasi = veri_dosyasi
        self.etkinlikler: list[dict] = []
        self._yukle()

    def _yukle(self):
        if os.path.exists(self.veri_dosyasi):
            try:
                with open(self.veri_dosyasi, encoding="utf-8") as f:
                    self.etkinlikler = json.load(f)
            except Exception as e:
                self.log.hata(KAYNAK, f"Takvim yüklenemedi: {e}")

    def kaydet(self):
        dizin = os.path.dirname(self.veri_dosyasi)
        if dizin:
            os.makedirs(dizin, exist_ok=True)
        with open(self.veri_dosyasi, "w", encoding="utf-8") as f:
            json.dump(self.etkinlikler, f, ensure_ascii=False, indent=2)

    def etkinlik_ekle(self, baslik: str, tarih: str, saat: str = "",
                       notlar: str = "") -> dict:
        """
        Etkinlik ekle.
        tarih: "2024-01-15" veya "yarın", "bugün", "pazartesi"
        saat:  "14:30"
        """
        tarih_coz = self._tarih_coz(tarih)
        etkinlik = {
            "id":     f"{int(datetime.now().timestamp())}",
            "baslik": baslik,
            "tarih":  tarih_coz,
            "saat":   saat,
            "notlar": notlar,
        }
        self.etkinlikler.append(etkinlik)
        # Tarih sıralaması
        self.etkinlikler.sort(key=lambda x: x["tarih"] + x.get("saat", ""))
        self.kaydet()
        self.log.bilgi(KAYNAK, f"Etkinlik eklendi: {baslik} — {tarih_coz}")
        return etkinlik

    def bugun_etkinlikler(self) -> list[dict]:
        bugun = datetime.now().strftime("%Y-%m-%d")
        return [e for e in self.etkinlikler if e["tarih"] == bugun]

    def yakin_etkinlikler(self, gun: int = 7) -> list[dict]:
        simdi = datetime.now()
        bitis = simdi + timedelta(days=gun)
        sonuc = []
        for e in self.etkinlikler:
            try:
                tarih = datetime.strptime(e["tarih"], "%Y-%m-%d")
                if simdi.date() <= tarih.date() <= bitis.date():
                    sonuc.append(e)
            except ValueError:
                pass
        return sonuc

    def etkinlik_sil(self, etkinlik_id: str) -> bool:
        onceki = len(self.etkinlikler)
        self.etkinlikler = [
            e for e in self.etkinlikler if e["id"] != etkinlik_id]
        if len(self.etkinlikler) < onceki:
            self.kaydet()
            return True
        return False

    def _tarih_coz(self, metin: str) -> str:
        """Doğal dil tarih çözümleyici."""
        ml = metin.lower().strip()
        simdi = datetime.now()

        if ml in ("bugün", "bugun", "today"):
            return simdi.strftime("%Y-%m-%d")
        if ml in ("yarın", "yarin", "tomorrow"):
            return (simdi + timedelta(days=1)).strftime("%Y-%m-%d")
        if ml in ("öbür gün", "obur gun"):
            return (simdi + timedelta(days=2)).strftime("%Y-%m-%d")

        gun_adlari = {
            "pazartesi": 0, "salı": 1, "çarşamba": 2,
            "perşembe": 3, "cuma": 4, "cumartesi": 5, "pazar": 6
        }
        for ad, gun_no in gun_adlari.items():
            if ad in ml:
                bugun_no = simdi.weekday()
                fark = (gun_no - bugun_no) % 7
                if fark == 0:
                    fark = 7
                return (simdi + timedelta(days=fark)).strftime("%Y-%m-%d")

        # Direkt tarih formatı dene
        for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(metin, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass

        # Fallback: bugün
        return simdi.strftime("%Y-%m-%d")

    def ozet_metin(self) -> str:
        """Bugün ve yakın etkinliklerin özeti."""
        bugun = self.bugun_etkinlikler()
        yakin = self.yakin_etkinlikler(7)

        satirlar = []
        if bugun:
            satirlar.append("📅 Bugün:")
            for e in bugun:
                saat = f" {e['saat']}" if e.get("saat") else ""
                satirlar.append(f"  • {e['baslik']}{saat}")
        else:
            satirlar.append("📅 Bugün etkinlik yok.")

        diger = [e for e in yakin if e not in bugun]
        if diger:
            satirlar.append("\n📆 Yakında:")
            for e in diger[:5]:
                tarih = e["tarih"][5:]  # MM-DD
                saat = f" {e['saat']}" if e.get("saat") else ""
                satirlar.append(f"  • {tarih}{saat} — {e['baslik']}")

        return "\n".join(satirlar)

    def sesli_komut_isle(self, metin: str) -> Optional[str]:
        ml = metin.lower()

        # Bugün ne var
        if any(k in ml for k in [
            "bugün ne var", "bugünkü program", "takvim",
            "etkinliklerim", "ne var bugün"
        ]):
            return self.ozet_metin()

        # Etkinlik ekle: "yarın saat 14:30'da toplantı var"
        import re
        etkinlik_m = re.search(
            r"(pazartesi|salı|çarşamba|perşembe|cuma|cumartesi|pazar|"
            r"bugün|yarın|öbür gün|\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})"
            r".*?(?:saat\s*(\d{1,2}[:.]\d{2}))?\s*"
            r"(?:da\s|de\s|için\s)?(.+?)(?:\s*var|\s*var\.?)?\s*$",
            ml
        )
        if etkinlik_m and any(k in ml for k in [
            "ekle", "kaydet", "hatırlat", "var"
        ]):
            tarih = etkinlik_m.group(1) or "bugün"
            saat  = (etkinlik_m.group(2) or "").replace(".", ":")
            baslik = etkinlik_m.group(3).strip()
            if baslik:
                e = self.etkinlik_ekle(baslik, tarih, saat)
                return f"Takvime eklendi: {e['baslik']} — {e['tarih']}"

        # Yakında ne var
        if any(k in ml for k in ["yakında", "bu hafta", "önümüzdeki"]):
            return self.ozet_metin()

        return None


# ─────────────────────────────────────────────────────────────────────────────
# OTOMATİK GÜNCELLEME
# ─────────────────────────────────────────────────────────────────────────────

class GuncellemeSistemi:
    def __init__(self, logcu: Logcu, proje_yolu: str):
        self.log = logcu
        self.proje_yolu = proje_yolu
        self._bildirim_fn: Optional[Callable[[str], None]] = None
        self._kontrol_suresi = 3600 * 6  # 6 saatte bir
        self._son_kontrol: float = 0.0
        self._thread: Optional[threading.Thread] = None
        self._calisıyor = False

    def bildirim_fn_ayarla(self, fn: Callable[[str], None]):
        self._bildirim_fn = fn

    def baslat(self):
        """Arka planda periyodik güncelleme kontrolü."""
        self._calisıyor = True
        self._thread = threading.Thread(
            target=self._kontrol_dongusu, daemon=True)
        self._thread.start()

    def durdur(self):
        self._calisıyor = False

    def _kontrol_dongusu(self):
        import time
        time.sleep(60)  # İlk 1 dakika bekle
        while self._calisıyor:
            self.guncelleme_kontrol()
            time.sleep(self._kontrol_suresi)

    def guncelleme_kontrol(self, sessiz: bool = False) -> Optional[dict]:
        """GitHub'dan son sürümü kontrol et."""
        try:
            import urllib.request
            url = (f"https://api.github.com/repos/"
                   f"{GITHUB_REPO}/releases/latest")
            req = urllib.request.Request(url, headers={
                "User-Agent": "ZihinKoprusu/7.0",
                "Accept": "application/vnd.github.v3+json",
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                veri = json.loads(r.read())

            son_surum  = veri.get("tag_name", "").lstrip("v")
            aciklama   = veri.get("body", "")[:200]
            indir_url  = ""
            for asset in veri.get("assets", []):
                if asset["name"].endswith(".tar.gz"):
                    indir_url = asset["browser_download_url"]
                    break

            if not son_surum:
                return None

            # Sürüm karşılaştırma
            yeni_mi = self._surum_karsilastir(SURUM, son_surum)

            if yeni_mi and not sessiz:
                mesaj = (f"Yeni sürüm mevcut: v{son_surum}. "
                         f"Güncellemek ister misiniz?")
                self.log.bilgi(KAYNAK, mesaj)
                if self._bildirim_fn:
                    self._bildirim_fn(mesaj)

            return {
                "mevcut":   SURUM,
                "son":      son_surum,
                "yeni_mi":  yeni_mi,
                "aciklama": aciklama,
                "url":      indir_url,
            }

        except Exception as e:
            if not sessiz:
                self.log.uyari(KAYNAK, f"Güncelleme kontrolü hatası: {e}")
            return None

    def _surum_karsilastir(self, mevcut: str, son: str) -> bool:
        """Semantic versioning karşılaştırması."""
        try:
            m = tuple(int(x) for x in mevcut.split(".")[:3])
            s = tuple(int(x) for x in son.split(".")[:3])
            return s > m
        except Exception:
            return False

    def guncelleme_indir(self, url: str = "",
                          callback: Optional[Callable[[bool, str], None]] = None):
        """Güncellemeyi indir ve uygula."""
        if not url:
            veri = self.guncelleme_kontrol(sessiz=True)
            if not veri or not veri.get("url"):
                if callback:
                    callback(False, "İndirme URL bulunamadı.")
                return
            url = veri["url"]

        threading.Thread(
            target=self._indir_thread,
            args=(url, callback),
            daemon=True
        ).start()

    def _indir_thread(self, url: str,
                       callback: Optional[Callable[[bool, str], None]]):
        try:
            import urllib.request, tarfile
            self.log.bilgi(KAYNAK, f"İndiriliyor: {url}")
            tmp = "/tmp/zk_guncelleme.tar.gz"
            urllib.request.urlretrieve(url, tmp)

            # Yedek al
            yedek = os.path.join(self.proje_yolu, "zihin_yedek")
            if os.path.exists(os.path.join(self.proje_yolu, "zihin")):
                import shutil
                shutil.copytree(
                    os.path.join(self.proje_yolu, "zihin"),
                    yedek, dirs_exist_ok=True)

            # Aç
            with tarfile.open(tmp, "r:gz") as tar:
                tar.extractall(self.proje_yolu)

            os.unlink(tmp)
            mesaj = "Güncelleme uygulandı. Yeniden başlatın."
            self.log.bilgi(KAYNAK, mesaj)
            if callback:
                callback(True, mesaj)

        except Exception as e:
            mesaj = f"Güncelleme hatası: {e}"
            self.log.hata(KAYNAK, mesaj)
            if callback:
                callback(False, mesaj)


# ─────────────────────────────────────────────────────────────────────────────
# ANA SARMALAYICI
# ─────────────────────────────────────────────────────────────────────────────

class HavaTakvimSistemi:
    """Hava, takvim ve güncelleme modüllerini tek çatı altında toplar."""

    def __init__(self, logcu: Logcu, proje_yolu: str):
        self.log = logcu
        self.hava = HavaDurumu(logcu)
        self.takvim = Takvim(
            logcu,
            os.path.join(proje_yolu, "takvim.json"))
        self.guncelleme = GuncellemeSistemi(logcu, proje_yolu)

    def baslat(self, bildirim_fn: Optional[Callable] = None):
        if bildirim_fn:
            self.guncelleme.bildirim_fn_ayarla(bildirim_fn)
        self.guncelleme.baslat()
        self.log.bilgi(KAYNAK, "Hava/Takvim/Güncelleme sistemi başladı.")

    def durdur(self):
        self.guncelleme.durdur()

    def sesli_komut_isle(self, metin: str) -> Optional[str]:
        """Tüm modülleri sesli komutla dene."""
        sonuc = self.hava.sesli_komut_isle(metin)
        if sonuc:
            return sonuc
        sonuc = self.takvim.sesli_komut_isle(metin)
        if sonuc:
            return sonuc

        # Güncelleme kontrolü
        ml = metin.lower()
        if any(k in ml for k in [
            "güncelleme var mı", "yeni sürüm", "güncelle"
        ]):
            veri = self.guncelleme.guncelleme_kontrol()
            if veri:
                if veri["yeni_mi"]:
                    return (f"Yeni sürüm mevcut: v{veri['son']}. "
                            f"GUI'den indirebilirsiniz.")
                return f"Sürüm güncel: v{veri['mevcut']}"
            return "Güncelleme bilgisi alınamadı."

        return None
