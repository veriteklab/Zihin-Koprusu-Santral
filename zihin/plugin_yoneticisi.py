"""
Zihin Köprüsü v6.0 – Plugin Yöneticisi
Yerel eklentiler + uzak plugin mağazası (onion/https sunucudan liste).
Plugin = eklenti slotuna hazır .zip paketi.

"""
from __future__ import annotations

import json
import os
import threading
import zipfile
from dataclasses import dataclass, asdict
from typing import Callable, Optional

from .logcu import Logcu

KAYNAK = "PLUGİN"

# Plugin mağazası URL (HTTPS veya .onion)
MAGAZA_URL = "https://www.exeteknoteam.com/zihin-koprusu/plugins"
MAGAZA_ONION_URL = ""  # .onion adresi bilindiğinde güncellenir


@dataclass
class Plugin:
    id: str
    ad: str
    versiyon: str = "1.0.0"
    aciklama: str = ""
    yazar: str = ""
    kategori: str = "genel"
    url: str = ""           # indirme linki
    yerel_yol: str = ""     # kurulu ise
    aktif: bool = False
    simge: str = "⬡"

    def to_dict(self) -> dict:
        return asdict(self)


class PluginYoneticisi:
    def __init__(self, logcu: Logcu, proje_yolu: str):
        self.log = logcu
        self.proje_yolu = proje_yolu
        self.plugin_dizini = os.path.join(proje_yolu, "pluginler")
        os.makedirs(self.plugin_dizini, exist_ok=True)
        self.pluginler: dict[str, Plugin] = {}
        self._magaza_cache: list[dict] = []
        self._durum_dinleyiciler: list[Callable[[str], None]] = []
        self._yukle()

    def durum_dinleyici_ekle(self, fn: Callable[[str], None]):
        self._durum_dinleyiciler.append(fn)

    def _bildir(self, mesaj: str):
        self.log.bilgi(KAYNAK, mesaj)
        for fn in self._durum_dinleyiciler:
            try: fn(mesaj)
            except Exception: pass

    # ── Disk ─────────────────────────────────────────────────────────────────

    def _yukle(self):
        dosya = os.path.join(self.plugin_dizini, "pluginler.json")
        if os.path.exists(dosya):
            try:
                with open(dosya) as f:
                    data = json.load(f)
                for pid, d in data.items():
                    self.pluginler[pid] = Plugin(**{
                        k: v for k, v in d.items()
                        if k in Plugin.__dataclass_fields__
                    })
            except Exception as e:
                self.log.hata(KAYNAK, f"Plugin yüklenemedi: {e}")

    def kaydet(self):
        dosya = os.path.join(self.plugin_dizini, "pluginler.json")
        with open(dosya, "w") as f:
            json.dump({pid: p.to_dict() for pid, p in self.pluginler.items()},
                      f, ensure_ascii=False, indent=2)

    # ── Mağaza ───────────────────────────────────────────────────────────────

    def magaza_listesi_al(self, tor: bool = False,
                          callback: Optional[Callable[[list], None]] = None):
        """Uzak sunucudan plugin listesini çeker."""
        def _cek():
            url = (MAGAZA_ONION_URL or MAGAZA_URL) + "/liste.json"
            try:
                import requests
                proxies = None
                if tor or url.endswith(".onion"):
                    proxies = {"https": "socks5h://127.0.0.1:9050",
                               "http":  "socks5h://127.0.0.1:9050"}
                r = requests.get(url, proxies=proxies, timeout=15)
                if r.status_code == 200:
                    self._magaza_cache = r.json().get("pluginler", [])
                    self._bildir(f"{len(self._magaza_cache)} plugin listelendi.")
                    if callback:
                        callback(self._magaza_cache)
                    return
            except Exception as e:
                self.log.uyari(KAYNAK, f"Mağaza listesi alınamadı: {e}")
            # Boş liste
            if callback:
                callback(self._magaza_cache)

        threading.Thread(target=_cek, daemon=True).start()

    def plugin_indir(self, plugin: Plugin, hedef_slot: str,
                     callback: Optional[Callable[[bool], None]] = None):
        """Plugini indir ve slota kur."""
        def _indir():
            try:
                import requests
                proxies = None
                if plugin.url and ".onion" in plugin.url:
                    proxies = {"https": "socks5h://127.0.0.1:9050",
                               "http":  "socks5h://127.0.0.1:9050"}
                r = requests.get(plugin.url, proxies=proxies, timeout=60, stream=True)
                if r.status_code != 200:
                    raise Exception(f"HTTP {r.status_code}")

                zip_dosya = os.path.join(self.plugin_dizini, f"{plugin.id}.zip")
                with open(zip_dosya, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)

                # Zip'i slota aç
                with zipfile.ZipFile(zip_dosya) as z:
                    z.extractall(hedef_slot)
                os.remove(zip_dosya)

                plugin.yerel_yol = hedef_slot
                plugin.aktif = True
                self.pluginler[plugin.id] = plugin
                self.kaydet()
                self._bildir(f"Plugin kuruldu: {plugin.ad}")
                if callback: callback(True)
            except Exception as e:
                self.log.hata(KAYNAK, f"Plugin indirme hatası: {e}")
                if callback: callback(False)

        threading.Thread(target=_indir, daemon=True).start()

    # ── Yerel Plugin Yönetimi ─────────────────────────────────────────────────

    def plugin_kaldir(self, pid: str):
        p = self.pluginler.pop(pid, None)
        if p and p.yerel_yol and os.path.isdir(p.yerel_yol):
            import shutil
            shutil.rmtree(p.yerel_yol, ignore_errors=True)
        self.kaydet()
        self._bildir(f"Plugin kaldırıldı: {pid}")

    def plugin_guncelle(self, pid: str, callback=None):
        p = self.pluginler.get(pid)
        if p and p.url:
            self.plugin_indir(p, p.yerel_yol, callback)

    def yerel_pluginler(self) -> list[Plugin]:
        return list(self.pluginler.values())

    def magaza_cache(self) -> list[dict]:
        return self._magaza_cache
