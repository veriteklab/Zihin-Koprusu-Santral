#!/usr/bin/env python3
"""
Uzuv istemci stub uretim CLI.

GUI acmadan Linux, Windows veya Android istemci dosyalari uretir.
"""
from __future__ import annotations

import argparse
import pathlib

from zihin.istemci_uretici import IstemciAyar, IstemciUretici
from zihin.logcu import Logcu


KOK = pathlib.Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Zihin Koprusu uzuv istemci dosyasi uret")
    p.add_argument("--id", required=True, help="Uzuv kimligi, ornek: laptop_01")
    p.add_argument("--ad", default="", help="Gorunen uzuv adi")
    p.add_argument("--tip", choices=["linux", "windows", "android", "mac"], default="linux")
    p.add_argument("--baglanti-modu", choices=["ssh_reverse", "tor_http", "tor_https", "telegram_agent"], default="ssh_reverse")
    p.add_argument("--onion", default="", help="Sunucu onion adresi")
    p.add_argument("--port", type=int, default=22, help="Sunucu SSH portu")
    p.add_argument("--kullanici", default="zihin", help="SSH kullanicisi")
    p.add_argument("--anahtar", default="", help="SSH anahtar yolu")
    p.add_argument("--bildirim-url", default="", help="Web bildirim URL")
    p.add_argument("--http-host", default="0.0.0.0", help="HTTP ajan dinleme hostu")
    p.add_argument("--http-port", type=int, default=8787, help="HTTP ajan dinleme portu")
    p.add_argument("--http-token", default="", help="HTTP ajan X-ZK-Token degeri")
    p.add_argument("--telegram-api-id", default="", help="Telegram API ID")
    p.add_argument("--telegram-api-hash", default="", help="Telegram API hash")
    p.add_argument("--telegram-session", default="zk_limb", help="Telegram session adi")
    p.add_argument("--telegram-chat", default="", help="Telegram chat id veya kullanici adi")
    p.add_argument("--windows-format", default="", help="Python + .bat | Yalnizca .bat | C++")
    p.add_argument("--android-format", default="", help="Termux | APK")
    p.add_argument("--cikti", default=str(KOK / "yedekler" / "uzuv_stublari"), help="Cikti klasoru")
    return p.parse_args()


def main() -> int:
    ns = parse_args()
    ayar = IstemciAyar(
        uzuv_id=ns.id,
        uzuv_ad=ns.ad or ns.id,
        uzuv_tip=ns.tip,
        baglanti_modu=ns.baglanti_modu,
        onion_host=ns.onion,
        onion_port=ns.port,
        ssh_kullanici=ns.kullanici,
        ssh_anahtar=ns.anahtar,
        bildirim_url=ns.bildirim_url,
        http_host=ns.http_host,
        http_port=ns.http_port,
        http_token=ns.http_token,
        telegram_api_id=ns.telegram_api_id,
        telegram_api_hash=ns.telegram_api_hash,
        telegram_session=ns.telegram_session,
        telegram_chat=ns.telegram_chat,
        windows_format=ns.windows_format,
        android_format=ns.android_format,
    )
    log = Logcu(str(KOK / "loglar" / "uzuv_stub_uret.log"))
    uretici = IstemciUretici(log)
    hedef = pathlib.Path(ns.cikti).resolve() / ayar.uzuv_id
    dosyalar = uretici.uret(ayar, str(hedef))
    if not dosyalar:
        print("HATA: dosya uretilemedi")
        return 1
    print("Uretilen dosyalar:")
    for dosya in dosyalar:
        print(pathlib.Path(dosya).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
