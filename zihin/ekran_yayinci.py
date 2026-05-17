"""
Zihin Köprüsü v7.0 – Ekran Yayıncısı

Uzuv cihazların ekranını GUI'de gösterir ve kontrol eder.

Desteklenen modlar:
  - scrcpy   → Android cihaz (USB veya WiFi, root gerekmez)
  - VNC      → Linux / Windows masaüstü (TigerVNC / TightVNC)
  - SSH X11  → Linux uzak masaüstü uygulamaları

Özellikler:
  - Gerçek zamanlı ekran yayını
  - Klavye + fare girişi yayını
  - Birden fazla cihaz aynı anda
  - Kayıt (ffmpeg ile)
  - GUI'de açılır/kapanır panel
  - Sesli komutla ekrana bak: "ev bilgisayarının ekranını aç"

"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .logcu import Logcu

KAYNAK = "EKRAN"


class YayinMod(str, Enum):
    SCRCPY   = "scrcpy"
    VNC      = "vnc"
    SSH_X11  = "ssh_x11"


@dataclass
class EkranYayinAyar:
    uzuv_id:    str = ""
    uzuv_ad:    str = ""
    mod:        YayinMod = YayinMod.SCRCPY
    host:       str = ""
    port:       int = 5900        # VNC default
    sifre:      str = ""
    ssh_host:   str = ""
    ssh_port:   int = 22
    ssh_kullanici: str = ""
    ssh_anahtar: str = ""
    tor_proxy:  str = "127.0.0.1:9050"
    kullan_tor: bool = False
    cozunurluk: str = "1280x720"  # scrcpy için
    bit_hizi:   int = 4000000     # scrcpy bps
    fps:        int = 30
    kayit_yap:  bool = False
    kayit_dosya: str = "/tmp/zk_kayit.mp4"
    salt_okunur: bool = False     # Sadece izle, kontrol etme


class EkranYayincisi:
    def __init__(self, logcu: Logcu):
        self.log = logcu
        self._prosesler: dict[str, subprocess.Popen] = {}
        self._ayarlar:   dict[str, EkranYayinAyar]   = {}
        self._durum_dinleyiciler: list[Callable[[str, str], None]] = []
        self._scrcpy_var  = shutil.which("scrcpy") is not None
        self._vncviewer_var = (shutil.which("vncviewer") is not None or
                               shutil.which("tigervnc") is not None or
                               shutil.which("xtigervncviewer") is not None)
        self._ffmpeg_var  = shutil.which("ffmpeg") is not None

    # ── Dinleyiciler ─────────────────────────────────────────────────────────

    def durum_dinleyici_ekle(self, fn: Callable[[str, str], None]):
        self._durum_dinleyiciler.append(fn)

    def _bildir(self, uzuv_id: str, mesaj: str):
        self.log.bilgi(KAYNAK, f"[{uzuv_id}] {mesaj}")
        for fn in self._durum_dinleyiciler:
            try:
                fn(uzuv_id, mesaj)
            except Exception:
                pass

    # ── Başlat ───────────────────────────────────────────────────────────────

    def baslat(self, ayar: EkranYayinAyar) -> bool:
        """Ekran yayınını başlat."""
        uid = ayar.uzuv_id or ayar.uzuv_ad or "uzuv"

        if uid in self._prosesler:
            if self._prosesler[uid].poll() is None:
                self._bildir(uid, "Zaten çalışıyor.")
                return True
            else:
                del self._prosesler[uid]

        self._ayarlar[uid] = ayar

        if ayar.mod == YayinMod.SCRCPY:
            return self._scrcpy_baslat(uid, ayar)
        elif ayar.mod == YayinMod.VNC:
            return self._vnc_baslat(uid, ayar)
        elif ayar.mod == YayinMod.SSH_X11:
            return self._ssh_x11_baslat(uid, ayar)
        else:
            self.log.hata(KAYNAK, f"Bilinmeyen mod: {ayar.mod}")
            return False

    def durdur(self, uzuv_id: str):
        """Ekran yayınını durdur."""
        for anahtar in (uzuv_id, f"{uzuv_id}_tunel"):
            proc = self._prosesler.get(anahtar)
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                del self._prosesler[anahtar]
        self._bildir(uzuv_id, "Yayın durduruldu.")

    def tumu_durdur(self):
        for uid in list(self._prosesler.keys()):
            self.durdur(uid)

    def calisiyor_mu(self, uzuv_id: str) -> bool:
        proc = self._prosesler.get(uzuv_id)
        return proc is not None and proc.poll() is None

    # ── scrcpy (Android) ─────────────────────────────────────────────────────

    def _scrcpy_baslat(self, uid: str, ayar: EkranYayinAyar) -> bool:
        if not self._scrcpy_var:
            self.log.uyari(KAYNAK,
                "scrcpy kurulu değil: sudo apt install scrcpy")
            return False

        args = ["scrcpy"]

        # Uzak cihaz mı (WiFi ADB) yoksa USB mi?
        if ayar.host:
            # WiFi ADB bağlantısı
            args += ["--serial", f"{ayar.host}:{ayar.port or 5555}"]

        # Çözünürlük
        if ayar.cozunurluk and ayar.cozunurluk != "tam":
            maks = ayar.cozunurluk.split("x")[1] if "x" in ayar.cozunurluk else "720"
            args += ["--max-size", maks]

        # Bit hızı
        args += ["--video-bit-rate", str(ayar.bit_hizi)]

        # FPS
        args += ["--max-fps", str(ayar.fps)]

        # Salt okunur
        if ayar.salt_okunur:
            args.append("--no-control")

        # Başlık
        args += ["--window-title",
                 f"ZK | {ayar.uzuv_ad} | Android"]

        # Kayıt
        if ayar.kayit_yap and self._ffmpeg_var:
            args += ["--record", ayar.kayit_dosya]

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._prosesler[uid] = proc
            self._bildir(uid, f"scrcpy başladı: {' '.join(args)}")

            # İzleme thread'i
            threading.Thread(
                target=self._proses_izle,
                args=(uid, proc),
                daemon=True
            ).start()
            return True
        except FileNotFoundError:
            self.log.hata(KAYNAK, "scrcpy bulunamadı.")
            return False
        except Exception as e:
            self.log.hata(KAYNAK, f"scrcpy hatası: {e}")
            return False

    # ── VNC (Linux/Windows) ──────────────────────────────────────────────────

    def _vnc_baslat(self, uid: str, ayar: EkranYayinAyar) -> bool:
        """VNC viewer başlat."""
        # VNC viewer bul
        viewer = None
        for kandidat in ["vncviewer", "xtigervncviewer",
                          "tigervnc", "gvncviewer", "remmina"]:
            if shutil.which(kandidat):
                viewer = kandidat
                break

        if not viewer:
            self.log.uyari(KAYNAK,
                "VNC viewer kurulu değil: sudo apt install tigervnc-viewer")
            return False

        host = ayar.host or "localhost"
        port = ayar.port or 5900
        display_num = (port - 5900) if port >= 5900 else 0

        # Tor proxy üzerinden SSH tüneli
        if ayar.kullan_tor and ayar.ssh_host:
            tunnel_ok = self._tor_ssh_tunel_ac(uid, ayar, port)
            if tunnel_ok:
                host = "127.0.0.1"
            else:
                return False
        elif ayar.ssh_host:
            tunnel_ok = self._ssh_tunel_ac(uid, ayar, port)
            if tunnel_ok:
                host = "127.0.0.1"

        args = [viewer]

        if viewer == "remmina":
            args += ["-c", f"vnc://{host}:{port}"]
        else:
            # TigerVNC / standard vncviewer
            if ayar.sifre:
                # Şifreyi geçici dosyaya yaz
                sifre_dosya = f"/tmp/zk_vnc_{uid}.pwd"
                try:
                    with open(sifre_dosya, "wb") as _sfd:
                        subprocess.run(
                            ["vncpasswd", "-f"],
                            input=ayar.sifre.encode(),
                            stdout=_sfd,
                            check=True
                        )
                    args += [f"-passwd={sifre_dosya}"]
                except Exception:
                    args += [f"-password={ayar.sifre}"]

            args += [
                "-SecurityTypes", "None,VncAuth",
                f"{host}:{display_num}",
            ]

        if ayar.salt_okunur:
            args.append("-ViewOnly")

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._prosesler[uid] = proc
            self._bildir(uid, f"VNC başladı: {host}:{port}")
            threading.Thread(
                target=self._proses_izle,
                args=(uid, proc),
                daemon=True
            ).start()
            return True
        except Exception as e:
            self.log.hata(KAYNAK, f"VNC hatası: {e}")
            return False

    # ── SSH X11 Forwarding ───────────────────────────────────────────────────

    def _ssh_x11_baslat(self, uid: str, ayar: EkranYayinAyar) -> bool:
        """SSH X11 forwarding ile uzak masaüstü uygulaması başlat."""
        args = [
            "ssh", "-X",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-p", str(ayar.ssh_port),
        ]

        if ayar.kullan_tor:
            args += ["-o",
                     f"ProxyCommand=nc -x {ayar.tor_proxy} %h %p"]

        if ayar.ssh_anahtar:
            args += ["-i", os.path.expanduser(ayar.ssh_anahtar)]

        args.append(f"{ayar.ssh_kullanici}@{ayar.ssh_host}")

        # Uzak masaüstü ortamına göre komut
        uzak_cmd = "DISPLAY=:0 x11vnc -forever -shared -nopw &; vncviewer localhost:5900"
        args.append(uzak_cmd)

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._prosesler[uid] = proc
            self._bildir(uid, f"SSH X11 başladı: {ayar.ssh_host}")
            threading.Thread(
                target=self._proses_izle,
                args=(uid, proc),
                daemon=True
            ).start()
            return True
        except Exception as e:
            self.log.hata(KAYNAK, f"SSH X11 hatası: {e}")
            return False

    # ── SSH Tünel ────────────────────────────────────────────────────────────

    def _ssh_tunel_ac(self, uid: str, ayar: EkranYayinAyar,
                       uzak_port: int) -> bool:
        """VNC için SSH tüneli açar."""
        yerel_port = 15900 + hash(uid) % 100
        args = [
            "ssh", "-N", "-L",
            f"{yerel_port}:localhost:{uzak_port}",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-p", str(ayar.ssh_port),
        ]
        if ayar.ssh_anahtar:
            args += ["-i", os.path.expanduser(ayar.ssh_anahtar)]
        args.append(f"{ayar.ssh_kullanici}@{ayar.ssh_host}")

        try:
            proc = subprocess.Popen(args,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._prosesler[f"{uid}_tunel"] = proc
            time.sleep(2)  # Tünel kurulsun
            return proc.poll() is None
        except Exception as e:
            self.log.hata(KAYNAK, f"SSH tünel hatası: {e}")
            return False

    def _tor_ssh_tunel_ac(self, uid: str, ayar: EkranYayinAyar,
                           uzak_port: int) -> bool:
        """Tor üzerinden SSH tüneli."""
        yerel_port = 15900 + hash(uid) % 100
        args = [
            "ssh", "-N", "-L",
            f"{yerel_port}:localhost:{uzak_port}",
            "-o", "StrictHostKeyChecking=no",
            "-o", f"ProxyCommand=nc -x {ayar.tor_proxy} %h %p",
            "-o", "ConnectTimeout=20",
            "-p", str(ayar.ssh_port),
        ]
        if ayar.ssh_anahtar:
            args += ["-i", os.path.expanduser(ayar.ssh_anahtar)]
        args.append(f"{ayar.ssh_kullanici}@{ayar.ssh_host}")

        try:
            proc = subprocess.Popen(args,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._prosesler[f"{uid}_tunel"] = proc
            time.sleep(3)
            return proc.poll() is None
        except Exception as e:
            self.log.hata(KAYNAK, f"Tor SSH tünel hatası: {e}")
            return False

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    def _proses_izle(self, uid: str, proc: subprocess.Popen):
        """Proses bitince bildir."""
        proc.wait()
        if uid in self._prosesler:
            del self._prosesler[uid]
        self._bildir(uid, "Yayın sona erdi.")

    def durum_listesi(self) -> list[dict]:
        """Tüm aktif yayınların durumunu döner."""
        sonuc = []
        for uid, proc in self._prosesler.items():
            if "_tunel" in uid:
                continue
            ayar = self._ayarlar.get(uid)
            sonuc.append({
                "uzuv_id":  uid,
                "uzuv_ad":  ayar.uzuv_ad if ayar else uid,
                "mod":      ayar.mod.value if ayar else "?",
                "calisiyor": proc.poll() is None,
            })
        return sonuc

    def gereksinim_kontrol(self) -> dict:
        return {
            "scrcpy":    self._scrcpy_var,
            "vncviewer": self._vncviewer_var,
            "ffmpeg":    self._ffmpeg_var,
            "xdotool":   shutil.which("xdotool") is not None,
            "adb":       shutil.which("adb") is not None,
        }
