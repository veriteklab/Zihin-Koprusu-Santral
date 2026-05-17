"""
Zihin Köprüsü – Eklenti Yöneticisi
Slot klasörlerine atılan .py dosyalarını otomatik keşfeder ve çalıştırır.
Her slot bağımsız bir süreçtir; hata yayılmaz.
"""
import os
import subprocess
import sys
import threading
from typing import Callable

from .logcu import Logcu

KAYNAK = "EKLENTİ"


class EklentiYoneticisi:
    def __init__(self, beyin: dict, logcu: Logcu, proje_yolu: str):
        self.log = logcu
        self.proje_yolu = proje_yolu
        self.slotlar: dict[str, dict] = {}
        self._durum_dinleyiciler: list[Callable[[str, str], None]] = []

        for slot_id, ayar in beyin.get("eklentiler", {}).items():
            klasor = os.path.join(proje_yolu, ayar["klasor"])
            os.makedirs(klasor, exist_ok=True)
            self.slotlar[slot_id] = {
                "ad": ayar.get("ad", slot_id),
                "simge": ayar.get("simge", "⚙️"),
                "klasor": klasor,
                "durum": "bos",
                "pid": None,
            }

    def durum_dinleyici_ekle(self, fn: Callable[[str, str], None]):
        """GUI durum güncellemelerini dinleyebilir."""
        self._durum_dinleyiciler.append(fn)

    def _durum_bildir(self, slot_id: str, durum: str):
        self.slotlar[slot_id]["durum"] = durum
        for fn in self._durum_dinleyiciler:
            try:
                fn(slot_id, durum)
            except Exception:
                pass

    def eklenti_bul(self, slot_id: str) -> list[str]:
        """Slot klasöründeki tüm .py dosyalarını döndürür."""
        klasor = self.slotlar[slot_id]["klasor"]
        dosyalar = []
        if os.path.isdir(klasor):
            for f in sorted(os.listdir(klasor)):
                if f.endswith(".py") and not f.startswith("_"):
                    dosyalar.append(os.path.join(klasor, f))
        return dosyalar

    def slot_calistir(self, slot_id: str) -> bool:
        """Slot klasöründeki main.py veya ilk .py dosyasını çalıştırır."""
        if slot_id not in self.slotlar:
            self.log.hata(KAYNAK, f"Bilinmeyen slot: {slot_id}")
            return False

        klasor = self.slotlar[slot_id]["klasor"]
        # Önce main.py ara
        ana_dosya = os.path.join(klasor, "main.py")
        if not os.path.exists(ana_dosya):
            dosyalar = self.eklenti_bul(slot_id)
            if not dosyalar:
                self.log.uyari(KAYNAK, f"[{slot_id}] Klasörde .py dosyası yok.")
                return False
            ana_dosya = dosyalar[0]

        self.log.bilgi(KAYNAK, f"[{slot_id}] Çalıştırılıyor: {ana_dosya}")
        self._durum_bildir(slot_id, "calisiyor")

        def _calistir():
            try:
                proc = subprocess.Popen(
                    [sys.executable, ana_dosya],
                    cwd=klasor,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.slotlar[slot_id]["pid"] = proc.pid
                stdout, stderr = proc.communicate()
                if stdout:
                    self.log.bilgi(KAYNAK, f"[{slot_id}] Çıktı: {stdout.decode('utf-8', errors='replace').strip()}")
                if stderr:
                    self.log.uyari(KAYNAK, f"[{slot_id}] Hata çıktısı: {stderr.decode('utf-8', errors='replace').strip()}")
                self._durum_bildir(slot_id, "tamamlandi")
            except Exception as e:
                self.log.hata(KAYNAK, f"[{slot_id}] Çalıştırma hatası: {e}")
                self._durum_bildir(slot_id, "hata")

        t = threading.Thread(target=_calistir, daemon=True)
        t.start()
        return True

    def slot_durdur(self, slot_id: str):
        """Çalışan slot işlemini durdurur."""
        pid = self.slotlar.get(slot_id, {}).get("pid")
        if pid:
            try:
                subprocess.run(["kill", str(pid)], check=False)
                self.log.bilgi(KAYNAK, f"[{slot_id}] Durduruldu (PID: {pid})")
            except Exception as e:
                self.log.hata(KAYNAK, f"[{slot_id}] Durdurulamadı: {e}")
            self._durum_bildir(slot_id, "durduruldu")

    def klasor_ac(self, slot_id: str):
        """Slot klasörünü dosya yöneticisinde açar."""
        klasor = self.slotlar[slot_id]["klasor"]
        subprocess.Popen(["xdg-open", klasor])

    def durum_al(self, slot_id: str) -> str:
        return self.slotlar.get(slot_id, {}).get("durum", "bos")
