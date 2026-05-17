"""
Zihin Köprüsü v6.0 – Ses Motoru
STT (Vosk) + TTS (gTTS / Edge-TTS / Piper) tek modülde.
Gürültü filtreleme, hız ayarı, fallback sistemi dahil.
Ses efektleri: pitch/tempo değişimi (sincap, derin, hızlı vb.)

"""
import asyncio
import json
import os
import queue
import re
import subprocess
import threading
import time
from typing import Callable

_sd_import_hatasi = None
try:
    import sounddevice as sd
except Exception as e:
    _sd_import_hatasi = e
    sd = None

_vosk_import_hatasi = None
try:
    from vosk import KaldiRecognizer, Model
except Exception as e:
    _vosk_import_hatasi = e
    KaldiRecognizer = None
    Model = None

from .logcu import Logcu

KAYNAK = "SES"
GECİCİ_SES   = "/tmp/zk_ses.mp3"
GECİCİ_SES2  = "/tmp/zk_ses_efekt.wav"
GECİCİ_PIPER = "/tmp/zk_piper.wav"
WAKE_KELIMELER = ["abi", "abla", "bacı", "birader", "ufaklık", "dayı", "kuzen", "acil"]

# Ses efekt ön ayarları (ffmpeg atempo/asetrate parametreleri)
SES_EFEKTLERI = {
    "normal":   {"pitch": 1.0,  "tempo": 1.0,  "label": "Normal"},
    "sincap":   {"pitch": 1.8,  "tempo": 1.3,  "label": "Sincap"},
    "derin":    {"pitch": 0.6,  "tempo": 0.85, "label": "Derin/Dayı"},
    "genc":     {"pitch": 1.15, "tempo": 1.1,  "label": "Genç"},
    "kadin":    {"pitch": 1.35, "tempo": 1.0,  "label": "Kadın"},
    "bebek":    {"pitch": 2.0,  "tempo": 0.85, "label": "Bebek"},
    "robot":    {"pitch": 0.9,  "tempo": 0.95, "label": "Robot"},
    "yasli":    {"pitch": 0.8,  "tempo": 0.8,  "label": "Yaşlı"},
    "hizli":    {"pitch": 1.0,  "tempo": 1.5,  "label": "Hızlı"},
    "yavas":    {"pitch": 1.0,  "tempo": 0.65, "label": "Yavaş"},
}

TTS_KES_KELIMELERI = {
    "ses kes", "sesi kes", "sus", "sus artık", "sus artik", "yeter",
    "yeterli", "tamam yeter", "uzatma", "kısa kes", "kisa kes",
    "kapat sesini", "konuşmayı kes", "konusmayi kes", "dur",
}

TERIM_CEVIRILERI = {
    "timeout": "zaman aşımı",
    "error": "hata",
    "warning": "uyarı",
    "failed": "başarısız",
    "success": "başarılı",
    "ok": "tamam",
    "done": "tamamlandı",
    "loading": "yükleniyor",
    "because": "çünkü",
    "please": "lütfen",
    "retry": "tekrar dene",
    "try again": "tekrar dene",
    "and": "ve",
    "download": "indir",
    "upload": "yükle",
    "submit": "gönder",
    "send": "gönder",
    "cancel": "iptal",
    "save": "kaydet",
    "delete": "sil",
    "close": "kapat",
    "open": "aç",
    "settings": "ayarlar",
    "login": "giriş",
    "logout": "çıkış",
    "username": "kullanıcı adı",
    "password": "şifre",
    "search": "ara",
    "next": "sonraki",
    "previous": "önceki",
    "play": "oynat",
    "pause": "duraklat",
    "stop": "durdur",
    "volume": "ses",
    "browser": "tarayıcı",
    "window": "pencere",
    "file": "dosya",
    "folder": "klasör",
    "permission denied": "izin reddedildi",
    "not found": "bulunamadı",
    "connection refused": "bağlantı reddedildi",
    "network unreachable": "ağa ulaşılamıyor",
}


