"""
Zihin Köprüsü v7.0 – Makro & Rutin Yöneticisi

Özellikler:
  - Makro: Birden fazla komutu sırayla çalıştır
  - Rutin: Belirli saatte/günde otomatik çalışan makrolar
  - Zamanlayıcı: "X dakika sonra hatırlat"
  - Koşullu tetikleyici: CPU > 90%, pil < 15%, internet kesilirse
  - Sesli komutla kayıt: "Bu komutu kaydet", "Sabah rutinini başlat"
  - GUI'den tam CRUD — ekle, düzenle, sil, çalıştır

"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from .logcu import Logcu

KAYNAK = "MAKRO"


class TetikTipi(str, Enum):
    MANUEL     = "manuel"       # Elle çalıştır
    ZAMANLI    = "zamanli"      # Belirli saatte
    ARALIKLI   = "aralikli"     # Her N dakikada
    KOSULLU    = "kosullu"      # CPU/RAM/ağ koşulu
    SESLI      = "sesli"        # Wake word sonrası


class KosulTipi(str, Enum):
    CPU_ASIM     = "cpu_asim"       # CPU % > eşik
    RAM_ASIM     = "ram_asim"       # RAM % > eşik
    PIL_DUSUK    = "pil_dusuk"      # Pil % < eşik
    INTERNET_YOK = "internet_yok"   # Ping başarısız
    INTERNET_VAR = "internet_var"   # Ping başarılı
    SICAKLIK     = "sicaklik"       # Sıcaklık > eşik
    UZUV_CEVRIM = "uzuv_cevrimdisi" # Uzuv bağlantısı kesildi


@dataclass
class MakroAdim:
    tip: str = "komut"        # "komut" | "bekle" | "konusma" | "sesli"
    deger: str = ""           # Komut metni, bekleme süresi (sn), konuşma metni
    timeout: int = 30
    hata_devam: bool = True   # Hata olunca devam et


@dataclass
class Makro:
    id: str
    ad: str
    aciklama: str = ""
    adimlar: list[MakroAdim] = field(default_factory=list)
    tetik_tipi: TetikTipi = TetikTipi.MANUEL
    # Zamanlı tetik
    saat: str = ""            # "07:30"
    gunler: list[int] = field(default_factory=list)  # 0=Pzt..6=Paz
    # Aralıklı tetik
    aralik_dakika: int = 60
    # Koşullu tetik
    kosul_tipi: str = ""
    kosul_esik: float = 80.0
    kosul_uzuv_id: str = ""
    # Sesli tetikleyici kelime
    sesli_kelime: str = ""
    # Durum
    aktif: bool = True
    son_calisma: str = ""
    calisma_sayisi: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["adimlar"] = [asdict(a) for a in self.adimlar]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Makro":
        d = dict(d)
        adimlar_raw = d.pop("adimlar", [])
        m = cls(**{k: v for k, v in d.items()
                   if k in cls.__dataclass_fields__})
        m.adimlar = [MakroAdim(**a) for a in adimlar_raw]
        return m


@dataclass
class Zamanlayici:
    id: str
    ad: str
    bitis: float          # time.time() hedef
    mesaj: str = ""
    tekrar: bool = False
    aralik: float = 0.0   # Tekrar için saniye
    aktif: bool = True


class MakroYoneticisi:
    def __init__(self, logcu: Logcu, veri_dosyasi: str):
        self.log = logcu
        self.veri_dosyasi = veri_dosyasi
        self.makrolar: dict[str, Makro] = {}
        self.zamanlayicilar: dict[str, Zamanlayici] = {}

        self._cekirdek = None         # cekirdek referansı (isle için)
        self._calisıyor = False
        self._izle_thread: Optional[threading.Thread] = None
        self._durum_dinleyiciler: list[Callable[[str, str], None]] = []
        self._bildirim_fn: Optional[Callable[[str], None]] = None

        # Ağ geçmişi (koşul tespiti için)
        self._son_ag_durumu: Optional[bool] = None
        self._son_uzuv_durumlari: dict[str, str] = {}

        self._yukle()

    # ── Dinleyiciler ─────────────────────────────────────────────────────────

    def durum_dinleyici_ekle(self, fn: Callable[[str, str], None]):
        self._durum_dinleyiciler.append(fn)

    def bildirim_fn_ayarla(self, fn: Callable[[str], None]):
        """Sesli bildirim için cekirdek.ses.konus benzeri fonksiyon."""
        self._bildirim_fn = fn

    def cekirdek_ayarla(self, cekirdek):
        self._cekirdek = cekirdek

    def _bildir(self, makro_id: str, mesaj: str):
        self.log.bilgi(KAYNAK, f"[{makro_id}] {mesaj}")
        for fn in self._durum_dinleyiciler:
            try:
                fn(makro_id, mesaj)
            except Exception:
                pass

    # ── Disk ─────────────────────────────────────────────────────────────────

    def _yukle(self):
        if os.path.exists(self.veri_dosyasi):
            try:
                with open(self.veri_dosyasi, encoding="utf-8") as f:
                    veri = json.load(f)
                for mid, d in veri.get("makrolar", {}).items():
                    self.makrolar[mid] = Makro.from_dict(d)
                self.log.bilgi(KAYNAK,
                    f"{len(self.makrolar)} makro yüklendi.")
                if self._hazir_makrolari_tamamla():
                    self.kaydet()
            except Exception as e:
                self.log.hata(KAYNAK, f"Yükleme hatası: {e}")
        else:
            self._varsayilan_yukle()
            self.kaydet()

    def kaydet(self):
        dizin = os.path.dirname(self.veri_dosyasi)
        if dizin:
            os.makedirs(dizin, exist_ok=True)
        with open(self.veri_dosyasi, "w", encoding="utf-8") as f:
            json.dump({
                "makrolar": {
                    mid: m.to_dict()
                    for mid, m in self.makrolar.items()
                }
            }, f, ensure_ascii=False, indent=2)

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def makro_ekle(self, makro: Makro):
        self.makrolar[makro.id] = makro
        self.kaydet()

    def makro_sil(self, mid: str):
        self.makrolar.pop(mid, None)
        self.kaydet()

    def makro_guncelle(self, makro: Makro):
        self.makrolar[makro.id] = makro
        self.kaydet()

    # ── Çalıştır ─────────────────────────────────────────────────────────────

    def calistir(self, mid: str,
                 callback: Optional[Callable[[bool, str], None]] = None):
        """Makroyu arka planda çalıştır."""
        makro = self.makrolar.get(mid)
        if not makro:
            if callback:
                callback(False, f"Makro bulunamadı: {mid}")
            return
        threading.Thread(
            target=self._calistir_thread,
            args=(makro, callback),
            daemon=True
        ).start()

    def _calistir_thread(self, makro: Makro,
                          callback: Optional[Callable]):
        self._bildir(makro.id, f"Başladı: {makro.ad}")
        hatalar = []

        for i, adim in enumerate(makro.adimlar):
            self._bildir(makro.id,
                f"Adım {i+1}/{len(makro.adimlar)}: {adim.tip} — {adim.deger[:50]}")

            try:
                if adim.tip == "komut":
                    import shutil as _sh
                    bash_yolu = _sh.which("bash")
                    r = subprocess.run(
                        adim.deger, shell=True,
                        capture_output=True, text=True,
                        timeout=adim.timeout,
                        **({"executable": bash_yolu} if bash_yolu else {})
                    )
                    if r.returncode != 0 and not adim.hata_devam:
                        hatalar.append(f"Adım {i+1} başarısız")
                        break
                    cikti = (r.stdout + r.stderr).strip()
                    if cikti:
                        self._bildir(makro.id, f"Çıktı: {cikti[:200]}")

                elif adim.tip == "bekle":
                    sure = float(adim.deger)
                    time.sleep(sure)

                elif adim.tip == "konusma":
                    if self._bildirim_fn:
                        self._bildirim_fn(adim.deger)
                        time.sleep(1)  # TTS bitsin

                elif adim.tip == "isle":
                    # cekirdek.isle() ile komut işle
                    if self._cekirdek:
                        self._cekirdek.isle(adim.deger, kanal="makro")

                elif adim.tip == "sesli":
                    # Sesle komut işle (sesin gelmesini bekler)
                    if self._cekirdek:
                        metin = self._cekirdek.ses.dinle()
                        if metin:
                            self._cekirdek.isle(metin, kanal="ses")

            except subprocess.TimeoutExpired:
                hatalar.append(f"Adım {i+1} zaman aşımı")
                if not adim.hata_devam:
                    break
            except Exception as e:
                hatalar.append(f"Adım {i+1}: {e}")
                if not adim.hata_devam:
                    break

        makro.son_calisma = datetime.now().isoformat()
        makro.calisma_sayisi += 1
        self.kaydet()

        basari = len(hatalar) == 0
        mesaj = (f"✓ {makro.ad} tamamlandı."
                 if basari else
                 f"⚠ {makro.ad} hatalarla tamamlandı: {'; '.join(hatalar)}")
        self._bildir(makro.id, mesaj)
        if callback:
            callback(basari, mesaj)

    # ── Zamanlayıcı ──────────────────────────────────────────────────────────

    def zamanlayici_ekle(self, ad: str, sure_dakika: float,
                          mesaj: str = "", tekrar: bool = False,
                          aralik_dakika: float = 0):
        import uuid
        zid = str(uuid.uuid4())[:8]
        z = Zamanlayici(
            id=zid, ad=ad,
            bitis=time.time() + sure_dakika * 60,
            mesaj=mesaj or ad,
            tekrar=tekrar,
            aralik=aralik_dakika * 60,
        )
        self.zamanlayicilar[zid] = z
        self.log.bilgi(KAYNAK,
            f"Zamanlayıcı kuruldu: {ad} — {sure_dakika} dakika sonra")
        return zid

    def zamanlayici_iptal(self, zid: str):
        self.zamanlayicilar.pop(zid, None)

    # ── Arka Plan İzleyici ───────────────────────────────────────────────────

    def baslat(self):
        self._calisıyor = True
        self._izle_thread = threading.Thread(
            target=self._izle_dongusu, daemon=True)
        self._izle_thread.start()
        self.log.bilgi(KAYNAK, "Makro izleyici başladı.")

    def durdur(self):
        self._calisıyor = False

    def _izle_dongusu(self):
        while self._calisıyor:
            simdi = time.time()
            simdi_dt = datetime.now()

            # ── Zamanlayıcılar ────────────────────────────────────────────
            bitmis = []
            for zid, z in list(self.zamanlayicilar.items()):
                if not z.aktif:
                    continue
                if simdi >= z.bitis:
                    self._bildir(zid, f"⏰ {z.mesaj}")
                    if self._bildirim_fn:
                        self._bildirim_fn(z.mesaj)
                    if z.tekrar and z.aralik > 0:
                        z.bitis = simdi + z.aralik
                    else:
                        bitmis.append(zid)
            for zid in bitmis:
                del self.zamanlayicilar[zid]

            # ── Makro Tetikleyiciler ───────────────────────────────────────
            for mid, makro in list(self.makrolar.items()):
                if not makro.aktif:
                    continue

                if makro.tetik_tipi == TetikTipi.ZAMANLI:
                    self._zamanli_kontrol(makro, simdi_dt)
                elif makro.tetik_tipi == TetikTipi.ARALIKLI:
                    self._aralikli_kontrol(makro, simdi)
                elif makro.tetik_tipi == TetikTipi.KOSULLU:
                    self._kosullu_kontrol(makro)

            time.sleep(10)  # 10 saniyede bir kontrol

    def _zamanli_kontrol(self, makro: Makro, simdi: datetime):
        if not makro.saat:
            return
        try:
            h, m = map(int, makro.saat.split(":"))
        except ValueError:
            return

        # Günler kontrolü (0=Pzt..6=Paz)
        if makro.gunler and simdi.weekday() not in makro.gunler:
            return

        # Dakika hassasiyetiyle eşleşme
        if simdi.hour == h and simdi.minute == m:
            # Son çalışmadan bu yana en az 1 dakika geçmiş mi?
            if makro.son_calisma:
                son = datetime.fromisoformat(makro.son_calisma)
                if (simdi - son).total_seconds() < 60:
                    return
            self.calistir(makro.id)

    def _aralikli_kontrol(self, makro: Makro, simdi: float):
        if makro.aralik_dakika <= 0:
            return
        if not makro.son_calisma:
            self.calistir(makro.id)
            return
        son = datetime.fromisoformat(makro.son_calisma).timestamp()
        if simdi - son >= makro.aralik_dakika * 60:
            self.calistir(makro.id)

    def _kosullu_kontrol(self, makro: Makro):
        try:
            if makro.kosul_tipi == KosulTipi.CPU_ASIM:
                cpu = self._cpu_al()
                if cpu > makro.kosul_esik:
                    self._tetikle_kosullu(makro,
                        f"CPU {cpu:.1f}% — eşik aşıldı!")

            elif makro.kosul_tipi == KosulTipi.RAM_ASIM:
                ram = self._ram_al()
                if ram > makro.kosul_esik:
                    self._tetikle_kosullu(makro,
                        f"RAM {ram:.1f}% — eşik aşıldı!")

            elif makro.kosul_tipi == KosulTipi.PIL_DUSUK:
                pil = self._pil_al()
                if pil is not None and pil < makro.kosul_esik:
                    self._tetikle_kosullu(makro,
                        f"Pil {pil}% — kritik seviye!")

            elif makro.kosul_tipi == KosulTipi.INTERNET_YOK:
                bag = self._internet_kontrol()
                if not bag and self._son_ag_durumu:
                    self._tetikle_kosullu(makro, "İnternet bağlantısı kesildi!")
                self._son_ag_durumu = bag

            elif makro.kosul_tipi == KosulTipi.INTERNET_VAR:
                bag = self._internet_kontrol()
                if bag and not self._son_ag_durumu:
                    self._tetikle_kosullu(makro, "İnternet bağlantısı kuruldu!")
                self._son_ag_durumu = bag

            elif makro.kosul_tipi == KosulTipi.SICAKLIK:
                sicak = self._sicaklik_al()
                if sicak is not None and sicak > makro.kosul_esik:
                    self._tetikle_kosullu(makro,
                        f"Sıcaklık {sicak:.1f}°C — eşik aşıldı!")

            elif makro.kosul_tipi == KosulTipi.UZUV_CEVRIM:
                if self._cekirdek and makro.kosul_uzuv_id:
                    uzuv = self._cekirdek.uzuv.uzuvlar.get(
                        makro.kosul_uzuv_id)
                    if uzuv:
                        eski = self._son_uzuv_durumlari.get(
                            makro.kosul_uzuv_id, "")
                        yeni = uzuv.durum
                        if (eski in ("bağlı", "baglı") and
                                yeni == "çevrimdışı"):
                            self._tetikle_kosullu(makro,
                                f"{uzuv.ad} çevrimdışı oldu!")
                        self._son_uzuv_durumlari[
                            makro.kosul_uzuv_id] = yeni

        except Exception as e:
            self.log.uyari(KAYNAK, f"Koşul kontrol hatası: {e}")

    def _tetikle_kosullu(self, makro: Makro, mesaj: str):
        """Koşullu tetikleme — çok sık tetiklenmesini önle."""
        if makro.son_calisma:
            gecen = (datetime.now() -
                     datetime.fromisoformat(makro.son_calisma)
                     ).total_seconds()
            if gecen < 300:  # 5 dakikadan önce tekrar tetikleme
                return
        self._bildir(makro.id, f"Koşul tetiklendi: {mesaj}")
        if self._bildirim_fn:
            self._bildirim_fn(f"Uyarı: {mesaj}")
        self.calistir(makro.id)

    # ── Sistem Metrikleri ─────────────────────────────────────────────────────

    def _cpu_al(self) -> float:
        try:
            r = subprocess.run(
                ["top", "-bn1"], capture_output=True, text=True, timeout=3)
            import re
            for satir in r.stdout.splitlines():
                m = re.search(r"(\d+\.\d+)\s*us", satir)
                if m:
                    return float(m.group(1))
        except Exception:
            pass
        return 0.0

    def _ram_al(self) -> float:
        try:
            r = subprocess.run(
                ["free", "-m"], capture_output=True, text=True, timeout=2)
            for satir in r.stdout.splitlines():
                if satir.startswith("Mem"):
                    p = satir.split()
                    return int(p[2]) * 100 / int(p[1]) if int(p[1]) else 0
        except Exception:
            pass
        return 0.0

    def _pil_al(self) -> Optional[float]:
        try:
            with open("/sys/class/power_supply/BAT0/capacity") as f:
                return float(f.read().strip())
        except Exception:
            return None

    def _internet_kontrol(self) -> bool:
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def _sicaklik_al(self) -> Optional[float]:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000.0
        except Exception:
            return None

    # ── Sesli Komut Tetikleme ────────────────────────────────────────────────

    def sesli_tetikle(self, metin: str) -> Optional[str]:
        """Sesli komut makro tetikleyicisiyle eşleşiyor mu?"""
        ml = metin.lower()
        for mid, makro in self.makrolar.items():
            if (makro.aktif and
                    makro.tetik_tipi == TetikTipi.SESLI and
                    makro.sesli_kelime and
                    makro.sesli_kelime.lower() in ml):
                self.calistir(mid)
                return f"✓ {makro.ad} başlatıldı."
        return None

    # ── Varsayılan Makrolar ───────────────────────────────────────────────────

    def _varsayilan_yukle(self):
        self.makrolar.update(self._hazir_makro_tanimlari())
        self.log.bilgi(KAYNAK,
            f"{len(self.makrolar)} varsayılan makro yüklendi.")

    def _hazir_makrolari_tamamla(self) -> int:
        """Mevcut kullanıcı makrolarını ezmeden eksik hazır makroları ekler."""
        eklendi = 0
        for mid, makro in self._hazir_makro_tanimlari().items():
            if mid not in self.makrolar:
                self.makrolar[mid] = makro
                eklendi += 1
        if eklendi:
            self.log.bilgi(KAYNAK, f"{eklendi} hazır makro eklendi.")
        return eklendi

    def _hazir_makro_tanimlari(self) -> dict[str, Makro]:
        def k(deger: str, timeout: int = 30) -> MakroAdim:
            return MakroAdim("komut", deger, timeout=timeout, hata_devam=True)

        def s(deger: str) -> MakroAdim:
            return MakroAdim("konusma", deger)

        def i(deger: str) -> MakroAdim:
            return MakroAdim("isle", deger)

        notify = "notify-send 'Zihin Köprüsü' '{mesaj}' 2>/dev/null || true"

        return {
            "gunaydin": Makro(
                id="gunaydin", ad="Günaydın Rutini",
                aciklama="Hava, haber ve genel başlangıç akışı.",
                adimlar=[
                    s("Günaydın. Sistem hazırlandı."),
                    k("curl -s --max-time 5 'wttr.in?format=3' || true", timeout=8),
                    i("haberler"),
                ],
                tetik_tipi=TetikTipi.SESLI,
                saat="07:30", gunler=[0, 1, 2, 3, 4],
                sesli_kelime="günaydın", aktif=True,
            ),
            "gece_modu": Makro(
                id="gece_modu", ad="Gece Modu",
                aciklama="Sesi ve parlaklığı düşürür.",
                adimlar=[
                    k("amixer set Master 20% 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ 20% 2>/dev/null || true"),
                    k("brightnessctl set 30% 2>/dev/null || true"),
                    s("Gece modu aktif."),
                ],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="gece modu", aktif=True,
            ),
            "calisma_modu": Makro(
                id="calisma_modu", ad="Çalışma Modu",
                aciklama="Ses, parlaklık ve çalışma ortamını hazırlar.",
                adimlar=[
                    k("amixer set Master 45% 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ 45% 2>/dev/null || true"),
                    k("brightnessctl set 75% 2>/dev/null || true"),
                    k(notify.format(mesaj="Çalışma modu hazır.")),
                    s("Çalışma modu hazır."),
                ],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="çalışma modu", aktif=True,
            ),
            "toplanti_modu": Makro(
                id="toplanti_modu", ad="Toplantı Modu",
                aciklama="Sistemi sessize alır, bildirim verir.",
                adimlar=[
                    k("amixer set Master mute 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 1 2>/dev/null || true"),
                    k(notify.format(mesaj="Toplantı modu aktif.")),
                    s("Toplantı modu aktif. Ses kapatıldı."),
                ],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="toplantı modu", aktif=True,
            ),
            "mola_modu": Makro(
                id="mola_modu", ad="Mola Modu",
                aciklama="Kısa mola hatırlatıcısı ve sakinleştirme.",
                adimlar=[
                    k("amixer set Master 30% 2>/dev/null || true"),
                    k(notify.format(mesaj="Mola zamanı. 5 dakika gözlerini dinlendir.")),
                    s("Mola zamanı. Beş dakika gözlerini dinlendir."),
                ],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="mola modu", aktif=True,
            ),
            "sistem_kontrol": Makro(
                id="sistem_kontrol", ad="Sistem Kontrol Özeti",
                aciklama="CPU, RAM, disk ve sıcaklığı raporlar.",
                adimlar=[
                    s("Sistem kontrolü başlatıldı."),
                    k("printf 'CPU:\\n'; top -bn1 | head -5; printf '\\nRAM:\\n'; free -h; printf '\\nDISK:\\n'; df -h /", timeout=10),
                    k("for f in /sys/class/thermal/thermal_zone*/temp /sys/class/hwmon/hwmon*/temp*_input; do [ -r \"$f\" ] && awk '{printf \"Sıcaklık: %.1f C\\n\", $1/1000}' \"$f\" && break; done", timeout=5),
                    s("Sistem kontrolü tamamlandı."),
                ],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="sistem kontrol", aktif=True,
            ),
            "uzuvlari_yokla": Makro(
                id="uzuvlari_yokla", ad="Tüm Uzuvları Yokla",
                aciklama="Merkezde kayıtlı uzuv durumlarını ister.",
                adimlar=[s("Uzuvlar yoklanıyor."), i("uzuv listesi")],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="uzuvları yokla", aktif=True,
            ),
            "tor_kontrol": Makro(
                id="tor_kontrol", ad="Tor Kontrol",
                aciklama="Tor servis ve onion durumunu kontrol eder.",
                adimlar=[
                    k("systemctl is-active tor 2>/dev/null || true"),
                    i("tor durumu"),
                ],
                tetik_tipi=TetikTipi.MANUEL, aktif=True,
            ),
            "telegram_kontrol": Makro(
                id="telegram_kontrol", ad="Telegram Kontrol",
                aciklama="Telegram bot durumunu kontrol eder.",
                adimlar=[i("telegram durumu"), k(notify.format(mesaj="Telegram kontrolü istendi."))],
                tetik_tipi=TetikTipi.MANUEL, aktif=True,
            ),
            "yedek_al": Makro(
                id="yedek_al", ad="Güvenli Yedek Al",
                aciklama="Ayar ve proje yedeği başlatır.",
                adimlar=[s("Yedekleme başlatılıyor."), i("yedek al")],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="yedek al", aktif=True,
            ),
            "log_ozeti": Makro(
                id="log_ozeti", ad="Log Özeti",
                aciklama="Son hataları hızlı gösterir.",
                adimlar=[
                    k("find loglar -type f -maxdepth 1 2>/dev/null | xargs -r tail -n 40 2>/dev/null | grep -Ei 'HATA|KRİTİK|ERROR|CRITICAL' | tail -n 40 || true"),
                ],
                tetik_tipi=TetikTipi.MANUEL, aktif=True,
            ),
            "internet_kontrol": Makro(
                id="internet_kontrol", ad="İnternet Kontrol",
                aciklama="DNS ve dış ağ erişimini kontrol eder.",
                adimlar=[
                    k("ping -c 1 -W 2 8.8.8.8 >/dev/null && echo 'IP erişimi var' || echo 'IP erişimi yok'"),
                    k("getent hosts google.com >/dev/null && echo 'DNS çalışıyor' || echo 'DNS çalışmıyor'"),
                ],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="internet kontrol", aktif=True,
            ),
            "disk_raporu": Makro(
                id="disk_raporu", ad="Disk Raporu",
                aciklama="Disk doluluk ve büyük klasör özetini verir.",
                adimlar=[
                    k("df -h /"),
                    k("du -sh ./* 2>/dev/null | sort -rh | head -10", timeout=20),
                ],
                tetik_tipi=TetikTipi.MANUEL, aktif=True,
            ),
            "en_cok_cpu": Makro(
                id="en_cok_cpu", ad="En Çok CPU Kullananlar",
                aciklama="CPU tüketen ilk süreçleri listeler.",
                adimlar=[k("ps aux --sort=-%cpu | head -8", timeout=8)],
                tetik_tipi=TetikTipi.MANUEL, aktif=True,
            ),
            "en_cok_ram": Makro(
                id="en_cok_ram", ad="En Çok RAM Kullananlar",
                aciklama="Bellek tüketen ilk süreçleri listeler.",
                adimlar=[k("ps aux --sort=-%mem | head -8", timeout=8)],
                tetik_tipi=TetikTipi.MANUEL, aktif=True,
            ),
            "sicaklik_raporu": Makro(
                id="sicaklik_raporu", ad="Sıcaklık Raporu",
                aciklama="Cihaz sıcaklık sensörlerini okur.",
                adimlar=[
                    k("for f in /sys/class/thermal/thermal_zone*/temp /sys/class/hwmon/hwmon*/temp*_input; do [ -r \"$f\" ] && awk -v n=\"$f\" '{printf \"%s %.1f C\\n\", n, $1/1000}' \"$f\"; done | head -12", timeout=8),
                ],
                tetik_tipi=TetikTipi.MANUEL, aktif=True,
            ),
            "ses_ac": Makro(
                id="ses_ac", ad="Sesi Aç",
                aciklama="Sesi %60 yapar ve mute kapatır.",
                adimlar=[k("amixer set Master unmute 60% 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null || true")],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="sesi aç", aktif=True,
            ),
            "ses_kis": Makro(
                id="ses_kis", ad="Sesi Kıs",
                aciklama="Sesi %25 seviyesine indirir.",
                adimlar=[k("amixer set Master 25% 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ 25% 2>/dev/null || true")],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="sesi kıs", aktif=True,
            ),
            "sessize_al": Makro(
                id="sessize_al", ad="Sessize Al",
                aciklama="Sistem sesini kapatır.",
                adimlar=[k("amixer set Master mute 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 1 2>/dev/null || true")],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="sessize al", aktif=True,
            ),
            "parlaklik_artir": Makro(
                id="parlaklik_artir", ad="Parlaklığı Artır",
                aciklama="Ekran parlaklığını yükseltir.",
                adimlar=[k("brightnessctl set +10% 2>/dev/null || true")],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="parlaklığı artır", aktif=True,
            ),
            "parlaklik_azalt": Makro(
                id="parlaklik_azalt", ad="Parlaklığı Azalt",
                aciklama="Ekran parlaklığını azaltır.",
                adimlar=[k("brightnessctl set 10%- 2>/dev/null || true")],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="parlaklığı azalt", aktif=True,
            ),
            "ekran_kilitle": Makro(
                id="ekran_kilitle", ad="Ekranı Kilitle",
                aciklama="Oturumu kilitler.",
                adimlar=[k("loginctl lock-session 2>/dev/null || gnome-screensaver-command -l 2>/dev/null || true")],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="ekranı kilitle", aktif=True,
            ),
            "panik_raporu": Makro(
                id="panik_raporu", ad="Acil Durum Raporu",
                aciklama="Sistem, ağ ve uzuv özetini hızlı toplar.",
                adimlar=[
                    s("Acil durum raporu hazırlanıyor."),
                    k("date; hostname; hostname -I; df -h /; free -h; ps aux --sort=-%cpu | head -5", timeout=15),
                    i("uzuv listesi"),
                ],
                tetik_tipi=TetikTipi.SESLI, sesli_kelime="acil durum", aktif=True,
            ),
            "haftalik_bakim": Makro(
                id="haftalik_bakim", ad="Haftalık Bakım Raporu",
                aciklama="Pazar akşamı sistem özet raporu üretir.",
                adimlar=[
                    k("df -h /; free -h; journalctl -p 3 -n 30 --no-pager 2>/dev/null || true", timeout=20),
                    s("Haftalık bakım raporu hazırlandı."),
                ],
                tetik_tipi=TetikTipi.ZAMANLI, saat="20:00", gunler=[6], aktif=False,
            ),
            "saatlik_saglik": Makro(
                id="saatlik_saglik", ad="Saatlik Sağlık Kontrolü",
                aciklama="Saatte bir hafif sistem kontrolü.",
                adimlar=[k("date; uptime; df -h / | tail -1; free -h | awk '/Mem:/{print $3\"/\"$2}'", timeout=8)],
                tetik_tipi=TetikTipi.ARALIKLI, aralik_dakika=60, aktif=False,
            ),
            "cpu_uyari": Makro(
                id="cpu_uyari", ad="CPU Aşım Uyarısı",
                aciklama="CPU %90 üstüne çıkınca uyarır.",
                adimlar=[
                    s("Dikkat. İşlemci kullanımı yüksek."),
                    k(notify.format(mesaj="CPU kullanımı kritik.")),
                    k("ps aux --sort=-%cpu | head -6", timeout=8),
                ],
                tetik_tipi=TetikTipi.KOSULLU, kosul_tipi=KosulTipi.CPU_ASIM,
                kosul_esik=90.0, aktif=True,
            ),
            "ram_uyari": Makro(
                id="ram_uyari", ad="RAM Aşım Uyarısı",
                aciklama="RAM %85 üstüne çıkınca uyarır.",
                adimlar=[
                    s("Dikkat. Bellek kullanımı yüksek."),
                    k(notify.format(mesaj="RAM kullanımı yüksek.")),
                    k("ps aux --sort=-%mem | head -6", timeout=8),
                ],
                tetik_tipi=TetikTipi.KOSULLU, kosul_tipi=KosulTipi.RAM_ASIM,
                kosul_esik=85.0, aktif=True,
            ),
            "sicaklik_uyari": Makro(
                id="sicaklik_uyari", ad="Sıcaklık Aşım Uyarısı",
                aciklama="Sıcaklık 80 dereceyi geçince uyarır.",
                adimlar=[
                    s("Dikkat. Sistem sıcaklığı yüksek."),
                    k(notify.format(mesaj="Sistem sıcaklığı yüksek.")),
                ],
                tetik_tipi=TetikTipi.KOSULLU, kosul_tipi=KosulTipi.SICAKLIK,
                kosul_esik=80.0, aktif=True,
            ),
            "pil_uyari": Makro(
                id="pil_uyari", ad="Pil Uyarısı",
                aciklama="Pil %15 altına düşünce uyarır.",
                adimlar=[
                    s("Dikkat. Pil seviyesi kritik. Şarj edin."),
                    k(notify.format(mesaj="Pil kritik. Şarj edin.")),
                ],
                tetik_tipi=TetikTipi.KOSULLU, kosul_tipi=KosulTipi.PIL_DUSUK,
                kosul_esik=15.0, aktif=True,
            ),
            "internet_uyari": Makro(
                id="internet_uyari", ad="İnternet Kesildi Uyarısı",
                aciklama="Bağlantı kesilince uyarır.",
                adimlar=[
                    s("Uyarı. İnternet bağlantısı kesildi."),
                    k(notify.format(mesaj="İnternet bağlantısı kesildi.")),
                ],
                tetik_tipi=TetikTipi.KOSULLU, kosul_tipi=KosulTipi.INTERNET_YOK,
                aktif=True,
            ),
        }
