"""
Zihin Köprüsü v6.0 – Niyet Motoru  (DÜZELTİLMİŞ)
Kullanıcı sesli/yazılı komutunu analiz edip niyete dönüştürür.

Düzeltmeler:
  - "saat kaç" artık HESAP değil komut DB'ye gidiyor (BILINMEZ → DB eşleşir)
  - "çalışan uygulamalar" artık MEDYA_OYNAT değil SISTEM niyetine giriyor
  - "internete gir" artık METIN_YAZ değil WEB_GEZ / UYGULAMA_AC'a gidiyor
  - "nasıl gidiyor" AI_SOHBET olarak doğru eşleşiyor
  - Güven eşiği ve öncelik sırası düzenlendi
  - Kural çakışmaları giderildi

"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from difflib import SequenceMatcher
from typing import Optional
from .logcu import Logcu

KAYNAK = "NİYET"


class NiyetTipi(str, Enum):
    SISTEM          = "sistem"
    UYGULAMA_AC     = "uygulama_ac"
    UYGULAMA_KAP    = "uygulama_kapat"
    WEB_GEZ         = "web_gez"
    WEB_TIKLA       = "web_tikla"
    WEB_KAYDIR      = "web_kaydir"
    WEB_YAZI_YAZ    = "web_yazi_yaz"
    MEDYA_OYNAT     = "medya_oynat"
    MEDYA_DUR       = "medya_dur"
    DOSYA_ISLE      = "dosya_isle"
    METIN_YAZ       = "metin_yaz"
    UZUV_KOMUT      = "uzuv_komut"
    AI_SOHBET       = "ai_sohbet"
    HAVA_DURUMU     = "hava_durumu"
    HABER           = "haber"
    HESAP           = "hesap"
    HATIRLATICI     = "hatirlatici"
    ARAMA           = "arama"
    EKRAN_GORUNTU   = "ekran_goruntu"
    OTOMASYON       = "otomasyon"
    BILINMEZ        = "bilinmez"


@dataclass
class Niyet:
    tip: NiyetTipi = NiyetTipi.BILINMEZ
    guven: float = 0.0
    ozne: str = ""
    eylem: str = ""
    hedef: str = ""
    parametreler: dict = field(default_factory=dict)
    ham_metin: str = ""

    def __str__(self):
        return (f"[{self.tip.value}] özne={self.ozne!r} "
                f"eylem={self.eylem!r} hedef={self.hedef!r} "
                f"güven={self.guven:.2f}")


# ── Sabitler ─────────────────────────────────────────────────────────────────

_UYGULAMA_ESLESMELER = {
    "chrome":           ["chrome", "google chrome", "krom"],
    "firefox":          ["firefox", "mozilla", "tarayıcı"],
    "youtube":          ["youtube", "you tube"],
    "spotify":          ["spotify"],
    "vscode":           ["vscode", "visual studio", "kod editörü"],
    "terminal":         ["terminal", "konsol aç", "komut satırı"],
    "dosya_yoneticisi": ["dosya yöneticisi", "nautilus", "gezgin"],
    "not_defteri":      ["not defteri", "notepad", "metin editörü", "gedit", "kate"],
    "hesap_makinesi":   ["hesap makinesi", "calculator"],
    "vlc":              ["vlc"],
    "whatsapp":         ["whatsapp"],
    "telegram":         ["telegram uygulaması", "telegram aç"],   # "telegram bot" ile çakışmasın
    "discord":          ["discord"],
}

# WEB adresi ya da "internete gir / web'e git" kalıpları
_WEB_AC_KALIPLARI = [
    r"(?:internete|web['\s]?e|siteye|adrese)\s+(?:gir|git|aç|bak)",
    r"(?:aç|git|gir)\s+(?:internete|web['\s]?e)",
]

_WEB_ARAMA_KALIPLARI = [
    r"(?:google['\s]?da|internette|web['\s]?de)\s+(.+?)\s+(?:ara|bul|sorgula)",
    r"(?:google|chrome|tarayıcı|tarayici)\s+(?:da|de|üzerinde|uzerinde)\s+(.+?)\s+(?:ara|bul|sorgula)",
    r"(?:youtube|yutub)\s+(?:da|de|üzerinde|uzerinde)\s+(.+?)\s+(?:ara|bul|sorgula)",
    r"(.+?)\s+(?:youtube|yutub)\s+(?:da|de|üzerinde|uzerinde)\s+(?:ara|bul|sorgula)",
    r"(?:wikipedia|vikipedi)\s+(?:da|de|üzerinde|uzerinde)\s+(.+?)\s+(?:ara|bul|sorgula)",
    r"(.+?)\s+(?:wikipedia|vikipedi)\s+(?:da|de|üzerinde|uzerinde)\s+(?:ara|bul|sorgula)",
    r"(?:ara|bul|sorgula)\s+(.+)",
    r"(.+?)\s+(?:google|chrome|tarayıcı|tarayici)\s+(?:da|de|üzerinde|uzerinde)\s+(?:ara|bul|sorgula)",
    r"(.+?)\s+(?:nedir|kimdir|ne\s+zaman|nerede|nasıl\s+yapılır)$",
]

_URL_KALIP = re.compile(
    r"(https?://[^\s]+)"
    r"|(www\.[^\s]+)"
    r"|([a-zA-Z0-9\-]+\.(?:com|net|org|io|tr|co|gov|edu)(/[^\s]*)?)",
    re.IGNORECASE
)

# UYARI: "yaz" tek başına metin yazma değil, sadece bağlam içinde
_METIN_YAZ_KALIPLARI = [
    r"(?:klavyeye|metin olarak|ekrana)\s+(?:yaz|gir)\s+(.+)",
    r"(?:type|write)\s+(.+)",
    r"(.+?)\s+(?:yaz|gir)\s+(?:bunu|şunu|onu)",
]

_KAYDIRMA_KALIPLARI = [
    "aşağı kaydır", "yukarı kaydır", "scroll aşağı", "scroll yukarı",
    "sayfayı kaydır", "aşağı in", "yukarı çık",
]

_TIKLA_KALIPLARI = [
    r"(.+?)\s+(?:tıkla|bas|click)(?:\s+üzerine)?$",
    r"(?:tıkla|bas)\s+(.+)",
]

# "çalış" → SISTEM, "oynat/çal/dinle/izle" → MEDYA
_MEDYA_OYNAT_TETIKLER  = ["oynat", "çal", "müzik başlat", "video başlat",
                           "şarkı çal", "müzik çal", "video oynat", "dinle", "izle"]
_MEDYA_DUR_TETIKLER    = ["durdur müziği", "müziği durdur", "müziği kapat",
                          "videoyu durdur", "pause", "medyayı durdur"]

_SISTEM_KALIPLARI = [
    "disk", "bellek", "ram", "cpu", "işlemci", "sıcaklık", "pil", "batarya",
    "ip adresi", "ağ", "internet bağlantısı", "wifi", "bluetooth",
    "sistem bilgisi", "güncelle", "yeniden başlat", "bilgisayarı kapat",
    "uyut", "kilitle", "çalışan", "süreçler", "işlemler", "servisler",
    "depolama", "kullanıcı",
]

_SOHBET_KALIPLARI = [
    "ne düşünüyorsun", "bana anlat", "sence", "neden",
    "merhaba", "selam", "nasılsın", "ne haber", "teşekkür",
    "günaydın", "iyi geceler", "iyi akşamlar", "nasıl gidiyor",
    "ne yapıyorsun", "ne var ne yok", "naber", "eyvallah",
    "canım sıkıldı", "sohbet", "espri", "şaka", "fıkra",
    "iyiyim", "tamam", "tamamdır", "anlaşıldı",
    "bilmem", "merak ettim", "öyle merak ettim",
    "konuşalım", "sohbet edelim", "fikrin ne", "bana yardım et",
    "ne önerirsin", "sence ne yapmalıyım", "bunu açıkla",
]

_OKUNUS_DUZELTME = {
    "gugıl": "google",
    "gugil": "google",
    "gugıl da": "google da",
    "gugilda": "google da",
    "gugıl'da": "google da",
    "gogıl": "google",
    "krom": "chrome",
    "kırom": "chrome",
    "kromda": "chrome da",
    "krom da": "chrome da",
    "krom'da": "chrome da",
    "yutub": "youtube",
    "yu tub": "youtube",
    "yutüp": "youtube",
    "vikipedi": "wikipedia",
    "vikı pedi": "wikipedia",
    "fayır foks": "firefox",
    "fairy fox": "firefox",
    "fair fox": "firefox",
    "bay fox": "firefox",
    "firefox ağaç": "firefox aç",
    "firefox agac": "firefox aç",
    "bay fox ağaç": "firefox aç",
    "sistem ve durumda": "sistem ne durumda",
}

_BILINC_DUZELTME = {
    "bir adar": "birader",
    "bir ader": "birader",
    "biraderim": "birader",
    "brader": "birader",
    "biraderde": "birader",
    "abey": "abi",
    "ağbi": "abi",
    "ağabey": "abi",
    "baci": "bacı",
    "bacim": "bacı",
    "ablaa": "abla",
    "ufak lik": "ufaklık",
    "ufaklik": "ufaklık",
    "ufak lık": "ufaklık",
    "dayi": "dayı",
    "kuzey": "kuzen",
    "kuzenim": "kuzen",
    "güzen": "kuzen",
    "key lo": "keylo",
    "keylow": "keylo",
    "keyla": "keylo",
    "kilo": "keylo",
}

# HESAP: yalnızca rakam içeren matematiksel ifadeler
_HESAP_KALIPLARI = [
    r"\d+\s*[\+\-\*\/\^]\s*\d+",        # 5+3, 10*2 gibi
    r"(?:toplam|çarp|böl|karekök|yüzde|logaritma)\s+\d+",
    r"\d+\s+(?:kere|bölü|artı|eksi)\s+\d+",
]

# "saat kaç" gibi ZAMAN soruları → BILINMEZ bırak, komut DB yakalar
_ZAMAN_SORULARI = ["saat kaç", "saat nedir", "kaç saat", "tarih nedir",
                   "bugün ne", "günün tarihi", "şu an saat"]

_EKRAN_GORUNTU_KALIPLARI = ["ekran görüntüsü", "screenshot", "ekran al",
                             "ekranı yakala"]


# STT sesli çıktıda Türkçe kelimelerin sık yanlış tanınan karşılıkları
# {yanlış_okunan: doğru_kelime}
_STT_DUZELTME = {
    "fair fox": "firefox",
    "fairy fox": "firefox",
    "bay fox": "firefox",
    "fire fox": "firefox",
    "google crome": "chrome",
    "google chrome": "chrome",
    "google krom": "chrome",
    "gugıl": "google",
    "gugil": "google",
    "gogıl": "google",
    "krom": "chrome",
    "kırom": "chrome",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "y tube": "youtube",
    "yutub": "youtube",
    "yutüp": "youtube",
    "you tüb": "youtube",
    "u tüb": "youtube",
    "spot if ay": "spotify",
    "disk cord": "discord",
    "whats ab": "whatsapp",
    "tele gram": "telegram",
    "abi devir al": "abi devral",
    "abla devir al": "abla devral",
    "bacı devir al": "bacı devral",
    "birader devir al": "birader devral",
    "bir ader devir al": "birader devral",
    "bir adar devir al": "birader devral",
    "brader devir al": "birader devral",
    "dayı devir al": "dayı devral",
    "kuzen devir al": "kuzen devral",
    "kuzey devir al": "kuzen devral",
    "güzen devir al": "kuzen devral",
    "ufaklık devir al": "ufaklık devral",
    "key lo devir al": "keylo devral",
    "keyla devir al": "keylo devral",
    "kilo devir al": "keylo devral",
    "ekran görüntü": "ekran görüntüsü",
    "ekran görüntü al": "ekran görüntüsü al",
    "internet bağlantı": "internet bağlantısı",
    "not al ": "not al:",
    "sistem ve durumda": "sistem ne durumda",
    "firefox ağaç": "firefox aç",
    "firefox agac": "firefox aç",
    "bay fox ağaç": "firefox aç",
}


def stt_duzelt(metin: str) -> str:
    """Yaygın STT yanlış tanımalarını düzelt."""
    ml = metin.lower()
    for sozluk in (_OKUNUS_DUZELTME, _BILINC_DUZELTME, _STT_DUZELTME):
        for yanlis, dogru in sozluk.items():
            if yanlis in ml:
                ml = ml.replace(yanlis, dogru)
    ml = re.sub(r"\b(devir al|devri al|devral|devralır|devr al)\b", "devral", ml)
    ml = re.sub(r"\b(emir komuta sende|emir komuta|komuta sende|kontrol sende)\b", "emir komuta sende", ml)
    return ml


def normalize_tr(metin: str) -> str:
    """Türkçe karakter, noktalama ve STT sapmalarını tek biçime indirir."""
    ml = stt_duzelt(metin)
    ceviri = str.maketrans({
        "ç": "c", "ğ": "g", "ı": "i", "i": "i", "ö": "o",
        "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u",
    })
    ml = ml.translate(ceviri)
    ml = re.sub(r"[^a-z0-9\s:/._-]+", " ", ml)
    ml = re.sub(r"\s+", " ", ml).strip()
    return ml


def benzerlik(a: str, b: str) -> float:
    a_n, b_n = normalize_tr(a), normalize_tr(b)
    if not a_n or not b_n:
        return 0.0
    if a_n == b_n:
        return 1.0
    if len(a_n) > 3 and (a_n in b_n or b_n in a_n):
        return 0.92
    return SequenceMatcher(None, a_n, b_n).ratio()


class NiyetMotoru:
    def __init__(self, logcu: Logcu, ai_motoru=None):
        self.log = logcu
        self.ai = ai_motoru
        self._onceki_niyet: Optional[Niyet] = None
        self._tekrar_sayaci: int = 0
        self._onceki_metin: str = ""

    def analiz_et(self, metin: str) -> Niyet:
        metin = metin.strip()
        if not metin:
            return Niyet(tip=NiyetTipi.BILINMEZ, guven=0.0)

        # STT düzeltme uygula
        duzeltilmis = stt_duzelt(metin)
        if duzeltilmis != metin:
            self.log.bilgi(KAYNAK, f"STT düzeltme: '{metin}' → '{duzeltilmis}'")
            metin = duzeltilmis

        if metin.lower() == self._onceki_metin.lower():
            self._tekrar_sayaci += 1
        else:
            self._tekrar_sayaci = 0
        self._onceki_metin = metin

        niyet = self._kural_tabanlı_analiz(metin)

        # AI destekli analiz: yalnızca çok belirsiz kalıplarda ve AI hazırsa
        if niyet.guven < 0.55 and self.ai and self.ai.hazir:
            niyet = self._ai_destekli_analiz(metin, niyet)

        self._onceki_niyet = niyet
        self.log.bilgi(KAYNAK, str(niyet))
        return niyet

    # ── Kural Tabanlı Analiz ─────────────────────────────────────────────────

    def _kural_tabanlı_analiz(self, metin: str) -> Niyet:
        n = Niyet(ham_metin=metin)
        ml = metin.lower().strip()

        # 1. ZAMAN soruları → BILINMEZ bırak (komut DB "saat kaç" → date komutuna eşleşir)
        if any(k in ml for k in _ZAMAN_SORULARI):
            n.tip, n.guven = NiyetTipi.BILINMEZ, 0.1
            return n

        # 2. EKRAN GÖRÜNTÜSÜ
        if any(k in ml for k in _EKRAN_GORUNTU_KALIPLARI):
            n.tip, n.guven = NiyetTipi.EKRAN_GORUNTU, 0.95
            return n

        # 3. HESAP — sadece rakam+operatör içeriyorsa
        for k in _HESAP_KALIPLARI:
            if re.search(k, ml):
                n.tip, n.guven, n.hedef = NiyetTipi.HESAP, 0.92, metin
                return n

        # 4. URL doğrudan girilmiş
        url_m = _URL_KALIP.search(metin)
        if url_m:
            url = url_m.group(0)
            if not url.startswith("http"):
                url = "https://" + url
            n.tip, n.hedef, n.eylem, n.guven = NiyetTipi.WEB_GEZ, url, "git", 0.95
            return n

        # 5. WEB AÇMA ("internete gir" vb.)
        for k in _WEB_AC_KALIPLARI:
            if re.search(k, ml):
                n.tip, n.hedef, n.eylem, n.guven = (
                    NiyetTipi.UYGULAMA_AC, "chrome", "ac", 0.88)
                return n

        # 6. KAYDIRMA
        if any(k in ml for k in _KAYDIRMA_KALIPLARI):
            yon = "asagi" if any(k in ml for k in ["aşağı", "aşağıya", "in"]) else "yukari"
            n.tip, n.eylem, n.guven = NiyetTipi.WEB_KAYDIR, yon, 0.90
            return n

        # 6.5 WEB ARAMA — "youtube/chrome/google ... ara" medya/uygulama açmaya düşmesin.
        for k in _WEB_ARAMA_KALIPLARI:
            m = re.search(k, ml)
            if m:
                hedef = m.group(1).strip()
                motor = "google"
                if "youtube" in ml:
                    motor = "youtube"
                elif "wikipedia" in ml:
                    motor = "wikipedia"
                n.tip, n.hedef, n.eylem, n.ozne, n.guven = (
                    NiyetTipi.ARAMA, hedef, "ara", motor, 0.88)
                return n

        # 7. TIKLA
        for k in _TIKLA_KALIPLARI:
            m = re.search(k, ml)
            if m:
                n.tip, n.eylem, n.guven = NiyetTipi.WEB_TIKLA, "tikla", 0.82
                n.hedef = m.group(1).strip() if m.lastindex else ""
                return n

        # 8. METIN YAZ — yalnızca açık kalıplarla
        for k in _METIN_YAZ_KALIPLARI:
            m = re.search(k, ml)
            if m:
                n.tip, n.eylem, n.guven = NiyetTipi.METIN_YAZ, "yaz", 0.82
                n.hedef = m.group(1).strip() if m.lastindex else ""
                return n

        # 9. MEDYA DURDUR (önce durdur, sonra oynat kontrol et)
        if any(k in ml for k in _MEDYA_DUR_TETIKLER):
            n.tip, n.eylem, n.guven = NiyetTipi.MEDYA_DUR, "durdur", 0.88
            return n

        # 10. MEDYA OYNAT — yalnızca kesin medya fiilleriyle
        if any(k in ml for k in _MEDYA_OYNAT_TETIKLER):
            # "çalışan uygulamalar" gibi ifadeleri kapsamaması için
            # en az biri açık medya fiili olmalı VE
            # sistem anahtar kelimeleri içermemeli
            sistem_cakisma = any(s in ml for s in ["çalışan", "çalışıyor", "süreç"])
            if not sistem_cakisma:
                n.tip, n.eylem, n.guven = NiyetTipi.MEDYA_OYNAT, "oynat", 0.82
                # Kaynak uygulama
                for app, klist in _UYGULAMA_ESLESMELER.items():
                    if any(k in ml for k in klist):
                        n.ozne = app
                        break
                # Sorgu
                for fiil in _MEDYA_OYNAT_TETIKLER:
                    if fiil in ml:
                        n.hedef = ml.replace(fiil, "").strip()
                        break
                return n

        # 11. UYGULAMA AÇ / KAPAT
        kapat_var = any(k in ml for k in ["kapat", "kapa", "çıkış", "çık", "sonlandır"])
        for app, klist in _UYGULAMA_ESLESMELER.items():
            if any(k in ml for k in klist):
                n.tip = NiyetTipi.UYGULAMA_KAP if kapat_var else NiyetTipi.UYGULAMA_AC
                n.eylem = "kapat" if kapat_var else "ac"
                n.ozne, n.guven = app, 0.90
                return n

        # 12. SİSTEM komutu
        if any(k in ml for k in _SISTEM_KALIPLARI):
            n.tip, n.guven, n.hedef = NiyetTipi.SISTEM, 0.75, metin
            return n

        # 13. HABER / HAVA
        if any(k in ml for k in ["haber", "gündem", "son dakika"]):
            n.tip, n.guven = NiyetTipi.HABER, 0.85
            return n
        if any(k in ml for k in ["hava durumu", "hava nasıl", "yağmur", "kar yağacak"]):
            n.tip, n.guven = NiyetTipi.HAVA_DURUMU, 0.85
            return n

        # 14. HATIRLATICI
        if any(k in ml for k in ["hatırlat", "alarm kur", "zamanlayıcı", "beni uyar"]):
            n.tip, n.guven, n.hedef = NiyetTipi.HATIRLATICI, 0.82, metin
            return n

        # 15. SOHBET — açıkça sohbet kalıpları
        if any(k in ml for k in _SOHBET_KALIPLARI):
            n.tip, n.guven, n.hedef = NiyetTipi.AI_SOHBET, 0.72, metin
            return n

        # 16. Hiçbirine uymadı → BILINMEZ (komut DB ve AI dener)
        n.tip, n.guven = NiyetTipi.BILINMEZ, 0.3
        return n

    # ── AI Destekli Analiz ───────────────────────────────────────────────────

    def _ai_destekli_analiz(self, metin: str, onceki: Niyet) -> Niyet:
        prompt = (
            f'Aşağıdaki Türkçe komutu analiz et ve yalnızca JSON döndür:\n'
            f'Komut: "{metin}"\n'
            f'Geçerli tipler: uygulama_ac, uygulama_kapat, web_gez, arama, '
            f'medya_oynat, medya_dur, metin_yaz, sistem, ai_sohbet, hesap, '
            f'ekran_goruntu, hatirlatici, bilinmez\n'
            f'{{"tip":"","ozne":"","eylem":"","hedef":""}}'
        )
        try:
            import json as _j
            yanit = self.ai.sor(prompt)
            m = re.search(r"\{.*?\}", yanit, re.DOTALL)
            if m:
                d = _j.loads(m.group(0))
                try:
                    tip = NiyetTipi(d.get("tip", "bilinmez"))
                except ValueError:
                    tip = NiyetTipi.BILINMEZ
                return Niyet(
                    tip=tip, guven=0.75,
                    ozne=d.get("ozne", ""),
                    eylem=d.get("eylem", ""),
                    hedef=d.get("hedef", ""),
                    ham_metin=metin
                )
        except Exception as e:
            self.log.uyari(KAYNAK, f"AI analiz hatası: {e}")
        return onceki

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    @property
    def tekrar_mi(self) -> bool:
        return self._tekrar_sayaci > 0

    def gecmisi_temizle(self):
        self._onceki_niyet = None
        self._tekrar_sayaci = 0
        self._onceki_metin = ""

    def niyet_acikla(self, niyet: Niyet) -> str:
        aciklamalar = {
            NiyetTipi.UYGULAMA_AC:  f"{niyet.ozne} açılıyor",
            NiyetTipi.UYGULAMA_KAP: f"{niyet.ozne} kapatılıyor",
            NiyetTipi.WEB_GEZ:      f"Adrese gidiliyor: {niyet.hedef}",
            NiyetTipi.WEB_TIKLA:    f"Tıklanıyor: {niyet.hedef}",
            NiyetTipi.WEB_KAYDIR:   f"Sayfa kaydırılıyor: {niyet.eylem}",
            NiyetTipi.MEDYA_OYNAT:  f"Oynatılıyor: {niyet.hedef}",
            NiyetTipi.MEDYA_DUR:    "Medya durduruluyor",
            NiyetTipi.ARAMA:        f"Aranıyor: {niyet.hedef}",
            NiyetTipi.SISTEM:       f"Sistem komutu: {niyet.hedef}",
            NiyetTipi.AI_SOHBET:    "Sohbet modu",
            NiyetTipi.METIN_YAZ:    f"Yazılıyor: {niyet.hedef}",
            NiyetTipi.HESAP:        f"Hesap: {niyet.hedef}",
            NiyetTipi.EKRAN_GORUNTU:"Ekran görüntüsü alınıyor",
            NiyetTipi.BILINMEZ:     "Komut DB veya AI deneniyor",
        }
        return aciklamalar.get(niyet.tip, str(niyet))
