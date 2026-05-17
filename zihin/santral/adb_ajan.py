from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass

import requests


@dataclass
class ADBAjanAyar:
    server_url: str = "http://127.0.0.1:8767"
    token: str = "zk-santral-yerel-test"
    device_id: str = "j2-prime"
    poll_sec: float = 1.0
    auto_answer: bool = True
    auto_prompt: bool = True
    adb_serial: str = ""


class ADBSantralAjan:
    def __init__(self, ayar: ADBAjanAyar):
        self.ayar = ayar
        self.onceki_durum = "0"
        self.onceki_call_id = ""
        self.onceki_numara = ""
        self.son_incoming_ts = 0.0
        self.son_answered_ts = 0.0
        self.son_hangup_ts = 0.0
        self.ring_debounce_sec = 4.0
        self.state_debounce_sec = 2.0

    def _adb(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = ["adb"]
        if self.ayar.adb_serial:
            cmd += ["-s", self.ayar.adb_serial]
        cmd += list(args)
        return subprocess.run(cmd, check=check, capture_output=True, text=True)

    def _shell(self, komut: str, check: bool = True) -> str:
        sonuc = self._adb("shell", komut, check=check)
        return (sonuc.stdout or "").strip()

    def _su_shell(self, komut: str, check: bool = True) -> str:
        return self._shell(f"su -c '{komut}'", check=check)

    def mevcut_durum(self) -> tuple[str, str]:
        veri = self._shell("dumpsys telephony.registry", check=False)
        durum = re.search(r"mCallState=(\d+)", veri)
        numara = re.search(r"mCallIncomingNumber=(.*)", veri)
        return (
            durum.group(1).strip() if durum else "0",
            numara.group(1).strip() if numara else "",
        )

    def olay_gonder(self, event_type: str, phone_number: str, state: str, call_id: str) -> None:
        payload = {
            "token": self.ayar.token,
            "device_id": self.ayar.device_id,
            "event_type": event_type,
            "phone_number": phone_number,
            "state": state,
            "call_id": call_id,
        }
        requests.post(
            f"{self.ayar.server_url}/api/v1/events",
            json=payload,
            timeout=10,
        ).raise_for_status()

    def prompt_hazirla(self, call_id: str) -> dict | None:
        if not self.ayar.auto_prompt:
            return None
        yanit = requests.post(
            f"{self.ayar.server_url}/api/v1/calls/{call_id}/prompt",
            json={"token": self.ayar.token},
            timeout=20,
        )
        yanit.raise_for_status()
        return yanit.json()

    def otomatik_cevapla(self) -> None:
        if not self.ayar.auto_answer:
            return
        self._shell("input keyevent KEYCODE_HEADSETHOOK", check=False)

    def healthcheck(self) -> None:
        call_id = f"health-{int(time.time())}"
        self.olay_gonder("healthcheck", "", "idle", call_id)

    def run_forever(self) -> None:
        while True:
            durum, numara = self.mevcut_durum()
            if durum == "1" and self.onceki_durum != "1":
                simdi = time.time()
                ayni_numara = bool(numara and numara == self.onceki_numara)
                if self.onceki_call_id and ayni_numara and (simdi - self.son_incoming_ts) < self.ring_debounce_sec:
                    pass
                else:
                    call_id = str(int(simdi))
                    self.onceki_call_id = call_id
                    self.onceki_numara = numara
                    self.son_incoming_ts = simdi
                    self.olay_gonder("incoming", numara, "ringing", call_id)
                    self.otomatik_cevapla()
            elif durum == "2" and self.onceki_durum != "2":
                simdi = time.time()
                if (simdi - self.son_answered_ts) >= self.state_debounce_sec:
                    call_id = self.onceki_call_id or str(int(simdi))
                    if numara:
                        self.onceki_numara = numara
                    self.olay_gonder("answered", numara, "active", call_id)
                    self.prompt_hazirla(call_id)
                    self.son_answered_ts = simdi
            elif durum == "0" and self.onceki_durum != "0":
                simdi = time.time()
                if (simdi - self.son_hangup_ts) >= self.state_debounce_sec:
                    call_id = self.onceki_call_id or str(int(simdi))
                    self.olay_gonder("hangup", numara, "idle", call_id)
                    self.son_hangup_ts = simdi
                    self.onceki_call_id = ""
                    self.onceki_numara = ""
            self.onceki_durum = durum
            time.sleep(self.ayar.poll_sec)
