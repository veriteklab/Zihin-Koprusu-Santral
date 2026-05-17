"""
Zihin Köprüsü – Ana Çekirdek
Merkez sunucu davranışı, komut akışı ve uzuv orkestrasyonu.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import re
import sys
import threading
import time
import uuid
from typing import Callable

import yaml

from .logcu import Logcu
from .ses_motoru import SesMotoru
from .komut_veritabani import KomutVeritabani
from .ai_motoru import AIMotoru, AIAyar, AISağlayici
from .eklenti_yoneticisi import EklentiYoneticisi
from .dil_yukleyici import DilYukleyici
from .uzuv_yoneticisi import UzuvYoneticisi
from .niyet_motoru import NiyetMotoru, NiyetTipi, stt_duzelt, normalize_tr, benzerlik
from .otomasyon_motoru import OtomasyonMotoru
from .tor_yoneticisi import TorYoneticisi
from .plugin_yoneticisi import PluginYoneticisi
from .telegram_bot import TelegramBot
from .wake_word_motoru import WakeWordMotoru
from .web_kontrolcu import WebKontrolcu
from .ekran_yayinci import EkranYayincisi
from .makro_yoneticisi import MakroYoneticisi
from .hafiza_motoru import HafizaMotoru
from .hava_takvim import HavaTakvimSistemi
from .yedek_yoneticisi import YedekYoneticisi

KAYNAK = "ÇEKİRDEK"

# Proje kökünü __file__ üzerinden otomatik tespit et (zihin/cekirdek.py → ../.. )
_OTOMATIK_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SES_KES_KELIMELER = [
    "ses kes", "sesi kes", "dur", "sus", "susun", "yeter",
    "yeterli", "uzatma", "kısa kes", "kisa kes",
    "kapat sesini", "durdur", "tamam yeter", "konuşmayı kes",
    "konusmayi kes"
]

# Bu niyet tipleri doğrudan AI'a gönderilir, komut DB aranmaz
AI_SOHBET_TIPLERI = {NiyetTipi.AI_SOHBET}

OTOMASYON_TIPLERI = {
    NiyetTipi.UYGULAMA_AC, NiyetTipi.UYGULAMA_KAP,
    NiyetTipi.WEB_GEZ, NiyetTipi.WEB_TIKLA,
    NiyetTipi.WEB_KAYDIR, NiyetTipi.METIN_YAZ,
    NiyetTipi.MEDYA_OYNAT, NiyetTipi.MEDYA_DUR,
    NiyetTipi.ARAMA, NiyetTipi.EKRAN_GORUNTU,
    NiyetTipi.HESAP,
}

ONAY_TETIKLERI = {
    "onay ver", "onayla", "evet", "uygula", "devam et",
    "çalıştır", "calistir", "tamam"
}
IPTAL_TETIKLERI = {"iptal", "vazgeç", "vazgec", "dur", "hayır", "hayir"}
TEHLIKELI_KOMUT_DESENLERI = (
    "shutdown", "reboot", "poweroff", " rm ", "rm -", "kill ", "killall",
    "pkill", "sudo", "apt ", "apt-get", "systemctl stop", "systemctl disable",
    "drop_caches", "mkfs", "dd if=", "xkill", "shutdown /", "format "
)


def _beyin_yukle(dosya: str) -> dict:
    with open(dosya, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _beyin_kaydet(dosya: str, veri: dict):
    with open(dosya, "w", encoding="utf-8") as f:
        yaml.safe_dump(veri, f, allow_unicode=True, sort_keys=False)


def _devir_kontrol(metin: str, bilincler: dict) -> str | None:
    metin_duz = stt_duzelt(metin)
    metin_norm = normalize_tr(metin_duz)
    devir_ifadesi = any(k in metin_norm for k in (
        "devral", "emir komuta sende", "komuta sende",
        "kontrol sende", "sira sende", "sen devral"
    ))
    for isim, veri in bilincler.items():
        if not isinstance(veri, dict):
            continue
        adlar = {isim}
        adlar.add(str(isim).replace("İ", "I").lower())
        if isinstance(veri.get("ad"), str):
            adlar.add(veri["ad"])
        if isinstance(veri.get("gosterim"), str):
            adlar.add(veri["gosterim"])
        for ad in list(adlar):
            ad_norm = normalize_tr(ad)
            ilk_kelime = metin_norm.split()[0] if metin_norm.split() else ""
            if ad_norm and devir_ifadesi and (
                re.search(rf"(?<!\w){re.escape(ad_norm)}(?!\w)", metin_norm) is not None
                or (len(ad_norm) > 3 and benzerlik(ad_norm, ilk_kelime) >= 0.82)
            ):
                return isim
        for komut in veri.get("devir_komutlari", []):
            komut_norm = normalize_tr(komut)
            komut_ilk = komut_norm.split()[0] if komut_norm.split() else ""
            metin_ilk = metin_norm.split()[0] if metin_norm.split() else ""
            if komut_norm in metin_norm:
                return isim
            if (komut_ilk == metin_ilk or (len(komut_ilk) > 3 and benzerlik(komut_ilk, metin_ilk) >= 0.88)) \
                    and benzerlik(metin_norm, komut_norm) >= 0.84:
                return isim
    return None


def _merkez_erisim_varsayilanlari() -> dict:
    return {
        "varsayilanlar": {
            "ssh_reverse": "local_ip",
            "tor_http": "tor_hidden_service",
            "tor_https": "tor_hidden_service",
            "telegram_agent": "telegram",
        },
        "profiller": {
            "local_ip": {
                "etiket": "Yerel IP",
                "tur": "local_ip",
                "host": "",
                "port": 22,
                "etkin": True,
            },
            "clearnet": {
                "etiket": "Clearnet Sunucu",
                "tur": "clearnet",
                "host": "",
                "port": 22,
                "etkin": False,
            },
            "tor_hidden_service": {
                "etiket": "Tor Hidden Service",
                "tur": "tor",
                "host": "",
                "port": 22,
                "etkin": True,
                "otomatik": True,
            },
            "telegram": {
                "etiket": "Telegram",
                "tur": "telegram",
                "host": "",
                "port": 0,
                "etkin": True,
            },
        },
    }


def _yerel_ip_bul() -> str:
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return ""


class Cekirdek:
    def __init__(self, proje_yolu: str | None = None):
        self.proje_yolu = proje_yolu or _OTOMATIK_KOK
        self.beyin_dosyasi = os.path.join(self.proje_yolu, "beyin.yaml")
        self.dil_klasoru   = os.path.join(self.proje_yolu, "dil")

        self.beyin = _beyin_yukle(self.beyin_dosyasi)
        self._merkez_erisim_hazirla()
        self.dil   = DilYukleyici(self.dil_klasoru)
        self.log   = Logcu(os.path.join(
            self.proje_yolu, self.beyin["sistem"]["log_dosyasi"]))

        self.ses      = SesMotoru(self.beyin, self.log, self.proje_yolu)
        self.komut_db = KomutVeritabani(
            self.log, os.path.join(self.proje_yolu, "komutlar.json"))
        self.eklenti  = EklentiYoneticisi(self.beyin, self.log, self.proje_yolu)
        self.uzuv     = UzuvYoneticisi(
            self.log, os.path.join(self.proje_yolu, "uzuvlar.json"))
        self.uzuv.baglanti_isleyici_ayarla("telegram", self._uzuv_telegram_baglanti_isle)

        self.tor     = TorYoneticisi(self.log, self.proje_yolu)
        self.tor.kayit_dinleyici_ekle(self._uzuv_kayit_isle)
        self.plugin  = PluginYoneticisi(self.log, self.proje_yolu)
        self.yedek   = YedekYoneticisi(self.log, self.proje_yolu)
        self.otomasyon = OtomasyonMotoru(self.log)
        self.otomasyon._cekirdek = self

        # Onion adresi hazır olunca otomatik kaydet
        self.tor.onion_hazir_dinleyici_ekle(self._onion_hazir_isle)

        # Wake word motoru
        self.wake = WakeWordMotoru(self.log, self.ses)
        self.wake.tetikleme_callback_ayarla(self._wake_word_tetiklendi)

        # Web & PC kontrol
        self.web = WebKontrolcu(self.log, self.ses)

        # Ekran yayıncısı
        self.ekran = EkranYayincisi(self.log)

        # Hafıza motoru
        self.hafiza = HafizaMotoru(
            self.log,
            os.path.join(self.proje_yolu, "hafiza.json"))

        # Hava durumu, takvim, güncelleme
        self.hava_takvim = HavaTakvimSistemi(self.log, self.proje_yolu)

        # Makro & Rutin yöneticisi
        self.makro = MakroYoneticisi(
            self.log,
            os.path.join(self.proje_yolu, "makrolar.json"))
        self.makro.cekirdek_ayarla(self)
        self.makro.bildirim_fn_ayarla(
            lambda m: self.ses.konus(self.aktif_bilinc, m))

        # Tor'u arka planda otomatik başlat
        import threading as _th
        _th.Thread(target=self._tor_otomatik_baslat, daemon=True).start()

        # AI
        self.ai: AIMotoru | None = None
        self._ai_ayar = AIAyar()
        self._ai_yedek_ayarlar: list[AIAyar] = []
        self._ai_motorlari: list[AIMotoru] = []
        self._ai_ayar_yukle()
        self._ai_baslat()

        # Niyet motoru
        self.niyet = NiyetMotoru(self.log, self.ai)

        # Bilinç
        self.aktif_bilinc: str = (
            self.beyin.get("aktif_bilinc") or
            self.beyin.get("bilincler", {}).get("aktif", "ABLA")
        ).upper()
        self._calisıyor   = False
        self._dinleyiciler: list[Callable[[str, str], None]] = []

        # Wake word modunu beyin.yaml'dan oku
        self._wake_word_aktif: bool = bool(
            self.beyin.get("ses", {}).get("wake_word_aktif", False)
        )

        # Hitap
        self._hitap_adlari: dict[str, str] = {}
        self._hitap_yukle()

        # Tekrar önleme
        self._son_yanit: str = ""
        self._son_giris: str = ""
        self._bekleyen_onay: dict | None = None
        self._telegram_uzuv_gorevleri: dict[str, dict] = {}
        self._telegram_uzuv_gorev_kilit = threading.Lock()
        self._telegram_log_dinleyici = None
        self._uzuv_odak_hedefleri: list[str] = []
        self._uzuv_odak_etiket: str = ""

        # Telegram
        self.telegram: TelegramBot | None = None
        self._telegram_yukle()

    # ── Hitap ────────────────────────────────────────────────────────────────

    def _hitap_yukle(self):
        dosya = os.path.join(self.proje_yolu, "hitap_ayar.json")
        if os.path.exists(dosya):
            try:
                with open(dosya, "r", encoding="utf-8") as f:
                    self._hitap_adlari = json.load(f)
            except Exception:
                pass

    def hitap_al(self, bilinc: str | None = None) -> str:
        b = bilinc or self.aktif_bilinc
        return self._hitap_adlari.get(
            b, self.beyin["sistem"].get("sahip", "Operatör"))

    def _hitap_yerlestir(self, metin: str) -> str:
        """
        Metindeki {sahip} yer tutucusunu hitap adıyla değiştirir.
        Metindeki {bilinc} yer tutucusunu aktif bilinç adıyla değiştirir.
        "Operatör" kelimesini sadece gerçek hitap adı varsa değiştirir.
        """
        hitap = self.hitap_al()
        metin = metin.replace("{sahip}", hitap)
        metin = metin.replace("{bilinc}", self.aktif_bilinc)
        # "Operatör" sözcüğünü sadece hitap tanımlıysa değiştir
        if hitap:
            metin = metin.replace("Sahip", hitap).replace("Operatör", hitap)
        else:
            metin = (metin.replace(" Sahip", "").replace("Sahip ", "")
                          .replace(" Operatör", "").replace("Operatör ", ""))
        return metin.strip()

    def tehlikeli_komut_onayi_aktif_mi(self) -> bool:
        return bool(self.beyin.get("guvenlik", {}).get("tehlikeli_komutlarda_onay", True))

    def _tehlikeli_komut_mu(self, komut_nesnesi=None, metin: str = "") -> bool:
        adaylar = [metin.lower()]
        if komut_nesnesi:
            adaylar.extend([
                str(getattr(komut_nesnesi, "ad", "")).lower(),
                str(getattr(komut_nesnesi, "komut", "")).lower(),
                str(getattr(komut_nesnesi, "komut_windows", "")).lower(),
                str(getattr(komut_nesnesi, "komut_android", "")).lower(),
            ])
        return any(any(parca in aday for parca in TEHLIKELI_KOMUT_DESENLERI) for aday in adaylar)

    def _onay_istenen_yanit(self, metin: str, kanal: str) -> str:
        self._bekleyen_onay = {"metin": metin, "kanal": kanal}
        return "Bu komut tehlikeli görünüyor. Çalıştırmak için 'onay ver', iptal için 'iptal' deyin."

    def _bekleyen_onayi_isle(self, metin: str) -> tuple[bool, str | None]:
        if not self._bekleyen_onay:
            return False, None
        temiz = metin.strip().lower()
        if temiz in IPTAL_TETIKLERI:
            self._bekleyen_onay = None
            return True, "Tehlikeli komut iptal edildi."
        if temiz in ONAY_TETIKLERI:
            bekleyen = self._bekleyen_onay
            self._bekleyen_onay = None
            return True, self.isle(bekleyen["metin"], bekleyen["kanal"], _onay_atla=True)
        return True, "Bekleyen tehlikeli komut var. Çalıştırmak için 'onay ver', vazgeçmek için 'iptal' deyin."

    # ── AI ───────────────────────────────────────────────────────────────────

    def _ai_ayar_yukle(self):
        if not self.beyin: return
        dosya = os.path.join(self.proje_yolu, "ai_ayar.json")
        if os.path.exists(dosya):
            try:
                with open(dosya, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self._ai_ayar = AIAyar.from_dict(d)
                self._ai_yedek_ayarlar = [
                    AIAyar.from_dict(y)
                    for y in d.get("yedekler", [])
                    if isinstance(y, dict)
                ]
            except Exception as e:
                self.log.hata(KAYNAK, f"AI ayar yüklenemedi: {e}")

        if not self._ai_ayar.api_anahtari:
            self._ai_ayar.api_anahtari = (
                os.getenv("GEMINI_API_KEY") or
                os.getenv("OPENAI_API_KEY") or
                os.getenv("GROQ_API_KEY") or
                os.getenv("ANTHROPIC_API_KEY") or
                (self.beyin.get("gizli") or {}).get("gemini_api_anahtari", "")
            )

    def beyin_kaydet(self):
        _beyin_kaydet(self.beyin_dosyasi, self.beyin)

    def aktif_bilinc_kaydet(self):
        self.beyin["aktif_bilinc"] = self.aktif_bilinc
        self.beyin.setdefault("bilincler", {})
        self.beyin["bilincler"]["aktif"] = self.aktif_bilinc
        self.beyin_kaydet()

    def _merkez_erisim_hazirla(self):
        varsayilan = _merkez_erisim_varsayilanlari()
        mevcut = self.beyin.setdefault("merkez_erisim", {})
        mevcut.setdefault("varsayilanlar", {})
        mevcut.setdefault("profiller", {})
        for anahtar, deger in varsayilan["varsayilanlar"].items():
            mevcut["varsayilanlar"].setdefault(anahtar, deger)
        for ad, profil in varsayilan["profiller"].items():
            mevcut["profiller"].setdefault(ad, {})
            for alan, deger in profil.items():
                mevcut["profiller"][ad].setdefault(alan, deger)
        degisti = False
        local = mevcut["profiller"].setdefault("local_ip", {})
        if not local.get("host"):
            yerel_ip = _yerel_ip_bul()
            if yerel_ip:
                local["host"] = yerel_ip
                degisti = True
        tg = mevcut["profiller"].setdefault("telegram", {})
        if not tg.get("host"):
            try:
                with open(os.path.join(self.proje_yolu, "telegram_ayar.json"), "r", encoding="utf-8") as f:
                    tg_ayar = json.load(f)
                chat = tg_ayar.get("agent_chat") or tg_ayar.get("chat_id") or ""
                if chat:
                    tg["host"] = str(chat)
                    degisti = True
            except Exception:
                pass
        if degisti:
            self.beyin_kaydet()

    def merkez_erisim_profilleri(self) -> dict:
        self._merkez_erisim_hazirla()
        return self.beyin["merkez_erisim"]

    def merkez_erisim_profili_getir(self, ad: str) -> dict:
        return dict(self.merkez_erisim_profilleri().get("profiller", {}).get(ad, {}))

    def merkez_erisim_kaydet(self, profiller: dict, varsayilanlar: dict | None = None):
        self._merkez_erisim_hazirla()
        self.beyin["merkez_erisim"]["profiller"] = profiller
        if varsayilanlar is not None:
            self.beyin["merkez_erisim"]["varsayilanlar"] = varsayilanlar
        self.beyin_kaydet()

    def merkez_erisim_bilgisi(self, baglanti_modu: str) -> dict:
        self._merkez_erisim_hazirla()
        mod = (baglanti_modu or "ssh_reverse").strip().lower()
        profiller = self.beyin["merkez_erisim"]["profiller"]
        varsayilanlar = self.beyin["merkez_erisim"]["varsayilanlar"]
        profil_ad = varsayilanlar.get(mod, "local_ip")
        if mod == "ssh_reverse":
            for aday in ("local_ip", "clearnet", "tor_hidden_service"):
                profil = profiller.get(aday, {})
                if profil.get("etkin") and profil.get("host"):
                    profil_ad = aday
                    break
        profil = dict(profiller.get(profil_ad, {}))
        if profil_ad == "tor_hidden_service":
            onion = self.tor.onion_adresi_al("ssh") or self.uzuv.onion_host or profil.get("host", "")
            if onion:
                profil["host"] = onion
                profil["port"] = int(profil.get("port") or self.uzuv.onion_port or 22)
        if profil_ad == "telegram":
            try:
                with open(os.path.join(self.proje_yolu, "telegram_ayar.json"), "r", encoding="utf-8") as f:
                    tg = json.load(f)
                profil["host"] = tg.get("agent_chat") or tg.get("chat_id") or profil.get("host", "")
            except Exception:
                pass
        profil["ad"] = profil_ad
        return profil

    def _ai_ayar_kaydet(self):
        dosya = os.path.join(self.proje_yolu, "ai_ayar.json")
        veri = self._ai_ayar.to_dict(gizli_dahil=True)
        veri["yedekler"] = [
            y.to_dict(gizli_dahil=True) for y in self._ai_yedek_ayarlar
        ]
        with open(dosya, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _ai_anahtar_gerektirir(ayar: AIAyar) -> bool:
        return ayar.saglayici not in (
            AISağlayici.OLLAMA,
            AISağlayici.OLLAMA_UZAK,
        )

    @staticmethod
    def _ai_ortam_anahtari(ayar: AIAyar) -> str:
        if ayar.saglayici == AISağlayici.GEMINI:
            return os.getenv("GEMINI_API_KEY", "")
        if ayar.saglayici == AISağlayici.OPENAI:
            return os.getenv("OPENAI_API_KEY", "")
        if ayar.saglayici == AISağlayici.GROQ:
            return os.getenv("GROQ_API_KEY", "")
        if ayar.saglayici == AISağlayici.ANTHROPIC:
            return os.getenv("ANTHROPIC_API_KEY", "")
        return ""

    def _ai_baslat(self):
        self.ai = None
        self._ai_motorlari = []
        for ayar in [self._ai_ayar] + self._ai_yedek_ayarlar:
            if self._ai_anahtar_gerektirir(ayar) and not (ayar.api_anahtari or self._ai_ortam_anahtari(ayar)):
                self.log.uyari(KAYNAK, f"AI API anahtarı yok, atlandı: {ayar.saglayici}")
                continue
            try:
                motor = AIMotoru(ayar, self.log)
                self._ai_motorlari.append(motor)
                if motor.hazir and self.ai is None:
                    self.ai = motor
            except Exception as e:
                self.log.hata(KAYNAK, f"AI başlatılamadı ({ayar.saglayici}): {e}")
        if self.ai is None:
            self.ai = self._ai_motorlari[0] if self._ai_motorlari else None
        if not self._ai_motorlari:
            self.log.uyari(KAYNAK, "Hazır AI sağlayıcı bulunamadı. AI devre dışı.")
            return

    def ai_yeniden_baslat(self, yeni_ayar: AIAyar | None = None,
                          yedek_ayarlar: list[AIAyar] | None = None):
        if yeni_ayar:
            self._ai_ayar = yeni_ayar
        if yedek_ayarlar is not None:
            self._ai_yedek_ayarlar = yedek_ayarlar
        if yeni_ayar or yedek_ayarlar is not None:
            self._ai_ayar_kaydet()
        for motor in self._ai_motorlari:
            try:
                motor.yeniden_baslat()
            except Exception:
                pass
        self._ai_baslat()
        self.niyet.ai = self.ai

    def _ai_hazir_mi(self) -> bool:
        return any(m.hazir for m in self._ai_motorlari)

    def _ai_sor(self, metin: str) -> str:
        son_yanit = ""
        for motor in self._ai_motorlari:
            if not motor.hazir:
                continue
            yanit = motor.sor(metin)
            son_yanit = yanit
            basarisiz = (
                not yanit
                or "hazır değil" in yanit.lower()
                or "yanıt veremiyorum" in yanit.lower()
            )
            if not basarisiz:
                self.ai = motor
                self.niyet.ai = motor
                return yanit
            self.log.uyari(KAYNAK, f"AI sağlayıcı başarısız, yedeğe geçiliyor: {motor.ayar.saglayici}")
        return son_yanit or "AI motoru hazır değil. Lütfen ayarları kontrol edin."

    # ── Telegram ─────────────────────────────────────────────────────────────

    def _telegram_yukle(self):
        dosya = os.path.join(self.proje_yolu, "telegram_ayar.json")
        if not os.path.exists(dosya):
            return
        try:
            with open(dosya, "r", encoding="utf-8") as f:
                ayar = json.load(f)
            if not ayar.get("aktif"):
                return
            token = ayar.get("token", "").strip()
            if not token or token.startswith("BOT_TOKEN"):
                self.log.uyari(KAYNAK, "Telegram token ayarlanmamış, bot devre dışı.")
                return

            self._telegram_bot_kur(ayar)
        except Exception as e:
            self.log.hata(KAYNAK, f"Telegram yüklenemedi: {e}")

    def _telegram_bot_kur(self, ayar: dict):
        """TelegramBot nesnesini oluşturur, tüm bağlantıları ayarlar ve başlatır."""
        self.telegram = TelegramBot(self.log, ayar)
        self.telegram.komut_isleyici_ayarla(
            lambda m, k="telegram": self.isle(m, kanal=k)
        )
        self.telegram.panel_saglayici_ayarla(self.telegram_panel_durumu)
        self.telegram.kontrol_isleyici_ayarla(self.telegram_kontrol_uygula)
        self.telegram.varlik_saglayici_ayarla(self.telegram_varlik_getir)
        self.telegram.uzuv_gorev_saglayici_ayarla(self.telegram_uzuv_gorevleri)
        self.telegram.uzuv_gorev_cevap_isleyici_ayarla(self.telegram_uzuv_gorev_cevap_isle)
        self.telegram.uzuv_ekran_cevap_isleyici_ayarla(self.telegram_uzuv_ekran_cevap_isle)
        vosk_yol = self.beyin["ses"]["stt"].get("model_yolu", "")
        if vosk_yol and not os.path.isabs(vosk_yol):
            vosk_yol = os.path.join(self.proje_yolu, vosk_yol)
        self.telegram.vosk_model_yolu_ayarla(vosk_yol)
        self._telegram_log_dinleyici_ayarla()
        self.telegram.baslat()

    def _telegram_log_dinleyici_ayarla(self):
        if self._telegram_log_dinleyici:
            self.log.dinleyici_sil(self._telegram_log_dinleyici)
            self._telegram_log_dinleyici = None
        if self.telegram:
            self._telegram_log_dinleyici = self.telegram.log_bildir
            self.log.dinleyici_ekle(self._telegram_log_dinleyici)

    def telegram_panel_durumu(self) -> dict:
        return {
            "aktif_bilinc": self.aktif_bilinc,
            "bilincler": [
                k for k, v in self.beyin.get("bilincler", {}).items()
                if isinstance(v, dict)
            ],
            "wake_word_aktif": bool(getattr(self, "_wake_word_aktif", False)),
            "tehlikeli_onay": self.tehlikeli_komut_onayi_aktif_mi(),
            "bekleyen_onay": (self._bekleyen_onay or {}).get("metin", ""),
            "uzuvlar": [
                {
                    "id": u.id,
                    "ad": u.ad,
                    "durum": u.durum,
                    "baglanti": u.baglanti_ozeti() if hasattr(u, "baglanti_ozeti") else str(u.yontem),
                }
                for u in self.uzuv.uzuvlar.values()
            ],
            "makrolar": [
                {
                    "id": mid,
                    "ad": m.ad,
                    "aktif": m.aktif,
                    "tetik_tipi": m.tetik_tipi,
                    "adim_sayisi": len(m.adimlar),
                }
                for mid, m in sorted(self.makro.makrolar.items())
            ] if hasattr(self, "makro") else [],
        }

    def telegram_kontrol_uygula(self, eylem: str, deger: str = "") -> str:
        eylem = (eylem or "").strip().lower()
        deger = (deger or "").strip().lower()
        if eylem == "wake_word":
            aktif = deger in ("ac", "aç", "on", "true", "1")
            self.wake_word_modu_ayarla(aktif)
            self.beyin.setdefault("ses", {})
            self.beyin["ses"]["wake_word_aktif"] = aktif
            self.beyin_kaydet()
            return f"Wake word {'açıldı' if aktif else 'kapatıldı'}."
        if eylem == "wake_word_durum":
            return f"Wake word şu an {'açık' if getattr(self, '_wake_word_aktif', False) else 'kapalı'}."
        if eylem == "tehlikeli_onay":
            aktif = deger in ("ac", "aç", "on", "true", "1")
            self.beyin.setdefault("guvenlik", {})
            self.beyin["guvenlik"]["tehlikeli_komutlarda_onay"] = aktif
            self.beyin_kaydet()
            return f"Tehlikeli komut onayı {'açıldı' if aktif else 'kapatıldı'}."
        return "Bilinmeyen kontrol eylemi."

    def _uzuv_ekran_goruntu_al(self, uid: str) -> dict:
        uzuv = self.uzuv.uzuvlar.get(uid)
        if not uzuv:
            return {"ok": False, "mesaj": f"Uzuv bulunamadı: {uid}"}

        hedef = os.path.join("/tmp", f"zk_telegram_ekran_{uid}.png")
        baglanti_sirasi = self.uzuv._baglanti_sirasi(uzuv) if hasattr(self.uzuv, "_baglanti_sirasi") else []
        for baglanti in baglanti_sirasi:
            if baglanti.yontem in ("tor_http", "tor_https"):
                try:
                    r = self.uzuv._http_istek(baglanti, "/ekran", method="GET")
                    if r is not None:
                        if r.status_code == 200 and r.content:
                            with open(hedef, "wb") as f:
                                f.write(r.content)
                            return {"ok": True, "yol": hedef, "mesaj": f"{uzuv.ad} ekran görüntüsü"}
                        detay = ""
                        try:
                            detay = (r.text or "").strip()
                        except Exception:
                            detay = ""
                        if detay:
                            return {"ok": False, "mesaj": f"{uzuv.ad} HTTP ekran hatası: {detay[:180]}"}
                except Exception as e:
                    self.log.uyari(KAYNAK, f"{uid} HTTP ekran alma başarısız: {e}")
            if baglanti.yontem == "telegram" and self.telegram and self.telegram.calisıyor_mu():
                gorev = self._telegram_uzuv_gorev_olustur(uzuv, baglanti, "ekran_goruntusu", tur="ekran")
                if self.telegram.uzuv_ekran_istegi_gonder(gorev):
                    return self._telegram_uzuv_ekran_bekle(gorev["id"], 90.0)

        uzak = ""
        komut = ""
        temiz_uid = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in uid)
        if uzuv.tip in ("linux", "mac"):
            uzak = f"/tmp/zk_screen_{temiz_uid}.png"
            komut = (
                f"mkdir -p /tmp && "
                f"(gnome-screenshot -f {uzak} || scrot {uzak} || import -window root {uzak}) >/dev/null 2>&1"
            )
        elif uzuv.tip == "android":
            uzak = f"/sdcard/zk_screen_{temiz_uid}.png"
            komut = f"screencap -p {uzak}"
        elif uzuv.tip == "windows":
            return {"ok": False, "mesaj": "Windows uzuv ekran alma henüz eklenmedi."}
        else:
            return {"ok": False, "mesaj": f"Bu uzuv tipi için ekran alma desteklenmiyor: {uzuv.tip}"}

        sonuc = self.uzuv.komut_calistir(uid, komut)
        if "Tüm bağlantı yolları başarısız oldu." in (sonuc or ""):
            return {"ok": False, "mesaj": sonuc}
        if not self.uzuv.dosya_al(uid, uzak, hedef):
            return {"ok": False, "mesaj": f"{uid} uzvundan ekran görüntüsü alınamadı."}
        self.uzuv.komut_calistir(uid, f"rm -f {uzak}")
        return {"ok": os.path.exists(hedef), "yol": hedef, "mesaj": f"{uzuv.ad} ekran görüntüsü"}

    def telegram_varlik_getir(self, tur: str, hedef_id: str = "") -> dict:
        tur = (tur or "").strip().lower()
        if tur == "ekran":
            if hedef_id:
                return self._uzuv_ekran_goruntu_al(hedef_id)
            hedef = "/tmp/zk_telegram_ekran.png"
            mesaj = self.otomasyon.ekran_goruntu_al(hedef)
            ok = os.path.exists(hedef)
            return {"ok": ok, "yol": hedef if ok else "", "mesaj": mesaj}

        if tur == "log":
            log_yolu = os.path.join(self.proje_yolu, self.beyin["sistem"]["log_dosyasi"])
            if not os.path.exists(log_yolu):
                return {"ok": False, "mesaj": "Log dosyası bulunamadı."}
            hedef = "/tmp/zk_telegram_log.txt"
            try:
                with open(log_yolu, "r", encoding="utf-8", errors="replace") as src:
                    satirlar = src.readlines()[-300:]
                rapor = self._telegram_log_ozeti_olustur(satirlar)
                with open(hedef, "w", encoding="utf-8") as dst:
                    dst.write(rapor)
                return {"ok": True, "yol": hedef, "mesaj": "Filtreli log özeti"}
            except Exception as e:
                return {"ok": False, "mesaj": f"Log hazırlanamadı: {e}"}

        if tur == "yedek":
            liste = self.yedek.yedek_listesi()
            if not liste:
                try:
                    self.yedek._yedek_al_thread(hassas_dahil=False, callback=None)
                    liste = self.yedek.yedek_listesi()
                except Exception as e:
                    return {"ok": False, "mesaj": f"Yedek üretilemedi: {e}"}
            if not liste:
                return {"ok": False, "mesaj": "Henüz yedek yok."}
            son = liste[0]["tam_yol"]
            return {"ok": True, "yol": son, "mesaj": "En son yedek"}

        if tur == "tani":
            tani_dosyasi = os.path.join("/tmp", "zk_tani_raporu.txt")
            rapor = []
            rapor.append(f"Aktif bilinç: {self.aktif_bilinc}")
            rapor.append(f"Wake word: {'aktif' if getattr(self, '_wake_word_aktif', False) else 'pasif'}")
            rapor.append(f"Tehlikeli komut onayı: {'aktif' if self.tehlikeli_komut_onayi_aktif_mi() else 'pasif'}")
            rapor.append(f"Uzuv sayısı: {len(self.uzuv.uzuvlar)}")
            for uzuv in self.uzuv.uzuvlar.values():
                rapor.append(f"- {uzuv.id}: {uzuv.ad} | {uzuv.durum} | {uzuv.baglanti_ozeti() if hasattr(uzuv, 'baglanti_ozeti') else uzuv.yontem}")
            try:
                with open(tani_dosyasi, "w", encoding="utf-8") as f:
                    f.write("\n".join(rapor) + "\n")
                return {"ok": True, "yol": tani_dosyasi, "mesaj": "Tanı raporu"}
            except Exception as e:
                return {"ok": False, "mesaj": f"Tanı raporu yazılamadı: {e}"}

        return {"ok": False, "mesaj": "Bilinmeyen varlık türü."}

    def _telegram_log_ozeti_olustur(self, satirlar: list[str]) -> str:
        log_re = re.compile(r"^\[(?P<zaman>[^\]]+)\]\s+\[(?P<seviye>[^\]]+)\]\s+\[(?P<kaynak>[^\]]+)\]\s+(?P<mesaj>.*)$")
        kayitlar: list[dict] = []
        seviye_sayac = {"KRİTİK": 0, "HATA": 0, "UYARI": 0, "BİLGİ": 0}
        kaynak_sayac: dict[str, int] = {}
        tekrarli_mesajlar: dict[tuple[str, str], int] = {}

        for satir in satirlar:
            eslesme = log_re.match(satir.strip())
            if not eslesme:
                continue
            kayit = eslesme.groupdict()
            seviye = kayit["seviye"]
            kaynak = kayit["kaynak"]
            mesaj = kayit["mesaj"]
            kayitlar.append(kayit)
            seviye_sayac[seviye] = seviye_sayac.get(seviye, 0) + 1
            kaynak_sayac[kaynak] = kaynak_sayac.get(kaynak, 0) + 1
            tekrarli_mesajlar[(seviye, mesaj)] = tekrarli_mesajlar.get((seviye, mesaj), 0) + 1

        kritikler = [k for k in kayitlar if k["seviye"] in ("KRİTİK", "HATA")]
        uyarilar = [k for k in kayitlar if k["seviye"] == "UYARI"]
        operasyon = [
            k for k in kayitlar
            if k["kaynak"] in ("UZUV", "TOR", "YEDEK", "TELEGRAM", "ÇEKİRDEK")
        ]
        tekrarli = sorted(
            ((adet, seviye, mesaj) for (seviye, mesaj), adet in tekrarli_mesajlar.items() if adet > 1),
            reverse=True
        )
        kaynaklar = sorted(kaynak_sayac.items(), key=lambda x: (-x[1], x[0]))[:8]

        rapor = []
        rapor.append("Zihin Koprusu Telegram Log Ozeti")
        rapor.append("")
        if kayitlar:
            rapor.append(f"Kapsam: son {len(kayitlar)} kayit")
            rapor.append(f"Aralik: {kayitlar[0]['zaman']} -> {kayitlar[-1]['zaman']}")
        else:
            rapor.append("Kayit bulunamadi.")
            return "\n".join(rapor) + "\n"

        rapor.append("")
        rapor.append("Seviye ozeti:")
        for seviye in ("KRİTİK", "HATA", "UYARI", "BİLGİ"):
            rapor.append(f"- {seviye}: {seviye_sayac.get(seviye, 0)}")

        rapor.append("")
        rapor.append("En aktif kaynaklar:")
        for kaynak, adet in kaynaklar:
            rapor.append(f"- {kaynak}: {adet}")

        if tekrarli:
            rapor.append("")
            rapor.append("Tekrarlayan sorunlar:")
            for adet, seviye, mesaj in tekrarli[:5]:
                rapor.append(f"- {seviye} x{adet}: {mesaj[:140]}")

        if kritikler:
            rapor.append("")
            rapor.append("Son kritik / hata kayitlari:")
            for kayit in kritikler[-8:]:
                rapor.append(f"- {kayit['zaman']} [{kayit['seviye']}][{kayit['kaynak']}] {kayit['mesaj'][:180]}")

        if uyarilar:
            rapor.append("")
            rapor.append("Son uyarilar:")
            for kayit in uyarilar[-6:]:
                rapor.append(f"- {kayit['zaman']} [{kayit['kaynak']}] {kayit['mesaj'][:180]}")

        if operasyon:
            rapor.append("")
            rapor.append("Son operasyon olaylari:")
            for kayit in operasyon[-10:]:
                rapor.append(f"- {kayit['zaman']} [{kayit['kaynak']}] {kayit['mesaj'][:180]}")

        return "\n".join(rapor) + "\n"

    def telegram_uzuv_gorevleri(self) -> list[dict]:
        with self._telegram_uzuv_gorev_kilit:
            gorevler = list(self._telegram_uzuv_gorevleri.values())
        return sorted(gorevler, key=lambda x: x.get("olusturma_zamani", 0), reverse=True)

    def _telegram_uzuv_gorev_olustur(self, uzuv, baglanti, komut: str, tur: str = "komut") -> dict:
        gorev_id = f"tg-{uuid.uuid4().hex[:8]}"
        olay = threading.Event()
        gorev = {
            "id": gorev_id,
            "tur": tur,
            "uzuv_id": uzuv.id,
            "uzuv_ad": uzuv.ad,
            "baglanti": baglanti.yontem,
            "hedef": baglanti.host or baglanti.url or "tanımsız",
            "komut": komut,
            "durum": "bekliyor",
            "yanit": "",
            "dosya_yolu": "",
            "olusturma_zamani": time.time(),
            "tamamlanma_zamani": 0.0,
            "olay": olay,
        }
        with self._telegram_uzuv_gorev_kilit:
            self._telegram_uzuv_gorevleri[gorev_id] = gorev
        return gorev

    def telegram_uzuv_gorev_cevap_isle(self, gorev_id: str, durum: str, mesaj: str) -> str:
        gid = (gorev_id or "").strip()
        if not gid:
            return "Görev kimliği boş."
        with self._telegram_uzuv_gorev_kilit:
            gorev = self._telegram_uzuv_gorevleri.get(gid)
            if not gorev:
                return f"Görev bulunamadı: {gid}"
            gorev["durum"] = "tamamlandi" if (durum or "").strip().lower() in ("ok", "tamam", "basarili", "başarılı") else "hata"
            gorev["yanit"] = (mesaj or "").strip()
            gorev["tamamlanma_zamani"] = time.time()
            olay = gorev.get("olay")
        if isinstance(olay, threading.Event):
            olay.set()
        self.log.bilgi(KAYNAK, f"Telegram uzuv görevi kapandı: {gid} [{gorev['durum']}]")
        return f"Görev işlendi: {gid} [{gorev['durum']}]"

    def telegram_uzuv_ekran_cevap_isle(self, gorev_id: str, dosya_yolu: str, mesaj: str = "") -> str:
        gid = (gorev_id or "").strip()
        if not gid:
            return "Görev kimliği boş."
        if not dosya_yolu or not os.path.exists(dosya_yolu):
            return "Ekran dosyası bulunamadı."
        hedef = os.path.join("/tmp", f"zk_telegram_ekran_cevap_{gid}{os.path.splitext(dosya_yolu)[1] or '.bin'}")
        try:
            shutil.copy2(dosya_yolu, hedef)
        except Exception as e:
            return f"Ekran dosyası kopyalanamadı: {e}"

        with self._telegram_uzuv_gorev_kilit:
            gorev = self._telegram_uzuv_gorevleri.get(gid)
            if not gorev:
                return f"Görev bulunamadı: {gid}"
            gorev["durum"] = "tamamlandi"
            gorev["yanit"] = (mesaj or "").strip()
            gorev["dosya_yolu"] = hedef
            gorev["tamamlanma_zamani"] = time.time()
            olay = gorev.get("olay")
        if isinstance(olay, threading.Event):
            olay.set()
        self.log.bilgi(KAYNAK, f"Telegram uzuv ekran görevi kapandı: {gid}")
        return f"Ekran görevi işlendi: {gid}"

    def _telegram_uzuv_gorev_bekle(self, gorev_id: str, zaman_asimi: float) -> tuple[bool, str]:
        with self._telegram_uzuv_gorev_kilit:
            gorev = self._telegram_uzuv_gorevleri.get(gorev_id)
        if not gorev:
            return False, "Görev kaydı bulunamadı."
        olay = gorev.get("olay")
        if not isinstance(olay, threading.Event):
            return False, "Görev bekleme nesnesi bulunamadı."
        tamamlandi = olay.wait(timeout=zaman_asimi)
        with self._telegram_uzuv_gorev_kilit:
            guncel = self._telegram_uzuv_gorevleri.get(gorev_id, gorev)
        if not tamamlandi:
            return False, (
                f"Telegram uzuv görevi oluşturuldu: {gorev_id}. "
                "Yanıt süresi doldu; görev açık kaldı. "
                "Durumu görmek için /uzuv_gorevler, kapatmak için /uzuv_cevap kullanın."
            )
        if guncel.get("durum") == "tamamlandi":
            return True, guncel.get("yanit") or f"Telegram uzuv görevi tamamlandı: {gorev_id}"
        return False, guncel.get("yanit") or f"Telegram uzuv görevi hata ile döndü: {gorev_id}"

    def _telegram_uzuv_ekran_bekle(self, gorev_id: str, zaman_asimi: float) -> dict:
        with self._telegram_uzuv_gorev_kilit:
            gorev = self._telegram_uzuv_gorevleri.get(gorev_id)
        if not gorev:
            return {"ok": False, "mesaj": "Ekran görevi kaydı bulunamadı."}
        olay = gorev.get("olay")
        if not isinstance(olay, threading.Event):
            return {"ok": False, "mesaj": "Ekran görevi bekleme nesnesi bulunamadı."}
        tamamlandi = olay.wait(timeout=zaman_asimi)
        with self._telegram_uzuv_gorev_kilit:
            guncel = self._telegram_uzuv_gorevleri.get(gorev_id, gorev)
        if not tamamlandi:
            return {
                "ok": False,
                "mesaj": (
                    f"Telegram uzuv ekran görevi oluşturuldu: {gorev_id}. "
                    "Yanıt süresi doldu; görev açık kaldı. "
                    "Durumu görmek için /uzuv_ekran_gorevler."
                ),
            }
        yol = guncel.get("dosya_yolu", "")
        if guncel.get("durum") == "tamamlandi" and yol and os.path.exists(yol):
            return {"ok": True, "yol": yol, "mesaj": guncel.get("yanit") or "Uzuv ekranı alındı."}
        return {"ok": False, "mesaj": guncel.get("yanit") or "Telegram ekran görevi başarısız oldu."}

    def _uzuv_telegram_baglanti_isle(self, eylem: str, uzuv, baglanti, veri: dict):
        if eylem == "ping":
            return self.telegram is not None and self.telegram.calisıyor_mu()
        if eylem == "komut":
            komut = veri.get("komut", "").strip()
            if not komut:
                return "Telegram yedeği için komut boş."
            if self.telegram and self.telegram.calisıyor_mu():
                gorev = self._telegram_uzuv_gorev_olustur(uzuv, baglanti, komut)
                if not self.telegram.uzuv_gorevi_gonder(gorev):
                    return "Telegram yedek görevi gönderilemedi."
                basarili, yanit = self._telegram_uzuv_gorev_bekle(gorev["id"], 20.0)
                return yanit
            return "Telegram yedek kanalı tanımlı ama bot aktif değil."
        if eylem == "dosya_gonder":
            return False
        return None

    def telegram_yeniden_baslat(self, ayar: dict):
        if self.telegram:
            if self._telegram_log_dinleyici:
                self.log.dinleyici_sil(self._telegram_log_dinleyici)
                self._telegram_log_dinleyici = None
            self.telegram.durdur()
        dosya = os.path.join(self.proje_yolu, "telegram_ayar.json")
        with open(dosya, "w", encoding="utf-8") as f:
            json.dump(ayar, f, ensure_ascii=False, indent=2)
        if ayar.get("aktif") and ayar.get("token", "").strip():
            self._telegram_bot_kur(ayar)

    # ── Olay Sistemi ─────────────────────────────────────────────────────────

    def olay_dinleyici_ekle(self, fn: Callable[[str, str], None]):
        self._dinleyiciler.append(fn)

    def _olay_gonder(self, tip: str, veri: str):
        for fn in self._dinleyiciler:
            try:
                fn(tip, veri)
            except Exception:
                pass

    # ── Ana İşleyici ─────────────────────────────────────────────────────────

    def isle(self, metin: str, kanal: str = "ses", _onay_atla: bool = False) -> str:
        """
        kanal = "ses"      → Sesli komut: ses.konus() çağrılır, Telegram'a gönderilir
        kanal = "telegram" → Telegram komutu: ses.konus() çağrılmaz,
                             Telegram bot handler kendi gönderir (echo yok)
        kanal = "gui"      → GUI yazı komutu: ses.konus() çağrılır, Telegram'a gönderilmez
        """
        metin = metin.strip()
        if not metin:
            return ""

        if self._bekleyen_onay and not _onay_atla:
            ele_alindi, cevap = self._bekleyen_onayi_isle(metin)
            if ele_alindi:
                return cevap or ""

        # Ses kanalından geliyorsa STT düzeltmesini uygula
        if kanal == "ses":
            duzeltilmis = stt_duzelt(metin)
            if duzeltilmis != metin:
                self.log.bilgi("STT", f"Düzeltme: '{metin}' → '{duzeltilmis}'")
                metin = duzeltilmis

        self.log.bilgi("GİRDİ", f"[{kanal}] {metin}")
        self._olay_gonder("giris", metin)

        # Telegram ayar dosyasından çapraz ses bayraklarını oku
        _tg_ayar = self.telegram.ayar if self.telegram else {}
        _pc_tg_bildir = _tg_ayar.get("pc_tg_bildir", True)
        _tg_pc_konus  = _tg_ayar.get("tg_pc_konus",  False)
        _ses_pc_konus = _tg_ayar.get("ses_pc_konus",  False)

        if kanal == "ses":
            ses_aktif = True
            tg_bildir = _pc_tg_bildir   # PC sesli komut → TG'ye bildir (opsiyonel)
        elif kanal == "telegram_yazi":
            ses_aktif = _tg_pc_konus    # TG yazı → PC konuşsun (opsiyonel)
            tg_bildir = False           # TG handler kendi gönderir
        elif kanal == "telegram_ses":
            ses_aktif = _ses_pc_konus   # TG ses → PC konuşsun (opsiyonel)
            tg_bildir = False
        elif kanal == "telegram":
            # Geriye dönük uyumluluk
            ses_aktif = False
            tg_bildir = False
        elif kanal == "makro":
            # Makrolar sesli konuşabilir ama Telegram'a iletilmez
            ses_aktif = True
            tg_bildir = False
        else:  # "gui"
            ses_aktif = True
            tg_bildir = False

        # ── Ses kes ──────────────────────────────────────────────────────────
        if self.ses.komut_ses_kes_mi(metin) or any(k in metin.lower() for k in SES_KES_KELIMELER):
            self.ses.ses_kes()
            self.niyet.gecmisi_temizle()
            return ""

        # ── Tekrar önleme ────────────────────────────────────────────────────
        if metin.lower() == self._son_giris.lower() and self._son_yanit:
            self._olay_gonder("yanit", self._son_yanit)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, self._son_yanit)
            return self._son_yanit
        self._son_giris = metin

        # ── Bilinç devri ─────────────────────────────────────────────────────
        yeni = _devir_kontrol(metin, self.beyin["bilincler"])
        if yeni:
            self.aktif_bilinc = yeni
            self.aktif_bilinc_kaydet()
            self.niyet.gecmisi_temizle()
            yanit = self._hitap_yerlestir(self.dil.al("sistem", "devir"))
            self._olay_gonder("devir", self.aktif_bilinc)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit)
            if tg_bildir and self.telegram:
                self.telegram.bildirim_gonder(f"Bilinç → {yeni}")
            self._son_yanit = yanit
            return yanit

        # ── Niyet analizi ────────────────────────────────────────────────────
        niyet = self.niyet.analiz_et(metin)

        odak_yanit = self._uzuv_odak_komut_kontrol(metin)
        if odak_yanit:
            odak_yanit = self._hitap_yerlestir(odak_yanit)
            self._olay_gonder("yanit", odak_yanit)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, odak_yanit)
            if tg_bildir:
                self._telegram_yanit_gonder(odak_yanit)
            self._son_yanit = odak_yanit
            return odak_yanit

        if self._uzuv_odak_hedefleri:
            if (not _onay_atla and self.tehlikeli_komut_onayi_aktif_mi()
                    and self._uzuv_komut_tehlikeli_mi(metin)):
                yanit_onay = self._onay_istenen_yanit(metin, kanal)
                if ses_aktif:
                    self.ses.konus(self.aktif_bilinc, yanit_onay)
                return yanit_onay
            odakli_yanit = self._ham_uzuv_komut_kontrol(metin) or self._uzuv_komut_kontrol(metin)
            if odakli_yanit:
                odakli_yanit = self._hitap_yerlestir(odakli_yanit)
                self._olay_gonder("yanit", odakli_yanit)
                if ses_aktif:
                    self.ses.konus(self.aktif_bilinc, odakli_yanit)
                if tg_bildir:
                    self._telegram_yanit_gonder(odakli_yanit)
                self._son_yanit = odakli_yanit
                return odakli_yanit

        # ── Komut DB'de sohbet/sistem komutu var mı? → Önce kontrol et ─────────
        eslesen_komut = self.komut_db.esles(self.aktif_bilinc, metin)
        if (eslesen_komut and not _onay_atla and self.tehlikeli_komut_onayi_aktif_mi()
                and self._tehlikeli_komut_mu(eslesen_komut, metin)):
            yanit_onay = self._onay_istenen_yanit(metin, kanal)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit_onay)
            return yanit_onay

        yanit_db_once = self.komut_db.calistir(
            self.aktif_bilinc, metin,
            hedef_os="linux", uzuv_yoneticisi=self.uzuv)
        if yanit_db_once:
            # Özel tur sinyalleri işle
            if yanit_db_once.startswith("__TUR:") or yanit_db_once.startswith("__WEB:"):
                yanit_db_once = self._tur_sinyali_isle(yanit_db_once, metin)
            if yanit_db_once:
                yanit_db_once = self._hitap_yerlestir(yanit_db_once)
                self._olay_gonder("yanit", yanit_db_once)
                if ses_aktif:
                    self.ses.konus(self.aktif_bilinc, yanit_db_once)
                if tg_bildir:
                    self._telegram_yanit_gonder(yanit_db_once)
                self._hafiza_kaydet(metin, yanit_db_once)
                self._son_yanit = yanit_db_once
                return yanit_db_once

        # ── Web/Jarvis komutları → Sekme yerine doğrudan sesli/yazılı kontrol ─
        yanit_web = self._web_komut_kontrol(metin, niyet)
        if yanit_web:
            yanit_web = self._hitap_yerlestir(yanit_web)
            self._olay_gonder("yanit", yanit_web)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit_web)
            if tg_bildir:
                self._telegram_yanit_gonder(yanit_web)
            self._son_yanit = yanit_web
            return yanit_web

        # ── Sohbet niyeti → AI'ye gönder ─────────────────────────────────────
        if niyet.tip in AI_SOHBET_TIPLERI and self._ai_hazir_mi():
            yanit = self._ai_sor(metin)
            yanit = self._hitap_yerlestir(yanit)
            self._olay_gonder("yanit", yanit)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit)
            if tg_bildir:
                self._telegram_yanit_gonder(yanit)
            self._hafiza_kaydet(metin, yanit)
            self._son_yanit = yanit
            return yanit
        if niyet.tip in AI_SOHBET_TIPLERI:
            yanit = self._yerel_sohbet_yanit(metin)
            if yanit:
                yanit = self._hitap_yerlestir(yanit)
                self._olay_gonder("yanit", yanit)
                if ses_aktif:
                    self.ses.konus(self.aktif_bilinc, yanit)
                if tg_bildir:
                    self._telegram_yanit_gonder(yanit)
                self._son_yanit = yanit
                return yanit

        # ── Otomasyon niyetleri ──────────────────────────────────────────────
        if niyet.tip in OTOMASYON_TIPLERI and niyet.guven >= 0.75:
            yanit_oto = self.otomasyon.isle(niyet)
            if yanit_oto:
                yanit_oto = self._hitap_yerlestir(yanit_oto)
                self._olay_gonder("yanit", yanit_oto)
                if ses_aktif:
                    self.ses.konus(self.aktif_bilinc, yanit_oto)
                if tg_bildir:
                    self._telegram_yanit_gonder(yanit_oto)
                self._son_yanit = yanit_oto
                return yanit_oto

        # ── Uzuv yönlendirmeli komut ─────────────────────────────────────────
        if (not _onay_atla and self.tehlikeli_komut_onayi_aktif_mi()
                and self._uzuv_komut_tehlikeli_mi(metin)):
            yanit_onay = self._onay_istenen_yanit(metin, kanal)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit_onay)
            return yanit_onay

        yanit = self._ham_uzuv_komut_kontrol(metin)
        if yanit:
            yanit = self._hitap_yerlestir(yanit)
            self._olay_gonder("yanit", yanit)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit)
            if tg_bildir:
                self._telegram_yanit_gonder(yanit)
            self._son_yanit = yanit
            return yanit

        yanit = self._uzuv_komut_kontrol(metin)
        if yanit:
            yanit = self._hitap_yerlestir(yanit)
            self._olay_gonder("yanit", yanit)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit)
            if tg_bildir:
                self._telegram_yanit_gonder(yanit)
            self._son_yanit = yanit
            return yanit

        # (Komut DB önce işlendi — yukarıda)
        # ── AI (geri dönüş) ──────────────────────────────────────────────────
        if self._ai_hazir_mi():
            yanit = self._ai_sor(metin)
            yanit = self._hitap_yerlestir(yanit)
            self._olay_gonder("yanit", yanit)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit)
            if tg_bildir:
                self._telegram_yanit_gonder(yanit)
            self._son_yanit = yanit
            return yanit

        # AI kapalıyken basit sohbeti yine de yanıtsız bırakma.
        yanit = self._yerel_sohbet_yanit(metin)
        if yanit:
            yanit = self._hitap_yerlestir(yanit)
            self._olay_gonder("yanit", yanit)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit)
            if tg_bildir:
                self._telegram_yanit_gonder(yanit)
            self._son_yanit = yanit
            return yanit

        metin_norm = normalize_tr(metin)
        if any(k in metin_norm for k in ("nedir", "kimdir", "neden", "nasil", "niye", "anlat", "acikla", "sence")):
            yanit = "Bunu cevaplamak için AI bağlantısı hazır değil. AI ayarlarına Gemini, OpenAI, Groq veya yerel Ollama ekleyin."
            self._olay_gonder("yanit", yanit)
            if ses_aktif:
                self.ses.konus(self.aktif_bilinc, yanit)
            if tg_bildir:
                self._telegram_yanit_gonder(yanit)
            self._son_yanit = yanit
            return yanit

        # ── Hiçbirine uymadı ────────────────────────────────────────────────
        yanit = self._hitap_yerlestir(self.dil.al("sistem", "anlamadim"))
        if ses_aktif:
            self.ses.konus(self.aktif_bilinc, yanit)
        self._son_yanit = yanit
        return yanit

    def _yerel_sohbet_yanit(self, metin: str) -> str:
        ml = normalize_tr(metin or "")
        if any(k in ml for k in ("ne var ne yok", "naber", "ne haber", "nasilsin")):
            return "Buradayım. Komutları dinliyorum."
        if "ne yapiyorsun" in ml:
            return "Komut bekliyorum ve sistemi izliyorum."
        if any(k in ml for k in ("ne yapacagiz", "ne yapalim", "ne yapayim")):
            return "Uygulama açabilir, webde arama yapabilir, ekranı okuyabilir veya uzuvları kontrol edebilirim."
        if any(k in ml for k in ("merak ettim", "bilmem", "oyle")):
            return "Anladım. Bir şey istersen kısa ve net söylemen yeterli."
        if any(k in ml for k in ("yardim", "ne yapabilirsin")):
            return "Uygulama açma, web arama, tıklama, yazma, ekran okuma ve uzuv kontrolü yapabilirim."
        return ""


    def _tur_sinyali_isle(self, sinyal: str, orijinal_metin: str) -> str:
        """__TUR:tip:kod__ ve __WEB:url__ sinyallerini işler."""
        import urllib.parse, subprocess as _sp
        if sinyal.startswith("__WEB:"):
            url_sablon = sinyal[6:].strip("_")
            sorgu = self._web_sorgu_ayikla(orijinal_metin, url_sablon)
            url = url_sablon.replace("{sorgu}", urllib.parse.quote(sorgu))
            _sp.Popen(["xdg-open", url])
            return f"Aranıyor: {sorgu}"

        if sinyal.startswith("__TUR:"):
            parcalar = sinyal.strip("_").split(":")
            tur  = parcalar[1] if len(parcalar) > 1 else ""
            kod  = parcalar[2] if len(parcalar) > 2 else ""
            try:
                if tur == "sistem_bilgi":
                    return self.otomasyon.sistem_bilgi(kod)
                elif tur == "hafiza":
                    return self.hafiza.sesli_komut_isle(orijinal_metin) or ""
                elif tur in ("hava", "takvim"):
                    return self.hava_takvim.sesli_komut_isle(orijinal_metin) or ""
                elif tur == "makro":
                    return self.makro.sesli_tetikle(orijinal_metin) or ""
            except Exception as e:
                self.log.hata(KAYNAK, f"Sinyal işleme hatası: {e}")
                return ""
        return sinyal

    def _web_sorgu_ayikla(self, metin: str, url_sablon: str = "") -> str:
        ml = (metin or "").strip().lower()
        if not ml:
            return ""
        temiz = re.sub(r"\b(?:açar mısın|acar misin|açarmısın|acarmisin|aç|ac|bul|ara|lütfen|lutfen|hadi|bana)\b", " ", ml)
        if "youtube" in url_sablon or "youtube" in ml or "yutub" in ml:
            temiz = re.sub(r"\b(?:youtube|yutub|you tube)\s*(?:da|de)?\b", " ", temiz)
        elif "google" in url_sablon:
            temiz = re.sub(r"\b(?:google|gugıl|gugil|internette|webde|web)\s*(?:da|de)?\b", " ", temiz)
        elif "wikipedia" in url_sablon:
            temiz = re.sub(r"\b(?:wikipedia|vikipedi)\s*(?:da|de)?\b", " ", temiz)
        temiz = re.sub(r"\s+", " ", temiz).strip(" ?.,!")
        return temiz or ml

    def _web_komut_kontrol(self, metin: str, niyet=None) -> str:
        """Web sekmesine bağlı işleri doğrudan sesli/yazılı komut olarak yürütür."""
        if not getattr(self, "web", None):
            return ""

        ml = (metin or "").strip().lower()
        if not ml:
            return ""

        def _web_aktif_et() -> None:
            # Sesli kullanımda en sağlam varsayılan: görünür Playwright.
            try:
                self.web.mod_ayarla("playwright")
                self.web.gorunurluk_ayarla(True)
                self.web.baslat()
            except Exception:
                pass

        # Açık URL veya site açma.
        url_m = re.search(
            r"(https?://[^\s]+|www\.[^\s]+|[a-z0-9\-]+\.(?:com|net|org|io|tr|co|gov|edu)(?:/[^\s]*)?)",
            ml,
            re.I,
        )
        if url_m and any(k in ml for k in ("aç", "git", "gir", "bak")):
            return self.web.git(url_m.group(0))

        # Arama motorları.
        arama_kaliplari = [
            (r"(?:google['\s]?da|internette|web['\s]?de)\s+(.+?)\s+(?:ara|bul|sorgula)$", "google"),
            (r"(?:google|chrome|tarayıcı|tarayici)\s+(?:da|de|üzerinde|uzerinde)\s+(.+?)\s+(?:ara|bul|sorgula)$", "google"),
            (r"(?:ara|bul|sorgula)\s+(.+)$", "google"),
            (r"(.+?)\s+(?:google['\s]?da|internette|web['\s]?de)\s+(?:ara|bul|sorgula)$", "google"),
            (r"(.+?)\s+(?:google|chrome|tarayıcı|tarayici)\s+(?:da|de|üzerinde|uzerinde)\s+(?:ara|bul|sorgula)$", "google"),
            (r"(?:youtube['\s]?da|yutub['\s]?da)\s+(.+?)\s+(?:ara|bul)$", "youtube"),
            (r"(.+?)\s+(?:youtube['\s]?da|yutub['\s]?da)\s+(?:ara|bul)$", "youtube"),
            (r"(?:wikipedia['\s]?da|vikipedi['\s]?de)\s+(.+?)\s+(?:ara|bul)$", "wikipedia"),
        ]
        for desen, motor in arama_kaliplari:
            m = re.search(desen, ml)
            if m:
                sorgu = m.group(1).strip()
                if sorgu and sorgu not in ("bunu", "şunu", "onu"):
                    return self.web.ara(sorgu, motor=motor)

        # Tarayıcı/sayfa kontrolü.
        if any(k in ml for k in ("yeni sekme aç", "yeni sekme")):
            return self.web.yeni_sekme()
        if any(k in ml for k in ("geri git", "geri dön", "önceki sayfa")):
            return self.web.geri_git()
        if any(k in ml for k in ("ileri git", "sonraki sayfa")):
            return self.web.ileri_git()
        if any(k in ml for k in ("sayfayı yenile", "yenile", "tekrar yükle")):
            return self.web.yenile()
        if any(k in ml for k in ("aşağı kaydır", "aşağı in", "sayfayı aşağı")):
            return self.web.kaydır("asagi")
        if any(k in ml for k in ("yukarı kaydır", "yukarı çık", "sayfayı yukarı")):
            return self.web.kaydır("yukari")

        # Web sayfası okuma/OCR.
        if any(k in ml for k in ("ekrandaki yazıyı oku", "ekranı oku", "ne yazıyor")):
            return self.web.ekran_oku_ve_seslendir()
        if any(k in ml for k in (
            "sayfadaki düğmeleri oku", "sayfadaki dugmeleri oku",
            "sayfadaki öğeleri oku", "sayfadaki ogeleri oku",
            "neler var", "tıklanacakları oku", "tiklanacaklari oku",
        )):
            _web_aktif_et()
            return self.web.sayfa_elemanlari_oku()
        if any(k in ml for k in ("sayfayı oku", "bu sayfayı oku", "web sayfasını oku")):
            _web_aktif_et()
            return self.web.haber_oku()
        if any(k in ml for k in ("haberleri oku", "gündemi oku", "son haberleri oku")):
            _web_aktif_et()
            self.web.git("https://news.google.com/topstories?hl=tr&gl=TR&ceid=TR:tr")
            return "Haberler açıldı. Bir haber seçince 'sayfayı oku' diyebilirsiniz."

        # Tıklama ve yazma.
        for desen in (
            r"(?:ekrandaki|sayfadaki)\s+(.+?)\s+(?:yazısına|yazisina|metnine|butonuna|düğmesine|dugmesine|linkine)?\s*(?:tıkla|tikla|bas)$",
            r"(.+?)\s+(?:düğmesine|dugmesine|butonuna|linkine|bağlantısına|baglantisina)\s+(?:tıkla|tikla|bas)$",
        ):
            m = re.search(desen, ml)
            if m:
                hedef = m.group(1).strip()
                if hedef:
                    _web_aktif_et()
                    return self.web.tikla(hedef)

        for desen in (
            r"(.+?)\s+(?:butonuna|linkine)?\s*(?:tıkla|bas)$",
            r"(?:tıkla|bas)\s+(.+)$",
        ):
            m = re.search(desen, ml)
            if m:
                hedef = m.group(1).strip()
                if hedef and hedef not in ("fareye", "buraya"):
                    return self.web.tikla(hedef)

        for desen in (
            r"(.+?)\s+(?:alanına|alanina|kutusuna|bölümüne|bolumune|formuna)\s+(.+?)\s+(?:yaz|gir|doldur)$",
            r"(.+?)\s+(?:yaz|gir)\s+(.+?)\s+(?:alanına|alanina|kutusuna|bölümüne|bolumune|formuna)$",
            r"(?:alana|kutucuğa|kutucuga|forma)\s+(.+?)\s+(?:olarak\s+)?(.+?)\s+(?:yaz|gir)$",
        ):
            m = re.search(desen, ml)
            if m:
                birinci = m.group(1).strip()
                ikinci = m.group(2).strip()
                if birinci and ikinci:
                    _web_aktif_et()
                    if " yaz " in ml or " gir " in ml:
                        alan, yazi = (ikinci, birinci) if desen.startswith("(.+?)\\s+(?:yaz") else (birinci, ikinci)
                    else:
                        alan, yazi = birinci, ikinci
                    return self.web.alana_yaz(alan, yazi)

        for desen in (
            r"(?:webde|sayfada|alana|kutucuğa|forma)\s+(.+?)\s+(?:yaz|gir)$",
            r"(?:yaz|gir)\s+(.+)$",
        ):
            m = re.search(desen, ml)
            if m and any(k in ml for k in ("webde", "sayfada", "alana", "kutucuğa", "forma", "yaz ")):
                yazi = m.group(1).strip()
                if yazi:
                    return self.web.yaz(yazi)

        for desen in (
            r"(?:yorum\s+yaz|yorum\s+yap|yoruma\s+yaz)\s+(.+)$",
            r"(.+?)\s+(?:diye\s+yorum\s+yaz|yorum\s+olarak\s+yaz)$",
        ):
            m = re.search(desen, ml)
            if m:
                yorum = m.group(1).strip()
                if yorum:
                    _web_aktif_et()
                    return self.web.yorum_yap(yorum)

        if ml in ("gönder", "formu gönder", "yorumu gönder", "tamam gönder"):
            return self.web.gonder()

        # Niyet motorunun yakaladığı web niyetleri.
        if niyet and getattr(niyet, "guven", 0) >= 0.75:
            if niyet.tip == NiyetTipi.WEB_GEZ and niyet.hedef:
                return self.web.git(niyet.hedef)
            if niyet.tip == NiyetTipi.WEB_TIKLA:
                return self.web.tikla(niyet.hedef or "")
            if niyet.tip == NiyetTipi.WEB_KAYDIR:
                return self.web.kaydır(niyet.eylem or "asagi")
            if niyet.tip == NiyetTipi.ARAMA and niyet.hedef:
                return self.web.ara(niyet.hedef)

        return ""

    def _hafiza_kaydet(self, giris: str, yanit: str):
        """Konuşmayı hafızaya kaydet."""
        if hasattr(self, 'hafiza'):
            self.hafiza.konusma_ekle(
                "kullanici", giris, self.aktif_bilinc)
            self.hafiza.konusma_ekle(
                "sistem", yanit, self.aktif_bilinc)

    def _telegram_yanit_gonder(self, yanit: str):
        """Sadece ses kanalından gelen komutların yanıtını Telegram'a ilet."""
        if self.telegram and self.telegram.ayar.get("yanit_gonder"):
            self.telegram.bildirim_gonder(yanit)

    def _uzuv_hedeflerini_coz(self, metin: str) -> tuple[list[tuple[str, object]], str]:
        orijinal = (metin or "").strip()
        ml = orijinal.lower()
        tum_tetikler = [
            "tüm uzuvlara", "tum uzuvlara", "hepsine", "tüm cihazlara",
            "tum cihazlara", "bütün uzuvlara", "butun uzuvlara",
            "tüm bilgisayarlara", "tum bilgisayarlara",
        ]
        for tetik in tum_tetikler:
            if ml.startswith(tetik):
                kalan = orijinal[len(tetik):].strip(" ,:")
                return list(self.uzuv.uzuvlar.items()), kalan

        for uid, uzuv in self.uzuv.uzuvlar.items():
            for isaret in uzuv.sesli_isimler():
                if ml.startswith(isaret + " "):
                    kalan = orijinal[len(isaret):].strip(" ,:")
                    return [(uid, uzuv)], kalan
                if ml == isaret:
                    return [(uid, uzuv)], ""
        if self._uzuv_odak_hedefleri:
            hedefler = [
                (uid, self.uzuv.uzuvlar[uid])
                for uid in self._uzuv_odak_hedefleri
                if uid in self.uzuv.uzuvlar
            ]
            if hedefler:
                return hedefler, orijinal
        return [], orijinal

    def _uzuv_odak_komut_kontrol(self, metin: str) -> str | None:
        orijinal = (metin or "").strip()
        ml = orijinal.lower().strip(" .,!?:")
        if not ml:
            return None

        temizle_tetikleri = (
            "odağı temizle", "odagi temizle", "odaktan çık", "odaktan cik",
            "merkeze odaklan", "kendi sistemime odaklan", "bu bilgisayara odaklan",
            "merkez komuta dön", "merkez komuta don",
        )
        if any(t in ml for t in temizle_tetikleri):
            self._uzuv_odak_hedefleri = []
            self._uzuv_odak_etiket = ""
            return "Odak merkeze alındı. Komutlar bu sistemde çalışacak."

        odak_tetikleri = (
            " odaklan", " odak ol", " hedef al", " kilitlen",
            " üzerine odaklan", " uzerine odaklan",
        )
        if not any(t in ml for t in odak_tetikleri):
            return None

        tum_tetikler = (
            "tüm uzuvlara", "tum uzuvlara", "tüm cihazlara", "tum cihazlara",
            "hepsine", "bütün uzuvlara", "butun uzuvlara",
        )
        if any(t in ml for t in tum_tetikler):
            self._uzuv_odak_hedefleri = list(self.uzuv.uzuvlar.keys())
            self._uzuv_odak_etiket = "tüm uzuvlar"
            return "Odak tüm uzuvlara alındı. Sonraki uygun komutlar tüm uzuvlara gönderilecek."

        for uid, uzuv in self.uzuv.uzuvlar.items():
            for isaret in uzuv.sesli_isimler():
                if re.search(rf"(?<!\w){re.escape(isaret.lower())}(?!\w)", ml):
                    self._uzuv_odak_hedefleri = [uid]
                    self._uzuv_odak_etiket = uzuv.ad
                    return f"Odak {uzuv.ad} uzvuna alındı. Sonraki uygun komutlar bu uzuva gönderilecek."
        return None

    @staticmethod
    def _uzuv_ham_modu_coz(metin: str) -> tuple[str, str]:
        kaliplar = [
            ("powershell komutu", "powershell"),
            ("powershell", "powershell"),
            ("cmd komutu", "cmd"),
            ("cmd", "cmd"),
            ("adb komutu", "adb"),
            ("adb", "adb"),
            ("terminal komutu", "terminal"),
            ("terminal", "terminal"),
            ("kabuk komutu", "terminal"),
            ("shell komutu", "terminal"),
            ("ham komut", "terminal"),
            ("direkt komut", "terminal"),
        ]
        temiz = (metin or "").strip(" ,:")
        alt = temiz.lower()
        for kalip, mod in kaliplar:
            if alt.startswith(kalip):
                return mod, temiz[len(kalip):].strip(" ,:")
        return "", temiz

    @staticmethod
    def _uzuv_ham_komut_paketle(uzuv, mod: str, komut: str) -> str:
        komut = (komut or "").strip()
        if not komut:
            return ""
        tip = str(getattr(uzuv, "tip", "")).lower()
        if mod == "adb":
            return komut
        if mod == "powershell":
            guvenli = komut.replace('"', '`"')
            return f'powershell -NoProfile -Command "{guvenli}"'
        if mod == "cmd":
            guvenli = komut.replace('"', '\\"')
            return f'cmd /c "{guvenli}"'
        if mod == "terminal":
            if tip == "windows":
                guvenli = komut.replace('"', '\\"')
                return f'cmd /c "{guvenli}"'
            if tip == "android":
                return f"sh -lc {shlex.quote(komut)}"
            return f"bash -lc {shlex.quote(komut)}"
        return komut

    def _ham_uzuv_komut_kontrol(self, metin: str) -> str | None:
        hedefler, kalan = self._uzuv_hedeflerini_coz(metin)
        if not hedefler:
            return None
        mod, komut = self._uzuv_ham_modu_coz(kalan)
        if not mod or not komut:
            return None

        yanitlar = []
        for uid, uzuv in hedefler:
            calisacak = self._uzuv_ham_komut_paketle(uzuv, mod, komut)
            if not calisacak:
                continue
            sonuc = self.uzuv.komut_calistir(uid, calisacak, timeout=45)
            yanitlar.append(f"[{uzuv.ad}] {sonuc}")
        return "\n".join(yanitlar) if yanitlar else None

    def _uzuv_komut_kontrol(self, metin: str) -> str | None:
        hedefler, kalan = self._uzuv_hedeflerini_coz(metin)
        if len(hedefler) > 1:
            yanit_parcalari = []
            for uid, uzuv in hedefler:
                sonuc = self.komut_db.calistir(
                    self.aktif_bilinc, kalan,
                    hedef_os=uzuv.tip,
                    uzuv_yoneticisi=self.uzuv
                )
                if sonuc:
                    yanit_parcalari.append(f"[{uzuv.ad}] {sonuc}")
            return "\n".join(yanit_parcalari) if yanit_parcalari else None

        if len(hedefler) == 1:
            uid, uzuv = hedefler[0]
            if not kalan:
                return None
            yanit = self.komut_db.calistir(
                self.aktif_bilinc, kalan,
                hedef_os=uzuv.tip,
                uzuv_yoneticisi=self.uzuv
            )
            if yanit:
                return f"[{uzuv.ad}] {yanit}"
        return None

    def _uzuv_komut_tehlikeli_mi(self, metin: str) -> bool:
        hedefler, kalan = self._uzuv_hedeflerini_coz(metin)
        if not hedefler:
            return False
        mod, ham_komut = self._uzuv_ham_modu_coz(kalan)
        if mod and ham_komut:
            return self._tehlikeli_komut_mu(metin=ham_komut)
        if kalan:
            return self._tehlikeli_komut_mu(metin=kalan)
        return False

    # ── Ses Döngüsü ──────────────────────────────────────────────────────────

    def baslat(self):
        self._calisıyor = True
        self.log.bilgi(KAYNAK, f"Başladı | Aktif: {self.aktif_bilinc}")
        hazir_metni = self._hitap_yerlestir(self.dil.al("sistem", "hazir"))
        self.ses.konus(self.aktif_bilinc, hazir_metni)
        self._olay_gonder("basladi", self.aktif_bilinc)

        # Hava/Takvim/Güncelleme başlat
        self.hava_takvim.baslat(
            bildirim_fn=lambda m: self.ses.konus(self.aktif_bilinc, m))

        # Makro izleyiciyi başlat
        self.makro.baslat()

        # Wake word modu aktifse döngü yerine wake word motoru kullan
        if getattr(self, '_wake_word_aktif', False):
            self.wake.baslat()
            import time as _t
            while self._calisıyor:
                _t.sleep(0.5)
            return

        # Normal mod: sürekli dinle
        while self._calisıyor:
            try:
                metin = self.ses.dinle()
                if metin:
                    self.isle(metin, kanal="ses")
            except Exception as e:
                self.log.hata(KAYNAK, f"Döngü hatası: {e}")

    def baslat_arkaplanda(self):
        t = threading.Thread(target=self.baslat, daemon=True)
        t.start()
        return t

    def _tor_otomatik_baslat(self):
        """Tor'u arka planda otomatik başlat."""
        import time as _t
        _t.sleep(3)
        try:
            self.tor.baslat()
        except Exception as e:
            self.log.uyari(KAYNAK, f"Tor otomatik başlatma hatası: {e}")

    def _wake_word_tetiklendi(self, kelime: str):
        """
        Wake word algılandı:
        - Kısa onay sesi çal
        - Komut dinlemeye geç
        - Komut işle
        """
        self.log.bilgi(KAYNAK, f"Wake word: '{kelime}'")
        self._olay_gonder("wake_word", kelime)

        # Acil komut özel akış
        if kelime == "acil":
            self._olay_gonder("durum", "acil")

        # Onay sesi (kısa bip) — efekt parametresiyle farklılaştır
        try:
            self.ses.konus_bloklu(self.aktif_bilinc, "Efendim?")
        except Exception:
            pass

        # Komut dinle
        try:
            metin = self.ses.dinle(zaman_asimi=9.0, sessizlik_suresi=1.0)
            if metin:
                self.isle(metin, kanal="ses")
            else:
                self.log.bilgi(KAYNAK, "Wake word sonrası komut algılanmadı.")
        except Exception as e:
            self.log.hata(KAYNAK, f"Wake word komut hatası: {e}")

    def _onion_hazir_isle(self, onion: str):
        """
        Tor onion adresi hazır olunca:
        - uzuv_yoneticisi.onion_host'u günceller
        - uzuvlar.json'ı kaydeder
        - GUI dinleyicilerine olayı iletir
        """
        if not onion:
            return
        self.uzuv.onion_host = onion
        self._merkez_erisim_hazirla()
        tor_profil = self.beyin["merkez_erisim"]["profiller"].setdefault(
            "tor_hidden_service", {}
        )
        tor_profil["host"] = onion
        tor_profil["port"] = int(tor_profil.get("port") or self.uzuv.onion_port or 22)
        tor_profil["etkin"] = True
        self.beyin_kaydet()
        self.uzuv.kaydet()
        self.log.bilgi(KAYNAK,
            f"Onion adresi otomatik tanımlandı → {onion}")
        self._olay_gonder("onion_hazir", onion)

    def _uzuv_kayit_isle(self, veri: dict):
        uid = str(veri.get("uzuv_id", "")).strip()
        if not uid:
            return
        uzuv = self.uzuv.uzuvlar.get(uid)
        if not uzuv:
            return
        host = str(veri.get("ip") or veri.get("yerel_ip") or "").strip()
        http_port = int(veri.get("http_port") or 0)
        token = str(veri.get("http_token") or veri.get("token") or "").strip()
        bag_modu = str(veri.get("baglanti_yontemi") or veri.get("baglanti_modu") or "").strip().lower()
        guncellendi = False
        if host and http_port:
            hedefler = uzuv.etkin_baglantilar() or [uzuv.birincil_baglanti()]
            tercih = None
            for bag in hedefler:
                if bag.yontem in ("tor_http", "tor_https"):
                    tercih = bag
                    break
            if tercih is None and hedefler:
                tercih = hedefler[0]
            if tercih is not None:
                tercih.host = host
                tercih.port = http_port
                tercih.aktif = True
                if token:
                    tercih.token = token
                if bag_modu in ("tor_http", "tor_https"):
                    tercih.yontem = bag_modu
                guncellendi = True
        uzuv.durum = "bağlı"
        if guncellendi:
            self.uzuv.kaydet()
            self.log.bilgi(KAYNAK, f"Uzuv kaydı güncellendi: {uid} -> {host}:{http_port}")
        self._olay_gonder("uzuv_durum", uid)

    def durdur(self):
        self._calisıyor = False
        self.aktif_bilinc_kaydet()
        self.ses.ses_kes()
        if hasattr(self, 'hava_takvim'):
            self.hava_takvim.durdur()
        if hasattr(self, 'makro'):
            self.makro.durdur()
        if hasattr(self, 'wake') and self.wake.aktif_mi:
            self.wake.durdur()
        if self.telegram:
            self.telegram.durdur()
        self.log.bilgi(KAYNAK, "Durduruldu.")
        self._olay_gonder("durduruldu", "")

    def wake_word_modu_ayarla(self, aktif: bool,
                               kelimeler: list[str] | None = None):
        """Wake word modunu aç/kapat, kelimeleri güncelle."""
        self._wake_word_aktif = aktif
        if kelimeler:
            self.wake.wake_words_guncelle(kelimeler)
        if aktif and self._calisıyor:
            self.wake.baslat()
        elif not aktif:
            self.wake.durdur()
        self.log.bilgi(KAYNAK,
            f"Wake word modu: {'aktif' if aktif else 'pasif'}")

    # ── Güncelleme ───────────────────────────────────────────────────────────

    def guncelleme_kontrol(self, url: str) -> dict:
        return self.tor.guncelleme_kontrol(url)

    def guncelleme_uygula(self, url: str) -> bool:
        return self.tor.guncelleme_indir(url, self.proje_yolu)


def calistir():
    cekirdek = Cekirdek()
    try:
        cekirdek.baslat()
    except KeyboardInterrupt:
        print("\nZihin Köprüsü kapatıldı.")
        sys.exit(0)


if __name__ == "__main__":
    calistir()
