"""
Zihin Köprüsü v6.0 – Telegram Bot Modülü  (DÜZELTİLMİŞ v2)

Düzeltmeler v2:
  - _komut_isleyici artık kanal="telegram" ile çağrılıyor (cekirdek.py tarafından)
    Bu sayede cekirdek echo loop yaratmıyor.
  - Yazı mesajı → yalnızca yazı yanıtı (sesli=False)
  - Sesli mesaj → sesli + yazı yanıtı (sesli=True) — gTTS ile ses dosyası üretilip
    Telegram'a voice olarak gönderiliyor.
  - bildirim_gonder() → chat_id'ye metin + opsiyonel ses
  - Vosk model yolu dinamik arama (proje kökünden)
  - run_polling yerine non-blocking başlatma
  - Gelen sesler geçici dizine güvenli yazılıyor
  - Tor proxy desteği korundu

"""
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import subprocess
import tempfile
import threading
from typing import Callable, Optional

from .logcu import Logcu

KAYNAK = "TELEGRAM"
_TMP_SES = "/tmp/zk_tg_yanit.mp3"


class TelegramBot:
    def __init__(self, logcu: Logcu, ayar: dict):
        self.log = logcu
        self.ayar = ayar
        self._komut_isleyici: Optional[Callable[[str], str]] = None
        self._durum_dinleyiciler: list[Callable[[str], None]] = []
        self._panel_saglayici: Optional[Callable[[], dict]] = None
        self._kontrol_isleyici: Optional[Callable[[str, str], str]] = None
        self._varlik_saglayici: Optional[Callable[..., dict]] = None
        self._uzuv_gorev_saglayici: Optional[Callable[[], list[dict]]] = None
        self._uzuv_gorev_cevap_isleyici: Optional[Callable[[str, str, str], str]] = None
        self._uzuv_ekran_cevap_isleyici: Optional[Callable[[str, str, str], str]] = None
        self._uygulama = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._calisıyor = False
        self._vosk_model_yolu: str = ""

    # ── Dinleyiciler ─────────────────────────────────────────────────────────

    def durum_dinleyici_ekle(self, fn: Callable[[str], None]):
        self._durum_dinleyiciler.append(fn)

    def _bildir(self, mesaj: str):
        self.log.bilgi(KAYNAK, mesaj)
        for fn in self._durum_dinleyiciler:
            try:
                fn(mesaj)
            except Exception:
                pass

    def komut_isleyici_ayarla(self, fn: Callable[[str], str]):
        """
        Telegram'dan gelen metni çekirdeğe iletecek fonksiyon.
        cekirdek.py bu fonksiyonu lambda m: self.isle(m, kanal="telegram")
        şeklinde ayarlar → ses.konus() çağrılmaz, _telegram_yanit_gonder() çağrılmaz.
        Yanıt yalnızca bu handler tarafından kullanıcıya iletilir.
        """
        self._komut_isleyici = fn

    def vosk_model_yolu_ayarla(self, yol: str):
        self._vosk_model_yolu = yol

    def panel_saglayici_ayarla(self, fn: Callable[[], dict]):
        self._panel_saglayici = fn

    def kontrol_isleyici_ayarla(self, fn: Callable[[str, str], str]):
        self._kontrol_isleyici = fn

    def varlik_saglayici_ayarla(self, fn: Callable[..., dict]):
        self._varlik_saglayici = fn

    def uzuv_gorev_saglayici_ayarla(self, fn: Callable[[], list[dict]]):
        self._uzuv_gorev_saglayici = fn

    def uzuv_gorev_cevap_isleyici_ayarla(self, fn: Callable[[str, str, str], str]):
        self._uzuv_gorev_cevap_isleyici = fn

    def uzuv_ekran_cevap_isleyici_ayarla(self, fn: Callable[[str, str, str], str]):
        self._uzuv_ekran_cevap_isleyici = fn

    # ── Başlat / Durdur ──────────────────────────────────────────────────────

    def baslat(self) -> bool:
        if not self.ayar.get("aktif") or not self.ayar.get("token"):
            self.log.uyari(KAYNAK, "Token yok veya bot devre dışı.")
            return False
        if importlib.util.find_spec("telegram") is None:
            self.log.hata(KAYNAK,
                "python-telegram-bot kurulu değil: "
                "pip install 'python-telegram-bot>=20.0'")
            return False

        self._calisıyor = True
        self._thread = threading.Thread(target=self._calistir_thread, daemon=True)
        self._thread.start()
        return True

    def durdur(self):
        self._calisıyor = False

    # ── Bot Thread ───────────────────────────────────────────────────────────

    def _calistir_thread(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._bot_async())
        except Exception as e:
            self.log.hata(KAYNAK, f"Bot thread hatası: {e}")

    async def _bot_async(self):
        from telegram import Update
        from telegram.ext import (Application, MessageHandler,
                                   ContextTypes, filters)

        token = self.ayar["token"]
        proxy_url = None
        if self.ayar.get("tor"):
            proxy_url = "socks5h://127.0.0.1:9050"

        builder = Application.builder().token(token)
        if proxy_url:
            builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)

        self._uygulama = builder.build()

        # ── İşleyiciler ───────────────────────────────────────────────────────


        # ── Inline Menü Yardımcıları ──────────────────────────────────────────
        def _ana_menu_kb():
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Panel", callback_data="panel"),
                 InlineKeyboardButton("📈 Sistem", callback_data="durum")],
                [InlineKeyboardButton("🧠 Bilinçler", callback_data="bilincler"),
                 InlineKeyboardButton("📝 Notlarım", callback_data="notlar")],
                [InlineKeyboardButton("⚡ Makrolar", callback_data="makrolar"),
                 InlineKeyboardButton("🖥 Uzuvlar", callback_data="uzuvlar")],
                [InlineKeyboardButton("🎤 Wake Word", callback_data="wake"),
                 InlineKeyboardButton("🛡 Güvenlik", callback_data="guvenlik")],
                [InlineKeyboardButton("📸 Ekran", callback_data="ekran"),
                 InlineKeyboardButton("📦 Son Yedek", callback_data="yedek")],
                [InlineKeyboardButton("📜 Son Log", callback_data="loglar"),
                 InlineKeyboardButton("📄 Tanı", callback_data="tani")],
                [InlineKeyboardButton("✅ Onay Ver", callback_data="onay_ver"),
                 InlineKeyboardButton("✖ İptal", callback_data="iptal_et")],
                [InlineKeyboardButton("🔄 Yenile", callback_data="yenile"),
                 InlineKeyboardButton("❓ Yardım", callback_data="yardim")],
            ])

        def _panel_ozeti() -> str:
            veri = self._panel_saglayici() if self._panel_saglayici else {}
            aktif = veri.get("aktif_bilinc", "—")
            wake = "Açık" if veri.get("wake_word_aktif") else "Kapalı"
            onay = "Açık" if veri.get("tehlikeli_onay") else "Kapalı"
            uzuvlar = veri.get("uzuvlar", [])
            uzuv_satiri = ", ".join(
                f"{u.get('ad', u.get('id', '?'))}:{u.get('durum', '?')}"
                for u in uzuvlar[:6]
            ) or "Kayıtlı uzuv yok"
            return (
                "⬡ *MERKEZ KOMUTA PANELİ*\n\n"
                f"🧠 Aktif bilinç: `{aktif}`\n"
                f"🎤 Wake word: `{wake}`\n"
                f"🛡 Tehlikeli komut onayı: `{onay}`\n"
                f"🖥 Uzuv sayısı: `{len(uzuvlar)}`\n"
                f"🔗 Bağlantılar: {uzuv_satiri}"
            )

        def _bilinc_ozeti() -> str:
            veri = self._panel_saglayici() if self._panel_saglayici else {}
            aktif = veri.get("aktif_bilinc", "")
            bilincler = veri.get("bilincler", [])
            if not bilincler:
                return "Bilinç bilgisi alınamadı."
            satirlar = ["🧠 *BİLİNÇLER*"]
            for bilinc in bilincler:
                isaret = "✅" if bilinc == aktif else "▫"
                satirlar.append(f"{isaret} `{bilinc}`")
            satirlar.append("\nDeğiştirmek için `/bilinc ABLA` gibi komut verin.")
            return "\n".join(satirlar)

        def _uzuv_ozeti() -> str:
            veri = self._panel_saglayici() if self._panel_saglayici else {}
            uzuvlar = veri.get("uzuvlar", [])
            if not uzuvlar:
                return "Kayıtlı uzuv yok."
            satirlar = ["🖥 *UZUVLAR*"]
            for uzuv in uzuvlar[:12]:
                satirlar.append(
                    f"▫ `{uzuv.get('id', '?')}` | {uzuv.get('ad', '?')} | "
                    f"{uzuv.get('durum', '?')} | {uzuv.get('baglanti', '—')}"
                )
            satirlar.append("\nUzak komut için `/uzuv uzuv_id komut` kullanın.")
            return "\n".join(satirlar)

        def _makro_ozeti() -> str:
            veri = self._panel_saglayici() if self._panel_saglayici else {}
            makrolar = veri.get("makrolar", [])
            if not makrolar:
                return "⚡ Kayıtlı makro yok."
            satirlar = ["⚡ *MAKROLAR*"]
            for makro in makrolar[:30]:
                durum = "açık" if makro.get("aktif") else "kapalı"
                tetik = makro.get("tetik_tipi") or "manuel"
                satirlar.append(
                    f"▫ `{makro.get('id', '?')}` | {makro.get('ad', '?')} | "
                    f"{durum} | {tetik} | {makro.get('adim_sayisi', 0)} adım"
                )
            if len(makrolar) > 30:
                satirlar.append(f"\n... {len(makrolar) - 30} makro daha var.")
            satirlar.append("\nÇalıştırmak için doğal komutunu veya `/komut ...` kullanın.")
            return "\n".join(satirlar)

        def _guvenlik_ozeti() -> str:
            veri = self._panel_saglayici() if self._panel_saglayici else {}
            onay = "Açık" if veri.get("tehlikeli_onay") else "Kapalı"
            bekleyen = veri.get("bekleyen_onay") or "yok"
            return (
                "🛡 *GÜVENLİK*\n\n"
                f"Tehlikeli komut onayı: `{onay}`\n"
                f"Bekleyen onay: `{bekleyen}`\n\n"
                "`/onay ac` veya `/onay kapat` ile değiştirebilirsiniz."
            )

        def _kontrol_uygula(eylem: str, deger: str = "") -> str:
            if not self._kontrol_isleyici:
                return "Kontrol arabirimi bağlı değil."
            return self._kontrol_isleyici(eylem, deger) or "İşlem tamamlandı."

        async def _varlik_gonder(chat_id, tur: str, hedef_id: str = ""):
            if not self._varlik_saglayici:
                await self._uygulama.bot.send_message(chat_id=chat_id, text="Varlık sağlayıcı bağlı değil.")
                return
            sonuc = self._varlik_saglayici_cagir(tur, hedef_id) or {}
            if not sonuc.get("ok"):
                await self._uygulama.bot.send_message(chat_id=chat_id, text=sonuc.get("mesaj", "İşlem başarısız."))
                return
            yol = sonuc.get("yol", "")
            mesaj = sonuc.get("mesaj", "")
            if tur == "ekran" and yol and os.path.exists(yol):
                with open(yol, "rb") as f:
                    await self._uygulama.bot.send_photo(chat_id=chat_id, photo=f, caption=mesaj or "Ekran görüntüsü")
                return
            if yol and os.path.exists(yol):
                with open(yol, "rb") as f:
                    await self._uygulama.bot.send_document(chat_id=chat_id, document=f, caption=mesaj or tur)
                return
            await self._uygulama.bot.send_message(chat_id=chat_id, text=mesaj or "İşlem tamamlandı.")

        def _sistem_ozeti() -> str:
            """Hızlı sistem özeti metni."""
            import subprocess, re
            satirlar = ["⬡ *ZİHİN KÖPRÜSÜ SİSTEM DURUMU*\n"]
            # CPU
            try:
                r = subprocess.run(
                    ["top","-bn1"], capture_output=True, text=True, timeout=3)
                for satir in r.stdout.splitlines():
                    m = re.search(r"(\d+\.\d+)\s*us", satir)
                    if m:
                        satirlar.append(f"🔧 CPU: `{m.group(1)}%`")
                        break
            except Exception:
                pass
            # RAM
            try:
                r = subprocess.run(
                    ["free","-m"], capture_output=True, text=True, timeout=2)
                for satir in r.stdout.splitlines():
                    if satir.startswith("Mem"):
                        p = satir.split()
                        yuzde = int(p[2])*100//int(p[1]) if int(p[1]) else 0
                        satirlar.append(f"🧠 RAM: `{yuzde}%` ({p[2]}/{p[1]} MB)")
                        break
            except Exception:
                pass
            # Disk
            try:
                r = subprocess.run(
                    ["df","-h","/"], capture_output=True, text=True, timeout=2)
                satirlar_r = r.stdout.splitlines()
                if len(satirlar_r) >= 2:
                    p = satirlar_r[1].split()
                    if len(p) >= 5:
                        satirlar.append(f"💾 Disk: `{p[4]}` ({p[2]}/{p[1]})")
            except Exception:
                pass
            # Pil
            try:
                with open("/sys/class/power_supply/BAT0/capacity") as f:
                    satirlar.append(f"🔋 Pil: `{f.read().strip()}%`")
            except Exception:
                satirlar.append("🔋 Pil: AC")
            return "\n".join(satirlar)

        # ── Komut Handler'ları ────────────────────────────────────────────────
        async def _cmd_start(update, ctx):
            if not self._yetki_kontrol(update): return
            await update.message.reply_text(
                "⬡ *Merkez komuta sistemi* hazır.\n"
                "Sesli komutlar, yazılı komutlar ve uzuv yönetimi aktif.",
                parse_mode="Markdown",
                reply_markup=_ana_menu_kb()
            )

        async def _cmd_durum(update, ctx):
            if not self._yetki_kontrol(update): return
            await update.message.reply_text(
                _sistem_ozeti(), parse_mode="Markdown")

        async def _cmd_panel(update, ctx):
            if not self._yetki_kontrol(update): return
            await update.message.reply_text(
                _panel_ozeti(), parse_mode="Markdown",
                reply_markup=_ana_menu_kb())

        async def _cmd_ping(update, ctx):
            if not self._yetki_kontrol(update): return
            chat_id = update.effective_chat.id
            await self._guvenli_mesaj_gonder(
                chat_id,
                f"pong | chat_id={chat_id} | bot=aktif"
            )

        async def _cmd_komut(update, ctx):
            if not self._yetki_kontrol(update): return
            if not ctx.args:
                await self._guvenli_mesaj_gonder(
                    update.effective_chat.id,
                    "Kullanım: /komut yapılacak iş\n"
                    "Örnek: /komut internette buildozer hatası ara"
                )
                return
            metin = " ".join(ctx.args).strip()
            yanit = self._komut_isleyici_kanal(metin, "telegram_yazi")
            await self._guvenli_mesaj_gonder(
                update.effective_chat.id,
                yanit or "Komut yanıt üretmedi."
            )

        async def _cmd_odak(update, ctx):
            if not self._yetki_kontrol(update): return
            if not ctx.args:
                await self._guvenli_mesaj_gonder(
                    update.effective_chat.id,
                    "Kullanım: /odak uzuv_id|tumu|merkez\n"
                    "Örnek: /odak lavlak\n"
                    "Örnek: /odak tumu"
                )
                return
            hedef = " ".join(ctx.args).strip()
            hedef_l = hedef.lower()
            if hedef_l in ("tumu", "tüm", "tum", "hepsi", "all"):
                metin = "tüm uzuvlara odaklan"
            elif hedef_l in ("merkez", "pc", "bilgisayar", "kendi"):
                metin = "merkeze odaklan"
            else:
                metin = f"{hedef} odaklan"
            yanit = self._komut_isleyici_kanal(metin, "telegram_yazi")
            await self._guvenli_mesaj_gonder(
                update.effective_chat.id,
                yanit or "Odak komutu çalıştırılamadı."
            )

        async def _cmd_merkez(update, ctx):
            if not self._yetki_kontrol(update): return
            yanit = self._komut_isleyici_kanal("merkeze odaklan", "telegram_yazi")
            await self._guvenli_mesaj_gonder(
                update.effective_chat.id,
                yanit or "Merkez odağı ayarlanamadı."
            )

        async def _cmd_toplu(update, ctx):
            if not self._yetki_kontrol(update): return
            if not ctx.args:
                yanit = self._komut_isleyici_kanal("tüm uzuvlara odaklan", "telegram_yazi")
                await self._guvenli_mesaj_gonder(
                    update.effective_chat.id,
                    yanit or "Toplu odak ayarlanamadı."
                )
                return
            komut = " ".join(ctx.args).strip()
            yanit = self._komut_isleyici_kanal(f"tüm uzuvlara {komut}", "telegram_yazi")
            await self._guvenli_mesaj_gonder(
                update.effective_chat.id,
                yanit or "Toplu komut yanıt üretmedi."
            )

        async def _cmd_notlar(update, ctx):
            if not self._yetki_kontrol(update): return
            if self._komut_isleyici:
                yanit = self._komut_isleyici_kanal(
                    "notlarımı göster", "telegram_yazi")
                await update.message.reply_text(
                    yanit or "Not bulunamadı.")
            else:
                await update.message.reply_text("Sistem bağlı değil.")

        async def _cmd_makro(update, ctx):
            if not self._yetki_kontrol(update): return
            await update.message.reply_text(
                _makro_ozeti(),
                parse_mode="Markdown")

        async def _cmd_sistem(update, ctx):
            if not self._yetki_kontrol(update): return
            await update.message.reply_text(
                _sistem_ozeti(), parse_mode="Markdown")

        async def _cmd_bilincler(update, ctx):
            if not self._yetki_kontrol(update): return
            await update.message.reply_text(
                _bilinc_ozeti(), parse_mode="Markdown",
                reply_markup=_ana_menu_kb())

        async def _cmd_bilinc(update, ctx):
            if not self._yetki_kontrol(update): return
            if not ctx.args:
                await update.message.reply_text("Kullanım: /bilinc ABLA")
                return
            hedef = ctx.args[0].upper()
            if not self._bilinc_izinli(hedef):
                await update.message.reply_text(f"{hedef} bilinci Telegram için yetkili değil.")
                return
            yanit = self._komut_isleyici_kanal(f"{hedef.lower()} devral", "telegram_yazi")
            await update.message.reply_text(yanit or f"{hedef} için devir komutu çalıştırılamadı.")

        async def _cmd_wake(update, ctx):
            if not self._yetki_kontrol(update): return
            if not ctx.args:
                await update.message.reply_text("Kullanım: /wake ac|kapat")
                return
            durum = ctx.args[0].lower()
            if durum in ("ac", "aç", "on", "true"):
                yanit = _kontrol_uygula("wake_word", "ac")
            elif durum in ("kapat", "kapa", "off", "false"):
                yanit = _kontrol_uygula("wake_word", "kapat")
            else:
                yanit = "Kullanım: /wake ac|kapat"
            await update.message.reply_text(yanit)

        async def _cmd_onay(update, ctx):
            if not self._yetki_kontrol(update): return
            if not ctx.args:
                await update.message.reply_text("Kullanım: /onay ac|kapat")
                return
            durum = ctx.args[0].lower()
            if durum in ("ac", "aç", "on", "true"):
                yanit = _kontrol_uygula("tehlikeli_onay", "ac")
            elif durum in ("kapat", "kapa", "off", "false"):
                yanit = _kontrol_uygula("tehlikeli_onay", "kapat")
            else:
                yanit = "Kullanım: /onay ac|kapat"
            await update.message.reply_text(yanit)

        async def _cmd_uzuv(update, ctx):
            if not self._yetki_kontrol(update): return
            if len(ctx.args) < 2:
                await update.message.reply_text("Kullanım: /uzuv uzuv_id komut")
                return
            uid = ctx.args[0]
            komut = " ".join(ctx.args[1:])
            yanit = self._komut_isleyici_kanal(f"{uid} {komut}", "telegram_yazi")
            await update.message.reply_text(yanit or "Uzuv komutu çalıştırılamadı.")

        async def _cmd_uzuv_ping(update, ctx):
            if not self._yetki_kontrol(update): return
            if not ctx.args:
                await self._guvenli_mesaj_gonder(
                    update.effective_chat.id,
                    "Kullanım: /uzuv_ping uzuv_id"
                )
                return
            uid = ctx.args[0].strip()
            yanit = self._komut_isleyici_kanal(f"{uid} terminal komutu echo zk_ok", "telegram_yazi")
            await self._guvenli_mesaj_gonder(
                update.effective_chat.id,
                yanit or "Uzuv ping yanıt üretmedi."
            )

        async def _cmd_uzuv_gorevler(update, ctx):
            if not self._yetki_kontrol(update): return
            if not self._uzuv_gorev_saglayici:
                await update.message.reply_text("Uzuv görev sağlayıcı bağlı değil.")
                return
            gorevler = self._uzuv_gorev_saglayici() or []
            if not gorevler:
                await update.message.reply_text("Bekleyen uzuv Telegram görevi yok.")
                return
            satirlar = ["🧩 *UZUV TELEGRAM GÖREVLERİ*"]
            for gorev in gorevler[:10]:
                satirlar.append(
                    f"▫ `{gorev.get('id', '?')}` | {gorev.get('uzuv_id', '?')} | "
                    f"{gorev.get('durum', '?')} | `{gorev.get('komut', '')[:40]}`"
                )
            satirlar.append("\nYanıt için: `/uzuv_cevap gorev_id ok çıktı`")
            await update.message.reply_text("\n".join(satirlar), parse_mode="Markdown")

        async def _cmd_uzuv_ekran_gorevler(update, ctx):
            if not self._yetki_kontrol(update): return
            if not self._uzuv_gorev_saglayici:
                await update.message.reply_text("Uzuv görev sağlayıcı bağlı değil.")
                return
            gorevler = [g for g in (self._uzuv_gorev_saglayici() or []) if g.get("tur") == "ekran"]
            if not gorevler:
                await update.message.reply_text("Bekleyen uzuv ekran görevi yok.")
                return
            satirlar = ["📸 *UZUV EKRAN GÖREVLERİ*"]
            for gorev in gorevler[:10]:
                satirlar.append(
                    f"▫ `{gorev.get('id', '?')}` | {gorev.get('uzuv_id', '?')} | "
                    f"{gorev.get('durum', '?')}"
                )
            satirlar.append("\nYanıt için foto veya dosya başlığına `/uzuv_ekran_cevap gorev_id` yazın.")
            await update.message.reply_text("\n".join(satirlar), parse_mode="Markdown")

        async def _cmd_uzuv_cevap(update, ctx):
            if not self._yetki_kontrol(update): return
            if len(ctx.args) < 3:
                await update.message.reply_text("Kullanım: /uzuv_cevap gorev_id ok|hata çıktı")
                return
            if not self._uzuv_gorev_cevap_isleyici:
                await update.message.reply_text("Uzuv görev cevap işleyici bağlı değil.")
                return
            gorev_id = ctx.args[0]
            durum = ctx.args[1]
            mesaj = " ".join(ctx.args[2:])
            yanit = self._uzuv_gorev_cevap_isleyici(gorev_id, durum, mesaj)
            await update.message.reply_text(yanit or "Görev yanıtı işlendi.")

        async def _cmd_ekran(update, ctx):
            if not self._yetki_kontrol(update): return
            hedef_id = ctx.args[0].strip() if ctx.args else ""
            await _varlik_gonder(update.effective_chat.id, "ekran", hedef_id)

        async def _cmd_log(update, ctx):
            if not self._yetki_kontrol(update): return
            await _varlik_gonder(update.effective_chat.id, "log")

        async def _cmd_yedek(update, ctx):
            if not self._yetki_kontrol(update): return
            await _varlik_gonder(update.effective_chat.id, "yedek")

        async def _cmd_tani(update, ctx):
            if not self._yetki_kontrol(update): return
            await _varlik_gonder(update.effective_chat.id, "tani")

        async def _cmd_uzuvlar(update, ctx):
            if not self._yetki_kontrol(update): return
            if self._komut_isleyici:
                yanit = self._komut_isleyici_kanal(
                    "uzuv listesi", "telegram_yazi")
                await update.message.reply_text(
                    yanit or "Uzuv bilgisi alınamadı.")
            else:
                await update.message.reply_text("Sistem bağlı değil.")

        async def _cmd_yardim(update, ctx):
            if not self._yetki_kontrol(update): return
            yardim = (
                "⬡ *ZİHİN KÖPRÜSÜ — TELEGRAM KOMUTLARI*\n\n"
                "/start — Ana menü\n"
                "/ping — Bot ve chat ID kontrolü\n"
                "/durum — Sistem durumu (CPU/RAM/Disk)\n"
                "/panel — Merkez panel özeti\n"
                "/komut metin — Serbest merkez komutu çalıştır\n"
                "/notlar — Sesli notlarım\n"
                "/makro — Makro listesi\n"
                "/sistem — Sistem özeti\n"
                "/bilincler — Bilinç listesi\n"
                "/bilinc ABLA — Aktif bilinci değiştir\n"
                "/wake ac|kapat — Wake word modunu değiştir\n"
                "/onay ac|kapat — Tehlikeli komut onayını değiştir\n"
                "/odak uzuv_id|tumu|merkez — Komut hedefini seç\n"
                "/merkez — Odağı merkeze al\n"
                "/toplu komut — Tüm uzuvlara komut gönder\n"
                "/uzuvlar — Bağlı uzuv listesi\n"
                "/uzuv kimlik komut — Uzak uzuvda komut çalıştır\n"
                "/uzuv_ping kimlik — Uzuv bağlantısını test et\n"
                "Örnek ham komut: `/uzuv reader terminal komutu uptime`\n"
                "Örnek PowerShell: `/uzuv winpc powershell Get-Process`\n"
                "/uzuv_gorevler — Bekleyen Telegram uzuv görevleri\n"
                "/uzuv_ekran_gorevler — Bekleyen uzuv ekran görevleri\n"
                "/uzuv_cevap id ok|hata çıktı — Uzuv görevine yanıt ver\n"
                "/ekran [uzuv_id] — Yerel veya seçili uzvun ekranını gönder\n"
                "/log — Son log özetini gönder\n"
                "/yedek — En son yedeği gönder\n"
                "/tani — Tanı raporunu gönder\n"
                "/yardim — Bu yardım\n\n"
                "📝 *Not almak için:*\n`not al: hatırlatmam gereken şey`\n\n"
                "🎤 *Sesli komut:*\nSes mesajı gönderin"
            )
            await self._guvenli_mesaj_gonder(
                update.effective_chat.id,
                yardim,
                parse_mode="Markdown",
                reply_markup=_ana_menu_kb())

        async def _inline_callback(update, ctx):
            """Inline buton tıklamalarını işle."""
            query = update.callback_query
            await query.answer()
            veri = query.data

            if veri == "panel":
                await query.edit_message_text(
                    _panel_ozeti(), parse_mode="Markdown",
                    reply_markup=_ana_menu_kb())

            elif veri == "durum":
                await query.edit_message_text(
                    _sistem_ozeti(), parse_mode="Markdown",
                    reply_markup=_ana_menu_kb())

            elif veri == "bilincler":
                await query.edit_message_text(
                    _bilinc_ozeti(), parse_mode="Markdown",
                    reply_markup=_ana_menu_kb())

            elif veri == "notlar":
                if self._komut_isleyici:
                    yanit = self._komut_isleyici_kanal(
                        "notlarımı göster", "telegram_yazi")
                    await query.edit_message_text(
                        yanit or "Not yok.",
                        reply_markup=_ana_menu_kb())

            elif veri == "makrolar":
                await query.edit_message_text(
                    _makro_ozeti(),
                    parse_mode="Markdown",
                    reply_markup=_ana_menu_kb())

            elif veri == "uzuvlar":
                if self._komut_isleyici:
                    yanit = self._komut_isleyici_kanal(
                        "uzuv listesi", "telegram_yazi")
                    await query.edit_message_text(
                        yanit or "Uzuv yok.",
                        reply_markup=_ana_menu_kb())

            elif veri == "wake":
                await query.edit_message_text(
                    _kontrol_uygula("wake_word_durum", ""),
                    reply_markup=_ana_menu_kb())

            elif veri == "guvenlik":
                await query.edit_message_text(
                    _guvenlik_ozeti(), parse_mode="Markdown",
                    reply_markup=_ana_menu_kb())

            elif veri == "ekran":
                await _varlik_gonder(query.message.chat_id, "ekran")

            elif veri == "yedek":
                await _varlik_gonder(query.message.chat_id, "yedek")

            elif veri == "loglar":
                await _varlik_gonder(query.message.chat_id, "log")

            elif veri == "tani":
                await _varlik_gonder(query.message.chat_id, "tani")

            elif veri == "onay_ver":
                if self._komut_isleyici:
                    yanit = self._komut_isleyici_kanal("onay ver", "telegram_yazi")
                else:
                    yanit = "Komut işleyici bağlı değil."
                await query.edit_message_text(
                    yanit,
                    reply_markup=_ana_menu_kb())

            elif veri == "iptal_et":
                if self._komut_isleyici:
                    yanit = self._komut_isleyici_kanal("iptal", "telegram_yazi")
                else:
                    yanit = "Komut işleyici bağlı değil."
                await query.edit_message_text(
                    yanit,
                    reply_markup=_ana_menu_kb())

            elif veri == "yenile":
                await query.edit_message_text(
                    _panel_ozeti(), parse_mode="Markdown",
                    reply_markup=_ana_menu_kb())

            elif veri == "yardim":
                await _cmd_yardim(update, ctx)

        async def metin_isle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if not self._yetki_kontrol(update):
                return
            metin = update.message.text or ""
            self._bildir(f"TG yazı alındı: {metin[:60]}")

            if not (self.ayar.get("komut_al") and self._komut_isleyici):
                return

            chat_id = update.effective_chat.id

            def _isle():
                # kanal="telegram_yazi" → cekirdek tg_pc_konus bayrağına göre
                # PC'den sesli yanıt verip vermemeye karar verir
                yanit = self._komut_isleyici_kanal(metin, "telegram_yazi")
                if yanit and self.ayar.get("yanit_gonder"):
                    asyncio.run_coroutine_threadsafe(
                        self._yanit_gonder(chat_id, yanit, sesli=False),
                        self._loop
                    )
            threading.Thread(target=_isle, daemon=True).start()

        async def medya_isle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if not self._yetki_kontrol(update):
                return
            if not self._uzuv_ekran_cevap_isleyici:
                return
            mesaj = update.message
            baslik = (mesaj.caption or "").strip()
            if not baslik.lower().startswith("/uzuv_ekran_cevap"):
                return
            parcalar = baslik.split(maxsplit=2)
            if len(parcalar) < 2:
                await mesaj.reply_text("Kullanım: foto veya dosya başlığına `/uzuv_ekran_cevap gorev_id` yazın.")
                return
            gorev_id = parcalar[1].strip()
            ek_metin = parcalar[2].strip() if len(parcalar) > 2 else ""

            kaynak = None
            uzanti = ".bin"
            if mesaj.photo:
                kaynak = mesaj.photo[-1]
                uzanti = ".jpg"
            elif mesaj.document:
                kaynak = mesaj.document
                ad = (mesaj.document.file_name or "").lower()
                uzanti = os.path.splitext(ad)[1] or ".bin"
            if kaynak is None:
                await mesaj.reply_text("Bu komut fotoğraf veya dosya ile kullanılmalı.")
                return

            tg_file = await kaynak.get_file()
            with tempfile.NamedTemporaryFile(suffix=uzanti, delete=False, dir="/tmp") as tmp:
                yerel_yol = tmp.name
            await tg_file.download_to_drive(yerel_yol)
            yanit = self._uzuv_ekran_cevap_isleyici(gorev_id, yerel_yol, ek_metin)
            await mesaj.reply_text(yanit or "Uzuv ekran yanıtı işlendi.")

        async def ses_isle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if not self._yetki_kontrol(update):
                return
            self._bildir("TG sesli mesaj alındı, dönüştürülüyor...")

            try:
                voice_obj = update.message.voice or update.message.audio
                tg_file = await voice_obj.get_file()

                with tempfile.NamedTemporaryFile(
                        suffix=".ogg", delete=False, dir="/tmp") as tmp:
                    ogg_yol = tmp.name
                await tg_file.download_to_drive(ogg_yol)

                wav_yol = ogg_yol.replace(".ogg", "_16k.wav")
                ffmpeg_r = subprocess.run(
                    ["ffmpeg", "-y", "-i", ogg_yol,
                     "-ar", "16000", "-ac", "1", "-f", "wav", wav_yol],
                    capture_output=True
                )
                try:
                    os.unlink(ogg_yol)
                except OSError:
                    pass

                if ffmpeg_r.returncode != 0:
                    self.log.hata(KAYNAK, "ffmpeg dönüşüm hatası.")
                    return

                metin = self._vosk_oku(wav_yol)
                try:
                    os.unlink(wav_yol)
                except OSError:
                    pass

                chat_id = update.effective_chat.id

                if not metin:
                    await self._uygulama.bot.send_message(
                        chat_id=chat_id,
                        text="⚠️ Ses anlaşılamadı, tekrar dener misiniz?"
                    )
                    return

                self._bildir(f"TG ses→metin: {metin}")

                if not self._komut_isleyici:
                    return

                def _isle():
                    # kanal="telegram_ses" → ses_pc_konus bayrağına göre PC konuşur
                    yanit = self._komut_isleyici_kanal(metin, "telegram_ses")
                    if yanit and self.ayar.get("yanit_gonder"):
                        asyncio.run_coroutine_threadsafe(
                            self._yanit_gonder(
                                chat_id, yanit,
                                sesli=True,
                                orijinal_metin=metin),
                            self._loop
                        )
                threading.Thread(target=_isle, daemon=True).start()

            except Exception as e:
                self.log.hata(KAYNAK, f"Ses işleme hatası: {e}")

        # Komut handler'ları
        from telegram.ext import CommandHandler
        self._uygulama.add_handler(CommandHandler("start",   _cmd_start))
        self._uygulama.add_handler(CommandHandler("durum",   _cmd_durum))
        self._uygulama.add_handler(CommandHandler("panel",   _cmd_panel))
        self._uygulama.add_handler(CommandHandler("ping",   _cmd_ping))
        self._uygulama.add_handler(CommandHandler("komut",   _cmd_komut))
        self._uygulama.add_handler(CommandHandler("notlar",  _cmd_notlar))
        self._uygulama.add_handler(CommandHandler("makro",   _cmd_makro))
        self._uygulama.add_handler(CommandHandler("sistem",  _cmd_sistem))
        self._uygulama.add_handler(CommandHandler("bilincler", _cmd_bilincler))
        self._uygulama.add_handler(CommandHandler("bilinc", _cmd_bilinc))
        self._uygulama.add_handler(CommandHandler("wake", _cmd_wake))
        self._uygulama.add_handler(CommandHandler("onay", _cmd_onay))
        self._uygulama.add_handler(CommandHandler("odak", _cmd_odak))
        self._uygulama.add_handler(CommandHandler("merkez", _cmd_merkez))
        self._uygulama.add_handler(CommandHandler("toplu", _cmd_toplu))
        self._uygulama.add_handler(CommandHandler("uzuvlar", _cmd_uzuvlar))
        self._uygulama.add_handler(CommandHandler("uzuv", _cmd_uzuv))
        self._uygulama.add_handler(CommandHandler("uzuv_ping", _cmd_uzuv_ping))
        self._uygulama.add_handler(CommandHandler("uzuv_gorevler", _cmd_uzuv_gorevler))
        self._uygulama.add_handler(CommandHandler("uzuv_ekran_gorevler", _cmd_uzuv_ekran_gorevler))
        self._uygulama.add_handler(CommandHandler("uzuv_cevap", _cmd_uzuv_cevap))
        self._uygulama.add_handler(CommandHandler("ekran", _cmd_ekran))
        self._uygulama.add_handler(CommandHandler("log", _cmd_log))
        self._uygulama.add_handler(CommandHandler("yedek", _cmd_yedek))
        self._uygulama.add_handler(CommandHandler("tani", _cmd_tani))
        self._uygulama.add_handler(CommandHandler("yardim",  _cmd_yardim))

        # Inline buton callback
        from telegram.ext import CallbackQueryHandler
        self._uygulama.add_handler(
            CallbackQueryHandler(_inline_callback))

        self._uygulama.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, metin_isle))
        self._uygulama.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, ses_isle))
        self._uygulama.add_handler(
            MessageHandler(filters.PHOTO | filters.Document.ALL, medya_isle))

        self._bildir("Telegram bot başlatıldı.")

        await self._uygulama.initialize()
        await self._uygulama.start()
        await self._uygulama.updater.start_polling(drop_pending_updates=True)

        while self._calisıyor:
            await asyncio.sleep(1)

        try:
            if self._uygulama.updater and self._uygulama.updater.running:
                await self._uygulama.updater.stop()
        except Exception as e:
            self.log.uyari(KAYNAK, f"Telegram polling durdurma uyarısı: {e}")
        try:
            if self._uygulama.running:
                await self._uygulama.stop()
        except Exception as e:
            self.log.uyari(KAYNAK, f"Telegram uygulama durdurma uyarısı: {e}")
        try:
            await self._uygulama.shutdown()
        except Exception as e:
            self.log.uyari(KAYNAK, f"Telegram shutdown uyarısı: {e}")

    # ── Yanıt Gönder ─────────────────────────────────────────────────────────

    async def _yanit_gonder(self, chat_id, metin: str,
                            sesli: bool = False,
                            orijinal_metin: str = ""):
        """
        Kullanıcıya yanıt gönderir.
        sesli=False → yalnızca metin
        sesli=True  → metin + ses dosyası (gTTS)
        """
        if not self._uygulama:
            return
        try:
            gonder_metin = metin
            if orijinal_metin:
                gonder_metin = (
                    f"🎤 Anlaşılan: {orijinal_metin}\n\n{metin}"
                )
            if len(gonder_metin) > 3500:
                gonder_metin = gonder_metin[:3400] + "\n\n...[kesildi]"
            await self._guvenli_mesaj_gonder(chat_id, gonder_metin)

            if sesli and metin.strip():
                ses_dosya = await asyncio.get_running_loop().run_in_executor(
                    None, self._tts_olustur, metin)
                if ses_dosya and os.path.exists(ses_dosya):
                    with open(ses_dosya, "rb") as f:
                        await self._uygulama.bot.send_voice(
                            chat_id=chat_id,
                            voice=f,
                            caption="🔊 Sesli yanıt"
                        )
                    try:
                        os.unlink(ses_dosya)
                    except OSError:
                        pass

        except Exception as e:
            self.log.hata(KAYNAK, f"Yanıt gönderme hatası: {e}")

    async def _guvenli_mesaj_gonder(self, chat_id, metin: str,
                                    parse_mode: str | None = None,
                                    reply_markup=None):
        """Telegram parse hatası veya uzun mesaj durumunda güvenli gönderim."""
        if not self._uygulama:
            return
        gonder = str(metin or "")
        if len(gonder) > 3900:
            gonder = gonder[:3800] + "\n\n...[kesildi]"
        try:
            await self._uygulama.bot.send_message(
                chat_id=chat_id,
                text=gonder,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        except Exception as e:
            if parse_mode:
                try:
                    await self._uygulama.bot.send_message(
                        chat_id=chat_id,
                        text=gonder,
                        reply_markup=reply_markup,
                    )
                    return
                except Exception as e2:
                    self.log.hata(KAYNAK, f"Yanıt gönderme hatası: {e2}")
                    return
            self.log.hata(KAYNAK, f"Yanıt gönderme hatası: {e}")

    # ── TTS ──────────────────────────────────────────────────────────────────

    def _tts_olustur(self, metin: str) -> Optional[str]:
        try:
            from gtts import gTTS
            tts = gTTS(text=metin, lang="tr", slow=False)
            tts.save(_TMP_SES)
            return _TMP_SES
        except Exception as e:
            self.log.uyari(KAYNAK, f"TTS oluşturulamadı: {e}")
            return None

    # ── Vosk STT ─────────────────────────────────────────────────────────────

    def _vosk_oku(self, wav_dosya: str) -> str:
        model_yol = self._vosk_model_yolu or self._vosk_model_bul()
        if not model_yol or not os.path.isdir(model_yol):
            self.log.uyari(KAYNAK, f"Vosk model bulunamadı: {model_yol}")
            return ""
        try:
            import wave
            import json as _j
            from vosk import Model, KaldiRecognizer

            model = Model(model_yol)
            with wave.open(wav_dosya, "rb") as wf:
                rec = KaldiRecognizer(model, wf.getframerate())
                rec.SetWords(False)
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    rec.AcceptWaveform(data)
                sonuc = _j.loads(rec.FinalResult())
                return sonuc.get("text", "").strip()
        except Exception as e:
            self.log.hata(KAYNAK, f"Vosk STT hatası: {e}")
            return ""

    def _vosk_model_bul(self) -> str:
        adaylar = [
            os.path.join(os.path.expanduser("~"), "Zihin_Koprusu",
                         "modeller", "vosk-tr", "vosk-model-small-tr-0.3"),
            os.path.join(os.path.dirname(__file__), "..", "..",
                         "modeller", "vosk-tr", "vosk-model-small-tr-0.3"),
            "/opt/zihin-koprusu/modeller/vosk-tr/vosk-model-small-tr-0.3",
        ]
        for aday in adaylar:
            aday = os.path.normpath(aday)
            if os.path.isdir(aday):
                return aday
        return ""

    # ── Dışarıdan Bildirim ───────────────────────────────────────────────────

    def bildirim_gonder(self, metin: str, sesli: bool = False):
        """
        Çekirdek veya GUI'nin dışarıdan çağırdığı yöntem.
        Sadece 'ses' kanalından gelen komutlar için çağrılır (cekirdek.py'de tg_bildir koşulu).
        """
        chat_id = self.ayar.get("chat_id")
        if not chat_id or not self._loop or not self._calisıyor:
            return
        asyncio.run_coroutine_threadsafe(
            self._yanit_gonder(chat_id, metin, sesli=sesli),
            self._loop
        )

    def uzuv_gorevi_gonder(self, gorev: dict) -> bool:
        chat_id = self.ayar.get("chat_id")
        if not chat_id or not self._loop or not self._calisıyor:
            return False
        gorev_id = gorev.get("id", "?")
        durum = gorev.get("durum", "bekliyor")
        uzuv_ad = gorev.get("uzuv_ad") or gorev.get("uzuv_id", "?")
        baglanti = gorev.get("baglanti", "telegram")
        hedef = gorev.get("hedef", "tanımsız")
        komut = gorev.get("komut", "")
        mesaj = (
            "🧩 *UZUV TELEGRAM GÖREVİ*\n\n"
            f"ID: `{gorev_id}`\n"
            f"Uzuv: `{uzuv_ad}`\n"
            f"Bağlantı: `{baglanti}`\n"
            f"Hedef: `{hedef}`\n"
            f"Durum: `{durum}`\n"
            f"Komut: `{komut}`\n\n"
            f"Yanıt: `/uzuv_cevap {gorev_id} ok çıktı`\n"
            f"`ZK_TASK|{gorev_id}|{gorev.get('uzuv_id', '?')}|komut`"
        )
        asyncio.run_coroutine_threadsafe(
            self._guvenli_mesaj_gonder(chat_id, mesaj, parse_mode="Markdown"),
            self._loop
        )
        return True

    def uzuv_ekran_istegi_gonder(self, gorev: dict) -> bool:
        chat_id = self.ayar.get("chat_id")
        if not chat_id or not self._loop or not self._calisıyor:
            return False
        gorev_id = gorev.get("id", "?")
        uzuv_ad = gorev.get("uzuv_ad") or gorev.get("uzuv_id", "?")
        baglanti = gorev.get("baglanti", "telegram")
        hedef = gorev.get("hedef", "tanımsız")
        mesaj = (
            "📸 *UZUV EKRAN İSTEĞİ*\n\n"
            f"ID: `{gorev_id}`\n"
            f"Uzuv: `{uzuv_ad}`\n"
            f"Bağlantı: `{baglanti}`\n"
            f"Hedef: `{hedef}`\n\n"
            "Yanıt için ekran görüntüsünü foto veya dosya olarak gönderin.\n"
            f"Başlık: `/uzuv_ekran_cevap {gorev_id}`\n"
            f"`ZK_TASK|{gorev_id}|{gorev.get('uzuv_id', '?')}|ekran`"
        )
        asyncio.run_coroutine_threadsafe(
            self._guvenli_mesaj_gonder(chat_id, mesaj, parse_mode="Markdown"),
            self._loop
        )
        return True

    def log_bildir(self, seviye: str, kaynak: str, mesaj: str):
        """Seçili log seviyelerini Telegram'a iletir."""
        if not self.ayar.get("log_gonder"):
            return
        filtre_str = self.ayar.get("log_filtre", "").strip()
        if filtre_str:
            filtreler = [f.strip().upper() for f in filtre_str.split(",") if f.strip()]
            if seviye.upper() not in filtreler:
                return
        if seviye.upper() == "BİLGİ":
            return
        self.bildirim_gonder(f"[{seviye}][{kaynak}] {mesaj}")

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    def _yetki_kontrol(self, update) -> bool:
        """
        Erişim modları:
          herkese_acik: true  → herkese açık, hiçbir filtre yok
          izin_listesi (liste) → sadece listede olan chat_id'ler
          chat_id (tek)        → sadece bu tek ID
          hiçbiri              → herkese açık (varsayılan)
        """
        # 1. Herkese açık mod
        if self.ayar.get("herkese_acik", False):
            return True

        gelen_id = str(update.effective_chat.id)

        # 2. İzin listesi (birden fazla ID)
        izin_listesi = self.ayar.get("izin_listesi", [])
        if izin_listesi:
            return gelen_id in [str(x) for x in izin_listesi]

        # 3. Tek chat_id
        chat_id = self.ayar.get("chat_id", "")
        if chat_id:
            return gelen_id == str(chat_id)

        # 4. Hiçbiri tanımlı değil → herkese açık
        return True

    def _bilinc_izinli(self, bilinc: str) -> bool:
        izin = self.ayar.get("izin_bilincler", [])
        if not izin:
            return True
        return bilinc.upper() in {str(x).upper() for x in izin}

    def _komut_isleyici_kanal(self, metin: str, kanal: str) -> str:
        """
        _komut_isleyici'yi doğru kanal bilgisiyle çağırır.
        cekirdek.isle(metin, kanal) imzasını desteklemeyen eski lambda
        için geriye dönük uyumluluk sağlar.
        """
        if self._komut_isleyici is None:
            return ""
        import inspect
        try:
            sig = inspect.signature(self._komut_isleyici)
            if len(sig.parameters) >= 2:
                return self._komut_isleyici(metin, kanal) or ""
            else:
                return self._komut_isleyici(metin) or ""
        except Exception as e:
            self.log.uyari(KAYNAK, f"Komut işleyici hatası: {e}")
            return ""

    def _varlik_saglayici_cagir(self, tur: str, hedef_id: str = "") -> dict:
        if self._varlik_saglayici is None:
            return {}
        try:
            sig = inspect.signature(self._varlik_saglayici)
            if len(sig.parameters) >= 2:
                return self._varlik_saglayici(tur, hedef_id) or {}
            return self._varlik_saglayici(tur) or {}
        except Exception as e:
            self.log.uyari(KAYNAK, f"Varlık sağlayıcı hatası: {e}")
            return {}

    def calisıyor_mu(self) -> bool:
        return self._calisıyor
