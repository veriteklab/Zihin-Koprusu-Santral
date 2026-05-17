"""
Zihin Köprüsü – Loglama Modülü
Tek yerden loglama. Hem dosyaya hem terminale yazar.
Sinyal sistemi ile GUI'ye canlı log iletimi desteklenir.
"""
import os
import re
from datetime import datetime
from typing import Callable


class Logcu:
    def __init__(self, dosya_yolu: str):
        self.dosya_yolu = dosya_yolu
        self._dinleyiciler: list[Callable[[str, str, str], None]] = []
        dizin = os.path.dirname(dosya_yolu)
        if dizin:
            os.makedirs(dizin, exist_ok=True)

    def dinleyici_ekle(self, fn: Callable[[str, str, str], None]):
        """GUI veya başka modüller log olaylarını dinleyebilir."""
        if fn not in self._dinleyiciler:
            self._dinleyiciler.append(fn)

    def dinleyici_sil(self, fn: Callable[[str, str, str], None]):
        """Kapanan modüllerin log dinleyicisini kaldırır."""
        try:
            self._dinleyiciler.remove(fn)
        except ValueError:
            pass

    def yaz(self, seviye: str, kaynak: str, mesaj: str):
        zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mesaj = self._maskele(str(mesaj))
        satir = f"[{zaman}] [{seviye}] [{kaynak}] {mesaj}"
        print(satir)
        try:
            with open(self.dosya_yolu, "a", encoding="utf-8") as f:
                f.write(satir + "\n")
        except OSError as e:
            print(f"[GÜNLÜK HATASI] {e}")
        for fn in self._dinleyiciler:
            try:
                fn(seviye, kaynak, mesaj)
            except Exception:
                pass

    def bilgi(self, kaynak: str, mesaj: str):
        self.yaz("BİLGİ", kaynak, mesaj)

    def hata(self, kaynak: str, mesaj: str):
        self.yaz("HATA", kaynak, mesaj)

    def kritik(self, kaynak: str, mesaj: str):
        self.yaz("KRİTİK", kaynak, mesaj)

    def uyari(self, kaynak: str, mesaj: str):
        self.yaz("UYARI", kaynak, mesaj)

    @staticmethod
    def _maskele(metin: str) -> str:
        kaliplar = [
            r"(api[_-]?key['\"\s:=]+)([A-Za-z0-9_\-\.]{12,})",
            r"(api[_-]?anahtari['\"\s:=]+)([A-Za-z0-9_\-\.]{12,})",
            r"(token['\"\s:=]+)([A-Za-z0-9:_\-\.]{12,})",
            r"(Authorization:\s*Bearer\s+)([A-Za-z0-9_\-\.]{12,})",
        ]
        sonuc = metin
        for kalip in kaliplar:
            sonuc = re.sub(kalip, lambda m: m.group(1) + "***", sonuc, flags=re.IGNORECASE)
        return sonuc
