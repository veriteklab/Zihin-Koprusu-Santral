# Zihin Köprüsü v7.0

Sesli komutlarla sistem yönetimi, uzak cihaz kontrolü ve web otomasyonu.

---

## Hızlı Kurulum

```bash
cd ~/Zihin_Koprusu
chmod +x kur.sh && ./kur.sh
./baslat.sh
```

---

## İlk Yapılandırma

### 1. AI Anahtarı (opsiyonel)
```bash
nano ai_ayar.json
# api_anahtari alanına Gemini/OpenAI anahtarınızı yazın
```

### 2. Telegram Botu (opsiyonel)
```bash
nano telegram_ayar.json
# token → @BotFather'dan alın
# chat_id → @userinfobot'tan alın
# aktif → true yapın
```

### 3. Hitap Adınızı Belirleyin
GUI → Karakterler sekmesi → her bilinç için hitap adı yazın

---

## Sesli Komutlar

| Söyle | Ne Yapar |
|-------|---------|
| "Merhaba" | Karşılama |
| "Sistem durumu" | CPU/RAM/Disk özeti |
| "Saat kaç" | Saati söyler |
| "Hava nasıl" | Hava durumu |
| "Not al: ..." | Notu kaydeder |
| "Günaydın rutini" | Sabah makrosunu başlatır |
| "Gece modu" | Ekranı karartır, sesi kısar |
| "Tor başlat" | Anonim bağlantı |

---

## Wake Word

GUI → Ana Ekran → "Wake Word" checkbox'ını işaretle.

Varsayılan tetikleyiciler: **zihin, abi, abla, acil, hey**

---

## Dizin Yapısı

```
Zihin_Koprusu/
├── zihin/              # 23 Python modülü
├── eklentiler/         # slot_01..10
├── dil/tr.json         # Türkçe dil paketi
├── modeller/vosk-tr/   # STT modeli
├── beyin.yaml          # Ana yapılandırma
├── komutlar.json       # Sesli komut veritabanı
├── ai_ayar.json        # AI ayarları ⚠ gizli
├── telegram_ayar.json  # Telegram token ⚠ gizli
└── kur.sh              # Kurulum betiği
```

---

## Güvenlik Uyarıları

- `ai_ayar.json` ve `telegram_ayar.json` dosyalarını Git'e **ekleme**
- `.gitignore`'a şunu ekle: `ai_ayar.json telegram_ayar.json uzuvlar.json`
- Telegram token'ını herkesle paylaşma

---

## Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| Ses tanıma çalışmıyor | Vosk modeli kurulu mu? `kur.sh` çalıştır |
| GUI açılmıyor | `loglar/crash.log` dosyasına bak |
| Tor onion yok | GUI → Tor sekmesi → Başlat |
| Telegram yanıt vermiyor | `telegram_ayar.json` → `aktif: true` |

---

© 2024 Veri Teknolojileri Laboatuvarı — Tüm hakları saklıdır.
