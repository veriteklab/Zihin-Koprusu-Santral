"""
Zihin Köprüsü v7.0 – Yedek Yöneticisi  (TAM SÜRÜM)

Özellikler:
  - Tüm ayar, komut, uzuv, eklenti, dil dosyalarını .zip yedekler
  - Hassas dosyalar (token, API) opsiyonel
  - Geri yüklemede önce mevcut durum otomatik yedeklenir
  - Seçili dosyaları VEYA tümünü geri yükle
  - Her dosyanın .bak kopyası bırakılır (tekrar geri alınabilir)
  - Meta bilgisi (_meta.json): tarih, sürüm, hassas mı, dosya listesi
  - Thread güvenli, callback destekli

Yedeklenen dosyalar:
  beyin.yaml, komutlar.json, uzuvlar.json,
  hitap_ayar.json, dil/tr.json, web/index.html,
  pluginler/pluginler.json,
  eklentiler/slot_NN/*.py

  Hassas (opsiyonel):
  ai_ayar.json, telegram_ayar.json

"""
from __future__ import annotations

import json
import os
import shutil
import threading
import zipfile
from datetime import datetime
from typing import Callable, Optional

from .logcu import Logcu

KAYNAK = "YEDEK"
SURUM  = "7.0.0"

NORMAL_DOSYALAR = [
    "beyin.yaml",
    "komutlar.json",
    "makrolar.json",
    "uzuvlar.json",
    "hitap_ayar.json",
    "dil/tr.json",
    "web/index.html",
    "pluginler/pluginler.json",
]

HASSAS_DOSYALAR = [
    "ai_ayar.json",
    "telegram_ayar.json",
]

SLOT_SAYISI = 10