class SesMotoru:
    def __init__(self, beyin: dict, logcu: Logcu, proje_yolu: str = ""):
        self.log = logcu
        self._proje_yolu = proje_yolu
        self._durum_dinleyiciler: list[Callable[[str], None]] = []
        stt_ayar = beyin["ses"]["stt"]
        self.ornekleme_hizi = stt_ayar["ornekleme_hizi"]
        self.bilincler = beyin["bilincler"]
        self.konusma_hizi = beyin["ses"].get("konusma_hizi", 1.0)
        self._aktif = True
        self._ses_kes_flag = False
        self._konusuyor   = False          # eş zamanlı ses önleme kilidi
        self._konusma_lock = threading.Lock()
        self._mikrofon_lock = threading.RLock()
        self._konusma_thread: threading.Thread | None = None
        self._konusma_id = 0
        self._ffplay_proc: subprocess.Popen | None = None
        self._tts_proc: subprocess.Popen | None = None
        self._son_kesme_zamani = 0.0
        ses_ayar = beyin.get("ses", {})
        self.kisa_yanit_aktif = bool(ses_ayar.get("kisa_yanit_aktif", True))
        self.turkcelestirme_aktif = bool(ses_ayar.get("turkcelestirme_aktif", True))
        self.tts_max_karakter = int(ses_ayar.get("tts_max_karakter", 420))
        self.tts_max_cumle = int(ses_ayar.get("tts_max_cumle", 3))
        self.hazir = False
        self.model = None
        self.taniyici = None

        # Model yolunu mutlak yap
        model_yolu = stt_ayar["model_yolu"]
        if proje_yolu and not os.path.isabs(model_yolu):
            model_yolu = os.path.join(proje_yolu, model_yolu)

        if sd is None:
            self.log.kritik(KAYNAK, f"sounddevice yüklenemedi: {_sd_import_hatasi}. STT pasif.")
        elif Model is None or KaldiRecognizer is None:
            self.log.kritik(KAYNAK, f"vosk yüklenemedi: {_vosk_import_hatasi}. STT pasif.")
        elif not os.path.isdir(model_yolu):
            self.log.kritik(KAYNAK, f"Vosk modeli bulunamadı: {model_yolu}. STT pasif.")
        else:
            try:
                self.model    = Model(model_yolu)
                self.taniyici = KaldiRecognizer(self.model, self.ornekleme_hizi)
                self.hazir = True
            except Exception as e:
                self.log.kritik(KAYNAK, f"Vosk modeli yüklenemedi: {e}. STT pasif.")

        self.kuyruk: queue.Queue = queue.Queue()
        # Ses dalgası animasyonu için amplitüd dinleyiciler
        self._amplitud_dinleyiciler: list = []

        # Bilinç bazlı ses efekti ayarı: {bilinc_adi: efekt_adi}
        self.bilinc_efekt: dict[str, str] = {}
        # Bilinç bazlı özel pitch/tempo: {bilinc_adi: {"pitch":..., "tempo":...}}
        self.bilinc_efekt_ozel: dict[str, dict] = {}
        for bilinc, ayar in self.bilincler.items():
            if not isinstance(ayar, dict):
                continue
            efekt = ayar.get("ses_efekti", "normal")
            self.bilinc_efekt[bilinc] = efekt if efekt in SES_EFEKTLERI else "normal"
            self.bilinc_efekt_ozel[bilinc] = {
                "pitch": float(ayar.get("pitch", SES_EFEKTLERI[self.bilinc_efekt[bilinc]]["pitch"])),
                "tempo": float(ayar.get("tempo", SES_EFEKTLERI[self.bilinc_efekt[bilinc]]["tempo"])),
            }

    def durum_dinleyici_ekle(self, fn: Callable[[str], None]):
        self._durum_dinleyiciler.append(fn)

    def amplitud_dinleyici_ekle(self, fn):
        """Ses dalgası animasyonu için 0.0-1.0 arası amplitüd değeri alır."""
        self._amplitud_dinleyiciler.append(fn)

    def _durum_bildir(self, durum: str):
        for fn in self._durum_dinleyiciler:
            try:
                fn(durum)
            except Exception:
                pass

    # ── STT ────────────────────────────────────────────────────────────────

    @property
    def mikrofon_lock(self):
        return self._mikrofon_lock

    def konusuyor_mu(self) -> bool:
        return bool(self._konusuyor)

    def konusma_bitisini_bekle(self, zaman_asimi: float = 8.0):
        basla = time.monotonic()
        while self._konusuyor and time.monotonic() - basla < zaman_asimi:
            time.sleep(0.05)

    def _kuyruk_temizle(self):
        try:
            while True:
                self.kuyruk.get_nowait()
        except queue.Empty:
            pass

    def _taniyici_sifirla(self):
        try:
            if self.taniyici is not None and hasattr(self.taniyici, "Reset"):
                self.taniyici.Reset()
        except Exception:
            pass

    def _ses_callback(self, indata, frames, time_, status):
        if status:
            self.log.uyari(KAYNAK, str(status))
        self.kuyruk.put(bytes(indata))
        # Ses dalgası animasyonu için amplitüd hesapla ve yayınla
        try:
            import struct
            ornekler = struct.unpack(f"{len(indata)//2}h", bytes(indata))
            if ornekler:
                rms = (sum(o*o for o in ornekler) / len(ornekler)) ** 0.5
                normalize = min(1.0, rms / 8000.0)
                for fn in self._amplitud_dinleyiciler:
                    try:
                        fn(normalize)
                    except Exception:
                        pass
        except Exception:
            pass

    def dinle(self, zaman_asimi: float | None = None, sessizlik_suresi: float = 1.1) -> str:
        """Mikrofonu dinler, anlamlı bir cümle gelince döndürür.
        Wake word modu aktifse cümle wake word ile başlamış demektir."""
        if not self.hazir or sd is None or self.taniyici is None:
            import time
            self._durum_bildir("hata")
            time.sleep(1)
            return ""

        self.konusma_bitisini_bekle()
        with self._mikrofon_lock:
            self._kuyruk_temizle()
            self._taniyici_sifirla()
            self._durum_bildir("dinleniyor")
            basla = time.monotonic()
            son_ses = basla
            son_partial = ""
            with sd.RawInputStream(
                samplerate=self.ornekleme_hizi,
                blocksize=4000,
                dtype="int16",
                channels=1,
                callback=self._ses_callback,
            ):
                while True:
                    simdi = time.monotonic()
                    if zaman_asimi is not None and simdi - basla > zaman_asimi:
                        self._durum_bildir("bosta")
                        return ""
                    if self._ses_kes_flag:
                        self._ses_kes_flag = False
                        self._durum_bildir("bosta")
                        return ""
                    try:
                        veri = self.kuyruk.get(timeout=0.1)
                    except queue.Empty:
                        if son_partial and simdi - son_ses >= sessizlik_suresi:
                            self._durum_bildir("bosta")
                            return son_partial
                        continue
                    if self.taniyici.AcceptWaveform(veri):
                        sonuc = json.loads(self.taniyici.Result())
                        metin = sonuc.get("text", "").strip()
                        if len(metin) >= 2:
                            if "acil" in metin.lower():
                                self.log.kritik(KAYNAK, f"ACİL KOMUT: {metin}")
                            self._durum_bildir("bosta")
                            return metin
                    else:
                        sonuc = json.loads(self.taniyici.PartialResult())
                        partial = sonuc.get("partial", "").strip()
                        if partial:
                            son_partial = partial
                            son_ses = time.monotonic()

    def ses_kes(self):
        """Çalan sesi anında durdur ve bayrağı kaldır."""
        self._ses_kes_flag = True
        self._son_kesme_zamani = time.monotonic()
        self._tts_durdur()
        self._ffplay_durdur()
        self._durum_bildir("bosta")

    def _ffplay_durdur(self):
        """Çalan ffplay işlemini öldür."""
        try:
            if self._ffplay_proc and self._ffplay_proc.poll() is None:
                self._ffplay_proc.terminate()
                self._ffplay_proc.wait(timeout=1)
        except Exception:
            pass
        self._ffplay_proc = None
        self._konusuyor = False

    def _tts_durdur(self):
        try:
            if self._tts_proc and self._tts_proc.poll() is None:
                self._tts_proc.terminate()
                self._tts_proc.wait(timeout=1)
        except Exception:
            try:
                if self._tts_proc:
                    self._tts_proc.kill()
            except Exception:
                pass
        self._tts_proc = None

    # ── TTS ────────────────────────────────────────────────────────────────

    def konus(self, bilinc: str, metin: str):
        """Konuşmayı arka planda başlatır; ana STT döngüsünü kilitlemez."""
        if not metin or not metin.strip():
            return
        temiz = self._tts_metni_hazirla(metin)
        if not temiz:
            return
        if self._ses_kes_flag:
            if time.monotonic() - self._son_kesme_zamani < 0.7:
                return
            self._ses_kes_flag = False

        with self._konusma_lock:
            if self._konusuyor:
                self._tts_durdur()
                self._ffplay_durdur()
            self._konusuyor = True
            self._ses_kes_flag = False
            self._konusma_id += 1
            konusma_id = self._konusma_id
            t = threading.Thread(
                target=self._konus_sync,
                args=(bilinc, temiz, konusma_id),
                daemon=True,
            )
            self._konusma_thread = t
            t.start()

    def konus_bloklu(self, bilinc: str, metin: str):
        """Test/makro gibi yerlerde gerekirse bloklu konuşma."""
        temiz = self._tts_metni_hazirla(metin)
        if temiz:
            with self._konusma_lock:
                self._konusma_id += 1
                konusma_id = self._konusma_id
                self._konusuyor = True
                self._ses_kes_flag = False
            self._konus_sync(bilinc, temiz, konusma_id)

    def _konus_sync(self, bilinc: str, metin: str, konusma_id: int):
        """Bilinç ayarına göre uygun TTS motoruyla seslendirme yapar.
        Eş zamanlı ikinci konuşma girişimini engeller."""
        if not metin.strip():
            return
        if self._ses_kes_flag:
            return
        if not self._konusma_guncel_mi(konusma_id):
            return

        self._durum_bildir("konusuyor")
        ayar = self.bilincler.get(bilinc, {})
        motor = ayar.get("tts_motor", "gtts") if isinstance(ayar, dict) else "gtts"

        try:
            if motor == "gtts":
                self._gtts_konus(bilinc, metin, konusma_id)
            elif motor == "edge-tts":
                ses = ayar.get("ses", "tr-TR-AhmetNeural")
                # asyncio.run() mevcut event loop varsa çöker — yeni loop aç
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self._edge_konus(bilinc, ses, metin, konusma_id))
                finally:
                    loop.close()
            elif motor == "piper":
                self._piper_konus(bilinc, metin, konusma_id)
            else:
                self.log.hata(KAYNAK, f"Bilinmeyen motor: {motor}, gTTS'e geçiliyor.")
                self._gtts_konus(bilinc, metin, konusma_id)

            if self._konusma_guncel_mi(konusma_id):
                self.log.bilgi(KAYNAK, f"[{bilinc}] {metin}")
        except Exception as e:
            if not self._konusma_guncel_mi(konusma_id):
                return
            self.log.hata(KAYNAK, f"{bilinc} konuşamadı: {e}")
            self._tts_fallback(bilinc, metin, motor, konusma_id)
        finally:
            self._konusuyor = False
            if self._konusma_guncel_mi(konusma_id):
                self._durum_bildir("bosta")

    def _konusma_guncel_mi(self, konusma_id: int) -> bool:
        return (not self._ses_kes_flag) and konusma_id == self._konusma_id

    def komut_ses_kes_mi(self, metin: str) -> bool:
        norm = self._norm(metin)
        return any(self._norm(k) in norm for k in TTS_KES_KELIMELERI)

    def _tts_metni_hazirla(self, metin: str) -> str:
        metin = str(metin or "").strip()
        if not metin:
            return ""
        if self.turkcelestirme_aktif:
            metin = self.turkce_metne_cevir(metin)
        if self.kisa_yanit_aktif:
            metin = self._kisalt(metin)
        return metin.strip()

    def turkce_metne_cevir(self, metin: str) -> str:
        """Sistem/web çıktılarındaki yaygın İngilizce terimleri Türkçeleştirir."""
        return self._turkcelestir(metin)

    def _kisalt(self, metin: str) -> str:
        metin = re.sub(r"\s+", " ", metin).strip()
        metin = re.sub(r"\b(?:http|https)://\S+", "bağlantı", metin)
        metin = re.sub(r"/[A-Za-z0-9_./-]{18,}", "dosya yolu", metin)
        cumleler = re.split(r"(?<=[.!?])\s+", metin)
        secilen = " ".join(cumleler[:max(1, self.tts_max_cumle)]).strip()
        if len(secilen) > self.tts_max_karakter:
            secilen = secilen[:self.tts_max_karakter].rsplit(" ", 1)[0].strip()
            secilen += ". Devamını ekrandan okuyabilirsiniz."
        return secilen

    def _turkcelestir(self, metin: str) -> str:
        sonuc = metin
        for kaynak, hedef in TERIM_CEVIRILERI.items():
            sonuc = re.sub(rf"(?<!\w){re.escape(kaynak)}(?!\w)", hedef, sonuc, flags=re.I)
        return sonuc

    @staticmethod
    def _norm(metin: str) -> str:
        ceviri = str.maketrans({
            "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g",
            "ı": "i", "I": "i", "İ": "i", "ö": "o",
            "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
        })
        temiz = metin.translate(ceviri).lower()
        temiz = re.sub(r"[^a-z0-9]+", " ", temiz)
        return " ".join(temiz.split())

    def _tts_fallback(self, bilinc: str, metin: str, onceki_motor: str, konusma_id: int):
        """İnternetli TTS bozulursa offline Piper, o da olmazsa gTTS dene."""
        siralama = []
        if onceki_motor != "piper":
            siralama.append("piper")
        if onceki_motor != "gtts":
            siralama.append("gtts")

        for motor in siralama:
            if not self._konusma_guncel_mi(konusma_id):
                return
            try:
                if motor == "piper":
                    self._piper_konus(bilinc, metin, konusma_id)
                elif motor == "gtts":
                    self._gtts_konus(bilinc, metin, konusma_id)
                self.log.uyari(KAYNAK, f"TTS fallback kullanıldı: {motor}")
                return
            except Exception as e:
                self.log.uyari(KAYNAK, f"TTS fallback başarısız ({motor}): {e}")

    def _efekt_args(self, bilinc: str) -> list[str] | None:
        """
        Bilinç için ffmpeg ses efekti argümanları üret.
        None döner → efekt yok, direkt oynat.
        """
        # Özel ayar öncelikli
        ozel = self.bilinc_efekt_ozel.get(bilinc)
        if not ozel:
            efekt_adi = self.bilinc_efekt.get(bilinc, "normal")
            efekt = SES_EFEKTLERI.get(efekt_adi, SES_EFEKTLERI["normal"])
        else:
            efekt = ozel

        pitch = efekt.get("pitch", 1.0)
        tempo = efekt.get("tempo", 1.0)

        if abs(pitch - 1.0) < 0.01 and abs(tempo - 1.0) < 0.01:
            return None  # efekt yok

        # asetrate ile pitch, atempo ile tempo
        ornekleme = 44100
        yeni_rate = int(ornekleme * pitch)
        # atempo 0.5–2.0 aralığında olmalı, zincirle
        tempo_args = _tempo_zincir(tempo)

        filtre = f"asetrate={yeni_rate},aresample={ornekleme},{tempo_args}"
        return ["-af", filtre]

    def _gtts_konus(self, bilinc: str, metin: str, konusma_id: int):
        from gtts import gTTS
        tts = gTTS(text=metin, lang="tr", slow=(self.konusma_hizi < 0.8))
        tts.save(GECİCİ_SES)
        if self._konusma_guncel_mi(konusma_id):
            self._oynat_efektli(bilinc, GECİCİ_SES, konusma_id)

    async def _edge_konus(self, bilinc: str, ses: str, metin: str, konusma_id: int):
        import edge_tts
        iletisim = edge_tts.Communicate(text=metin, voice=ses)
        await iletisim.save(GECİCİ_SES)
        if self._konusma_guncel_mi(konusma_id):
            self._oynat_efektli(bilinc, GECİCİ_SES, konusma_id)

    def _piper_konus(self, bilinc: str, metin: str, konusma_id: int):
        try:
            import shutil as _sh
            import sys as _sys
            piper_komut = _sh.which("piper")
            if not piper_komut:
                aday = os.path.join(os.path.dirname(_sys.executable), "piper")
                if os.path.exists(aday):
                    piper_komut = aday
            if not piper_komut:
                raise RuntimeError("Piper kurulu değil.")
            model_yolu = "modeller/piper-tr/tr_TR-dfki-medium.onnx"
            if self._proje_yolu:
                model_yolu = os.path.join(self._proje_yolu, model_yolu)
            if not os.path.exists(model_yolu):
                raise RuntimeError(f"Piper modeli bulunamadı: {model_yolu}")
            proc = subprocess.Popen(
                [piper_komut, "--model", model_yolu,
                 "--output_file", GECİCİ_PIPER],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._tts_proc = proc
            proc.communicate(input=metin.encode("utf-8"))
            self._tts_proc = None
            if proc.returncode not in (0, None):
                raise RuntimeError(f"Piper hata kodu: {proc.returncode}")
            if not self._konusma_guncel_mi(konusma_id):
                return
            self._oynat_efektli(bilinc, GECİCİ_PIPER, konusma_id)
        except FileNotFoundError:
            raise RuntimeError("Piper kurulu değil.")

    def _oynat_efektli(self, bilinc: str, dosya: str, konusma_id: int):
        """Her zaman ffmpeg üzerinden WAV'a dönüştürür.
        gTTS'in MP3 chunk birleştirme noktalarındaki kekemeleri giderir."""
        if not self._konusma_guncel_mi(konusma_id):
            return
        efekt_args = self._efekt_args(bilinc)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", dosya] + (efekt_args or []) + [GECİCİ_SES2],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
            if not self._konusma_guncel_mi(konusma_id):
                return
            self._oynat(GECİCİ_SES2, konusma_id)
            return
        except Exception as e:
            self.log.uyari(KAYNAK, f"Dönüştürme başarısız: {e}, direkt oynatılıyor.")
        self._oynat(dosya, konusma_id)

    def _oynat(self, dosya: str, konusma_id: int):
        if not self._konusma_guncel_mi(konusma_id):
            return
        import shutil as _sh
        # Oynatıcı tercih sırası
        for oynatici in (["ffplay", "-nodisp", "-autoexit", dosya],
                         ["aplay", dosya],
                         ["paplay", dosya]):
            if _sh.which(oynatici[0]):
                if not self._konusma_guncel_mi(konusma_id):
                    return
                self._ffplay_proc = subprocess.Popen(
                    oynatici,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._ffplay_proc.wait()
                if self._konusma_guncel_mi(konusma_id):
                    self._ffplay_proc = None
                return
        self.log.hata(KAYNAK, "Ses oynatıcı bulunamadı (ffplay/aplay/paplay).")


def _tempo_zincir(tempo: float) -> str:
    """
    atempo filtresi 0.5–2.0 aralığını aşarsa zincir oluşturur.
    """
    parts = []
    remaining = tempo
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)
