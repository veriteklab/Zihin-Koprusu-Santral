"""
Zihin Köprüsü v6.0 – Çok Sağlayıcılı AI Motoru
Desteklenen: Gemini, OpenAI/uyumlu, Ollama (yerel), uzak Ollama (SSH/Tor),
             Anthropic, Groq

"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, asdict
from enum import Enum

import requests

from .logcu import Logcu

KAYNAK = "AI"


class AISağlayici(str, Enum):
    GEMINI      = "gemini"
    OPENAI      = "openai"
    OLLAMA      = "ollama"
    OLLAMA_UZAK = "ollama_uzak"
    ANTHROPIC   = "anthropic"
    GROQ        = "groq"


@dataclass
class AIAyar:
    saglayici: str = AISağlayici.GEMINI
    model: str = ""
    api_anahtari: str = ""
    api_url: str = ""
    uzak_ssh_host: str = ""
    uzak_ssh_port: int = 22
    uzak_ssh_kullanici: str = ""
    uzak_ssh_anahtar: str = ""
    uzak_ollama_port: int = 11434
    tor_proxy: str = "socks5h://127.0.0.1:9050"
    kullan_tor: bool = False
    sistem_mesaji: str = (
        "Sen Zihin Köprüsü sisteminin asistanısın. "
        "Sahibine hitap adıyla seslenirsin. "
        "Kısa, net ve yardımsever Türkçe yanıtlar verirsin."
    )
    max_gecmis: int = 20
    ad: str = ""

    def to_dict(self, gizli_dahil: bool = False) -> dict:
        d = asdict(self)
        if not gizli_dahil:
            d.pop("api_anahtari", None)
            d.pop("uzak_ssh_anahtar", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AIAyar":
        d = dict(d)
        d.setdefault("api_anahtari", "")
        d.setdefault("uzak_ssh_anahtar", "")
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class AIMotoru:
    def __init__(self, ayar: AIAyar, logcu: Logcu):
        self.ayar = ayar
        self.log = logcu
        self._gecmis: list[dict] = []
        self._tünel_proc: subprocess.Popen | None = None
        self._hazir = False
        self._baslat()

    def _baslat(self):
        s = self.ayar.saglayici
        try:
            if s == AISağlayici.GEMINI:
                self._baslat_gemini()
            elif s == AISağlayici.OPENAI:
                self._hazir = bool(self.ayar.api_anahtari or os.getenv("OPENAI_API_KEY", ""))
            elif s == AISağlayici.ANTHROPIC:
                self._hazir = bool(self.ayar.api_anahtari or os.getenv("ANTHROPIC_API_KEY", ""))
            elif s == AISağlayici.GROQ:
                self._baslat_groq()
            elif s == AISağlayici.OLLAMA:
                self._hazir = self._ollama_ping(
                    f"http://localhost:{self.ayar.uzak_ollama_port or 11434}")
            elif s == AISağlayici.OLLAMA_UZAK:
                self._hazir = self._tünel_ac_ve_ping()
            self.log.bilgi(KAYNAK, f"Sağlayıcı hazır: {s} | Model: {self.ayar.model}")
        except Exception as e:
            self.log.hata(KAYNAK, f"AI başlatılamadı: {e}")
            self._hazir = False

    def _baslat_gemini(self):
        import google.generativeai as genai
        anahtar = self.ayar.api_anahtari or os.getenv("GEMINI_API_KEY", "")
        if not anahtar:
            self._hazir = False
            return
        genai.configure(api_key=anahtar)
        model_adi = self.ayar.model or self._gemini_model_sec(genai)
        self._gemini_model = genai.GenerativeModel(
            model_adi, system_instruction=self.ayar.sistem_mesaji)
        self._gemini_sohbet = self._gemini_model.start_chat(history=[])
        self._hazir = True

    def _gemini_model_sec(self, genai) -> str:
        try:
            for m in genai.list_models():
                if "flash" in m.name.lower() and \
                        "generateContent" in m.supported_generation_methods:
                    return m.name
        except Exception:
            pass
        return "gemini-pro"

    def _baslat_groq(self):
        anahtar = self.ayar.api_anahtari or os.getenv("GROQ_API_KEY", "")
        if not anahtar:
            self._hazir = False
            return
        try:
            from groq import Groq
            self._groq_client = Groq(api_key=anahtar)
            self._hazir = True
        except ImportError:
            self.log.uyari(KAYNAK, "groq paketi kurulu değil: pip install groq")
            self._hazir = False

    def _ollama_ping(self, url: str) -> bool:
        try:
            r = requests.get(url, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _tünel_ac_ve_ping(self) -> bool:
        lokal_port = 11435
        args = [
            "ssh", "-N", "-L",
            f"{lokal_port}:localhost:{self.ayar.uzak_ollama_port}",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-p", str(self.ayar.uzak_ssh_port),
        ]
        if self.ayar.uzak_ssh_anahtar:
            args += ["-i", os.path.expanduser(self.ayar.uzak_ssh_anahtar)]
        if self.ayar.kullan_tor:
            args += ["-o", "ProxyCommand=nc -x 127.0.0.1:9050 %h %p"]
        args.append(
            f"{self.ayar.uzak_ssh_kullanici}@{self.ayar.uzak_ssh_host}")
        try:
            self._tünel_proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import time; time.sleep(2)
            self.ayar.api_url = f"http://localhost:{lokal_port}"
            return self._ollama_ping(self.ayar.api_url)
        except Exception as e:
            self.log.hata(KAYNAK, f"Tünel açılamadı: {e}")
            return False

    # ── Ana Sorgu ────────────────────────────────────────────────────────────

    def sor(self, metin: str) -> str:
        if not self._hazir:
            return "AI motoru hazır değil. Lütfen ayarları kontrol edin."
        s = self.ayar.saglayici
        try:
            if s == AISağlayici.GEMINI:
                return self._gemini_sor(metin)
            elif s == AISağlayici.OPENAI:
                return self._openai_sor(metin)
            elif s == AISağlayici.ANTHROPIC:
                return self._anthropic_sor(metin)
            elif s == AISağlayici.GROQ:
                return self._groq_sor(metin)
            elif s in (AISağlayici.OLLAMA, AISağlayici.OLLAMA_UZAK):
                return self._ollama_sor(metin)
        except Exception as e:
            self.log.hata(KAYNAK, str(e))
            return "Şu an yanıt veremiyorum, lütfen tekrar deneyin."
        return "Desteklenmeyen AI sağlayıcısı."

    def _gecmis_ekle(self, rol: str, icerik: str):
        self._gecmis.append({"role": rol, "content": icerik})
        if len(self._gecmis) > self.ayar.max_gecmis * 2:
            self._gecmis = self._gecmis[-(self.ayar.max_gecmis * 2):]

    def _gemini_sor(self, metin: str) -> str:
        yanit = self._gemini_sohbet.send_message(metin)
        return yanit.text

    def _openai_sor(self, metin: str) -> str:
        self._gecmis_ekle("user", metin)
        url = self._openai_chat_url()
        anahtar = self.ayar.api_anahtari or os.getenv("OPENAI_API_KEY", "")
        model = self.ayar.model or "gpt-4o-mini"
        mesajlar = [{"role": "system",
                     "content": self.ayar.sistem_mesaji}] + self._gecmis
        proxies = ({"https": self.ayar.tor_proxy,
                    "http":  self.ayar.tor_proxy}
                   if self.ayar.kullan_tor else None)
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {anahtar}",
                     "Content-Type": "application/json"},
            json={"model": model, "messages": mesajlar},
            proxies=proxies, timeout=60,
        )
        r.raise_for_status()
        yanit = r.json()["choices"][0]["message"]["content"]
        self._gecmis_ekle("assistant", yanit)
        return yanit

    def _anthropic_sor(self, metin: str) -> str:
        self._gecmis_ekle("user", metin)
        anahtar = self.ayar.api_anahtari or os.getenv("ANTHROPIC_API_KEY", "")
        model = self.ayar.model or "claude-3-haiku-20240307"
        proxies = ({"https": self.ayar.tor_proxy}
                   if self.ayar.kullan_tor else None)
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": anahtar,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={"model": model, "max_tokens": 1024,
                  "system": self.ayar.sistem_mesaji,
                  "messages": self._gecmis},
            proxies=proxies, timeout=60,
        )
        r.raise_for_status()
        yanit = r.json()["content"][0]["text"]
        self._gecmis_ekle("assistant", yanit)
        return yanit

    def _groq_sor(self, metin: str) -> str:
        self._gecmis_ekle("user", metin)
        model = self.ayar.model or "llama3-8b-8192"
        mesajlar = [{"role": "system",
                     "content": self.ayar.sistem_mesaji}] + self._gecmis
        tamamlama = self._groq_client.chat.completions.create(
            messages=mesajlar,
            model=model,
            max_tokens=1024,
        )
        yanit = tamamlama.choices[0].message.content
        self._gecmis_ekle("assistant", yanit)
        return yanit

    def _ollama_sor(self, metin: str) -> str:
        self._gecmis_ekle("user", metin)
        url = (self.ayar.api_url or "http://localhost:11434") + "/api/chat"
        model = self.ayar.model or "llama3"
        mesajlar = [{"role": "system",
                     "content": self.ayar.sistem_mesaji}] + self._gecmis
        r = requests.post(
            url,
            json={"model": model, "messages": mesajlar, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        yanit = r.json()["message"]["content"]
        self._gecmis_ekle("assistant", yanit)
        return yanit

    def _openai_chat_url(self) -> str:
        url = (self.ayar.api_url or "https://api.openai.com").rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        return url + "/v1/chat/completions"

    # ── Yönetim ──────────────────────────────────────────────────────────────

    def sohbet_sifirla(self):
        self._gecmis = []
        if self.ayar.saglayici == AISağlayici.GEMINI and self._hazir:
            self._gemini_sohbet = self._gemini_model.start_chat(history=[])
        self.log.bilgi(KAYNAK, "Sohbet sıfırlandı.")

    def yeniden_baslat(self, yeni_ayar: AIAyar | None = None):
        if yeni_ayar:
            self.ayar = yeni_ayar
        if self._tünel_proc:
            self._tünel_proc.terminate()
            self._tünel_proc = None
        self._gecmis = []
        self._hazir = False
        self._baslat()

    @property
    def hazir(self) -> bool:
        return self._hazir

    def modeller_listele(self) -> list[str]:
        s = self.ayar.saglayici
        try:
            if s == AISağlayici.GEMINI:
                import google.generativeai as genai
                return [m.name for m in genai.list_models()
                        if "generateContent" in m.supported_generation_methods]
            elif s == AISağlayici.GROQ:
                modeller = self._groq_client.models.list()
                return [m.id for m in modeller.data]
            elif s in (AISağlayici.OLLAMA, AISağlayici.OLLAMA_UZAK):
                url = (self.ayar.api_url or "http://localhost:11434") + "/api/tags"
                r = requests.get(url, timeout=5)
                return [m["name"] for m in r.json().get("models", [])]
            elif s == AISağlayici.OPENAI:
                r = requests.get(
                    (self.ayar.api_url or "https://api.openai.com") + "/v1/models",
                    headers={"Authorization": f"Bearer {self.ayar.api_anahtari}"},
                    timeout=10,
                )
                return [m["id"] for m in r.json().get("data", [])]
        except Exception as e:
            self.log.uyari(KAYNAK, f"Model listesi alınamadı: {e}")
        return []
