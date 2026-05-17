from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

try:
    from vosk import KaldiRecognizer, Model
except Exception:
    KaldiRecognizer = None
    Model = None


class SantralSesIslem:
    def __init__(self, model_yolu: str, piper_model: str, edge_ses: str, gtts_dil: str):
        self.model_yolu = Path(model_yolu)
        self.piper_model = piper_model
        self.edge_ses = edge_ses
        self.gtts_dil = gtts_dil
        self._model = None

    def _wav_hazirla(self, kaynak: str) -> str:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return kaynak
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        subprocess.run(
            [ffmpeg, "-y", "-i", kaynak, "-ar", "16000", "-ac", "1", tmp.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return tmp.name

    def _donustur(self, kaynak: str, hedef: str) -> str:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("Ses donusumu icin ffmpeg bulunamadi.")
        subprocess.run(
            [ffmpeg, "-y", "-i", kaynak, hedef],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return hedef

    def transkript_yap(self, kaynak: str) -> str:
        if Model is None or KaldiRecognizer is None or not self.model_yolu.exists():
            return ""
        if self._model is None:
            self._model = Model(str(self.model_yolu))
        wav = self._wav_hazirla(kaynak)
        with wave.open(wav, "rb") as handle:
            tan = KaldiRecognizer(self._model, handle.getframerate())
            parcali: list[str] = []
            while True:
                veri = handle.readframes(4000)
                if not veri:
                    break
                if tan.AcceptWaveform(veri):
                    sonuc = json.loads(tan.Result())
                    if sonuc.get("text"):
                        parcali.append(sonuc["text"])
            final = json.loads(tan.FinalResult())
            if final.get("text"):
                parcali.append(final["text"])
        return " ".join([x.strip() for x in parcali if x.strip()]).strip()

    def tts_uret(self, metin: str, hedef: str) -> str:
        hedef_yolu = Path(hedef)
        hedef_yolu.parent.mkdir(parents=True, exist_ok=True)
        piper = shutil.which("piper")
        if piper and Path(self.piper_model).exists():
            subprocess.run(
                [piper, "--model", self.piper_model, "--output_file", str(hedef_yolu)],
                input=metin.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return str(hedef_yolu)
        edge = shutil.which("edge-tts")
        if edge:
            gecici = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            gecici.close()
            subprocess.run(
                [edge, "--voice", self.edge_ses, "--text", metin, "--write-media", gecici.name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            if hedef_yolu.suffix.lower() == ".mp3":
                return str(Path(gecici.name).replace(hedef_yolu))
            try:
                return self._donustur(gecici.name, str(hedef_yolu))
            except Exception:
                gercek = hedef_yolu.with_suffix(".mp3")
                Path(gecici.name).replace(gercek)
                return str(gercek)
        gtts = shutil.which("gtts-cli")
        if gtts:
            gecici = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            gecici.close()
            subprocess.run(
                [gtts, "--lang", self.gtts_dil, metin, "--output", gecici.name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            if hedef_yolu.suffix.lower() == ".mp3":
                Path(gecici.name).replace(hedef_yolu)
                return str(hedef_yolu)
            try:
                return self._donustur(gecici.name, str(hedef_yolu))
            except Exception:
                gercek = hedef_yolu.with_suffix(".mp3")
                Path(gecici.name).replace(gercek)
                return str(gercek)
        raise RuntimeError("TTS motoru bulunamadi.")
