from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .ayar import SantralAyar
from .akis import AkisYonetici
from .depo import SantralDepo
from .ses_islem import SantralSesIslem
from .telegram import TelegramBildirici


class SantralSunucu:
    def __init__(self, ayar: SantralAyar):
        self.ayar = ayar
        self.depo = SantralDepo(ayar.depo.kok_dizin, ayar.depo.cagri_dizin)
        self.telegram = TelegramBildirici(
            ayar.telegram.ayar_dosyasi,
            ayar.telegram.varsayilan_chat_id,
        )
        self.akis = AkisYonetici(ayar.depo.akis_dosyasi)
        self.ses = SantralSesIslem(
            ayar.stt.model_yolu,
            ayar.tts.piper_model,
            ayar.tts.edge_ses,
            ayar.tts.gtts_dil,
        )

    def _telegram_olay(self, kayit, olay: str) -> None:
        if not self.ayar.telegram.etkin or not self.telegram.etkin:
            return
        numara = kayit.phone_number or "bilinmiyor"
        self.telegram.mesaj_gonder(
            f"[Santral] {olay}\n"
            f"Cagri: {kayit.call_id}\n"
            f"Cihaz: {kayit.device_id}\n"
            f"Numara: {numara}\n"
            f"Durum: {kayit.state}"
        )

    def _akis_bildir(self, kayit, akis_metin: str) -> None:
        if not self.ayar.telegram.etkin or not self.telegram.etkin:
            return
        self.telegram.mesaj_gonder(
            f"[Santral] Akis\n"
            f"Cagri: {kayit.call_id}\n"
            f"Numara: {kayit.phone_number or 'bilinmiyor'}\n"
            f"{akis_metin}"
        )

    def olay_isle(self, payload: dict[str, Any]) -> dict[str, Any]:
        call_id = str(payload["call_id"])
        device_id = str(payload.get("device_id", self.ayar.cihaz_adi))
        event_type = str(payload["event_type"])
        phone_number = str(payload.get("phone_number", ""))
        state = str(payload.get("state", event_type))
        extra = payload.get("extra", {}) or {}
        kayit = self.depo.olay_ekle(call_id, device_id, event_type, phone_number, state, extra)
        if event_type in {"incoming", "answered", "hangup", "missed"}:
            self._telegram_olay(kayit, f"Olay: {event_type}")
        if event_type == "incoming":
            akis = self.akis.getir(extra.get("akis_id") if extra else None)
            kayit.meta["akis_id"] = akis.akis_id
            self.depo.kaydet(kayit)
        return {"ok": True, "call_id": call_id, "state": kayit.state}

    def recording_isle(self, call_id: str, filename: str, veri: bytes) -> dict[str, Any]:
        dosya = self.depo.recording_kaydet(call_id, filename, veri)
        kayit = self.depo.recording_guncelle(call_id, str(dosya))
        transcript = ""
        if self.ayar.davranis.auto_transkript and self.ayar.stt.etkin:
            try:
                transcript = self.ses.transkript_yap(str(dosya))
            except Exception:
                transcript = ""
            if transcript:
                kayit = self.depo.transcript_guncelle(call_id, transcript)
        if self.ayar.telegram.etkin and self.telegram.etkin:
            if self.ayar.davranis.telegrama_ses_dosyasi_gonder:
                self.telegram.dosya_gonder(str(dosya), f"Kayit | {call_id}")
            if transcript and self.ayar.davranis.telegrama_transkript_gonder:
                self.telegram.mesaj_gonder(
                    f"[Santral] Transkript\nCagri: {call_id}\n\n{transcript}"
                )
        return {
            "ok": True,
            "call_id": call_id,
            "recording_path": str(dosya),
            "transcript": transcript,
            "state": kayit.state,
        }

    def tts_isle(self, text: str, filename: str = "anons.wav") -> dict[str, Any]:
        hedef = Path(self.ayar.depo.kok_dizin) / self.ayar.depo.prompt_dizin / filename
        sonuc = self.ses.tts_uret(text, str(hedef))
        return {"ok": True, "path": sonuc}

    def call_getir(self, call_id: str) -> dict[str, Any]:
        kayit = self.depo.yukle(call_id)
        if kayit is None:
            return {"ok": False, "error": "not_found"}
        return {
            "ok": True,
            "call_id": kayit.call_id,
            "device_id": kayit.device_id,
            "phone_number": kayit.phone_number,
            "state": kayit.state,
            "recording_path": kayit.recording_path,
            "transcript": kayit.transcript,
            "events": kayit.events,
            "meta": kayit.meta,
        }

    def call_menu_isle(self, call_id: str, tus: str) -> dict[str, Any]:
        kayit = self.depo.yukle(call_id)
        if kayit is None:
            return {"ok": False, "error": "not_found"}
        sonuc = self.akis.secim_isle(kayit.meta.get("akis_id"), tus)
        kayit.notes.append(f"secim:{tus}:{sonuc.get('eylem','')}")
        kayit.meta["son_secim"] = tus
        kayit.meta["son_eylem"] = sonuc.get("eylem", "")
        self.depo.kaydet(kayit)
        bildirim = sonuc.get("bildirim", "")
        if bildirim:
            self._akis_bildir(kayit, bildirim)
        return {"ok": True, "call_id": call_id, "selection": sonuc}

    def call_prompt_uret(self, call_id: str) -> dict[str, Any]:
        kayit = self.depo.yukle(call_id)
        if kayit is None:
            return {"ok": False, "error": "not_found"}
        akis = self.akis.getir(kayit.meta.get("akis_id"))
        filename = f"{call_id}_prompt.wav"
        try:
            sonuc = self.tts_isle(akis.anons_metni(), filename)
            path = sonuc["path"]
            tts_hazir = True
            hata = ""
        except Exception as exc:
            path = ""
            tts_hazir = False
            hata = str(exc)
        kayit.meta["prompt_text"] = akis.anons_metni()
        kayit.meta["prompt_path"] = path
        kayit.meta["prompt_tts_hazir"] = tts_hazir
        if hata:
            kayit.meta["prompt_hata"] = hata
        self.depo.kaydet(kayit)
        return {
            "ok": True,
            "call_id": call_id,
            "akis_id": akis.akis_id,
            "text": akis.anons_metni(),
            "path": path,
            "tts_hazir": tts_hazir,
            "error": hata,
        }

    def call_prompt_ses_getir(self, call_id: str) -> tuple[Path, str] | None:
        kayit = self.depo.yukle(call_id)
        if kayit is None:
            return None
        prompt_path = str(kayit.meta.get("prompt_path", "")).strip()
        if not prompt_path:
            sonuc = self.call_prompt_uret(call_id)
            prompt_path = str(sonuc.get("path", "")).strip()
        if not prompt_path:
            return None
        yol = Path(prompt_path)
        if not yol.exists():
            return None
        icerik_tipi = mimetypes.guess_type(str(yol))[0] or "application/octet-stream"
        return yol, icerik_tipi

    def serve_forever(self) -> None:
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "ZKSantral/0.1"

            def _json(self, status: int, veri: dict[str, Any]) -> None:
                ham = json.dumps(veri, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(ham)))
                self.end_headers()
                self.wfile.write(ham)

            def _bytes(self, status: int, veri: bytes, icerik_tipi: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", icerik_tipi)
                self.send_header("Content-Length", str(len(veri)))
                self.end_headers()
                self.wfile.write(veri)

            def _yetki_var(self, token: str) -> bool:
                return token == app.ayar.sunucu.erisim_tokeni

            def do_GET(self) -> None:
                try:
                    parsed = urlparse(self.path)
                    if parsed.path == "/health":
                        self._json(HTTPStatus.OK, {"ok": True, "service": "zk-santral"})
                        return
                    eslesme = re.fullmatch(r"/api/v1/calls/([^/]+)/prompt-audio", parsed.path)
                    if eslesme:
                        query = parse_qs(parsed.query)
                        token = (query.get("token") or [""])[0]
                        if not self._yetki_var(token):
                            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "forbidden"})
                            return
                        sonuc = app.call_prompt_ses_getir(eslesme.group(1))
                        if sonuc is None:
                            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "prompt_not_found"})
                            return
                        yol, icerik_tipi = sonuc
                        self._bytes(HTTPStatus.OK, yol.read_bytes(), icerik_tipi)
                        return
                    eslesme = re.fullmatch(r"/api/v1/calls/([^/]+)", parsed.path)
                    if eslesme:
                        self._json(HTTPStatus.OK, app.call_getir(eslesme.group(1)))
                        return
                    self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                except Exception as exc:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})

            def do_POST(self) -> None:
                try:
                    parsed = urlparse(self.path)
                    if parsed.path == "/api/v1/events":
                        uzunluk = int(self.headers.get("Content-Length", "0"))
                        payload = json.loads(self.rfile.read(uzunluk).decode("utf-8"))
                        if not self._yetki_var(str(payload.get("token", ""))):
                            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "forbidden"})
                            return
                        self._json(HTTPStatus.OK, app.olay_isle(payload))
                        return
                    if parsed.path == "/api/v1/tts":
                        uzunluk = int(self.headers.get("Content-Length", "0"))
                        payload = json.loads(self.rfile.read(uzunluk).decode("utf-8"))
                        if not self._yetki_var(str(payload.get("token", ""))):
                            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "forbidden"})
                            return
                        sonuc = app.tts_isle(payload["text"], payload.get("filename", "anons.wav"))
                        self._json(HTTPStatus.OK, sonuc)
                        return
                    eslesme = re.fullmatch(r"/api/v1/calls/([^/]+)/menu", parsed.path)
                    if eslesme:
                        uzunluk = int(self.headers.get("Content-Length", "0"))
                        payload = json.loads(self.rfile.read(uzunluk).decode("utf-8"))
                        if not self._yetki_var(str(payload.get("token", ""))):
                            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "forbidden"})
                            return
                        self._json(HTTPStatus.OK, app.call_menu_isle(eslesme.group(1), str(payload["digit"])))
                        return
                    eslesme = re.fullmatch(r"/api/v1/calls/([^/]+)/prompt", parsed.path)
                    if eslesme:
                        uzunluk = int(self.headers.get("Content-Length", "0"))
                        payload = json.loads(self.rfile.read(uzunluk).decode("utf-8"))
                        if not self._yetki_var(str(payload.get("token", ""))):
                            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "forbidden"})
                            return
                        self._json(HTTPStatus.OK, app.call_prompt_uret(eslesme.group(1)))
                        return
                    eslesme = re.fullmatch(r"/api/v1/calls/([^/]+)/recording", parsed.path)
                    if eslesme:
                        query = parse_qs(parsed.query)
                        token = (query.get("token") or [""])[0]
                        if not self._yetki_var(token):
                            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "forbidden"})
                            return
                        call_id = eslesme.group(1)
                        filename = (query.get("filename") or ["kayit.raw"])[0]
                        uzunluk = int(self.headers.get("Content-Length", "0"))
                        veri = self.rfile.read(uzunluk)
                        self._json(HTTPStatus.OK, app.recording_isle(call_id, filename, veri))
                        return
                    self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                except Exception as exc:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})

            def log_message(self, format: str, *args: Any) -> None:
                return

        sunucu = ThreadingHTTPServer((self.ayar.sunucu.host, self.ayar.sunucu.port), Handler)
        try:
            sunucu.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            sunucu.server_close()
