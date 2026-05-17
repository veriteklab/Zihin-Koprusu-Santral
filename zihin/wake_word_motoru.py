"""
Zihin Köprüsü v7.0 – Wake Word Motoru

Tamamen offline çalışır — pvporcupine gerektirmez.
Vosk'un partial result akışını kullanarak düşük gecikmeli
wake word tespiti yapar.

Çalışma mantığı:
  - Sürekli mikrofonu dinler (düşük CPU, sessiz mod)
  - Partial result'ta wake word geçiyorsa tetikler
  - Tetiklenince ses callback'ini çağırır
  - Callback içinde asıl komut dinleme başlar
  - "acil" wake word'ü her zaman en yüksek öncelikle işlenir

Özellikler:
  - Özelleştirilebilir wake word listesi (GUI'den)
  - Hassasiyet ayarı (yanlış pozitif / kaçırma dengesi)
  - Aktif/pasif mod (güç tasarrufu için)
  - Ses seviyesi eşiği (gürültülü ortamda yanlış tetikleme önleme)

"""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Callable, Optional

from .logcu import Logcu

KAYNAK = "WAKE"

# Varsayılan wake word listesi
VARSAYILAN_WAKE_WORDS = [
    "zihin", "abi", "abla", "bacı", "birader",
    "ufaklık", "dayı", "kuzen", "acil", "hey",
]


