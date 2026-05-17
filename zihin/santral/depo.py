from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_simdi() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CagriKaydi:
    call_id: str
    device_id: str
    phone_number: str = ""
    state: str = "new"
    created_at: str = field(default_factory=utc_simdi)
    updated_at: str = field(default_factory=utc_simdi)
    recording_path: str = ""
    transcript: str = ""
    notes: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


class SantralDepo:
    def __init__(self, kok_dizin: str, cagri_dizin: str):
        self.kok = Path(kok_dizin)
        self.cagri_kok = self.kok / cagri_dizin
        self.cagri_kok.mkdir(parents=True, exist_ok=True)

    def cagri_dizini(self, call_id: str) -> Path:
        yol = self.cagri_kok / call_id
        yol.mkdir(parents=True, exist_ok=True)
        return yol

    def meta_yolu(self, call_id: str) -> Path:
        return self.cagri_dizini(call_id) / "kayit.json"

    def yukle(self, call_id: str) -> CagriKaydi | None:
        yol = self.meta_yolu(call_id)
        if not yol.exists():
            return None
        veri = json.loads(yol.read_text(encoding="utf-8"))
        return CagriKaydi(**veri)

    def tum_cagrilar(self) -> list[CagriKaydi]:
        sonuc: list[CagriKaydi] = []
        if not self.cagri_kok.exists():
            return sonuc
        for klasor in sorted(self.cagri_kok.iterdir()):
            if not klasor.is_dir():
                continue
            yol = klasor / "kayit.json"
            if not yol.exists():
                continue
            try:
                veri = json.loads(yol.read_text(encoding="utf-8"))
                sonuc.append(CagriKaydi(**veri))
            except Exception:
                continue
        return sonuc

    def son_cagri(self, device_id: str = "", state: str = "") -> CagriKaydi | None:
        adaylar = self.tum_cagrilar()
        if device_id:
            adaylar = [x for x in adaylar if x.device_id == device_id]
        if state:
            adaylar = [x for x in adaylar if x.state == state]
        if not adaylar:
            return None
        adaylar.sort(key=lambda x: x.updated_at, reverse=True)
        return adaylar[0]

    def kaydet(self, kayit: CagriKaydi) -> None:
        kayit.updated_at = utc_simdi()
        self.meta_yolu(kayit.call_id).write_text(
            json.dumps(asdict(kayit), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def getir_veya_olustur(self, call_id: str, device_id: str, phone_number: str = "") -> CagriKaydi:
        kayit = self.yukle(call_id)
        if kayit is None:
            kayit = CagriKaydi(call_id=call_id, device_id=device_id, phone_number=phone_number)
        elif phone_number and not kayit.phone_number:
            kayit.phone_number = phone_number
        return kayit

    def olay_ekle(
        self,
        call_id: str,
        device_id: str,
        event_type: str,
        phone_number: str = "",
        state: str = "",
        extra: dict[str, Any] | None = None,
    ) -> CagriKaydi:
        kayit = self.getir_veya_olustur(call_id, device_id, phone_number)
        kayit.state = state or event_type
        kayit.events.append({
            "event_type": event_type,
            "state": state or event_type,
            "phone_number": phone_number or kayit.phone_number,
            "timestamp": utc_simdi(),
            "extra": extra or {},
        })
        if extra:
            kayit.meta.update(extra)
        self.kaydet(kayit)
        return kayit

    def recording_kaydet(self, call_id: str, filename: str, ham_veri: bytes) -> Path:
        hedef = self.cagri_dizini(call_id) / filename
        hedef.write_bytes(ham_veri)
        return hedef

    def transcript_guncelle(self, call_id: str, transcript: str) -> CagriKaydi:
        kayit = self.yukle(call_id)
        if kayit is None:
            raise FileNotFoundError(call_id)
        kayit.transcript = transcript
        self.kaydet(kayit)
        return kayit

    def recording_guncelle(self, call_id: str, recording_path: str) -> CagriKaydi:
        kayit = self.yukle(call_id)
        if kayit is None:
            raise FileNotFoundError(call_id)
        kayit.recording_path = recording_path
        self.kaydet(kayit)
        return kayit
