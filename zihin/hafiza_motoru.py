"""
Zihin Köprüsü v7.0 – Hafıza Motoru

Özellikler:
  1. Kısa süreli oturum hafızası
     - "Az önce ne dedim?" → son N konuşmayı hatırlar
     - Bağlam: isim, konu, tercih takibi
     - Oturum kapatınca temizlenir (opsiyonel kalıcı)

  2. Sesli Not Sistemi
     - "Not al: ..." → metni kaydeder
     - "Notlarımı göster" → listeler
     - "Şu notu sil" → siler
     - JSON olarak diske kaydedilir, aranabilir

  3. Öğrenme / Tercih Sistemi
     - Sık kullanılan komutları öne çıkarır
     - Kullanıcı tercihlerini öğrenir (favori arama motoru vb.)
     - Komut geçmişi + frekans analizi

"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from .logcu import Logcu

KAYNAK = "HAFIZA"
MAX_OTURUM = 50   # Oturumda saklanacak max konuşma


@dataclass
class Konusma:
    rol: str          # "kullanici" | "sistem"
    metin: str
    zaman: str = field(default_factory=lambda: datetime.now().isoformat())
    bilinc: str = ""


@dataclass
class SesliNot:
    id: str
    metin: str
    etiketler: list[str] = field(default_factory=list)
    zaman: str = field(default_factory=lambda: datetime.now().isoformat())
    onem: int = 1     # 1=normal, 2=önemli, 3=kritik

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SesliNot":
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


class HafizaMotoru:
    def __init__(self, logcu: Logcu, veri_dosyasi: str):
        self.log = logcu
        self.veri_dosyasi = veri_dosyasi

        # Oturum hafızası (RAM'de, kalıcı değil)
        self._oturum: list[Konusma] = []

        # Sesli notlar (diske kaydedilir)
        self.notlar: dict[str, SesliNot] = {}

        # Komut frekansları (öğrenme)
        self._frekans: dict[str, int] = {}

        # Bağlam takibi
        self._aktif_konu: str = ""
        self._bilinen_isimler: list[str] = []
        self._tercihler: dict[str, str] = {}

        self._yukle()

    # ── Disk ─────────────────────────────────────────────────────────────────

    def _yukle(self):
        if os.path.exists(self.veri_dosyasi):
            try:
                with open(self.veri_dosyasi, encoding="utf-8") as f:
                    veri = json.load(f)
                for nid, d in veri.get("notlar", {}).items():
                    self.notlar[nid] = SesliNot.from_dict(d)
                self._frekans   = veri.get("frekans", {})
                self._tercihler = veri.get("tercihler", {})
                self.log.bilgi(KAYNAK,
                    f"{len(self.notlar)} not, "
                    f"{len(self._frekans)} komut frekansı yüklendi.")
            except Exception as e:
                self.log.hata(KAYNAK, f"Yükleme hatası: {e}")

    def kaydet(self):
        dizin = os.path.dirname(self.veri_dosyasi)
        if dizin:
            os.makedirs(dizin, exist_ok=True)
        with open(self.veri_dosyasi, "w", encoding="utf-8") as f:
            json.dump({
                "notlar":    {nid: n.to_dict()
                              for nid, n in self.notlar.items()},
                "frekans":   self._frekans,
                "tercihler": self._tercihler,
            }, f, ensure_ascii=False, indent=2)

    # ── Oturum Hafızası ───────────────────────────────────────────────────────

    def konusma_ekle(self, rol: str, metin: str, bilinc: str = ""):
        """Konuşmayı oturum hafızasına ekle."""
        k = Konusma(rol=rol, metin=metin, bilinc=bilinc)
        self._oturum.append(k)
        if len(self._oturum) > MAX_OTURUM:
            self._oturum.pop(0)

        # Bağlam analizi
        self._baglam_guncelle(metin)

        # Komut frekansı güncelle
        if rol == "kullanici":
            self._frekans_guncelle(metin)

    def son_n_konusma(self, n: int = 5) -> list[Konusma]:
        """Son N konuşmayı döndür."""
        return self._oturum[-n:]

    def son_konusma_ozeti(self, n: int = 5) -> str:
        """Son N konuşmayı özet metin olarak döndür."""
        konusmalar = self.son_n_konusma(n)
        if not konusmalar:
            return "Henüz konuşma geçmişi yok."
        satirlar = []
        for k in konusmalar:
            rol_ad = "Sen" if k.rol == "kullanici" else (k.bilinc or "Sistem")
            satirlar.append(f"{rol_ad}: {k.metin[:80]}")
        return "\n".join(satirlar)

    def oturum_temizle(self):
        self._oturum.clear()
        self._aktif_konu = ""

    def hatirla_soru(self, metin: str) -> Optional[str]:
        """
        "Az önce ne dedim?", "ne konuşuyorduk?" gibi sorulara cevap ver.
        """
        ml = metin.lower()
        if any(k in ml for k in [
            "az önce", "ne dedim", "ne konuştuk",
            "son söylediğim", "hatırlıyor musun"
        ]):
            return self.son_konusma_ozeti(5)

        if any(k in ml for k in ["aktif konu", "ne hakkında", "konu ne"]):
            return (f"Son konumuz: {self._aktif_konu}"
                    if self._aktif_konu else "Belirli bir konu yok.")

        return None

    # ── Bağlam Takibi ─────────────────────────────────────────────────────────

    def _baglam_guncelle(self, metin: str):
        """Metinden konu ve isim çıkar."""
        # Basit konu tespiti
        konu_anahtar = {
            "hava": ["hava", "yağmur", "kar", "sıcaklık"],
            "müzik": ["müzik", "şarkı", "çal", "playlist"],
            "haber": ["haber", "gündem", "son dakika"],
            "sistem": ["cpu", "ram", "disk", "bellek"],
            "web": ["site", "internet", "browser", "aç"],
        }
        ml = metin.lower()
        for konu, kelimeler in konu_anahtar.items():
            if any(k in ml for k in kelimeler):
                self._aktif_konu = konu
                break

        # İsim tespiti (büyük harfle başlayan kelimeler)
        isimler = re.findall(r'\b[A-ZÇĞİÖŞÜ][a-zçğışöüa-z]+\b', metin)
        for isim in isimler:
            if isim not in self._bilinen_isimler:
                self._bilinen_isimler.append(isim)
                if len(self._bilinen_isimler) > 20:
                    self._bilinen_isimler.pop(0)

    def _frekans_guncelle(self, metin: str):
        """Komut frekansını artır."""
        # Temizle ve anahtar kelimeleri çıkar
        temiz = metin.lower().strip()[:50]
        self._frekans[temiz] = self._frekans.get(temiz, 0) + 1
        # Disk kaydını 10 komutta bir yap
        if sum(self._frekans.values()) % 10 == 0:
            self.kaydet()

    def en_sik_komutlar(self, n: int = 10) -> list[tuple[str, int]]:
        """En sık kullanılan N komutu döndür."""
        return sorted(self._frekans.items(),
                      key=lambda x: x[1], reverse=True)[:n]

    # ── Tercih Sistemi ────────────────────────────────────────────────────────

    def tercih_kaydet(self, anahtar: str, deger: str):
        self._tercihler[anahtar] = deger
        self.kaydet()

    def tercih_al(self, anahtar: str, varsayilan: str = "") -> str:
        return self._tercihler.get(anahtar, varsayilan)

    # ── Sesli Not Sistemi ─────────────────────────────────────────────────────

    def not_al(self, metin: str, etiketler: list[str] = None,
               onem: int = 1) -> SesliNot:
        """Yeni not kaydet."""
        import uuid
        nid = str(uuid.uuid4())[:8]
        not_ = SesliNot(
            id=nid,
            metin=metin,
            etiketler=etiketler or [],
            onem=onem,
        )
        self.notlar[nid] = not_
        self.kaydet()
        self.log.bilgi(KAYNAK, f"Not kaydedildi: {metin[:50]}")
        return not_

    def not_sil(self, nid: str) -> bool:
        if nid in self.notlar:
            del self.notlar[nid]
            self.kaydet()
            return True
        return False

    def not_ara(self, sorgu: str) -> list[SesliNot]:
        """Notlarda arama yap."""
        sorgu_l = sorgu.lower()
        return [
            n for n in self.notlar.values()
            if sorgu_l in n.metin.lower() or
               any(sorgu_l in e.lower() for e in n.etiketler)
        ]

    def not_listesi_metin(self) -> str:
        """Tüm notları okunabilir metin olarak döndür."""
        if not self.notlar:
            return "Hiç not yok."
        satirlar = []
        for n in sorted(self.notlar.values(),
                         key=lambda x: x.zaman, reverse=True):
            tarih = n.zaman[:10]
            onem = "⭐" * n.onem
            satirlar.append(f"{onem} [{tarih}] {n.metin}")
        return "\n".join(satirlar[:20])  # Son 20

    def sesli_komut_isle(self, metin: str) -> Optional[str]:
        """
        Sesli hafıza komutlarını işle.
        "Not al: ...", "Notlarımı göster", "Az önce ne dedim?" vb.
        """
        ml = metin.lower().strip()

        # Hafıza soruları
        hatirla = self.hatirla_soru(metin)
        if hatirla:
            return hatirla

        # Not al
        for tetik in ["not al:", "not al ", "kaydet:", "not: "]:
            if tetik in ml:
                icerik = metin[ml.index(tetik) + len(tetik):].strip()
                if icerik:
                    # Önem tespiti
                    onem = 1
                    if any(k in ml for k in ["önemli", "kritik", "acil"]):
                        onem = 3
                    elif "hatırla" in ml:
                        onem = 2
                    self.not_al(icerik, onem=onem)
                    return f"Not kaydedildi: {icerik[:50]}"

        # Notları göster
        if any(k in ml for k in [
            "notlarımı göster", "notlar", "kayıtlarım",
            "ne not aldım", "notlarımı oku"
        ]):
            return self.not_listesi_metin()

        # Not ara
        if "not ara" in ml or "notta ara" in ml:
            for tetik in ["not ara ", "notta ara "]:
                if tetik in ml:
                    sorgu = ml.split(tetik, 1)[1].strip()
                    bulunanlar = self.not_ara(sorgu)
                    if bulunanlar:
                        return "\n".join(
                            f"• {n.metin}" for n in bulunanlar[:5])
                    return f"'{sorgu}' için not bulunamadı."

        # En sık komutlar
        if any(k in ml for k in ["en çok ne dedim", "sık komutlarım"]):
            komutlar = self.en_sik_komutlar(5)
            if komutlar:
                return "En sık komutların:\n" + "\n".join(
                    f"  {i+1}. {k} ({s} kez)"
                    for i, (k, s) in enumerate(komutlar))

        return None
