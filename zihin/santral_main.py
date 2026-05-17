from __future__ import annotations

import argparse
import json
from pathlib import Path

from .santral import SantralAyar, SantralSunucu
from .santral.adb_ajan import ADBAjanAyar, ADBSantralAjan


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="zk-santral")
    p.add_argument("--config", default="santral_ayar.json", help="Santral ayar dosyasi")
    sp = p.add_subparsers(dest="komut", required=True)

    sp.add_parser("serve", help="Santral HTTP sunucusunu baslat")

    adb = sp.add_parser("adb-poller", help="ADB uzerinden telefon cagrilarini izle")
    adb.add_argument("--server-url", default="http://127.0.0.1:8767")
    adb.add_argument("--token", default="")
    adb.add_argument("--device-id", default="j2-prime")
    adb.add_argument("--adb-serial", default="")
    adb.add_argument("--poll-sec", type=float, default=1.0)
    adb.add_argument("--no-auto-answer", action="store_true")
    adb.add_argument("--no-auto-prompt", action="store_true")
    adb.add_argument("--healthcheck", action="store_true")

    tts = sp.add_parser("tts", help="TTS ile anons uret")
    tts.add_argument("--text", required=True, help="Anons metni")
    tts.add_argument("--filename", default="anons.wav", help="Hedef dosya adi")

    show = sp.add_parser("show-config", help="Yuklenen config'i yazdir")
    show.add_argument("--pretty", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _args()
    ayar = SantralAyar.yukle(args.config)
    if args.komut == "serve":
        SantralSunucu(ayar).serve_forever()
        return 0
    if args.komut == "adb-poller":
        ajan = ADBSantralAjan(
            ADBAjanAyar(
                server_url=args.server_url,
                token=args.token or ayar.sunucu.erisim_tokeni,
                device_id=args.device_id,
                adb_serial=args.adb_serial,
                poll_sec=args.poll_sec,
                auto_answer=not args.no_auto_answer,
                auto_prompt=not args.no_auto_prompt,
            )
        )
        if args.healthcheck:
            ajan.healthcheck()
            return 0
        ajan.run_forever()
        return 0
    if args.komut == "tts":
        sonuc = SantralSunucu(ayar).tts_isle(args.text, args.filename)
        print(sonuc["path"])
        return 0
    if args.komut == "show-config":
        veri = {
            "cihaz_adi": ayar.cihaz_adi,
            "sunucu": ayar.sunucu.__dict__,
            "telegram": ayar.telegram.__dict__,
            "stt": ayar.stt.__dict__,
            "tts": ayar.tts.__dict__,
            "davranis": ayar.davranis.__dict__,
            "depo": ayar.depo.__dict__,
        }
        print(json.dumps(veri, ensure_ascii=False, indent=2 if args.pretty else None))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
