#!/usr/bin/env python3
"""
Zihin Köprüsü İstemcisi — Windows Python Ajan (windows_python_ajan)
Hedef : Windows 10/11
Gereksinim: Python 3.10+ , OpenSSH (Windows özellik olarak), Tor Browser veya Expert Bundle

Merkez: avlihkczlpvz7cd423a3ydmoemkyeviw6xcya4zcxlqa43biaiaftqyd.onion:22
Bu dosya otomatik üretilmiştir.
"""
import subprocess, time, os, sys, socket, json, shutil

SUNUCU_HOST  = "avlihkczlpvz7cd423a3ydmoemkyeviw6xcya4zcxlqa43biaiaftqyd.onion"
SUNUCU_PORT  = 22
KULLANICI    = "zihin"
ANAHTAR      = r""
TOR_PROXY    = "127.0.0.1:9050"
YEREL_PORT   = 2222
BILDIRIM_URL = ""
UZUV_ID      = "windows_python_ajan"
UZUV_AD      = "Windows Python Ajan"

def tor_calisiyor_mu() -> bool:
    try:
        import socket as _s
        s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 9050))
        s.close()
        return True
    except Exception:
        return False


def hazir_bildir():
    if not BILDIRIM_URL:
        return
    try:
        import urllib.request
        veri = json.dumps({
            "olay": "hazir", "uzuv_id": UZUV_ID,
            "uzuv_ad": UZUV_AD, "host": socket.gethostname(),
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
        }).encode("utf-8")
        req = urllib.request.Request(
            BILDIRIM_URL.rstrip("/") + "/uzuv_bildir",
            data=veri,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=15)
        print("[ZK] Sunucuya hazirım bildirimi gönderildi.")
    except Exception as e:
        print(f"[ZK] Bildirim hatası: {e}")

def baglan() -> subprocess.Popen:
    nc_cmd = "nc"
    if TOR_PROXY:
        for candidate in ["nc", "ncat"]:
            if shutil.which(candidate):
                nc_cmd = candidate
                break

    args = [
        "ssh", "-N", "-R", f"{YEREL_PORT}:localhost:22",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-p", str(SUNUCU_PORT),
        "-o", f"ProxyCommand={nc_cmd} -x {TOR_PROXY} %h %p",
    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{KULLANICI}@{SUNUCU_HOST}")
    return subprocess.Popen(args, creationflags=0x08000000)

def main():
    print(f"[ZK] Windows istemcisi başlıyor — {UZUV_AD}")
    if not tor_calisiyor_mu():
        print("[ZK] UYARI: Tor çalışmıyor. Lütfen Tor Browser veya Expert Bundle başlatın.")
        print("[ZK]        İndirme: https://www.torproject.org/download/tor/")
        time.sleep(10)


    bildirim_gonderildi = False
    while True:
        print("[ZK] Bağlanıyor...")
        proc = baglan()
        if not bildirim_gonderildi:
            time.sleep(3)
            hazir_bildir()
            bildirim_gonderildi = True
        proc.wait()
        print("[ZK] Yeniden bağlanıyor (15s)...")
        time.sleep(15)

if __name__ == "__main__":
    main()
