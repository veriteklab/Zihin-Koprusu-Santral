#!/usr/bin/env python3
"""
Zihin Köprüsü erişilebilirlik komut üreticisi.

Amaç: klavye/fare/web/medya/pencere kontrolünü sesle kullanılabilecek
geniş Türkçe tetikleyici listelerine dönüştürmek. Script idempotent çalışır;
erisim_ ile başlayan kayıtları günceller, diğer kayıtları korur.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus


ROOT = Path(__file__).resolve().parent
DB = ROOT / "komutlar.json"
BACKUP_DIR = ROOT / "yedekler"
PREFIX = "erisim_"


def slug(text: str) -> str:
    table = str.maketrans({
        "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i",
        "İ": "i", "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u",
        "Ü": "u", "'": "", "\"": "", ".": "", ",": "", ":": "",
        "/": "_", "&": "ve", "+": "arti",
    })
    out = text.translate(table).lower()
    out = "".join(ch if ch.isalnum() else "_" for ch in out)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def uniq(items: list[str], limit: int = 48) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        clean = " ".join(item.strip().split())
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def phrases(objects: list[str], verbs: list[str], suffixes: list[str] | None = None,
            prefixes: list[str] | None = None, limit: int = 48) -> list[str]:
    suffixes = suffixes or [""]
    prefixes = prefixes or [""]
    out: list[str] = []
    for obj in objects:
        out.append(obj)
        for verb in verbs:
            out.append(f"{obj} {verb}")
            out.append(f"{verb} {obj}")
            for suffix in suffixes:
                if suffix:
                    out.append(f"{obj} {suffix}")
                    out.append(f"{verb} {obj} {suffix}")
            for prefix in prefixes:
                if prefix:
                    out.append(f"{prefix} {obj}")
                    out.append(f"{prefix} {obj} {verb}")
    return uniq(out, limit)


def command_record(kid: str, kategori: str, ad: str, tetikleyiciler: list[str],
                   komut: str, yanit: str = "", hedef_os: str = "linux",
                   aciklama: str = "") -> dict:
    return {
        "id": kid,
        "kategori": kategori,
        "ad": ad,
        "tetikleyiciler": uniq(tetikleyiciler),
        "tur": "kabuk",
        "komut": komut,
        "komut_windows": "",
        "komut_android": "",
        "yanit": yanit,
        "yanit_alternatif": [],
        "yetkili_bilincler": [],
        "hedef_os": hedef_os,
        "uzuv_id": "",
        "aciklama": aciklama,
        "aktif": True,
    }


def xdotool_key(keys: str) -> str:
    return f"xdotool key --clearmodifiers {keys}"


def xdotool_click(button: int) -> str:
    return f"xdotool click {button}"


def add(records: dict[str, dict], kategori: str, name: str, triggers: list[str],
        command: str, yanit: str = "", aciklama: str = "") -> None:
    kid = PREFIX + slug(kategori + "_" + name)
    records[kid] = command_record(kid, kategori, name, triggers, command, yanit, "linux", aciklama)


def build_keyboard(records: dict[str, dict]) -> None:
    key_defs = [
        ("Enter", ["enter", "giriş", "tamam tuşu"], "Return"),
        ("Tab", ["tab", "sonraki alan", "sonraki kutu"], "Tab"),
        ("Shift Tab", ["geri tab", "önceki alan", "önceki kutu"], "shift+Tab"),
        ("Escape", ["escape", "esc", "iptal tuşu", "çıkış tuşu"], "Escape"),
        ("Boşluk", ["boşluk", "space", "boşluk tuşu"], "space"),
        ("Backspace", ["geri sil", "backspace", "son harfi sil"], "BackSpace"),
        ("Delete", ["delete", "sil tuşu", "ileriden sil"], "Delete"),
        ("Yukarı Ok", ["yukarı ok", "imleç yukarı"], "Up"),
        ("Aşağı Ok", ["aşağı ok", "imleç aşağı"], "Down"),
        ("Sol Ok", ["sol ok", "imleç sol"], "Left"),
        ("Sağ Ok", ["sağ ok", "imleç sağ"], "Right"),
        ("Page Up", ["sayfa yukarı", "bir sayfa yukarı"], "Page_Up"),
        ("Page Down", ["sayfa aşağı", "bir sayfa aşağı"], "Page_Down"),
        ("Home", ["başa git", "satır başı", "home"], "Home"),
        ("End", ["sona git", "satır sonu", "end"], "End"),
        ("Kopyala", ["kopyala", "seçileni kopyala"], "ctrl+c"),
        ("Yapıştır", ["yapıştır", "panodan yapıştır"], "ctrl+v"),
        ("Kes", ["kes", "seçileni kes"], "ctrl+x"),
        ("Geri Al", ["geri al", "son işlemi geri al"], "ctrl+z"),
        ("Yinele", ["yinele", "ileri al", "tekrar uygula"], "ctrl+y"),
        ("Tümünü Seç", ["tümünü seç", "hepsini seç"], "ctrl+a"),
        ("Kaydet", ["kaydet", "dosyayı kaydet"], "ctrl+s"),
        ("Aç", ["aç penceresi", "dosya aç", "aç menüsü"], "ctrl+o"),
        ("Bul", ["bul", "sayfada bul", "metin ara"], "ctrl+f"),
        ("Yazdır", ["yazdır", "print", "çıktı al"], "ctrl+p"),
        ("Yeni", ["yeni belge", "yeni dosya"], "ctrl+n"),
        ("Alt Tab", ["pencere değiştir", "sonraki pencere", "alt tab"], "alt+Tab"),
        ("Alt F4", ["aktif pencereyi kapat", "pencereyi kapat"], "alt+F4"),
    ]
    verbs = ["bas", "tuşuna bas", "çalıştır", "uygula"]
    for name, names, key in key_defs:
        add(records, "Erişim Klavye", name, phrases(names, verbs, limit=36), xdotool_key(key), f"{name} uygulandı.")

    letters = [
        ("a", "a"), ("be", "b"), ("ce", "c"), ("çe", "ccedilla"), ("de", "d"),
        ("e", "e"), ("fe", "f"), ("ge", "g"), ("yumuşak ge", "gbreve"), ("he", "h"),
        ("ı", "idotless"), ("i", "i"), ("je", "j"), ("ke", "k"), ("le", "l"),
        ("me", "m"), ("ne", "n"), ("o", "o"), ("ö", "odiaeresis"), ("pe", "p"),
        ("re", "r"), ("se", "s"), ("şe", "scedilla"), ("te", "t"), ("u", "u"),
        ("ü", "udiaeresis"), ("ve", "v"), ("ye", "y"), ("ze", "z"),
    ]
    for spoken, key in letters:
        add(records, "Erişim Harf Yaz", f"Harf {spoken.upper()}",
            phrases([f"{spoken} harfi", f"{spoken} yaz", f"{spoken} tuşu"], ["bas", "yaz", "gir"], limit=40),
            xdotool_key(key), f"{spoken} yazıldı.")

    for number in range(10):
        add(records, "Erişim Rakam Yaz", f"Rakam {number}",
            phrases([f"{number}", f"{number} yaz", f"{number} rakamı", f"{number} tuşu"], ["bas", "yaz", "gir"], limit=40),
            xdotool_key(str(number)), f"{number} yazıldı.")

    punctuation = [
        ("Nokta", ["nokta", "nokta koy"], "period"),
        ("Virgül", ["virgül", "virgül koy"], "comma"),
        ("Soru İşareti", ["soru işareti", "soru koy"], "question"),
        ("Ünlem", ["ünlem", "ünlem koy"], "exclam"),
        ("İki Nokta", ["iki nokta", "iki nokta koy"], "colon"),
        ("Noktalı Virgül", ["noktalı virgül"], "semicolon"),
        ("Tırnak", ["tırnak aç", "tırnak koy"], "quotedbl"),
        ("Tek Tırnak", ["tek tırnak"], "apostrophe"),
        ("Slash", ["slash", "eğik çizgi"], "slash"),
        ("Ters Slash", ["ters slash", "ters eğik çizgi"], "backslash"),
        ("Eksi", ["eksi", "tire"], "minus"),
        ("Alt Çizgi", ["alt çizgi"], "underscore"),
        ("Artı", ["artı", "plus"], "plus"),
        ("Eşittir", ["eşittir"], "equal"),
        ("Parantez Aç", ["parantez aç"], "parenleft"),
        ("Parantez Kapat", ["parantez kapat"], "parenright"),
    ]
    for name, names, key in punctuation:
        add(records, "Erişim Noktalama", name, phrases(names, ["bas", "yaz", "gir"], limit=36), xdotool_key(key), f"{name} yazıldı.")

    for n in range(1, 13):
        add(records, "Erişim Fonksiyon Tuşu", f"F{n}",
            phrases([f"f {n}", f"f{n}", f"fonksiyon {n}"], ["bas", "tuşuna bas", "çalıştır"], limit=36),
            xdotool_key(f"F{n}"), f"F{n} uygulandı.")


def build_mouse(records: dict[str, dict]) -> None:
    clicks = [
        ("Sol Tık", ["tıkla", "sol tık", "buraya tıkla"], 1),
        ("Orta Tık", ["orta tık", "teker tıkla"], 2),
        ("Sağ Tık", ["sağ tık", "menüyü aç", "bağlam menüsü"], 3),
        ("Çift Tık", ["çift tık", "çift tıkla"], 1),
    ]
    for name, names, button in clicks:
        cmd = "xdotool click --repeat 2 --delay 120 1" if name == "Çift Tık" else xdotool_click(button)
        add(records, "Erişim Fare", name, phrases(names, ["yap", "bas"], limit=30), cmd, f"{name} yapıldı.")

    moves = [
        ("Fare Yukarı Küçük", ["fare yukarı", "imleç yukarı"], "0 -80"),
        ("Fare Aşağı Küçük", ["fare aşağı", "imleç aşağı"], "0 80"),
        ("Fare Sol Küçük", ["fare sola", "imleç sola"], "-- -80 0"),
        ("Fare Sağ Küçük", ["fare sağa", "imleç sağa"], "80 0"),
        ("Fare Yukarı Büyük", ["fare çok yukarı", "imleç çok yukarı"], "0 -240"),
        ("Fare Aşağı Büyük", ["fare çok aşağı", "imleç çok aşağı"], "0 240"),
        ("Fare Sol Büyük", ["fare çok sola", "imleç çok sola"], "-- -240 0"),
        ("Fare Sağ Büyük", ["fare çok sağa", "imleç çok sağa"], "240 0"),
    ]
    for name, names, delta in moves:
        add(records, "Erişim Fare", name, phrases(names, ["git", "kaydır", "hareket et"], limit=36),
            f"xdotool mousemove_relative {delta}", "Fare hareket etti.")

    add(records, "Erişim Fare", "Teker Aşağı",
        phrases(["teker aşağı", "sayfa teker aşağı", "mouse aşağı"], ["çevir", "kaydır"], limit=36),
        "xdotool click 5", "Teker aşağı çevrildi.")
    add(records, "Erişim Fare", "Teker Yukarı",
        phrases(["teker yukarı", "sayfa teker yukarı", "mouse yukarı"], ["çevir", "kaydır"], limit=36),
        "xdotool click 4", "Teker yukarı çevrildi.")


def build_browser(records: dict[str, dict]) -> None:
    browser_keys = [
        ("Adres Çubuğu", ["adres çubuğu", "url çubuğu", "site adresi"], "ctrl+l"),
        ("Yeni Sekme", ["yeni sekme", "sekme aç"], "ctrl+t"),
        ("Sekmeyi Kapat", ["sekmeyi kapat", "bu sekmeyi kapat"], "ctrl+w"),
        ("Kapalı Sekmeyi Aç", ["kapalı sekmeyi aç", "son sekmeyi geri getir"], "ctrl+shift+t"),
        ("Yeni Pencere", ["yeni pencere", "tarayıcı penceresi aç"], "ctrl+n"),
        ("Gizli Pencere", ["gizli pencere", "inkognito", "özel pencere"], "ctrl+shift+n"),
        ("Geri", ["geri git", "önceki sayfa", "tarayıcı geri"], "alt+Left"),
        ("İleri", ["ileri git", "sonraki sayfa", "tarayıcı ileri"], "alt+Right"),
        ("Yenile", ["yenile", "sayfayı yenile", "refresh"], "ctrl+r"),
        ("Sert Yenile", ["sert yenile", "önbelleksiz yenile"], "ctrl+shift+r"),
        ("Yakınlaştır", ["yakınlaştır", "zoom yap", "büyüt"], "ctrl+plus"),
        ("Uzaklaştır", ["uzaklaştır", "zoom azalt", "küçült"], "ctrl+minus"),
        ("Zoom Sıfırla", ["zoom sıfırla", "yakınlaştırmayı sıfırla"], "ctrl+0"),
        ("Yer İmi", ["yer imlerine ekle", "favorilere ekle"], "ctrl+d"),
    ]
    for name, names, key in browser_keys:
        add(records, "Erişim Tarayıcı", name, phrases(names, ["yap", "aç", "bas"], limit=36), xdotool_key(key), f"{name} uygulandı.")

    scrolls = [
        ("Sayfa Aşağı", ["aşağı kaydır", "sayfayı aşağı kaydır", "aşağı in"], "xdotool key Down Down Down"),
        ("Sayfa Yukarı", ["yukarı kaydır", "sayfayı yukarı kaydır", "yukarı çık"], "xdotool key Up Up Up"),
        ("Sayfa En Alt", ["en alta in", "sayfanın sonuna git"], xdotool_key("End")),
        ("Sayfa En Üst", ["en üste çık", "sayfanın başına git"], xdotool_key("Home")),
    ]
    for name, names, cmd in scrolls:
        add(records, "Erişim Tarayıcı", name, phrases(names, ["git", "hareket et"], limit=36), cmd, f"{name} uygulandı.")


def build_windows_media(records: dict[str, dict]) -> None:
    window_keys = [
        ("Pencere Büyüt", ["pencereyi büyüt", "tam ekran yap", "maksimize et"], "alt+F10"),
        ("Pencere Küçült", ["pencereyi küçült", "minimize et"], "alt+F9"),
        ("Masaüstünü Göster", ["masaüstünü göster", "pencereleri gizle"], "super+d"),
        ("Uygulama Menüsü", ["uygulama menüsü", "başlat menüsü", "arama menüsü"], "super"),
    ]
    for name, names, key in window_keys:
        add(records, "Erişim Pencere", name, phrases(names, ["yap", "aç"], limit=36), xdotool_key(key), f"{name} uygulandı.")

    media_keys = [
        ("Oynat Duraklat", ["oynat", "duraklat", "devam et", "müziği duraklat"], "XF86AudioPlay"),
        ("Medya Durdur", ["medyayı durdur", "müziği durdur"], "XF86AudioStop"),
        ("Sonraki Parça", ["sonraki parça", "sonraki şarkı"], "XF86AudioNext"),
        ("Önceki Parça", ["önceki parça", "önceki şarkı"], "XF86AudioPrev"),
        ("Ses Aç", ["sesi aç", "ses yükselt", "biraz ses ver"], "XF86AudioRaiseVolume"),
        ("Ses Kıs", ["sesi kıs", "ses azalt"], "XF86AudioLowerVolume"),
        ("Sessiz", ["sessize al", "sesi kapat"], "XF86AudioMute"),
        ("Parlaklık Aç", ["parlaklığı artır", "ekranı aydınlat"], "XF86MonBrightnessUp"),
        ("Parlaklık Kıs", ["parlaklığı azalt", "ekranı karart"], "XF86MonBrightnessDown"),
    ]
    for name, names, key in media_keys:
        add(records, "Erişim Medya", name, phrases(names, ["yap", "bas"], limit=36), xdotool_key(key), f"{name} uygulandı.")


def service_url(service: str, url: str) -> tuple[str, str]:
    return service, f"xdg-open '{url}'"


def build_services(records: dict[str, dict]) -> None:
    services = [
        service_url("YouTube", "https://www.youtube.com"),
        service_url("Netflix", "https://www.netflix.com"),
        service_url("Prime Video", "https://www.primevideo.com"),
        service_url("Disney Plus", "https://www.disneyplus.com"),
        service_url("JustWatch", "https://www.justwatch.com/tr"),
        service_url("IMDB", "https://www.imdb.com"),
        service_url("Google", "https://www.google.com"),
        service_url("Wikipedia", "https://tr.wikipedia.org"),
        service_url("Reddit", "https://www.reddit.com"),
        service_url("Ekşi Sözlük", "https://eksisozluk.com"),
        service_url("Donanım Haber", "https://forum.donanimhaber.com"),
        service_url("Technopat", "https://www.technopat.net/sosyal"),
        service_url("ShiftDelete", "https://forum.shiftdelete.net"),
        service_url("WhatsApp Web", "https://web.whatsapp.com"),
        service_url("Telegram Web", "https://web.telegram.org"),
        service_url("Gmail", "https://mail.google.com"),
        service_url("Outlook", "https://outlook.live.com/mail"),
        service_url("Google Drive", "https://drive.google.com"),
        service_url("Google Docs", "https://docs.google.com"),
        service_url("Google Maps", "https://maps.google.com"),
        service_url("Spotify", "https://open.spotify.com"),
        service_url("GitHub", "https://github.com"),
        service_url("Stack Overflow", "https://stackoverflow.com"),
        service_url("ChatGPT", "https://chatgpt.com"),
        service_url("Trendyol", "https://www.trendyol.com"),
        service_url("Hepsiburada", "https://www.hepsiburada.com"),
        service_url("Amazon Türkiye", "https://www.amazon.com.tr"),
        service_url("Sahibinden", "https://www.sahibinden.com"),
        service_url("E Devlet", "https://www.turkiye.gov.tr"),
        service_url("MHRS", "https://www.mhrs.gov.tr"),
        service_url("E Nabız", "https://enabiz.gov.tr"),
        service_url("Hürriyet", "https://www.hurriyet.com.tr"),
        service_url("Sözcü", "https://www.sozcu.com.tr"),
        service_url("BBC Türkçe", "https://www.bbc.com/turkce"),
        service_url("NTV", "https://www.ntv.com.tr"),
        service_url("Habertürk", "https://www.haberturk.com"),
        service_url("Mynet", "https://www.mynet.com"),
        service_url("Onedio", "https://onedio.com"),
        service_url("Webtekno", "https://www.webtekno.com"),
        service_url("Chip", "https://www.chip.com.tr"),
        service_url("LinkedIn", "https://www.linkedin.com"),
        service_url("X Twitter", "https://x.com"),
        service_url("Facebook", "https://www.facebook.com"),
        service_url("Instagram", "https://www.instagram.com"),
        service_url("Twitch", "https://www.twitch.tv"),
        service_url("Kick", "https://kick.com"),
        service_url("Udemy", "https://www.udemy.com"),
        service_url("Coursera", "https://www.coursera.org"),
        service_url("Khan Academy", "https://tr.khanacademy.org"),
        service_url("Duolingo", "https://www.duolingo.com"),
        service_url("Medium", "https://medium.com"),
        service_url("Quora", "https://www.quora.com"),
        service_url("Steam", "https://store.steampowered.com"),
        service_url("Epic Games", "https://store.epicgames.com/tr"),
        service_url("Booking", "https://www.booking.com"),
        service_url("Yemeksepeti", "https://www.yemeksepeti.com"),
        service_url("Getir", "https://getir.com"),
        service_url("N11", "https://www.n11.com"),
        service_url("Akakçe", "https://www.akakce.com"),
        service_url("Cimri", "https://www.cimri.com"),
        service_url("PttAVM", "https://www.pttavm.com"),
        service_url("Canlı TV", "https://www.canlitv.com"),
        service_url("TRT İzle", "https://www.trtizle.com"),
        service_url("BluTV", "https://www.blutv.com"),
        service_url("Exxen", "https://www.exxen.com"),
        service_url("Mubi", "https://mubi.com/tr"),
        service_url("PuhuTV", "https://puhutv.com"),
        service_url("TV Plus", "https://www.tvplus.com.tr"),
    ]
    for service, cmd in services:
        names = [service.lower(), f"{service.lower()} aç", f"{service.lower()} sitesine git"]
        add(records, "Erişim Web Servis", service, phrases(names, ["aç", "git", "başlat"], limit=42), cmd, f"{service} açılıyor.")

    search_targets = [
        ("YouTube Ara", "youtube", "https://www.youtube.com/results?search_query={q}",
         ["youtube ara", "youtube'da ara", "youtube da ara", "video ara", "şarkı ara"]),
        ("Google Ara", "google", "https://www.google.com/search?q={q}",
         ["google ara", "internette ara", "webde ara", "arama yap"]),
        ("Wikipedia Ara", "vikipedi", "https://tr.wikipedia.org/w/index.php?search={q}",
         ["vikipedi ara", "wikipedia ara", "ansiklopedide ara"]),
        ("IMDB Ara", "imdb", "https://www.imdb.com/find/?q={q}",
         ["imdb ara", "film bilgisi ara", "oyuncu ara"]),
        ("JustWatch Ara", "justwatch", "https://www.justwatch.com/tr/arama?q={q}",
         ["film nerede ara", "dizi nerede ara", "justwatch ara"]),
        ("Reddit Ara", "reddit", "https://www.reddit.com/search/?q={q}",
         ["reddit ara", "reddit'te ara", "forumlarda ara"]),
        ("Ekşi Sözlük Ara", "ekşi", "https://eksisozluk.com/?q={q}",
         ["ekşi ara", "sözlükte ara", "başlık ara"]),
    ]
    samples = [
        "film", "dizi", "müzik", "haber", "yorum", "konu", "yardım", "inceleme",
        "fragman", "belgesel", "komedi", "aksiyon", "bilim kurgu", "dram", "korku",
        "romantik komedi", "yerli film", "yabancı film", "en iyi filmler", "yeni diziler",
        "bugünkü haberler", "son dakika", "teknoloji haberleri", "sağlık haberleri",
        "spor haberleri", "ekonomi haberleri", "hava durumu", "borsa", "dolar",
        "altın", "kripto", "bitcoin", "yapay zeka", "python", "linux", "windows",
        "android", "iphone", "erişilebilirlik", "sesli kontrol", "forum konusu",
        "şikayet", "çözüm", "nasıl yapılır", "kurulum", "hata çözümü", "oyun",
        "oyun inceleme", "araba", "emlak", "kiralık ev", "satılık araba", "doktor",
        "hastane", "randevu", "ilaç", "tarif", "yemek tarifi", "alışveriş",
        "indirim", "kupon", "kargo takip", "harita", "yol tarifi", "otobüs",
        "uçak bileti", "otel", "tatil", "eğitim", "kurs", "ingilizce",
        "çeviri", "makale", "kitap", "sesli kitap", "podcast", "canlı yayın",
        "maç özeti", "futbol", "basketbol", "fenerbahçe", "galatasaray",
        "beşiktaş", "trabzonspor", "satranç", "not alma", "mail yazma",
        "forum yorumu", "sosyal medya", "iş ilanı", "cv hazırlama", "vergi",
        "sgk", "e devlet", "mhrs", "e nabız", "banka", "fatura ödeme",
        "elektrik faturası", "su faturası", "internet faturası", "telefon faturası",
        "youtube müzik", "spotify liste", "netflix film", "prime video dizi",
        "disney plus film", "imdb puanı", "justwatch nerede", "reddit tartışma",
        "ekşi başlık", "donanım haber konu", "technopat sorun", "github proje",
        "stackoverflow hata", "chatgpt soru", "harici disk", "yazıcı", "kamera",
        "mikrofon", "bluetooth", "wifi", "modem", "tarayıcı ayarları",
    ]
    for label, key, template, bases in search_targets:
        for sample in samples:
            url = template.format(q=quote_plus(sample))
            name = f"{label} {sample.title()}"
            trig = []
            for base in bases:
                trig.extend([
                    f"{base} {sample}", f"{sample} {base}", f"{sample} için {base}",
                    f"{sample} hakkında {base}", f"{sample} bul", f"{sample} aç",
                    f"{sample} göster", f"{sample} sonuçlarını aç",
                ])
            add(records, "Erişim Web Arama", name, trig, f"xdg-open '{url}'", f"{key} araması açılıyor.")


def build_app_launchers(records: dict[str, dict]) -> None:
    apps = [
        ("Terminal", ["terminal", "komut satırı", "uçbirim"], "gnome-terminal || xterm || konsole"),
        ("Dosya Yöneticisi", ["dosya yöneticisi", "dosyalar", "klasörler"], "xdg-open ."),
        ("Hesap Makinesi", ["hesap makinesi", "calculator"], "gnome-calculator || kcalc || galculator"),
        ("Metin Editörü", ["metin editörü", "not defteri", "yazı editörü"], "gedit || kate || mousepad || pluma"),
        ("VLC", ["vlc", "video oynatıcı", "film oynatıcı"], "vlc"),
        ("Ayarlar", ["ayarlar", "sistem ayarları"], "gnome-control-center || systemsettings"),
        ("Ekran Ayarları", ["ekran ayarları", "monitör ayarları"], "gnome-control-center display || systemsettings kcm_kscreen"),
        ("Ses Ayarları", ["ses ayarları", "mikrofon ayarları"], "gnome-control-center sound || pavucontrol"),
        ("Bluetooth Ayarları", ["bluetooth ayarları", "bluetooth"], "gnome-control-center bluetooth || blueman-manager"),
        ("Ağ Ayarları", ["ağ ayarları", "wifi ayarları", "internet ayarları"], "gnome-control-center wifi || nm-connection-editor"),
    ]
    for name, names, cmd in apps:
        add(records, "Erişim Uygulama", name, phrases(names, ["aç", "başlat", "çalıştır", "getir"], limit=54), cmd, f"{name} açılıyor.")


def build_workflow_shortcuts(records: dict[str, dict]) -> None:
    workflows = [
        ("Yorum Yazmaya Hazırla", ["yorum yazmaya hazırlan", "yorum kutusunu aç", "cevap yazmaya hazırlan"],
         "xdotool key ctrl+f && xdotool type --clearmodifiers 'yorum'"),
        ("Mail Yazmaya Hazırla", ["mail yazmaya hazırlan", "e posta yazmaya hazırlan"],
         "xdg-open 'https://mail.google.com/mail/u/0/#inbox?compose=new'"),
        ("Film Arama Masası", ["film arama masası aç", "film bulmaya hazırlan", "ne izleyeceğimi bul"],
         "xdg-open 'https://www.justwatch.com/tr'"),
        ("Forum Yazma Masası", ["forum yazmaya hazırlan", "konu açmaya hazırlan", "foruma yazacağım"],
         "xdg-open 'https://www.reddit.com'"),
        ("Haber Masası", ["haber masası aç", "gündemi aç", "haberleri sırala"],
         "xdg-open 'https://news.google.com/topstories?hl=tr&gl=TR&ceid=TR:tr'"),
        ("Alışveriş Masası", ["alışveriş masası aç", "ürün araştırmaya hazırlan"],
         "xdg-open 'https://www.akakce.com'"),
        ("Sağlık Masası", ["sağlık masası aç", "randevu ve sağlık aç"],
         "xdg-open 'https://www.mhrs.gov.tr'"),
        ("Resmi İşler Masası", ["resmi işler masası aç", "devlet işleri aç"],
         "xdg-open 'https://www.turkiye.gov.tr'"),
    ]
    for name, names, cmd in workflows:
        add(records, "Erişim İş Akışı", name, phrases(names, ["aç", "başlat", "hazırla"], limit=54), cmd, f"{name} açılıyor.")


def build_text_form_helpers(records: dict[str, dict]) -> None:
    helpers = [
        ("Form Gönder", ["formu gönder", "gönder tuşuna bas", "yorumu gönder", "mesajı gönder"], xdotool_key("ctrl+Return")),
        ("Satır Sonu", ["yeni satır", "alt satıra geç", "satır atla"], xdotool_key("Return")),
        ("Alan Temizle", ["alanı temizle", "kutuyu temizle", "yazıyı sil"], "xdotool key ctrl+a BackSpace"),
        ("Yorum Alanı Bul", ["yorum alanını bul", "yorum kutusuna git", "cevap kutusuna git"], xdotool_key("ctrl+f")),
        ("Okumayı Başlat", ["sayfayı oku", "ekranı oku", "görünen yazıyı oku"], "printf 'Okuma komutu web katmanında işlenir.\\n'"),
    ]
    for name, names, cmd in helpers:
        add(records, "Erişim Yazı Form", name, phrases(names, ["yap", "başlat"], limit=36), cmd, f"{name} uygulandı.")


def enrich_voice_variants(records: dict[str, dict], limit: int = 72) -> None:
    prefixes = ["zihin", "bilgisayar", "asistan", "hemen", "şimdi", "lütfen"]
    suffixes = ["lütfen", "hemen", "şimdi", "yapar mısın", "yapabilir misin", "rica etsem"]
    for record in records.values():
        base = record.get("tetikleyiciler", [])
        expanded: list[str] = []
        for item in base:
            expanded.append(item)
            for prefix in prefixes:
                expanded.append(f"{prefix} {item}")
            for suffix in suffixes:
                expanded.append(f"{item} {suffix}")
            expanded.append(f"bana {item}")
            expanded.append(f"hadi {item}")
            expanded.append(f"{item} komutunu çalıştır")
        record["tetikleyiciler"] = uniq(expanded, limit)


def main() -> None:
    data = json.loads(DB.read_text(encoding="utf-8"))
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"komutlar_json_erisim_once_{stamp}.json"
    shutil.copy2(DB, backup)

    kept = {k: v for k, v in data.items() if not k.startswith(PREFIX)}
    records: dict[str, dict] = {}
    build_keyboard(records)
    build_mouse(records)
    build_browser(records)
    build_windows_media(records)
    build_services(records)
    build_app_launchers(records)
    build_workflow_shortcuts(records)
    build_text_form_helpers(records)
    enrich_voice_variants(records)

    kept.update(records)
    kept["__meta__"] = data.get("__meta__", {})
    kept["__meta__"]["erisim_komut_uretici"] = {
        "son_uretim": stamp,
        "eklenen_erisim_kaydi": len(records),
        "eklenen_erisim_tetikleyici": sum(len(r["tetikleyiciler"]) for r in records.values()),
        "yedek": str(backup.relative_to(ROOT)),
    }

    DB.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total_triggers = sum(len(v.get("tetikleyiciler", [])) for k, v in kept.items() if not k.startswith("__"))
    print(f"Yedek: {backup}")
    print(f"Erişim kaydı: {len(records)}")
    print(f"Toplam kayıt: {sum(1 for k in kept if not k.startswith('__'))}")
    print(f"Toplam tetikleyici: {total_triggers}")


if __name__ == "__main__":
    main()
