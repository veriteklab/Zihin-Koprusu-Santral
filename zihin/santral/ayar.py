from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SunucuAyar:
    host: str = "0.0.0.0"
    port: int = 8767
    erisim_tokeni: str = "degistir-beni"


@dataclass
class TelegramAyar:
    etkin: bool = True
    ayar_dosyasi: str = "telegram_ayar.json"
    varsayilan_chat_id: str = ""


@dataclass
class STTAyar:
    etkin: bool = True
    model_yolu: str = "modeller/vosk-tr/vosk-model-small-tr-0.3"
    ffmpeg_bul: bool = True


@dataclass
class TTSAyar:
    etkin: bool = True
    motor: str = "piper"
    piper_model: str = "modeller/piper-tr/tr_TR-dfki-medium.onnx"
    edge_ses: str = "tr-TR-AhmetNeural"
    gtts_dil: str = "tr"


@dataclass
class DavranisAyar:
    auto_transkript: bool = True
    telegrama_ses_dosyasi_gonder: bool = True
    telegrama_transkript_gonder: bool = True
    olay_logu: bool = True


@dataclass
class DepoAyar:
    kok_dizin: str = "veri/santral"
    cagri_dizin: str = "cagrilar"
    prompt_dizin: str = "anonslar"
    akis_dosyasi: str = "santral_akislari.ornek.json"


@dataclass
class SantralAyar:
    cihaz_adi: str = "zk-santral"
    sunucu: SunucuAyar = field(default_factory=SunucuAyar)
    telegram: TelegramAyar = field(default_factory=TelegramAyar)
    stt: STTAyar = field(default_factory=STTAyar)
    tts: TTSAyar = field(default_factory=TTSAyar)
    davranis: DavranisAyar = field(default_factory=DavranisAyar)
    depo: DepoAyar = field(default_factory=DepoAyar)

    @staticmethod
    def _goreli_yol_coz(base_dir: Path, deger: str) -> str:
        if not deger:
            return deger
        yol = Path(deger).expanduser()
        if yol.is_absolute():
            return str(yol)
        return str((base_dir / yol).resolve())

    @classmethod
    def yukle(cls, dosya: str | Path) -> "SantralAyar":
        yol = Path(dosya)
        veri = json.loads(yol.read_text(encoding="utf-8"))
        base_dir = yol.resolve().parent
        telegram = TelegramAyar(**veri.get("telegram", {}))
        stt = STTAyar(**veri.get("stt", {}))
        tts = TTSAyar(**veri.get("tts", {}))
        depo = DepoAyar(**veri.get("depo", {}))

        telegram.ayar_dosyasi = cls._goreli_yol_coz(base_dir, telegram.ayar_dosyasi)
        stt.model_yolu = cls._goreli_yol_coz(base_dir, stt.model_yolu)
        tts.piper_model = cls._goreli_yol_coz(base_dir, tts.piper_model)
        depo.kok_dizin = cls._goreli_yol_coz(base_dir, depo.kok_dizin)
        depo.akis_dosyasi = cls._goreli_yol_coz(base_dir, depo.akis_dosyasi)

        return cls(
            cihaz_adi=veri.get("cihaz_adi", "zk-santral"),
            sunucu=SunucuAyar(**veri.get("sunucu", {})),
            telegram=telegram,
            stt=stt,
            tts=tts,
            davranis=DavranisAyar(**veri.get("davranis", {})),
            depo=depo,
        )
