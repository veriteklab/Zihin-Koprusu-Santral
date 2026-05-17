#!/usr/bin/env python3
"""
Zihin Koprusu Telegram Uzuv Ajani
Uzuv: macOS Telegram Ajan (macos_telegram_ajan)
Hedef: macOS Telegram Ajan
"""
import asyncio
import os
import platform
import re
import shutil
import subprocess
import tempfile

from telethon import TelegramClient, events

UZUV_ID = "macos_telegram_ajan"
UZUV_AD = "macOS Telegram Ajan"
API_ID = 33199989
API_HASH = "9dec76077667601b8b708e74a1d3dbcd"
SESSION = "zk_limb"
CHAT = "7795689621"

TASK_RE = re.compile(r"ZK_TASK\|(?P<gorev_id>[^|]+)\|(?P<uzuv_id>[^|]+)\|(?P<tur>[a-z_]+)")

def _komut_calistir(komut: str) -> tuple[bool, str]:
    try:
        kabuk = komut
        if platform.system().lower().startswith("win"):
            kabuk = f'powershell -Command "{komut}"'
        r = subprocess.run(kabuk, shell=True, capture_output=True, text=True, timeout=60, errors="replace")
        cikti = (r.stdout + r.stderr).strip() or "Komut tamamlandi."
        return r.returncode == 0, cikti[:3000]
    except Exception as exc:
        return False, f"Hata: {exc}"

def _ekran_goruntu_al() -> str:
    if platform.system().lower().startswith("win"):
        fd, gecici = tempfile.mkstemp(prefix="zk_tg_screen_", suffix=".png")
        os.close(fd)
        komut = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$bmp = New-Object System.Drawing.Bitmap "
            "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, "
            "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height; "
            "$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
            "$gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); "
            f"$bmp.Save('{gecici}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$gfx.Dispose(); $bmp.Dispose()"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", komut], capture_output=True, timeout=30)
        return gecici if r.returncode == 0 and os.path.exists(gecici) else ""
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
        fd, gecici = tempfile.mkstemp(prefix="zk_tg_screen_", suffix=".png")
        os.close(fd)
        try:
            r = subprocess.run(list(taban) + [gecici], capture_output=True, timeout=30)
            if r.returncode == 0 and os.path.exists(gecici) and os.path.getsize(gecici) > 0:
                return gecici
        except Exception:
            pass
        try:
            os.unlink(gecici)
        except OSError:
            pass
    return ""

async def main():
    if not API_ID or not API_HASH or not CHAT:
        raise SystemExit("API_ID, API_HASH ve CHAT tanimli olmali.")
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    print(f"[ZK] Telegram ajan basladi | uzuv={UZUV_ID}")

    @client.on(events.NewMessage(chats=CHAT))
    async def handler(event):
        metin = event.raw_text or ""
        es = TASK_RE.search(metin)
        if not es:
            return
        if es.group("uzuv_id") != UZUV_ID:
            return
        gorev_id = es.group("gorev_id")
        tur = es.group("tur")
        if tur == "komut":
            km = re.search(r"Komut:\s*`([^`]+)`", metin)
            if not km:
                return
            ok, sonuc = _komut_calistir(km.group(1))
            durum = "ok" if ok else "hata"
            await client.send_message(CHAT, f"/uzuv_cevap {gorev_id} {durum} {sonuc}")
        elif tur == "ekran":
            yol = _ekran_goruntu_al()
            if yol and os.path.exists(yol):
                try:
                    await client.send_file(CHAT, yol, caption=f"/uzuv_ekran_cevap {gorev_id}")
                finally:
                    try:
                        os.unlink(yol)
                    except OSError:
                        pass
            else:
                await client.send_message(CHAT, f"/uzuv_cevap {gorev_id} hata ekran_alinamadi")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
