from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AkisSecenek:
    tus: str
    etiket: str
    eylem: str
    hedef: str = ""
    bildirim: str = ""


@dataclass
class CagriAkisi:
    akis_id: str
    ad: str
    karsilama: str
    secenekler: list[AkisSecenek] = field(default_factory=list)
    zaman_asimi_saniye: int = 8
    varsayilan_eylem: str = "voice_note"

    def anons_metni(self) -> str:
        satirlar = [self.karsilama.strip()]
        for sec in self.secenekler:
            satirlar.append(f"{sec.etiket} icin {sec.tus} tuslayin.")
        return " ".join([s for s in satirlar if s]).strip()


class AkisYonetici:
    def __init__(self, dosya: str):
        self.dosya = Path(dosya)
        self.akislar = self._yukle()

    def _yukle(self) -> dict[str, CagriAkisi]:
        veri = json.loads(self.dosya.read_text(encoding="utf-8"))
        akislar: dict[str, CagriAkisi] = {}
        for akis_id, icerik in veri.get("akislar", {}).items():
            akislar[akis_id] = CagriAkisi(
                akis_id=akis_id,
                ad=icerik["ad"],
                karsilama=icerik["karsilama"],
                secenekler=[AkisSecenek(**sec) for sec in icerik.get("secenekler", [])],
                zaman_asimi_saniye=int(icerik.get("zaman_asimi_saniye", 8)),
                varsayilan_eylem=icerik.get("varsayilan_eylem", "voice_note"),
            )
        return akislar

    def varsayilan(self) -> CagriAkisi:
        if "varsayilan" in self.akislar:
            return self.akislar["varsayilan"]
        return next(iter(self.akislar.values()))

    def getir(self, akis_id: str | None) -> CagriAkisi:
        if akis_id and akis_id in self.akislar:
            return self.akislar[akis_id]
        return self.varsayilan()

    def secim_isle(self, akis_id: str | None, tus: str) -> dict[str, str]:
        akis = self.getir(akis_id)
        for sec in akis.secenekler:
            if sec.tus == tus:
                return {
                    "ok": "true",
                    "tus": tus,
                    "etiket": sec.etiket,
                    "eylem": sec.eylem,
                    "hedef": sec.hedef,
                    "bildirim": sec.bildirim,
                }
        return {
            "ok": "false",
            "tus": tus,
            "eylem": akis.varsayilan_eylem,
            "bildirim": "Gecersiz veya tanimsiz secim.",
        }
