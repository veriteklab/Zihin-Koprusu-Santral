"""
Zihin Köprüsü v7.0 – Web & PC Tam Kontrol Modülü

İki katmanlı kontrol:
  1. xdotool (hafif) — mevcut tarayıcıyı kontrol, klavye/fare simülasyonu
  2. Playwright (güçlü) — tam tarayıcı otomasyonu, form, yorum, OCR entegrasyonu

Özellikler:
  - Sesli komutla web gezme, tıklama, form doldurma
  - Haber okuma (metin çıkarma, sesli okuma)
  - Forum yorum yapma, beğenme
  - E-Arşiv / fatura sitesi otomasyonu
  - OCR ile ekrandaki metni okuma (tesseract)
  - Tam klavye + fare kontrolü (yerel ve uzuv)
  - Ayarlar GUI'den özelleştirilebilir

Kullanım:
  web = WebKontrolcu(logcu, ses_motoru)
  web.baslat()                        # Playwright başlat
  web.git("https://example.com")
  web.ara("günlük haber")
  web.tikla("Giriş Yap")
  web.yaz_ve_gonder(alan, metin)
  web.ekran_oku()                     # OCR
  web.kapat()

"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

from .logcu import Logcu

KAYNAK = "WEB"


class WebKontrolcu:
    def __init__(self, logcu: Logcu, ses_motoru=None):
        self.log = logcu
        self.ses = ses_motoru
        self._sayfa = None
        self._tarayici = None
        self._playwright = None
        self._aktif = False
        self._mod = "xdotool"       # "xdotool" | "playwright"
        self._gorunur = True        # Tarayıcı görünür mü (headless)
        self._varsayilan_tarayici = "chromium"  # chromium|firefox|webkit
        self._durum_dinleyiciler: list[Callable[[str], None]] = []
        self._xdotool_var = shutil.which("xdotool") is not None
        self._tesseract_var = shutil.which("tesseract") is not None
        self._ekran_araclari = [
            ["gnome-screenshot", "-f"],
            ["scrot"],
            ["import", "-window", "root"],
        ]

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

    # ── Mod & Ayarlar ────────────────────────────────────────────────────────

    def mod_ayarla(self, mod: str):
        """'xdotool' veya 'playwright'"""
        self._mod = mod
        self._bildir(f"Web kontrol modu: {mod}")

    def gorunurluk_ayarla(self, gorunur: bool):
        self._gorunur = gorunur

    def tarayici_ayarla(self, tarayici: str):
        """chromium | firefox | webkit"""
        self._varsayilan_tarayici = tarayici

    # ── Playwright Başlat / Kapat ─────────────────────────────────────────────

    def baslat(self) -> bool:
        """Playwright tarayıcısını başlat."""
        if self._aktif:
            return True
        try:
            from playwright.sync_api import sync_playwright
            self._playwright_ctx = sync_playwright().__enter__()
            tarayici_fab = getattr(
                self._playwright_ctx, self._varsayilan_tarayici)
            self._tarayici = tarayici_fab.launch(
                headless=not self._gorunur,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
                     if self._varsayilan_tarayici == "chromium" else [],
            )
            self._sayfa = self._tarayici.new_page()
            self._sayfa.set_default_timeout(15000)
            self._aktif = True
            self._bildir(
                f"Playwright başladı ({self._varsayilan_tarayici}, "
                f"{'görünür' if self._gorunur else 'arka plan'})")
            return True
        except ImportError:
            self.log.uyari(KAYNAK,
                "playwright kurulu değil: pip install playwright && "
                "playwright install chromium")
            return False
        except Exception as e:
            self.log.hata(KAYNAK, f"Playwright başlatma hatası: {e}")
            return False

    def kapat(self):
        try:
            if self._tarayici:
                self._tarayici.close()
            if getattr(self, '_playwright_ctx', None):
                self._playwright_ctx.__exit__(None, None, None)
        except Exception:
            pass
        self._aktif = False
        self._sayfa = None
        self._bildir("Playwright kapatıldı.")

    # ── Ana Web İşlemleri ────────────────────────────────────────────────────

    def git(self, url: str) -> str:
        """URL'ye git."""
        if not url.startswith("http"):
            url = "https://" + url

        if self._mod == "playwright" and self._playwright_baslat_gerekirse():
            try:
                self._sayfa.goto(url, wait_until="domcontentloaded")
                baslik = self._sayfa.title()
                self._bildir(f"Gezildi: {baslik}")
                return f"Açıldı: {baslik}"
            except Exception as e:
                self.log.uyari(KAYNAK, f"Playwright git hatası: {e}")

        # xdotool fallback
        subprocess.Popen(["xdg-open", url])
        return f"Açılıyor: {url}"

    def ara(self, sorgu: str, motor: str = "google") -> str:
        """Web'de arama yap."""
        import urllib.parse
        motorlar = {
            "google":    f"https://www.google.com/search?q={urllib.parse.quote(sorgu)}",
            "youtube":   f"https://www.youtube.com/results?search_query={urllib.parse.quote(sorgu)}",
            "wikipedia": f"https://tr.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(sorgu)}",
            "duckduckgo":f"https://duckduckgo.com/?q={urllib.parse.quote(sorgu)}",
        }
        url = motorlar.get(motor.lower(), motorlar["google"])
        return self.git(url)

    def tikla(self, hedef: str) -> str:
        """
        Sayfada metni bul ve tıkla.
        Playwright: selector veya metin ile tıkla
        xdotool: pencere içinde ara
        """
        if self._mod == "playwright" and self._aktif and self._sayfa:
            sonuc = self._playwright_hedefe_tikla(hedef)
            if sonuc:
                return sonuc

        ocr_sonuc = self.ekranda_metne_tikla(hedef)
        if not ocr_sonuc.startswith("OCR"):
            return ocr_sonuc
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "Return"], check=False)
            return f"Enter'a basıldı ({hedef} için)"
        return "Tıklama aracı bulunamadı."

    def yaz(self, metin: str, alan: str = "") -> str:
        """Alana metin yaz."""
        if self._mod == "playwright" and self._aktif and self._sayfa:
            try:
                if alan:
                    sonuc = self.alana_yaz(alan, metin)
                    if sonuc:
                        return sonuc
                else:
                    self._sayfa.keyboard.type(metin, delay=30)
                return f"Yazıldı: {metin[:50]}"
            except Exception as e:
                self.log.uyari(KAYNAK, f"Yazma hatası: {e}")

        # xdotool fallback
        if self._xdotool_var:
            subprocess.run([
                "xdotool", "type", "--clearmodifiers",
                "--delay", "30", metin])
            return f"Yazıldı: {metin[:50]}"
        return "Yazma aracı bulunamadı."

    def kaydır(self, yon: str = "asagi", miktar: int = 3) -> str:
        """Sayfayı kaydır."""
        if self._mod == "playwright" and self._aktif and self._sayfa:
            delta = 300 * miktar if yon == "asagi" else -300 * miktar
            try:
                self._sayfa.mouse.wheel(0, delta)
                return f"Kaydırıldı: {yon}"
            except Exception:
                pass

        if self._xdotool_var:
            tus = "Down" if yon == "asagi" else "Up"
            for _ in range(miktar):
                subprocess.run(["xdotool", "key", tus], check=False)
                time.sleep(0.05)
        return f"Kaydırıldı: {yon}"

    def geri_git(self) -> str:
        if self._aktif and self._sayfa:
            try:
                self._sayfa.go_back()
                return "Geri gidildi."
            except Exception:
                pass
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "alt+Left"], check=False)
        return "Geri gidildi."

    def ileri_git(self) -> str:
        if self._aktif and self._sayfa:
            try:
                self._sayfa.go_forward()
                return "İleri gidildi."
            except Exception:
                pass
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "alt+Right"], check=False)
        return "İleri gidildi."

    def yenile(self) -> str:
        if self._aktif and self._sayfa:
            try:
                self._sayfa.reload()
                return "Sayfa yenilendi."
            except Exception:
                pass
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "F5"], check=False)
        return "Sayfa yenilendi."

    def yeni_sekme(self, url: str = "") -> str:
        if self._aktif and self._tarayici:
            try:
                self._sayfa = self._tarayici.new_page()
                if url:
                    return self.git(url)
                return "Yeni sekme açıldı."
            except Exception as e:
                return f"Hata: {e}"
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "ctrl+t"], check=False)
        return "Yeni sekme açıldı."

    # ── Haber Okuma ──────────────────────────────────────────────────────────

    def haber_oku(self, url: str = "") -> str:
        """
        Sayfadaki ana içeriği çıkar, sesli oku.
        Playwright kullanır — JS render'ı bekler.
        """
        if url:
            self.git(url)

        if not (self._aktif and self._sayfa):
            return "Playwright aktif değil."

        try:
            # Ana içerik alanlarını dene
            for selector in [
                "article", "main", ".article-content",
                ".news-content", "#content", ".content",
                "p"
            ]:
                try:
                    icerik = self._sayfa.locator(selector).first.inner_text()
                    if len(icerik) > 100:
                        # İlk 500 kelime
                        kelimeler = icerik.split()[:500]
                        ozet = " ".join(kelimeler)
                        ozet = self._turkce_metne_cevir(ozet)
                        self._bildir(f"Haber okundu: {len(kelimeler)} kelime")
                        if self.ses:
                            threading.Thread(
                                target=self.ses.konus,
                                args=("ABLA", ozet[:800]),
                                daemon=True
                            ).start()
                        return ozet
                except Exception:
                    continue
            return "İçerik çıkarılamadı."
        except Exception as e:
            return f"Haber okuma hatası: {e}"

    def sayfa_metni_al(self) -> str:
        """Tüm sayfa metnini al."""
        if self._aktif and self._sayfa:
            try:
                return self._turkce_metne_cevir(self._sayfa.inner_text("body")[:2000])
            except Exception:
                pass
        return ""

    def sayfa_elemanlari_listele(self, limit: int = 80) -> list[dict]:
        """Görünen tıklanabilir/form öğelerinin kısa erişim dökümünü çıkar."""
        if not (self._aktif and self._sayfa):
            return []
        script = """
        (limit) => {
          const selectors = [
            'a', 'button', 'input', 'textarea', 'select',
            '[role=button]', '[role=link]', '[role=menuitem]',
            '[contenteditable=true]', '[aria-label]', '[title]'
          ];
          const seen = new Set();
          const items = [];
          const labelFor = (el) => {
            if (!el.id) return '';
            const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
            return label ? label.innerText.trim() : '';
          };
          for (const el of document.querySelectorAll(selectors.join(','))) {
            if (items.length >= limit) break;
            const rect = el.getBoundingClientRect();
            if (rect.width < 2 || rect.height < 2) continue;
            const style = window.getComputedStyle(el);
            if (style.visibility === 'hidden' || style.display === 'none') continue;
            const key = `${Math.round(rect.x)}:${Math.round(rect.y)}:${el.tagName}:${el.innerText}`;
            if (seen.has(key)) continue;
            seen.add(key);
            const text = [
              el.innerText, el.value, el.getAttribute('aria-label'),
              el.getAttribute('placeholder'), el.getAttribute('title'),
              el.getAttribute('name'), labelFor(el)
            ].filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim();
            items.push({
              tag: el.tagName.toLowerCase(),
              role: el.getAttribute('role') || '',
              text: text.slice(0, 160),
              x: Math.round(rect.x + rect.width / 2),
              y: Math.round(rect.y + rect.height / 2)
            });
          }
          return items;
        }
        """
        try:
            return self._sayfa.evaluate(script, limit) or []
        except Exception as e:
            self.log.uyari(KAYNAK, f"Sayfa elemanları alınamadı: {e}")
            return []

    def sayfa_elemanlari_oku(self) -> str:
        elemanlar = self.sayfa_elemanlari_listele(limit=40)
        if not elemanlar:
            return "Etkileşimli öğe bulunamadı."
        satirlar = []
        for i, e in enumerate(elemanlar, 1):
            ad = e.get("text") or e.get("tag") or "öğe"
            satirlar.append(f"{i}. {ad[:80]}")
        metin = "\n".join(satirlar)
        metin = self._turkce_metne_cevir(metin)
        if self.ses:
            threading.Thread(
                target=self.ses.konus,
                args=("ABLA", ". ".join(satirlar[:12])),
                daemon=True,
            ).start()
        return metin

    # ── Form & Yorum ─────────────────────────────────────────────────────────

    def form_doldur(self, alanlar: dict[str, str]) -> str:
        """
        Form alanlarını doldur.
        alanlar = {"#username": "faruk", "#password": "..."}
        """
        if not (self._aktif and self._sayfa):
            return "Playwright gerekli."
        try:
            for selector, deger in alanlar.items():
                self._sayfa.locator(selector).fill(deger)
                time.sleep(0.2)
            return f"{len(alanlar)} alan dolduruldu."
        except Exception as e:
            return f"Form hatası: {e}"

    def alana_yaz(self, alan: str, metin: str) -> str:
        """Etiket/placeholder/aria/selector ile form alanı bulup doldur."""
        if not (self._aktif and self._sayfa):
            return "Playwright gerekli."
        locator = self._playwright_alan_bul(alan)
        if locator:
            try:
                locator.fill(metin)
                return f"{alan} alanına yazıldı: {metin[:50]}"
            except Exception:
                try:
                    locator.click()
                    self._sayfa.keyboard.press("Control+A")
                    self._sayfa.keyboard.type(metin, delay=30)
                    return f"{alan} alanına yazıldı: {metin[:50]}"
                except Exception as e:
                    self.log.uyari(KAYNAK, f"Alan yazma hatası: {e}")
        return self.yaz(metin)

    def yorum_yap(self, yorum_metni: str,
                  alan_selector: str = "textarea") -> str:
        """Forum/haber sitesinde yorum yap."""
        if not (self._aktif and self._sayfa):
            return "Playwright gerekli."
        try:
            locator = None
            for hedef in ("yorum", "cevap", "comment", "reply"):
                locator = self._playwright_alan_bul(hedef)
                if locator:
                    break
            if not locator:
                for selector in [
                    alan_selector,
                    "textarea",
                    "[contenteditable=true]",
                    "input[type=text]",
                    "[role=textbox]",
                ]:
                    try:
                        aday = self._sayfa.locator(selector).first
                        if aday.count() > 0 and aday.is_visible():
                            locator = aday
                            break
                    except Exception:
                        continue
            if not locator:
                return "Yorum alanı bulunamadı."
            try:
                locator.fill(yorum_metni)
            except Exception:
                locator.click()
                self._sayfa.keyboard.type(yorum_metni, delay=30)
            self._bildir(f"Yorum yazıldı: {yorum_metni[:50]}")
            return "Yorum alanına yazıldı. Göndermek için 'gönder' deyin."
        except Exception as e:
            return f"Yorum hatası: {e}"

    def gonder(self) -> str:
        """Form veya yorum gönder."""
        if self._aktif and self._sayfa:
            try:
                # Submit butonunu ara
                for selector in [
                    "button[type=submit]", "input[type=submit]",
                    "button:has-text('Gönder')", "button:has-text('Yorum')",
                    "button:has-text('Kaydet')", "button:has-text('Send')",
                    "button:has-text('Paylaş')", "button:has-text('Cevapla')",
                    "[role=button]:has-text('Gönder')",
                    "[role=button]:has-text('Paylaş')",
                ]:
                    try:
                        self._sayfa.locator(selector).first.click()
                        return "Gönderildi."
                    except Exception:
                        continue
                for ad in ("Gönder", "Paylaş", "Yayınla", "Cevapla", "Send", "Submit", "Post"):
                    sonuc = self._playwright_hedefe_tikla(ad)
                    if sonuc:
                        return "Gönderildi."
            except Exception:
                pass
            try:
                self._sayfa.keyboard.press("Control+Enter")
                return "Ctrl+Enter gönderildi."
            except Exception:
                pass
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", "Return"], check=False)
        return "Enter'a basıldı."

    # ── PC Tam Kontrol ───────────────────────────────────────────────────────

    def fare_tasi(self, x: int, y: int) -> str:
        """Fareyi koordinata taşı."""
        if self._xdotool_var:
            subprocess.run(["xdotool", "mousemove", str(x), str(y)])
            return f"Fare taşındı: ({x}, {y})"
        return "xdotool gerekli."

    def fare_tikla(self, x: int = -1, y: int = -1,
                   dugme: str = "left") -> str:
        """Fareyle tıkla (koordinat veya mevcut konum)."""
        if not self._xdotool_var:
            return "xdotool gerekli."
        if x >= 0 and y >= 0:
            subprocess.run(["xdotool", "mousemove", str(x), str(y)])
            time.sleep(0.1)
        btn = "1" if dugme == "left" else ("3" if dugme == "right" else "2")
        subprocess.run(["xdotool", "click", btn])
        return f"Tıklandı: ({x},{y}) [{dugme}]"

    def fare_cift_tikla(self, x: int, y: int) -> str:
        if self._xdotool_var:
            subprocess.run(["xdotool", "mousemove", str(x), str(y)])
            time.sleep(0.1)
            subprocess.run(["xdotool", "doubleclick", "1"])
            return f"Çift tıklandı: ({x},{y})"
        return "xdotool gerekli."

    def klavye_bas(self, tus: str) -> str:
        """
        Tuş simüle et.
        Örnekler: 'Return', 'ctrl+c', 'ctrl+v', 'alt+F4', 'super'
        """
        if self._xdotool_var:
            subprocess.run(["xdotool", "key", tus])
            return f"Tuş: {tus}"
        return "xdotool gerekli."

    def klavye_yaz(self, metin: str) -> str:
        if self._xdotool_var:
            subprocess.run([
                "xdotool", "type",
                "--clearmodifiers", "--delay", "30", metin])
            return f"Yazıldı: {metin[:50]}"
        return "xdotool gerekli."

    def pencere_listele(self) -> list[dict]:
        """Açık pencereleri listele."""
        if not self._xdotool_var:
            return []
        try:
            r = subprocess.run(
                ["wmctrl", "-l"], capture_output=True, text=True)
            pencereler = []
            for satir in r.stdout.splitlines():
                parcalar = satir.split(None, 3)
                if len(parcalar) >= 4:
                    pencereler.append({
                        "id": parcalar[0],
                        "baslik": parcalar[3],
                    })
            return pencereler
        except Exception:
            return []

    def pencere_odakla(self, baslik: str) -> str:
        """Pencereyi ön plana getir."""
        try:
            subprocess.run(["wmctrl", "-a", baslik], check=False)
            return f"Odaklandı: {baslik}"
        except Exception as e:
            return f"Hata: {e}"

    def pencere_kapat(self, baslik: str) -> str:
        try:
            subprocess.run(["wmctrl", "-c", baslik], check=False)
            return f"Kapatıldı: {baslik}"
        except Exception as e:
            return f"Hata: {e}"

    # ── OCR — Ekrandan Metin Oku ─────────────────────────────────────────────

    def ekran_oku(self, bolge: Optional[tuple] = None) -> str:
        """
        Ekranı veya seçili bölgeyi OCR ile oku.
        bolge = (x, y, genislik, yukseklik) — None ise tüm ekran
        """
        if not self._tesseract_var:
            return "tesseract kurulu değil: sudo apt install tesseract-ocr tesseract-ocr-tur"

        ekran_dosya = "/tmp/zk_ekran_ocr.png"
        try:
            # Ekran görüntüsü al
            if bolge:
                x, y, g, y2 = bolge
                subprocess.run([
                    "import", "-window", "root",
                    "-crop", f"{g}x{y2}+{x}+{y}",
                    ekran_dosya
                ], check=True, capture_output=True)
            else:
                for cmd in [
                    ["gnome-screenshot", "-f", ekran_dosya],
                    ["scrot", ekran_dosya],
                    ["import", "-window", "root", ekran_dosya]
                ]:
                    if shutil.which(cmd[0]):
                        subprocess.run(cmd, capture_output=True)
                        break

            # OCR
            r = subprocess.run(
                ["tesseract", ekran_dosya, "stdout",
                 "-l", "tur+eng", "--psm", "3"],
                capture_output=True, text=True
            )
            metin = r.stdout.strip()
            if metin:
                metin = self._turkce_metne_cevir(metin)
                self._bildir(f"OCR: {len(metin)} karakter okundu")
                return metin
            return "OCR: Metin bulunamadı."
        except Exception as e:
            return f"OCR hatası: {e}"
        finally:
            try:
                os.unlink(ekran_dosya)
            except Exception:
                pass

    def ekranda_metne_tikla(self, hedef: str) -> str:
        """OCR TSV çıktısından hedef metnin yaklaşık koordinatını bulup tıkla."""
        if not hedef.strip():
            return "OCR hedefi boş."
        if not (self._tesseract_var and self._xdotool_var):
            return "OCR tıklama için tesseract ve xdotool gerekli."
        ekran_dosya = "/tmp/zk_ekran_tikla.png"
        tsv_dosya = "/tmp/zk_ekran_tikla.tsv"
        try:
            if not self._ekran_goruntusu_al(ekran_dosya):
                return "OCR ekran görüntüsü alınamadı."
            r = subprocess.run(
                ["tesseract", ekran_dosya, "/tmp/zk_ekran_tikla",
                 "-l", "tur+eng", "--psm", "6", "tsv"],
                capture_output=True, text=True,
            )
            if r.returncode != 0 or not os.path.exists(tsv_dosya):
                return "OCR metin bulunamadı."
            kelimeler = self._ocr_tsv_kelimeler(tsv_dosya)
            hedef_norm = self._norm(hedef)
            hedef_parca = hedef_norm.split()
            if not hedef_parca:
                return "OCR hedefi boş."
            for i in range(len(kelimeler)):
                parca = kelimeler[i:i + len(hedef_parca)]
                metin = self._norm(" ".join(k["text"] for k in parca))
                if metin == hedef_norm or hedef_norm in metin or metin in hedef_norm:
                    x1 = min(k["left"] for k in parca)
                    y1 = min(k["top"] for k in parca)
                    x2 = max(k["left"] + k["width"] for k in parca)
                    y2 = max(k["top"] + k["height"] for k in parca)
                    x = int((x1 + x2) / 2)
                    y = int((y1 + y2) / 2)
                    subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=False)
                    subprocess.run(["xdotool", "click", "1"], check=False)
                    return f"OCR ile tıklandı: {hedef}"
            return f"OCR hedef bulunamadı: {hedef}"
        except Exception as e:
            return f"OCR tıklama hatası: {e}"
        finally:
            for yol in (ekran_dosya, tsv_dosya):
                try:
                    os.unlink(yol)
                except Exception:
                    pass

    def ekran_oku_ve_seslendir(self) -> str:
        """Ekrandaki metni oku ve sesli söyle."""
        metin = self.ekran_oku()
        if metin and self.ses and len(metin) > 5:
            threading.Thread(
                target=self.ses.konus,
                args=("ABLA", metin[:600]),
                daemon=True
            ).start()
        return metin

    # ── Sesli Komut Çözümleyici ──────────────────────────────────────────────

    def sesli_komut_isle(self, metin: str) -> Optional[str]:
        """
        Sesli komuttan web/PC işlemi çıkar.
        Cekirdek'ten gelen metni işler, uygun metodu çağırır.
        """
        ml = metin.lower().strip()

        # Web gezme
        if any(k in ml for k in ["siteye git", "aç", "gir"]):
            import re
            url_m = re.search(
                r"(https?://[^\s]+|www\.[^\s]+|[a-z0-9\-]+\.(com|net|org|io|tr|co)[^\s]*)",
                ml, re.I)
            if url_m:
                return self.git(url_m.group(0))

        # Arama
        if any(k in ml for k in ["ara", "google'da", "internette"]):
            for tetik in ["ara ", "google'da ", "internette ", "araştır "]:
                if tetik in ml:
                    sorgu = ml.split(tetik, 1)[1].strip()
                    return self.ara(sorgu)

        # Kaydırma
        if "aşağı" in ml or "scroll" in ml and "aşağı" in ml:
            return self.kaydır("asagi")
        if "yukarı" in ml:
            return self.kaydır("yukari")

        # Tıklama
        if "tıkla" in ml or "bas " in ml:
            hedef = ml.replace("tıkla", "").replace("bas", "").strip()
            return self.tikla(hedef)

        # Geri/İleri
        if "geri git" in ml or "geri dön" in ml:
            return self.geri_git()
        if "ileri git" in ml:
            return self.ileri_git()

        # Sayfa yenile
        if "yenile" in ml or "yükle" in ml:
            return self.yenile()

        # Haber oku
        if "haber oku" in ml or "sayfayı oku" in ml:
            return self.haber_oku()

        # OCR
        if "ekranı oku" in ml or "ne yazıyor" in ml:
            return self.ekran_oku_ve_seslendir()
        if "neler var" in ml or "öğeleri oku" in ml or "sayfadaki düğmeleri oku" in ml:
            return self.sayfa_elemanlari_oku()

        # Yorum
        if "yorum yap" in ml or "yorum yaz" in ml:
            for tetik in ["yorum yap ", "yorum yaz "]:
                if tetik in ml:
                    icerik = ml.split(tetik, 1)[1].strip()
                    return self.yorum_yap(icerik)

        # Gönder
        if ml in ["gönder", "gönder", "kaydet", "tamam gönder"]:
            return self.gonder()

        return None

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    def _playwright_baslat_gerekirse(self) -> bool:
        """Playwright aktif değilse başlat."""
        if not self._aktif:
            return self.baslat()
        return True

    def _playwright_hedefe_tikla(self, hedef: str) -> str:
        if not hedef.strip():
            return ""
        for frame in self._playwright_frame_listesi():
            for locator in self._playwright_tiklama_adaylari(frame, hedef):
                try:
                    if locator.count() < 1:
                        continue
                    ilk = locator.first
                    ilk.scroll_into_view_if_needed(timeout=3000)
                    ilk.click(timeout=5000)
                    return f"Tıklandı: {hedef}"
                except Exception:
                    continue
        self.log.uyari(KAYNAK, f"Playwright hedef bulamadı: {hedef}")
        return ""

    def _playwright_alan_bul(self, hedef: str):
        hedef = (hedef or "").strip()
        for frame in self._playwright_frame_listesi():
            adaylar = []
            try:
                adaylar.extend([
                    frame.get_by_label(hedef, exact=False),
                    frame.get_by_placeholder(hedef, exact=False),
                    frame.get_by_role("textbox", name=re.compile(re.escape(hedef), re.I)),
                ])
            except Exception:
                pass
            if hedef:
                adaylar.extend([
                    frame.locator(
                        "input, textarea, [contenteditable=true], [role=textbox]"
                    ).filter(has_text=re.compile(re.escape(hedef), re.I)),
                    frame.locator(
                        f"input[aria-label*='{hedef}' i], textarea[aria-label*='{hedef}' i], "
                        f"input[placeholder*='{hedef}' i], textarea[placeholder*='{hedef}' i]"
                    ),
                ])
            adaylar.append(frame.locator("textarea, [contenteditable=true], [role=textbox], input[type=text]").first)
            for locator in adaylar:
                try:
                    if locator.count() > 0 and locator.first.is_visible():
                        locator.first.scroll_into_view_if_needed(timeout=3000)
                        return locator.first
                except Exception:
                    continue
        return None

    def _playwright_tiklama_adaylari(self, frame, hedef: str) -> list:
        escaped = re.escape(hedef)
        regex = re.compile(escaped, re.I)
        adaylar = []
        try:
            adaylar.extend([
                frame.get_by_role("button", name=regex),
                frame.get_by_role("link", name=regex),
                frame.get_by_role("menuitem", name=regex),
                frame.get_by_role("tab", name=regex),
                frame.get_by_text(hedef, exact=False),
                frame.get_by_label(hedef, exact=False),
                frame.get_by_title(regex),
            ])
        except Exception:
            pass
        try:
            adaylar.extend([
                frame.locator(f"[aria-label*='{hedef}' i]"),
                frame.locator(f"[title*='{hedef}' i]"),
                frame.locator(f"a:has-text('{hedef}')"),
                frame.locator(f"button:has-text('{hedef}')"),
                frame.locator(f"[role=button]:has-text('{hedef}')"),
            ])
        except Exception:
            pass
        try:
            adaylar.append(frame.locator(hedef))
        except Exception:
            pass
        return adaylar

    def _playwright_frame_listesi(self):
        if not (self._aktif and self._sayfa):
            return []
        try:
            return [self._sayfa] + list(self._sayfa.frames)
        except Exception:
            return [self._sayfa]

    def _ekran_goruntusu_al(self, hedef: str) -> bool:
        for cmd in self._ekran_araclari:
            if not shutil.which(cmd[0]):
                continue
            try:
                subprocess.run(cmd + [hedef], capture_output=True, timeout=10)
                if os.path.exists(hedef) and os.path.getsize(hedef) > 0:
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _ocr_tsv_kelimeler(tsv_dosya: str) -> list[dict]:
        kelimeler: list[dict] = []
        with open(tsv_dosya, "r", encoding="utf-8", errors="replace") as f:
            baslik = f.readline().strip().split("\t")
            for satir in f:
                parca = satir.rstrip("\n").split("\t")
                if len(parca) != len(baslik):
                    continue
                row = dict(zip(baslik, parca))
                text = row.get("text", "").strip()
                if not text:
                    continue
                try:
                    conf = float(row.get("conf", "-1"))
                    if conf < 25:
                        continue
                    kelimeler.append({
                        "text": text,
                        "left": int(row.get("left", "0")),
                        "top": int(row.get("top", "0")),
                        "width": int(row.get("width", "0")),
                        "height": int(row.get("height", "0")),
                    })
                except Exception:
                    continue
        return kelimeler

    @staticmethod
    def _norm(metin: str) -> str:
        ceviri = str.maketrans({
            "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g",
            "ı": "i", "I": "i", "İ": "i", "ö": "o",
            "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
        })
        temiz = metin.translate(ceviri).lower()
        temiz = re.sub(r"[^a-z0-9]+", " ", temiz)
        return " ".join(temiz.split())

    def _turkce_metne_cevir(self, metin: str) -> str:
        try:
            if self.ses and hasattr(self.ses, "turkce_metne_cevir"):
                return self.ses.turkce_metne_cevir(metin)
        except Exception:
            pass
        return metin

    def durum_al(self) -> dict:
        return {
            "mod":           self._mod,
            "playwright":    self._aktif,
            "xdotool":       self._xdotool_var,
            "tesseract":     self._tesseract_var,
            "gorunur":       self._gorunur,
            "tarayici":      self._varsayilan_tarayici,
            "mevcut_url":    self._sayfa.url if self._aktif and self._sayfa
                             else "",
        }
