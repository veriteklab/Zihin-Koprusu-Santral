"""
Zihin Köprüsü – Uzuv Yöneticisi
Merkez düğümün yerel ve uzak uzuvlarını çoklu bağlantı yöntemiyle yönetir.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import shutil
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Callable
from urllib.parse import urlparse

from .logcu import Logcu

KAYNAK = "UZUV"

# Varsayılan onion sunucu (Builder ile paketlenmiş istemciler bunu kullanır)
VARSAYILAN_ONION_HOST = ""      # GUI → Ayarlar'dan değiştirilebilir
VARSAYILAN_ONION_PORT = 22
VARSAYILAN_ONION_KULLANICI = "zihin"


class UzuvTipi(str, Enum):
    LINUX   = "linux"
    WINDOWS = "windows"
    ANDROID = "android"
    MAC     = "mac"


class BaglantiYontemi(str, Enum):
    YEREL     = "yerel"
    SSH       = "ssh"
    YEREL_SSH = "yerel_ssh"
    TERS_SSH  = "ters_ssh"
    TOR_SSH   = "tor_ssh"
    TOR_HTTP  = "tor_http"
    TOR_HTTPS = "tor_https"
    TELEGRAM  = "telegram"
    ADB       = "adb"


class UzuvDurum(str, Enum):
    CEVRIMDISI  = "çevrimdışı"
    BAGLANIYOR  = "bağlanıyor"
    BAGLI       = "bağlı"
    HATA        = "hata"


@dataclass
class Baglanti:
    id: str = ""
    yontem: str = BaglantiYontemi.SSH.value
    aktif: bool = True
    yedek: bool = False
    host: str = ""
    port: int = 22
    kullanici: str = ""
    anahtar: str = ""
    token: str = ""
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 9050
    url: str = ""
    notlar: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, veri: dict) -> "Baglanti":
        temiz = dict(veri or {})
        temiz["yontem"] = _baglanti_yontemi_norm(temiz.get("yontem", BaglantiYontemi.SSH))
        return cls(**{k: v for k, v in temiz.items() if k in cls.__dataclass_fields__})


@dataclass
class Uzuv:
    id: str
    ad: str
    takma_isim: str = ""         # Sesli komutlarda kullanılacak kısa isim
    tip: UzuvTipi = UzuvTipi.LINUX
    yontem: str = BaglantiYontemi.SSH.value
    baglantilar: list[Baglanti] = field(default_factory=list)

    ssh_host: str = ""
    ssh_port: int = 22
    ssh_kullanici: str = ""
    ssh_anahtar: str = ""
    ssh_sifre: str = ""

    tor_proxy_host: str = "127.0.0.1"
    tor_proxy_port: int = 9050

    adb_host: str = ""
    adb_port: int = 5555

    atanmis_bilincler: list[str] = field(default_factory=list)

    durum: str = UzuvDurum.CEVRIMDISI
    notlar: str = ""
    simge: str = "🖥️"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("ssh_sifre", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Uzuv":
        d = dict(d)
        d.setdefault("ssh_sifre", "")
        d.setdefault("takma_isim", "")
        d["yontem"] = _baglanti_yontemi_norm(d.get("yontem", BaglantiYontemi.SSH))
        raw_baglantilar = d.get("baglantilar") or []
        if raw_baglantilar:
            d["baglantilar"] = [Baglanti.from_dict(b) for b in raw_baglantilar if isinstance(b, dict)]
        else:
            d["baglantilar"] = [_baglanti_legacy_uret(d)]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def sesli_isimler(self) -> list[str]:
        """Sesli komutlarda eşleşecek isim listesi."""
        isimler = [self.ad.lower()]
        if self.takma_isim.strip():
            isimler.append(self.takma_isim.strip().lower())
        isimler.append(self.id.lower())
        return isimler

    def etkin_baglantilar(self) -> list[Baglanti]:
        baglantilar = self.baglantilar or [_baglanti_legacy_uret(self.to_dict())]
        return [b for b in baglantilar if getattr(b, "aktif", True)]

    def birincil_baglanti(self) -> Baglanti:
        baglantilar = self.etkin_baglantilar()
        for baglanti in baglantilar:
            if not baglanti.yedek:
                return baglanti
        return baglantilar[0] if baglantilar else _baglanti_legacy_uret(self.to_dict())

    def yedek_baglantilar(self) -> list[Baglanti]:
        return [b for b in self.etkin_baglantilar() if b.yedek]

    def baglanti_ozeti(self) -> str:
        baglantilar = self.etkin_baglantilar()
        if not baglantilar:
            return "baglanti yok"
        parcalar = []
        for baglanti in baglantilar:
            ek = "yedek" if baglanti.yedek else "birincil"
            parcalar.append(f"{baglanti.yontem} ({ek})")
        return ", ".join(parcalar)


def _baglanti_yontemi_norm(deger: str | BaglantiYontemi) -> str:
    ham = str(getattr(deger, "value", deger or "")).strip().lower()
    esleme = {
        "yerel_ssh": BaglantiYontemi.SSH,
        "local": BaglantiYontemi.YEREL,
        "local_ssh": BaglantiYontemi.SSH,
        "ssh": BaglantiYontemi.SSH,
        "ters_ssh": BaglantiYontemi.TERS_SSH,
        "reverse_ssh": BaglantiYontemi.TERS_SSH,
        "tor_ssh": BaglantiYontemi.TOR_SSH,
        "tor_http": BaglantiYontemi.TOR_HTTP,
        "tor_https": BaglantiYontemi.TOR_HTTPS,
        "telegram": BaglantiYontemi.TELEGRAM,
        "adb": BaglantiYontemi.ADB,
        "yerel": BaglantiYontemi.YEREL,
    }
    secim = esleme.get(ham, ham or BaglantiYontemi.SSH.value)
    return getattr(secim, "value", secim)


def _baglanti_legacy_uret(veri: dict) -> Baglanti:
    return Baglanti(
        id=f"{veri.get('id', 'uzuv')}-birincil",
        yontem=_baglanti_yontemi_norm(veri.get("yontem", BaglantiYontemi.SSH)),
        aktif=True,
        yedek=False,
        host=veri.get("ssh_host", "") or veri.get("adb_host", ""),
        port=int(veri.get("ssh_port", 22) or 22),
        kullanici=veri.get("ssh_kullanici", ""),
        anahtar=veri.get("ssh_anahtar", ""),
        token=veri.get("http_token", ""),
        proxy_host=veri.get("tor_proxy_host", "127.0.0.1"),
        proxy_port=int(veri.get("tor_proxy_port", 9050) or 9050),
    )


class UzuvYoneticisi:
    def __init__(self, logcu: Logcu, veri_dosyasi: str):
        self.log = logcu
        self.veri_dosyasi = veri_dosyasi
        self.uzuvlar: dict[str, Uzuv] = {}
        self._durum_dinleyiciler: list[Callable[[str, str], None]] = []
        self._baglanti_isleyiciler: dict[str, Callable[[str, Uzuv, Baglanti, dict], object]] = {}
        # Onion sunucu ayarları (GUI'den değiştirilebilir)
        self.onion_host: str = VARSAYILAN_ONION_HOST
        self.onion_port: int = VARSAYILAN_ONION_PORT
        self.onion_kullanici: str = VARSAYILAN_ONION_KULLANICI
        self._yukle()

    # ── Kayıt / Yükleme ─────────────────────────────────────────────────────

    def _yukle(self):
        if os.path.exists(self.veri_dosyasi):
            try:
                with open(self.veri_dosyasi, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # onion ayarları da kaydedilmiş olabilir
                meta = data.pop("__meta__", {})
                self.onion_host = meta.get("onion_host", VARSAYILAN_ONION_HOST)
                self.onion_port = meta.get("onion_port", VARSAYILAN_ONION_PORT)
                self.onion_kullanici = meta.get("onion_kullanici", VARSAYILAN_ONION_KULLANICI)
                for uid, d in data.items():
                    self.uzuvlar[uid] = Uzuv.from_dict(d)
                    self._baglanti_tutarlilik_kontrol(self.uzuvlar[uid])
                self.log.bilgi(KAYNAK, f"{len(self.uzuvlar)} uzuv yüklendi.")
            except Exception as e:
                self.log.hata(KAYNAK, f"Uzuv verisi yüklenemedi: {e}")

    def kaydet(self):
        os.makedirs(os.path.dirname(self.veri_dosyasi) or ".", exist_ok=True)
        meta = {
            "__meta__": {
                "onion_host": self.onion_host,
                "onion_port": self.onion_port,
                "onion_kullanici": self.onion_kullanici,
            }
        }
        veri = {uid: u.to_dict() for uid, u in self.uzuvlar.items()}
        veri.update(meta)
        with open(self.veri_dosyasi, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)

    def uzuv_ekle(self, uzuv: Uzuv):
        self._baglanti_tutarlilik_kontrol(uzuv)
        self.uzuvlar[uzuv.id] = uzuv
        self.kaydet()
        self.log.bilgi(KAYNAK, f"Uzuv eklendi: {uzuv.ad} ({uzuv.id})")

    def uzuv_guncelle(self, uzuv: Uzuv):
        self._baglanti_tutarlilik_kontrol(uzuv)
        self.uzuvlar[uzuv.id] = uzuv
        self.kaydet()

    def uzuv_sil(self, uid: str):
        self.uzuvlar.pop(uid, None)
        self.kaydet()

    # ── Durum Yönetimi ───────────────────────────────────────────────────────

    def durum_dinleyici_ekle(self, fn: Callable[[str, str], None]):
        self._durum_dinleyiciler.append(fn)

    def baglanti_isleyici_ayarla(self, yontem: str, fn: Callable[[str, Uzuv, Baglanti, dict], object]):
        self._baglanti_isleyiciler[_baglanti_yontemi_norm(yontem)] = fn

    def _durum_bildir(self, uid: str, durum: str):
        if uid in self.uzuvlar:
            self.uzuvlar[uid].durum = durum
        for fn in self._durum_dinleyiciler:
            try:
                fn(uid, durum)
            except Exception:
                pass

    # ── SSH Bağlantı Yardımcıları ────────────────────────────────────────────

    def _ssh_base_args(self, uzuv: Uzuv, baglanti: Baglanti | None = None) -> list[str]:
        bag = baglanti or uzuv.birincil_baglanti()
        args = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            "-p", str(bag.port or uzuv.ssh_port),
        ]
        if bag.yontem == BaglantiYontemi.TOR_SSH:
            args += [
                "-o", f"ProxyCommand=nc -x {bag.proxy_host or uzuv.tor_proxy_host}:{bag.proxy_port or uzuv.tor_proxy_port} %h %p",
            ]
        if bag.anahtar or uzuv.ssh_anahtar:
            args += ["-i", os.path.expanduser(bag.anahtar or uzuv.ssh_anahtar)]
        args.append(f"{bag.kullanici or uzuv.ssh_kullanici}@{bag.host or uzuv.ssh_host}")
        return args

    def _baglanti_sirasi(self, uzuv: Uzuv) -> list[Baglanti]:
        birincil = []
        yedek = []
        for baglanti in uzuv.etkin_baglantilar():
            (yedek if baglanti.yedek else birincil).append(baglanti)
        return birincil + yedek

    def _baglanti_isleyici_cagir(self, eylem: str, uzuv: Uzuv, baglanti: Baglanti, veri: dict) -> object:
        isleyici = self._baglanti_isleyiciler.get(_baglanti_yontemi_norm(baglanti.yontem))
        if not isleyici:
            return None
        try:
            return isleyici(eylem, uzuv, baglanti, veri)
        except Exception as e:
            self.log.uyari(KAYNAK, f"[{uzuv.id}] {baglanti.yontem} özel işleyici hatası: {e}")
            return None

    @staticmethod
    def _http_taban_url(baglanti: Baglanti) -> str:
        host = (baglanti.host or "").strip()
        if not host:
            return ""
        if host.startswith("http://") or host.startswith("https://"):
            return host.rstrip("/")
        sema = "https" if baglanti.yontem == BaglantiYontemi.TOR_HTTPS else "http"
        if baglanti.port:
            return f"{sema}://{host}:{baglanti.port}"
        return f"{sema}://{host}"

    @staticmethod
    def _http_proxy_gerekli_mi(baglanti: Baglanti) -> bool:
        host = (baglanti.host or "").strip().lower()
        if host.startswith("http://") or host.startswith("https://"):
            host = urlparse(host).hostname or host
        return host.endswith(".onion")

    @staticmethod
    def _host_lokal_mi(baglanti: Baglanti) -> bool:
        host = (baglanti.host or "").strip().lower()
        if not host:
            return False
        if host.startswith("http://") or host.startswith("https://"):
            host = urlparse(host).hostname or host
        return host in ("127.0.0.1", "localhost", "::1")

    def _http_istek(self, baglanti: Baglanti, yol: str, method: str = "GET", json_veri: dict | None = None):
        import requests
        url = self._http_taban_url(baglanti)
        if not url:
            return None
        proxies = None
        headers = {}
        if baglanti.token:
            headers["X-ZK-Token"] = baglanti.token
        if self._http_proxy_gerekli_mi(baglanti) and not self._host_lokal_mi(baglanti):
            proxies = {
                "http": f"socks5h://{baglanti.proxy_host}:{baglanti.proxy_port}",
                "https": f"socks5h://{baglanti.proxy_host}:{baglanti.proxy_port}",
            }
        hedef = url.rstrip("/") + "/" + yol.lstrip("/")
        try:
            return requests.request(method=method.upper(), url=hedef,
                                    json=json_veri, proxies=proxies, timeout=20,
                                    headers=headers)
        except Exception as e:
            mesaj = str(e).lower()
            if "missing dependencies for socks support" in mesaj or "pysocks" in mesaj:
                self.log.uyari(KAYNAK, "Tor HTTP için PySocks eksik. 'pip install PySocks' veya './kur.sh --full' çalıştırın.")
                return None
            if "connection refused" in mesaj and proxies:
                self.log.uyari(KAYNAK, f"Tor SOCKS erişilemiyor: {baglanti.proxy_host}:{baglanti.proxy_port}. Tor çalışmıyor olabilir.")
                return None
            raise

    def _baglanti_ping(self, uzuv: Uzuv, baglanti: Baglanti) -> bool:
        ozel = self._baglanti_isleyici_cagir("ping", uzuv, baglanti, {})
        if isinstance(ozel, bool):
            return ozel
        if baglanti.yontem == BaglantiYontemi.ADB:
            return self._adb_ping(uzuv, baglanti)
        if baglanti.yontem in (BaglantiYontemi.TOR_HTTP, BaglantiYontemi.TOR_HTTPS):
            try:
                for yol in ("/health", "/"):
                    r = self._http_istek(baglanti, yol, method="GET")
                    if r is not None and r.status_code < 500:
                        return True
            except Exception as e:
                self.log.uyari(KAYNAK, f"[{uzuv.id}] {baglanti.yontem} http ping başarısız: {e}")
            return False
        if baglanti.yontem == BaglantiYontemi.TELEGRAM:
            return False
        try:
            args = self._ssh_base_args(uzuv, baglanti) + ["echo zk_ok"]
            r = subprocess.run(args, capture_output=True, timeout=15)
            return r.returncode == 0 and b"zk_ok" in r.stdout
        except Exception as e:
            self.log.uyari(KAYNAK, f"[{uzuv.id}] {baglanti.yontem} ping başarısız: {e}")
            return False

    def _baglanti_komut_calistir(self, uzuv: Uzuv, baglanti: Baglanti, komut: str, timeout: int = 30) -> str | None:
        ozel = self._baglanti_isleyici_cagir("komut", uzuv, baglanti, {"komut": komut, "timeout": timeout})
        if isinstance(ozel, str):
            return ozel
        if baglanti.yontem == BaglantiYontemi.ADB:
            sonuc = self._adb_komut(uzuv, komut, baglanti)
            if self._adb_hata_mi(sonuc):
                return None
            return sonuc
        if baglanti.yontem in (BaglantiYontemi.TOR_HTTP, BaglantiYontemi.TOR_HTTPS):
            try:
                r = self._http_istek(
                    baglanti,
                    "/komut",
                    method="POST",
                    json_veri={"komut": komut, "uzuv_id": uzuv.id, "tip": uzuv.tip},
                )
                if r is None or r.status_code >= 400:
                    return None
                try:
                    veri = r.json()
                    return (veri.get("sonuc") or veri.get("output")
                            or veri.get("mesaj") or "✓")
                except Exception:
                    return r.text.strip() or "✓"
            except Exception as e:
                self.log.uyari(KAYNAK, f"[{uzuv.id}] {baglanti.yontem} http komut başarısız: {e}")
                return None
        if baglanti.yontem == BaglantiYontemi.TELEGRAM:
            return None
        komut_gercek = f'powershell -Command "{komut}"' if uzuv.tip == UzuvTipi.WINDOWS else komut
        args = self._ssh_base_args(uzuv, baglanti) + [komut_gercek]
        try:
            r = subprocess.run(args, capture_output=True, timeout=timeout,
                               text=True, errors="replace")
            if r.returncode != 0:
                return None
            cikti = (r.stdout + r.stderr).strip()
            return cikti if cikti else "✓"
        except subprocess.TimeoutExpired:
            return "Zaman aşımı."
        except Exception as e:
            self.log.uyari(KAYNAK, f"[{uzuv.id}] {baglanti.yontem} komut başarısız: {e}")
            return None

    def _baglanti_scp(self, uzuv: Uzuv, baglanti: Baglanti, yerel: str, uzak: str) -> bool:
        ozel = self._baglanti_isleyici_cagir("dosya_gonder", uzuv, baglanti, {"yerel": yerel, "uzak": uzak})
        if isinstance(ozel, bool):
            return ozel
        if baglanti.yontem in (BaglantiYontemi.ADB, BaglantiYontemi.TELEGRAM, BaglantiYontemi.TOR_HTTP, BaglantiYontemi.TOR_HTTPS):
            return False
        args = ["scp", "-P", str(baglanti.port or uzuv.ssh_port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10"]
        if baglanti.yontem == BaglantiYontemi.TOR_SSH:
            args += ["-o", f"ProxyCommand=nc -x {baglanti.proxy_host or uzuv.tor_proxy_host}:{baglanti.proxy_port or uzuv.tor_proxy_port} %h %p"]
        if baglanti.anahtar or uzuv.ssh_anahtar:
            args += ["-i", os.path.expanduser(baglanti.anahtar or uzuv.ssh_anahtar)]
        args += [yerel, f"{baglanti.kullanici or uzuv.ssh_kullanici}@{baglanti.host or uzuv.ssh_host}:{uzak}"]
        try:
            r = subprocess.run(args, capture_output=True, timeout=60)
            return r.returncode == 0
        except Exception as e:
            self.log.uyari(KAYNAK, f"[{uzuv.id}] {baglanti.yontem} dosya gönderimi başarısız: {e}")
            return False

    def _baglanti_dosya_al(self, uzuv: Uzuv, baglanti: Baglanti, uzak: str, yerel: str) -> bool:
        ozel = self._baglanti_isleyici_cagir("dosya_al", uzuv, baglanti, {"yerel": yerel, "uzak": uzak})
        if isinstance(ozel, bool):
            return ozel
        if baglanti.yontem == BaglantiYontemi.ADB:
            try:
                host = baglanti.host or uzuv.adb_host
                port = baglanti.port or uzuv.adb_port
                r = subprocess.run(
                    ["adb", "-H", host, "-P", str(port), "pull", uzak, yerel],
                    capture_output=True, timeout=60, text=True, errors="replace"
                )
                return r.returncode == 0 and os.path.exists(yerel)
            except Exception as e:
                self.log.uyari(KAYNAK, f"[{uzuv.id}] adb dosya alma başarısız: {e}")
                return False
        if baglanti.yontem in (BaglantiYontemi.TELEGRAM, BaglantiYontemi.TOR_HTTP, BaglantiYontemi.TOR_HTTPS):
            return False
        if baglanti.yontem == BaglantiYontemi.YEREL:
            try:
                shutil.copy2(uzak, yerel)
                return os.path.exists(yerel)
            except Exception as e:
                self.log.uyari(KAYNAK, f"[{uzuv.id}] yerel dosya alma başarısız: {e}")
                return False
        args = ["scp", "-P", str(baglanti.port or uzuv.ssh_port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10"]
        if baglanti.yontem == BaglantiYontemi.TOR_SSH:
            args += ["-o", f"ProxyCommand=nc -x {baglanti.proxy_host or uzuv.tor_proxy_host}:{baglanti.proxy_port or uzuv.tor_proxy_port} %h %p"]
        if baglanti.anahtar or uzuv.ssh_anahtar:
            args += ["-i", os.path.expanduser(baglanti.anahtar or uzuv.ssh_anahtar)]
        args += [f"{baglanti.kullanici or uzuv.ssh_kullanici}@{baglanti.host or uzuv.ssh_host}:{uzak}", yerel]
        try:
            r = subprocess.run(args, capture_output=True, timeout=60)
            return r.returncode == 0 and os.path.exists(yerel)
        except Exception as e:
            self.log.uyari(KAYNAK, f"[{uzuv.id}] {baglanti.yontem} dosya alma başarısız: {e}")
            return False

    def ping(self, uid: str) -> bool:
        uzuv = self.uzuvlar.get(uid)
        if not uzuv:
            return False
        self._durum_bildir(uid, UzuvDurum.BAGLANIYOR)
        for baglanti in self._baglanti_sirasi(uzuv):
            ok = self._baglanti_ping(uzuv, baglanti)
            if ok:
                self.log.bilgi(KAYNAK, f"[{uid}] erişim yolu aktif: {baglanti.yontem}")
                self._durum_bildir(uid, UzuvDurum.BAGLI)
                return True
        self._durum_bildir(uid, UzuvDurum.HATA)
        return False

    def ping_arkaplanda(self, uid: str, callback: Callable[[bool], None] | None = None):
        def _do():
            result = self.ping(uid)
            if callback:
                callback(result)
        threading.Thread(target=_do, daemon=True).start()

    def komut_calistir(self, uid: str, komut: str, timeout: int = 30) -> str:
        uzuv = self.uzuvlar.get(uid)
        if not uzuv:
            return "Uzuv bulunamadı."
        self.log.bilgi(KAYNAK, f"[{uid}] → {komut}")
        for baglanti in self._baglanti_sirasi(uzuv):
            sonuc = self._baglanti_komut_calistir(uzuv, baglanti, komut, timeout=timeout)
            if sonuc is not None:
                self.log.bilgi(KAYNAK, f"[{uid}] {baglanti.yontem} ← {sonuc[:200]}")
                return sonuc
        return "Tüm bağlantı yolları başarısız oldu."

    def komut_calistir_arkaplanda(self, uid: str, komut: str,
                                   callback: Callable[[str], None] | None = None):
        def _do():
            sonuc = self.komut_calistir(uid, komut)
            if callback:
                callback(sonuc)
        threading.Thread(target=_do, daemon=True).start()

    def dosya_gonder(self, uid: str, yerel: str, uzak: str) -> bool:
        uzuv = self.uzuvlar.get(uid)
        if not uzuv:
            return False
        for baglanti in self._baglanti_sirasi(uzuv):
            if self._baglanti_scp(uzuv, baglanti, yerel, uzak):
                self.log.bilgi(KAYNAK, f"[{uid}] dosya aktarımı {baglanti.yontem} ile tamamlandı.")
                return True
        return False

    def dosya_al(self, uid: str, uzak: str, yerel: str) -> bool:
        uzuv = self.uzuvlar.get(uid)
        if not uzuv:
            return False
        for baglanti in self._baglanti_sirasi(uzuv):
            if self._baglanti_dosya_al(uzuv, baglanti, uzak, yerel):
                self.log.bilgi(KAYNAK, f"[{uid}] dosya alımı {baglanti.yontem} ile tamamlandı.")
                return True
        return False

    def x11_forward_baslat(self, uid: str, uygulama: str) -> subprocess.Popen | None:
        uzuv = self.uzuvlar.get(uid)
        if not uzuv:
            return None
        for baglanti in self._baglanti_sirasi(uzuv):
            if baglanti.yontem in (BaglantiYontemi.ADB, BaglantiYontemi.TELEGRAM, BaglantiYontemi.TOR_HTTP, BaglantiYontemi.TOR_HTTPS):
                continue
            args = self._ssh_base_args(uzuv, baglanti)
            args.insert(1, "-X")
            args.append(uygulama)
            self.log.bilgi(KAYNAK, f"[{uid}] X11 {baglanti.yontem} → {uygulama}")
            try:
                return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                self.log.uyari(KAYNAK, f"[{uid}] X11 {baglanti.yontem} başarısız: {e}")
        return None

    # ── ADB ──────────────────────────────────────────────────────────────────

    def _adb_ping(self, uzuv: Uzuv, baglanti: Baglanti | None = None) -> bool:
        bag = baglanti or uzuv.birincil_baglanti()
        try:
            host = bag.host or uzuv.adb_host
            port = bag.port or uzuv.adb_port
            r = subprocess.run(["adb", "-H", host, "-P", str(port),
                                 "shell", "echo", "zk_ok"],
                                capture_output=True, timeout=10)
            return b"zk_ok" in r.stdout
        except Exception:
            return False

    def _adb_komut(self, uzuv: Uzuv, komut: str, baglanti: Baglanti | None = None) -> str:
        bag = baglanti or uzuv.birincil_baglanti()
        try:
            host = bag.host or uzuv.adb_host
            port = bag.port or uzuv.adb_port
            r = subprocess.run(
                ["adb", "-H", host, "-P", str(port), "shell", komut],
                capture_output=True, timeout=30, text=True, errors="replace")
            return (r.stdout + r.stderr).strip()
        except Exception as e:
            return f"ADB hata: {e}"

    @staticmethod
    def _adb_hata_mi(sonuc: str) -> bool:
        metin = (sonuc or "").lower()
        kaliplar = [
            "adb hata:",
            "cannot connect to daemon",
            "error: no devices",
            "device offline",
            "cannot start server",
            "failed to connect",
        ]
        return any(kalip in metin for kalip in kaliplar)

    # ── Bilinç ↔ Uzuv ────────────────────────────────────────────────────────

    def bilinc_uzuvlari(self, bilinc: str) -> list[Uzuv]:
        return [u for u in self.uzuvlar.values() if bilinc in u.atanmis_bilincler]

    def uzuva_gore_bilinc_komut(self, bilinc: str, komut: str) -> dict[str, str]:
        sonuclar = {}
        for uzuv in self.bilinc_uzuvlari(bilinc):
            sonuclar[uzuv.id] = self.komut_calistir(uzuv.id, komut)
        return sonuclar

    # ── İstemci Üreteci (Onion sunucu gömülü) ───────────────────────────────

    def istemci_uret(self, uid: str, cikti_klasoru: str) -> str | None:
        uzuv = self.uzuvlar.get(uid)
        if not uzuv:
            return None
        os.makedirs(cikti_klasoru, exist_ok=True)
        dosya_adi = os.path.join(cikti_klasoru, f"zk_istemci_{uzuv.id}.py")

        # Onion bilgileri ya uzuv'dan ya da genel ayardan
        birincil = uzuv.birincil_baglanti()
        onion_host = birincil.host if birincil.yontem == BaglantiYontemi.TOR_SSH and birincil.host else self.onion_host
        onion_port = birincil.port if birincil.yontem == BaglantiYontemi.TOR_SSH and birincil.host else self.onion_port
        onion_user = birincil.kullanici if birincil.kullanici else self.onion_kullanici

        if uzuv.tip == UzuvTipi.ANDROID:
            icerik = self._android_istemci_kodu(uzuv, onion_host, onion_port, onion_user)
        elif uzuv.tip == UzuvTipi.WINDOWS:
            icerik = self._windows_istemci_kodu(uzuv, onion_host, onion_port, onion_user)
        else:
            icerik = self._linux_istemci_kodu(uzuv, onion_host, onion_port, onion_user)

        with open(dosya_adi, "w", encoding="utf-8") as f:
            f.write(icerik)
        self.log.bilgi(KAYNAK, f"İstemci üretildi: {dosya_adi}")
        return dosya_adi

    def _linux_istemci_kodu(self, uzuv: Uzuv, onion_host: str, onion_port: int, onion_user: str) -> str:
        return f'''#!/usr/bin/env python3
"""
Zihin Köprüsü – Linux SSH Ters Tünel İstemcisi
Uzuv ID : {uzuv.id}  |  Hedef: {uzuv.ad}
Otomatik üretilmiştir. Sunucu: {onion_host or "ONION_ADRESI_GIR"}

