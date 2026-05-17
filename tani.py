#!/usr/bin/env python3
"""
Zihin Koprusu tani araci.

Agir GUI/ses dongusu baslatmadan kurulum ve dosya durumunu raporlar.
"""
from __future__ import annotations

import importlib.util
import importlib
import warnings
import json
import os
import pathlib
import shutil


KOK = pathlib.Path(__file__).resolve().parent
VENV_BIN = KOK / "birader_env" / "bin"
ARAC_PATH = (
    str(VENV_BIN) + os.pathsep + os.environ.get("PATH", "")
    if VENV_BIN.exists() else os.environ.get("PATH", "")
)


PYTHON_MODULLERI = [
    "vosk",
    "sounddevice",
    "gtts",
    "edge_tts",
    "yaml",
    "google.generativeai",
    "PyQt6",
    "requests",
    "psutil",
    "telegram",
    "python_socks",
    "socks",
    "telethon",
    "playwright",
]

SISTEM_ARACLARI = [
    "python3",
    "ffmpeg",
    "ffplay",
    "aplay",
    "paplay",
    "piper",
    "tor",
    "ssh",
    "nc",
    "xdotool",
    "wmctrl",
    "playerctl",
    "brightnessctl",
    "scrot",
    "adb",
    "scrcpy",
    "tesseract",
]

APT_PAKETLERI = {
    "ffmpeg": "ffmpeg",
    "ffplay": "ffmpeg",
    "paplay": "pulseaudio-utils",
    "tor": "tor",
    "xdotool": "xdotool",
    "wmctrl": "wmctrl",
    "playerctl": "playerctl",
    "brightnessctl": "brightnessctl",
    "scrot": "scrot",
    "tesseract": "tesseract-ocr tesseract-ocr-tur",
}

JSON_DOSYALARI = [
    "ai_ayar.json",
    "telegram_ayar.json",
    "hitap_ayar.json",
    "uzuvlar.json",
    "komutlar.json",
    "makrolar.json",
    "hafiza.json",
    "takvim.json",
    "bilinc_goruntu.json",
    "dil/tr.json",
]

MODEL_DOSYALARI = [
    ("Vosk TR", "modeller/vosk-tr/vosk-model-small-tr-0.3"),
    ("Piper TR model", "modeller/piper-tr/tr_TR-dfki-medium.onnx"),
    ("Piper TR config", "modeller/piper-tr/tr_TR-dfki-medium.onnx.json"),
]


def durum(ok: bool) -> str:
    return "OK" if ok else "EKSIK"


def baslik(metin: str):
    print(f"\n== {metin} ==")


def python_modulu_var(ad: str) -> bool:
    kok = ad.split(".", 1)[0]
    if importlib.util.find_spec(kok) is None:
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            importlib.import_module(ad)
        return True
    except Exception:
        return False


def json_kontrol():
    baslik("JSON")
    for rel in JSON_DOSYALARI:
        yol = KOK / rel
        if not yol.exists():
            print(f"{durum(False):5} {rel}")
            continue
        try:
            with yol.open("r", encoding="utf-8") as f:
                json.load(f)
            print(f"{durum(True):5} {rel}")
        except Exception as e:
            print(f"HATA  {rel}: {e}")


def yaml_kontrol():
    baslik("YAML")
    yol = KOK / "beyin.yaml"
    if not yol.exists():
        print("EKSIK beyin.yaml")
        return
    if not python_modulu_var("yaml"):
        print("EKSIK beyin.yaml kontrolu icin PyYAML")
        return
    try:
        import yaml
        with yol.open("r", encoding="utf-8") as f:
            yaml.safe_load(f)
        print("OK    beyin.yaml")
    except Exception as e:
        print(f"HATA  beyin.yaml: {e}")


def moduller():
    baslik("Python Modulleri")
    eksik = []
    for ad in PYTHON_MODULLERI:
        ok = python_modulu_var(ad)
        print(f"{durum(ok):5} {ad}")
        if not ok:
            eksik.append(ad)
    if "sounddevice" in eksik:
        print("ONERI sudo apt install portaudio19-dev")
    if "socks" in eksik:
        print("ONERI pip install PySocks")


def araclar():
    baslik("Sistem Araclari")
    eksik_apt = []
    for ad in SISTEM_ARACLARI:
        yol = shutil.which(ad, path=ARAC_PATH)
        print(f"{durum(bool(yol)):5} {ad}{' -> ' + yol if yol else ''}")
        if not yol and ad in APT_PAKETLERI:
            eksik_apt.extend(APT_PAKETLERI[ad].split())
    if eksik_apt:
        paketler = " ".join(sorted(set(eksik_apt)))
        print(f"ONERI sudo apt install {paketler}")


def modeller():
    baslik("Modeller")
    for ad, rel in MODEL_DOSYALARI:
        yol = KOK / rel
        print(f"{durum(yol.exists()):5} {ad}: {rel}")


def komut_db():
    baslik("Komut DB")
    try:
        from zihin.komut_veritabani import KomutVeritabani
        from zihin.logcu import Logcu
        db = KomutVeritabani(Logcu(str(KOK / "loglar" / "tani.log")),
                             str(KOK / "komutlar.json"))
        print(f"OK    {len(db.komutlar)} komut yuklendi")
        for metin in ("merhaba", "saat kac", "saat kaç"):
            sonuc = db.calistir("ABLA", metin)
            print(f"TEST  {metin!r} -> {sonuc or 'eslesme yok'}")
    except Exception as e:
        print(f"HATA  Komut DB yuklenemedi: {e}")


def kalintilar():
    baslik("Kurtarma Kalintilari")
    yanlis = KOK / "{zihin,dil,eklentiler,modeller"
    if yanlis.exists():
        print(f"HATA  hatali klasor var: {yanlis.name}")
    else:
        print("OK    hatali brace klasoru yok")


def tor_http_tani():
    baslik("Tor HTTP")
    tor_var = shutil.which("tor", path=ARAC_PATH)
    socks_modul = python_modulu_var("socks")
    requests_modul = python_modulu_var("requests")
    print(f"{durum(bool(tor_var)):5} tor binary")
    print(f"{durum(socks_modul):5} PySocks / socks modulu")
    print(f"{durum(requests_modul):5} requests modulu")
    if not tor_var:
        print("ONERI .onion erisimi icin: sudo apt install tor")
    if requests_modul and not socks_modul:
        print("ONERI requests SOCKS destegi icin: pip install PySocks")
    if tor_var and socks_modul:
        print("OK    tor_http / tor_https temel bagimliliklari hazir")


def main() -> int:
    print(f"Zihin Koprusu tani | kok={KOK}")
    json_kontrol()
    yaml_kontrol()
    moduller()
    araclar()
    modeller()
    komut_db()
    kalintilar()
    tor_http_tani()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
