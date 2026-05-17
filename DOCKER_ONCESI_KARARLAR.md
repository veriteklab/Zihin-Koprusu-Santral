# Docker Oncesi Kararlar

Bu dosya Docker paketlemeden once netlestirilmesi gereken mimari ve ozellik kararlarini tutar.

## 1. Calisma Modlari

- `yerel-gui`: Mikrofon, hoparlor, X11/Wayland, xdotool ve masaustu otomasyonu yerel sistemde calisir.
- `yerel-headless`: GUI acmadan Telegram, Tor, web endpoint, uzuv yonetimi ve komut isleme calisir.
- `docker-headless`: Kalici veri mount edilir; GUI ve masaustu otomasyonu varsayilmaz.
- `docker-gui`: Sadece karar alindiktan sonra; ses cihazi, X11 socket, izinler ve guvenlik ayrica tasarlanir.

## 2. Ses Kararlari

- STT varsayilan motoru: Vosk TR.
- TTS varsayilan sirasi: Piper offline, sonra edge-tts/gTTS internetli fallback.
- Mevcut blokaj: PortAudio sistem kutuphanesi yoksa `sounddevice` import edilemez.
- Docker icinde mikrofon kullanimi ayri karar ister: `/dev/snd`, PulseAudio socket veya PipeWire socket paylasimi.

## 3. Uzuv Mimarisi

- Uzuv stub uretimi CLI ve GUI tarafindan desteklenecek.
- Her uzuv icin minimum bilgiler: `id`, `ad`, `tip`, `baglanti_yontemi`, `ssh/adb/tor ayarlari`.
- Stub dosyalari `yedekler/uzuv_stublari/<uzuv_id>/` altinda uretilecek.
- Linux/Windows/Android stub dosyalari syntax testinden gecmeden kullaniciya "hazir" denmeyecek.
- Guvenlik icin stub icinde parola gomulmeyecek; anahtar veya kullanici kurulumu tercih edilecek.

## 4. Tor ve Ag Kararlari

- Yerelde sistem Tor varsa once sistem Tor kullanilacak.
- Sistem Tor yoksa kullanici alaninda Tor calistirma denenebilir.
- Docker icinde Tor stratejisi ayrica secilmeli:
  - Ayni container icinde Tor.
  - Ayri `tor` servisi.
  - Host Tor proxy kullanimi.
- Onion hostname dosyalari kalici volume olmadan kaybolur; Docker oncesi volume yolu netlesmeli.

## 5. Kalici Veri

Kalici kalmasi gerekenler:

- `ai_ayar.json`
- `telegram_ayar.json`
- `hitap_ayar.json`
- `uzuvlar.json`
- `hafiza.json`
- `makrolar.json`
- `takvim.json`
- `bilinc_goruntu.json`
- `loglar/`
- `yedekler/`
- `modeller/`
- `tor_veri/`

Docker oncesi hassas dosyalar icin `.env` mi JSON mu karari verilmeli.

## 6. Guvenlik Kararlari

- Sesli komutla `shutdown`, `reboot`, `sudo`, `apt upgrade`, `rm`, `kill` gibi komutlar icin onay mekanizmasi gerekecek.
- Telegram komutlari icin varsayilan `herkese_acik=false` olmali.
- Uzuv komutlari icin bilinc/yetki seviyesi zorunlu kontrol edilmeli.
- Loglarda token/API anahtari maskelenmeli.
- Stub uretiminde gizli anahtar dosya icerigi kopyalanmamali; sadece yol referansi kullanilmali.

## 7. Docker Oncesi Yapilacaklar

1. STT icin PortAudio kurulduktan sonra canli mikrofon testi.
2. Wake word akisini tek aktif dinleme dongusu olacak sekilde test etme.
3. Piper varsayilan TTS olarak secilecek mi karar verme.
4. Tor stratejisini secme: host Tor, container Tor veya ayri Tor servisi.
5. Uzuv yetki modeli ve tehlikeli komut onay akisini netlestirme.
6. Telegram izin listesi, chat id ve komut kanali davranisini netlestirme.
7. Web otomasyonu icin X11 mi Playwright headless mi ayrimini netlestirme.
8. Docker build/runtime hedeflerini bu kararlara gore son haline getirme.

## 8. Konusulacak Sorular

- Sesli asistan oncelik olarak yerel masaustu asistani mi, uzaktan yonetim sunucusu mu olacak?
- TTS varsayilani internet bagimsiz Piper mi olsun, yoksa daha dogal ses icin edge-tts mi?
- Uzuvlar ters SSH tunel ile mi, yoksa cihazlarin sunucuya HTTP/WebSocket baglanmasiyla mi yonetilsin?
- Telegram sadece bildirim/komut kanali mi, yoksa tam yonetim paneli gibi mi calissin?
- Tehlikeli sistem komutlari sesle dogrudan calissin mi, yoksa ikinci onay zorunlu mu olsun?
- Docker ilk hedefi GUI'siz headless servis mi, yoksa masaustu GUI de ilk pakete dahil mi?