class YedekYoneticisi:
    def __init__(self, logcu: Logcu, proje_yolu: str):
        self.log = logcu
        self.proje_yolu = proje_yolu
        self.yedek_dizini = os.path.join(proje_yolu, "yedekler")
        os.makedirs(self.yedek_dizini, exist_ok=True)
        self._durum_dinleyiciler: list[Callable[[str], None]] = []

    # ── Dinleyiciler ─────────────────────────────────────────────────────────

    def durum_dinleyici_ekle(self, fn: Callable[[str], None]):
        if fn not in self._durum_dinleyiciler:
            self._durum_dinleyiciler.append(fn)

    def _bildir(self, mesaj: str):
        self.log.bilgi(KAYNAK, mesaj)
        for fn in self._durum_dinleyiciler:
            try:
                fn(mesaj)
            except Exception:
                pass

    # ── Yedek Al ─────────────────────────────────────────────────────────────

    def yedek_al(self,
                 hassas_dahil: bool = False,
                 callback: Optional[Callable[[bool, str], None]] = None):
        threading.Thread(
            target=self._yedek_al_thread,
            args=(hassas_dahil, callback),
            daemon=True
        ).start()

    def _yedek_al_thread(self, hassas_dahil: bool,
                          callback: Optional[Callable]):
        try:
            zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
            etiket = "_hassas" if hassas_dahil else ""
            dosya_adi = f"ZK_yedek_{zaman}{etiket}.zip"
            tam_yol = os.path.join(self.yedek_dizini, dosya_adi)

            dosyalar = list(NORMAL_DOSYALAR)
            if hassas_dahil:
                dosyalar += HASSAS_DOSYALAR

            # Eklenti slotları
            for i in range(1, SLOT_SAYISI + 1):
                slot = f"eklentiler/slot_{i:02d}"
                slot_tam = os.path.join(self.proje_yolu, slot)
                if os.path.isdir(slot_tam):
                    for f in os.listdir(slot_tam):
                        if f.endswith(".py"):
                            dosyalar.append(f"{slot}/{f}")

            eklenen = []
            with zipfile.ZipFile(tam_yol, "w",
                                  compression=zipfile.ZIP_DEFLATED) as zf:
                meta = {
                    "tarih":      datetime.now().isoformat(),
                    "surum":      SURUM,
                    "hassas":     hassas_dahil,
                    "hassas_dahil": hassas_dahil,   # eski uyumluluk
                    "dosyalar":   [],
                }
                for goreli in dosyalar:
                    tam = os.path.join(self.proje_yolu, goreli)
                    if os.path.isfile(tam):
                        zf.write(tam, goreli)
                        eklenen.append(goreli)
                        self._bildir(f"Ekleniyor: {goreli}")
                meta["dosyalar"] = eklenen
                zf.writestr("_meta.json",
                            json.dumps(meta, ensure_ascii=False, indent=2))

            boyut_kb = os.path.getsize(tam_yol) // 1024
            mesaj = (f"{dosya_adi} hazır — "
                     f"{len(eklenen)} dosya, {boyut_kb} KB.")
            self._bildir(mesaj)
            if callback:
                callback(True, mesaj)

        except Exception as e:
            self.log.hata(KAYNAK, f"Yedek hatası: {e}")
            if callback:
                callback(False, str(e))

    # ── Yedek Listesi ─────────────────────────────────────────────────────────

    def yedek_listesi(self) -> list[dict]:
        sonuc = []
        if not os.path.isdir(self.yedek_dizini):
            return sonuc
        for f in sorted(os.listdir(self.yedek_dizini), reverse=True):
            if not f.endswith(".zip"):
                continue
            tam = os.path.join(self.yedek_dizini, f)
            boyut_kb = os.path.getsize(tam) // 1024
            tarih = surum = "?"
            hassas = False
            try:
                with zipfile.ZipFile(tam, "r") as zf:
                    if "_meta.json" in zf.namelist():
                        meta = json.loads(zf.read("_meta.json"))
                        tarih  = meta.get("tarih", "?")
                        surum  = meta.get("surum", "?")
                        hassas = meta.get("hassas",
                                  meta.get("hassas_dahil", False))
            except Exception:
                pass
            sonuc.append({
                "dosya":    f,
                "tam_yol":  tam,
                "boyut_kb": boyut_kb,
                "tarih":    tarih,
                "surum":    surum,
                "hassas":   hassas,
            })
        return sonuc

    # ── Yedek İçeriği ────────────────────────────────────────────────────────

    def yedek_icerigi(self, yedek_yolu: str) -> list[str]:
        try:
            with zipfile.ZipFile(yedek_yolu, "r") as zf:
                return zf.namelist()
        except Exception as e:
            self.log.hata(KAYNAK, f"İçerik okunamadı: {e}")
            return []

    # ── Yedek Sil ────────────────────────────────────────────────────────────

    def yedek_sil(self, yedek_yolu: str) -> bool:
        try:
            if not self._yedek_dizini_icinde_mi(yedek_yolu):
                raise ValueError("Yedek klasörü dışındaki dosya silinemez.")
            os.remove(yedek_yolu)
            self._bildir(f"Silindi: {os.path.basename(yedek_yolu)}")
            return True
        except Exception as e:
            self.log.hata(KAYNAK, f"Silme hatası: {e}")
            return False

    # ── Geri Yükle ───────────────────────────────────────────────────────────

    def geri_yukle(self,
                   yedek_yolu: str,
                   secili_dosyalar: Optional[list[str]] = None,
                   callback: Optional[Callable[[bool, str], None]] = None):
        threading.Thread(
            target=self._geri_yukle_thread,
            args=(yedek_yolu, secili_dosyalar, callback),
            daemon=True
        ).start()

    def _geri_yukle_thread(self,
                            yedek_yolu: str,
                            secili_dosyalar: Optional[list[str]],
                            callback: Optional[Callable]):
        try:
            # Önce mevcut durumu otomatik yedekle
            self._bildir("Güvenlik yedeği alınıyor...")
            self._yedek_al_thread(hassas_dahil=True, callback=None)

            yuklenen = []
            with zipfile.ZipFile(yedek_yolu, "r") as zf:
                tum = [n for n in zf.namelist()
                       if n != "_meta.json" and not n.endswith("/")]
                hedefler = tum if not secili_dosyalar else [
                    f for f in tum if f in secili_dosyalar
                ]
                for goreli in hedefler:
                    hedef = self._guvenli_hedef_yolu(goreli)
                    os.makedirs(os.path.dirname(hedef), exist_ok=True)
                    # Mevcut dosyayı .bak olarak sakla
                    if os.path.isfile(hedef):
                        shutil.copy2(hedef, hedef + ".bak")
                    with zf.open(goreli) as src, open(hedef, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    yuklenen.append(goreli)
                    self._bildir(f"Geri yüklendi: {goreli}")

            mesaj = (f"{len(yuklenen)} dosya geri yüklendi. "
                     "Yeniden başlatın.")
            self._bildir(mesaj)
            if callback:
                callback(True, mesaj)

        except Exception as e:
            self.log.hata(KAYNAK, f"Geri yükleme hatası: {e}")
            if callback:
                callback(False, str(e))

    def _guvenli_hedef_yolu(self, goreli: str) -> str:
        if os.path.isabs(goreli):
            raise ValueError(f"Geçersiz yedek yolu: {goreli}")
        kok = os.path.abspath(self.proje_yolu)
        hedef = os.path.abspath(os.path.join(kok, goreli))
        if os.path.commonpath([kok, hedef]) != kok:
            raise ValueError(f"Proje dışına yazma engellendi: {goreli}")
        return hedef

    def _yedek_dizini_icinde_mi(self, yol: str) -> bool:
        kok = os.path.abspath(self.yedek_dizini)
        hedef = os.path.abspath(yol)
        return os.path.commonpath([kok, hedef]) == kok
