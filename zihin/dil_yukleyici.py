"""
Zihin Köprüsü – Dil Yükleme Modülü  (DÜZELTİLMİŞ v2)

Düzeltmeler v2:
  - _yukle() artık birden fazla yolu dener (fallback zinciri)
    1. Verilen dil_klasoru
    2. Bu modülün bulunduğu dizin (zihin/ paketi yanı)
    3. Projenin kök dizini altındaki dil/
    4. Hiçbiri yoksa: gömülü minimum Türkçe sözlük (program yine de çalışır)
  - open() etrafında try/except → boot'ta crash yok
"""
import json
import os
import warnings

_GÖMÜLÜ_TR = {
    "sistem": {
        "baslik": "Zihin Köprüsü",
        "hazir": "Zihin Köprüsü hazır.",
        "kapaniyor": "Zihin Köprüsü kapatılıyor.",
        "basladi": "Sistem başladı.",
        "devir": "Komuta hazırım.",
        "anlamadim": "Anlamadım, tekrar söyler misiniz?",
        "hata": "Bir hata oluştu.",
        "tamamlandi": "İşlem tamamlandı.",
        "iptal": "İptal edildi.",
        "onay": "Onaylandı.",
        "bekle": "Lütfen bekleyin.",
        "hazirlanıyor": "Hazırlanıyor...",
        "baglanıyor": "Bağlanıyor...",
        "baglandi": "Bağlandı.",
        "baglanti_kesildi": "Bağlantı kesildi.",
    },
    "ses": {
        "dinleniyor": "Dinleniyor...",
        "anlasildi": "Anlaşıldı.",
        "model_yuklenemedi": "Ses modeli yüklenemedi.",
        "mikrofon_hatasi": "Mikrofon erişim hatası.",
        "tts_hatasi": "Ses sentezi başarısız.",
        "gurultu_fazla": "Ortam gürültüsü fazla, lütfen tekrarlayın.",
    },
    "komut": {
        "bulunamadi": "Komut bulunamadı.",
        "calistirildi": "Komut çalıştırıldı.",
        "hata": "Komut hata verdi.",
        "zaman_asimi": "Komut zaman aşımına uğradı.",
        "yetki_yok": "Bu işlem için yetkiniz yok.",
    },
    "ai": {
        "basladi": "Yapay zeka hazır.",
        "yanıt_yok": "Şu an yanıt veremiyorum, lütfen tekrar deneyin.",
        "anahtar_yok": "API anahtarı bulunamadı.",
        "baglanti_hatasi": "Yapay zeka bağlantı hatası.",
    },
    "arayuz": {
        "baslat": "Başlat", "durdur": "Durdur", "ayarlar": "Ayarlar",
        "gunluk": "Günlük", "uzuvlar": "Uzuvlar", "eklentiler": "Eklentiler",
        "hakkinda": "Hakkında", "cikis": "Çıkış",
        "aktif_bilinc": "Aktif Bilinç", "durum": "Durum",
        "dinleniyor": "Dinleniyor", "bosta": "Boşta",
        "konusuyor": "Konuşuyor", "dusunuyor": "Düşünüyor",
        "hata_durumu": "Hata", "slot_bos": "Boş Alan",
        "slot_ekle": "Eklenti Ekle", "slot_calistir": "Çalıştır",
        "slot_klasor_ac": "Klasörü Aç", "log_temizle": "Günlüğü Temizle",
        "kaydet": "Kaydet", "iptal": "İptal", "kapat": "Kapat",
    },
    "bilincler": {
        "ABİ": "Abi", "BİRADER": "Birader", "BACİ": "Bacı",
        "ABLA": "Abla", "UFAKLIK": "Ufaklık", "DAYI": "Dayı", "KUZEN": "Kuzen",
    },
}


class DilYukleyici:
    def __init__(self, dil_klasoru: str, dil_kodu: str = "tr"):
        self.dil_klasoru = dil_klasoru
        self.dil_kodu = dil_kodu
        self._veriler: dict = {}
        self._yukle()

    def _adaylar(self) -> list:
        kod = self.dil_kodu
        module_dir = os.path.dirname(os.path.abspath(__file__))
        proje_kok  = os.path.dirname(module_dir)
        return [
            os.path.join(self.dil_klasoru, f"{kod}.json"),
            os.path.join(self.dil_klasoru, "tr.json"),
            os.path.join(module_dir, "dil", f"{kod}.json"),
            os.path.join(module_dir, "dil", "tr.json"),
            os.path.join(proje_kok, "dil", f"{kod}.json"),
            os.path.join(proje_kok, "dil", "tr.json"),
            os.path.join(module_dir, f"{kod}.json"),
            os.path.join(module_dir, "tr.json"),
        ]

    def _yukle(self):
        for dosya in self._adaylar():
            if os.path.exists(dosya):
                try:
                    with open(dosya, "r", encoding="utf-8") as f:
                        self._veriler = json.load(f)
                    return
                except Exception:
                    continue
        warnings.warn(
            f"Dil dosyası bulunamadı (dil_klasoru={self.dil_klasoru!r}). "
            "Gömülü minimum Türkçe sözlük kullanılıyor.",
            RuntimeWarning, stacklevel=2,
        )
        self._veriler = _GÖMÜLÜ_TR

    def al(self, *anahtarlar: str, **yer_tutucular) -> str:
        veri = self._veriler
        for anahtar in anahtarlar:
            if isinstance(veri, dict):
                veri = veri.get(anahtar, "")
            else:
                return str(anahtar)
        metin = str(veri) if veri else ""
        for k, v in yer_tutucular.items():
            metin = metin.replace(f"{{{k}}}", str(v))
        return metin

    def dil_degistir(self, yeni_dil: str):
        self.dil_kodu = yeni_dil
        self._yukle()
