from __future__ import annotations

import json
from pathlib import Path

import requests


class TelegramBildirici:
    def __init__(self, ayar_dosyasi: str, varsayilan_chat_id: str = ""):
        veri = json.loads(Path(ayar_dosyasi).read_text(encoding="utf-8"))
        self.token = veri.get("token", "")
        self.chat_id = varsayilan_chat_id or str(veri.get("chat_id", ""))
        self.etkin = bool(self.token and self.chat_id)

    @property
    def api(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    def mesaj_gonder(self, metin: str) -> None:
        if not self.etkin:
            return
        requests.post(
            f"{self.api}/sendMessage",
            data={"chat_id": self.chat_id, "text": metin},
            timeout=20,
        ).raise_for_status()

    def dosya_gonder(self, yol: str, baslik: str = "") -> None:
        if not self.etkin:
            return
        with open(yol, "rb") as handle:
            requests.post(
                f"{self.api}/sendDocument",
                data={"chat_id": self.chat_id, "caption": baslik},
                files={"document": handle},
                timeout=60,
            ).raise_for_status()