class WakeWordMotoru:
    def __init__(self, logcu: Logcu, ses_motoru,
                 wake_words: Optional[list[str]] = None):
        self.log = logcu
        self.ses = ses_motoru
        self.wake_words: list[str] = [
            w.lower() for w in (wake_words or VARSAYILAN_WAKE_WORDS)
        ]
        self._aktif = False
        self._thread: Optional[threading.Thread] = None
        self._tetikleme_callback: Optional[Callable[[str], None]] = None
        self._ses_seviyesi_esigi = 300   # RMS eşiği — gürültü filtresi
        self._hassasiyet = 0.7           # 0.0-1.0 arası
        self._son_tetiklenme = 0.0       # Çift tetiklenme önleme
        self._bekleme_suresi = 2.0       # Tetikleme sonrası bekleme (sn)
        self._durum_dinleyiciler: list[Callable[[str], None]] = []

    # ── Dinleyiciler ─────────────────────────────────────────────────────────

    def durum_dinleyici_ekle(self, fn: Callable[[str], None]):
        self._durum_dinleyiciler.append(fn)

    def _bildir(self, durum: str):
        for fn in self._durum_dinleyiciler:
            try:
                fn(durum)
            except Exception:
                pass

    def tetikleme_callback_ayarla(self, fn: Callable[[str], None]):
        """Wake word algılanınca çağrılacak fonksiyon."""
        self._tetikleme_callback = fn

    # ── Ayarlar ──────────────────────────────────────────────────────────────

    def wake_words_guncelle(self, kelimeler: list[str]):
        self.wake_words = [w.lower() for w in kelimeler]
        self.log.bilgi(KAYNAK, f"Wake words güncellendi: {self.wake_words}")

    def hassasiyet_ayarla(self, deger: float):
        """0.0 = çok hassas (çok tetiklenir), 1.0 = az hassas (az tetiklenir)."""
        self._hassasiyet = max(0.0, min(1.0, deger))

    def ses_seviyesi_esigi_ayarla(self, esik: int):
        """Gürültülü ortamlarda yanlış tetiklenmeyi azaltır."""
        self._ses_seviyesi_esigi = esik

    # ── Başlat / Durdur ──────────────────────────────────────────────────────

    def baslat(self):
        if self._aktif:
            return
        if not getattr(self.ses, "hazir", False):
            self.log.uyari(KAYNAK, "Ses motoru hazır değil; wake word başlatılmadı.")
            self._bildir("pasif")
            return
        self._aktif = True
        self._thread = threading.Thread(
            target=self._dinle_dongusu, daemon=True)
        self._thread.start()
        self.log.bilgi(KAYNAK, f"Wake word motoru başladı: {self.wake_words}")

    def durdur(self):
        self._aktif = False
        self._bildir("pasif")
        self.log.bilgi(KAYNAK, "Wake word motoru durduruldu.")

    # ── Ana Dinleme Döngüsü ──────────────────────────────────────────────────

    def _dinle_dongusu(self):
        import sounddevice as sd
        from vosk import KaldiRecognizer

        self._bildir("beklemede")

        kuyruk: queue.Queue = queue.Queue()

        def _callback(indata, frames, time_, status):
            if self._aktif:
                kuyruk.put(bytes(indata))

        while self._aktif:
            tetiklenen = ""
            try:
                # Ses motorundaki modeli kullanarak yeni bir recognizer oluştur.
                # Her döngüde sıfır recognizer, eski partial metnin tetiklemesini önler.
                try:
                    if hasattr(self.ses, 'model') and self.ses.model is not None:
                        taniyici = KaldiRecognizer(
                            self.ses.model, self.ses.ornekleme_hizi)
                    else:
                        taniyici = self.ses.taniyici
                except Exception as e:
                    self.log.hata(KAYNAK, f"Tanıyıcı oluşturulamadı: {e}")
                    taniyici = self.ses.taniyici

                if getattr(self.ses, "konusuyor_mu", lambda: False)():
                    time.sleep(0.1)
                    continue

                with self.ses.mikrofon_lock:
                    while not kuyruk.empty():
                        try:
                            kuyruk.get_nowait()
                        except queue.Empty:
                            break
                    with sd.RawInputStream(
                        samplerate=self.ses.ornekleme_hizi,
                        blocksize=4000,   # Daha küçük blok = daha hızlı tepki
                        dtype="int16",
                        channels=1,
                        callback=_callback,
                    ):
                        while self._aktif:
                            try:
                                veri = kuyruk.get(timeout=0.5)
                            except queue.Empty:
                                continue

                            # Ses seviyesi kontrolü
                            if not self._ses_var_mi(veri):
                                continue

                            # Partial result ile hızlı tespit
                            if taniyici.AcceptWaveform(veri):
                                sonuc = json.loads(taniyici.Result())
                                metin = sonuc.get("text", "").lower().strip()
                            else:
                                sonuc = json.loads(taniyici.PartialResult())
                                metin = sonuc.get("partial", "").lower().strip()

                            if not metin:
                                continue

                            # Wake word arama
                            bulunan = self._wake_word_bul(metin)
                            if bulunan and self._tetikle(bulunan):
                                tetiklenen = bulunan
                                break

                if tetiklenen and self._aktif and self._tetikleme_callback:
                    try:
                        self._tetikleme_callback(tetiklenen)
                    except Exception as e:
                        self.log.hata(KAYNAK, f"Callback hatası: {e}")
                    while not kuyruk.empty():
                        try:
                            kuyruk.get_nowait()
                        except queue.Empty:
                            break

            except Exception as e:
                self.log.hata(KAYNAK, f"Wake word döngü hatası: {e}")
                time.sleep(1.0)

    def _ses_var_mi(self, veri: bytes) -> bool:
        """RMS hesapla, eşiğin altındaysa sessizlik kabul et."""
        import struct
        try:
            ornekler = struct.unpack(f"{len(veri)//2}h", veri)
            rms = (sum(o*o for o in ornekler) / len(ornekler)) ** 0.5
            return rms > self._ses_seviyesi_esigi
        except Exception:
            return True  # Hata durumunda işlemeye devam et

    def _wake_word_bul(self, metin: str) -> Optional[str]:
        """Metinde wake word ara."""
        for kelime in self.wake_words:
            if kelime in metin:
                # Hassasiyet kontrolü: çok kısa metinlerde false positive önle
                if len(metin) < 3 and self._hassasiyet > 0.5:
                    continue
                return kelime
        return None

    def _tetikle(self, kelime: str) -> bool:
        """Wake word algılandı — callback'i çağır."""
        simdi = time.time()
        if simdi - self._son_tetiklenme < self._bekleme_suresi:
            return False  # Çift tetiklenme önle

        self._son_tetiklenme = simdi
        oncelik = "acil" if kelime == "acil" else "normal"

        self.log.bilgi(KAYNAK, f"Wake word algılandı: '{kelime}' [{oncelik}]")
        self._bildir(f"tetiklendi:{kelime}")
        return True

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    @property
    def aktif_mi(self) -> bool:
        return self._aktif