"""
import subprocess, time

SUNUCU_HOST = "{onion_host or 'ONION_ADRESI_GIR'}"
SUNUCU_PORT = {onion_port}
KULLANICI   = "{onion_user}"
ANAHTAR     = "{uzuv.ssh_anahtar}"
TOR_PROXY   = "127.0.0.1:9050"
YEREL_PORT  = 2222

def baglan():
    args = [
        "ssh", "-N", "-R", f"{{YEREL_PORT}}:localhost:22",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ExitOnForwardFailure=yes",
        "-p", str(SUNUCU_PORT),
        "-o", f"ProxyCommand=nc -x {{TOR_PROXY}} %h %p",
    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{{KULLANICI}}@{{SUNUCU_HOST}}")
    return subprocess.Popen(args)

while True:
    print("[ZK] Bağlanıyor...")
    proc = baglan()
    proc.wait()
    print("[ZK] Bağlantı kesildi, 15 saniye sonra yeniden denenecek.")
    time.sleep(15)
'''

    def _windows_istemci_kodu(self, uzuv: Uzuv, onion_host: str, onion_port: int, onion_user: str) -> str:
        return f'''# Zihin Köprüsü – Windows SSH İstemcisi
# Uzuv: {uzuv.ad} ({uzuv.id})
# Sunucu: {onion_host or "ONION_ADRESI_GIR"}
# Gereksinim: Windows 10+ OpenSSH + Tor
import subprocess, time

SUNUCU_HOST = "{onion_host or 'ONION_ADRESI_GIR'}"
SUNUCU_PORT = {onion_port}
KULLANICI   = "{onion_user}"
ANAHTAR     = r"{uzuv.ssh_anahtar}"
TOR_PROXY   = "127.0.0.1:9050"

def baglan():
    args = [
        "ssh", "-N", "-R", "2222:localhost:22",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-p", str(SUNUCU_PORT),
        "-o", f"ProxyCommand=nc -x {{TOR_PROXY}} %h %p",
    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{{KULLANICI}}@{{SUNUCU_HOST}}")
    return subprocess.Popen(args, creationflags=0x08000000)

while True:
    print("[ZK] Bağlanıyor...")
    proc = baglan()
    proc.wait()
    print("[ZK] Yeniden bağlanıyor...")
    time.sleep(15)
'''

    def _android_istemci_kodu(self, uzuv: Uzuv, onion_host: str, onion_port: int, onion_user: str) -> str:
        return f'''#!/data/data/com.termux/files/usr/bin/python3
"""
Zihin Köprüsü – Android/Termux İstemcisi
Uzuv: {uzuv.ad} ({uzuv.id})  |  Sunucu: {onion_host or "ONION_ADRESI_GIR"}
Root GEREKMEZ. Termux uygulaması yeterlidir.

Kurulum (Termux):
  pkg install python openssh torsocks
  python zk_istemci_{uzuv.id}.py

"""
import subprocess, time

SUNUCU_HOST = "{onion_host or 'ONION_ADRESI_GIR'}"
SUNUCU_PORT = {onion_port}
KULLANICI   = "{onion_user}"
ANAHTAR     = "{uzuv.ssh_anahtar}"
TOR_PROXY   = "127.0.0.1:9050"

def baglan():
    args = [
        "ssh", "-N", "-R", "2222:localhost:8022",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-p", str(SUNUCU_PORT),
        "-o", f"ProxyCommand=nc -x {{TOR_PROXY}} %h %p",
    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{{KULLANICI}}@{{SUNUCU_HOST}}")
    return subprocess.Popen(args)

print("[ZK] Termux SSH istemcisi başlatılıyor...")
while True:
    proc = baglan()
    proc.wait()
    print("[ZK] Yeniden bağlanıyor (15s)...")
    time.sleep(15)
'''

    def _baglanti_tutarlilik_kontrol(self, uzuv: Uzuv):
        baglantilar = uzuv.etkin_baglantilar()
        if not baglantilar:
            self.log.uyari(KAYNAK, f"[{uzuv.id}] etkin bağlantı tanımı yok.")
            return
        normal = [b for b in baglantilar if not b.yedek]
        yedek = [b for b in baglantilar if b.yedek]
        if not normal:
            self.log.uyari(KAYNAK, f"[{uzuv.id}] en az bir birincil bağlantı önerilir.")
        if not yedek:
            self.log.uyari(KAYNAK, f"[{uzuv.id}] en az bir yedek bağlantı önerilir.")
