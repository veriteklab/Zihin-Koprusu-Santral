# Zihin Koprusu Santral

Zihin Koprusu Santral, tek Android telefon + tek Linux PC ile calisan hibrit bir cagri otomasyon sistemidir.

Amac:
- gelen cagrilari algilamak
- olaylari PC'ye aktarmak
- Telegram bildirimleri uretmek
- ses dosyalarini saklamak
- STT/TTS islemleri yapmak
- ileride farkli PC'lere kolay kurulabilir bir yapiyi hazir tutmak

## Mimari

```text
Android telefon (root)
  -> android/zk_santral_android_ajan.sh
  -> HTTP olaylari
PC / Linux
  -> zihin.santral_main serve
  -> veri/santral/*
  -> Telegram
  -> STT / TTS
```

## Mevcut durum

Bu depo su anda su parcalari icerir:

- `zihin/santral/`
  - ayar yukleme
  - cagri deposu
  - Telegram bildirimi
  - ses transkript/TTS yardimcilari
  - HTTP olay sunucusu
  - akis / menu yonetimi
- `zihin/santral_main.py`
  - CLI giris noktasi
- `android/zk_santral_android_ajan.sh`
  - Android ajan iskeleti
- `android/zk_santral_android_ajan_wrapper.sh`
  - Android ajan wrapper
- `kur_android_santral_ajan.sh`
  - ADB ile telefona ajan yukleme yardimcisi
- `deploy/zk-santral.service`
  - systemd servis dosyasi
- `baslat_santral.sh`
  - yerel baslatma scripti

## Sinirlar

Bu ilk surum bir GSM trunk PBX degildir.

Telefonla testlerde:
- AT ile giden arama baslatma calisti
- AT ile kapatma calisti
- AT portu klasik modem gibi `RING/CLIP` olayi vermedi

Bu nedenle mimari su an inbound algilama icin Android framework tarafina dayanir.

Pratikte daha saglam yol:
- telefon USB ile PC'ye bagliysa
- PC tarafinda `adb-poller` calisir
- telefonun ag erisimi yerine ADB kullanilir

## Kurulum

### 1. Konfig

```bash
cp santral_ayar.ornek.json santral_ayar.json
```

`santral_ayar.json` icinde en az sunlari doldur:
- `sunucu.erisim_tokeni`
- gerekirse `sunucu.host`
- gerekirse `telegram.varsayilan_chat_id`

### 2. Python ortami

Santral icin en temiz yol ayri bir sanal ortamdir:

```bash
chmod +x deploy/kur_bagimliliklar.sh
./deploy/kur_bagimliliklar.sh
```

Bu script repo kokunde `.venv` olusturur ve `santral_gereksinimler.txt` icindeki minimal bagimliliklari kurar.

Istersen mevcut ZK ortamini da kullanabilirsin:

```bash
./baslat.sh --tani
```

### 3. Sunucuyu baslat

```bash
./baslat_santral.sh
```

veya:

```bash
python3 -m zihin.santral_main --config santral_ayar.json serve
```

### 4. systemd

Kalici kurulum icin sablon servis dosyasini dogrudan kopyalama. En dogru yol kurulum scriptidir:

```bash
chmod +x deploy/kur_santral.sh
./deploy/kur_santral.sh "/home/$USER/zk-santral" "/home/$USER/zk-santral/santral_ayar.json" "j2-prime" "http://127.0.0.1:8767"
```

Argumanlar:
- `workdir`
- `config`
- `device_id`
- `server_url`

Bu script:
- systemd unit dosyalarini mevcut kullanici ve yola gore uretir
- `zk-santral.service` ve `zk-santral-adb-poller.service` servislerini kurar
- servisleri etkinlestirip baslatir

Elle kurmak istersen once `deploy/*.service` icindeki `__USER__`, `__WORKDIR__`, `__CONFIG__`, `__SERVER_URL__`, `__DEVICE_ID__` yer tutucularini doldurman gerekir.

Ornek:

```bash
sudo cp deploy/zk-santral.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zk-santral
```

### 5. ADB poller

Telefon USB ile PC'ye bagliysa asagidaki yol daha saglamdir:

```bash
python3 -m zihin.santral_main --config santral_ayar.json adb-poller --server-url http://127.0.0.1:8767 --device-id j2-prime
```

Tek seferlik healthcheck:

```bash
python3 -m zihin.santral_main --config santral_ayar.json adb-poller --healthcheck
```

systemd:

```bash
sudo cp deploy/zk-santral-adb-poller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zk-santral-adb-poller
```

## HTTP API

### Saglik

```http
GET /health
```

### Olay gonder

```http
POST /api/v1/events
Content-Type: application/json
```

Ornek:

```json
{
  "token": "degistir-beni",
  "device_id": "android-santral",
  "event_type": "incoming",
  "phone_number": "+90555...",
  "state": "ringing",
  "call_id": "1715890000"
}
```

### Kayit yukle

```http
POST /api/v1/calls/<call_id>/recording?token=...&filename=kayit.wav
Content-Type: application/octet-stream
```

Govdede ham dosya icerigi gonderilir.

### TTS olustur

```http
POST /api/v1/tts
Content-Type: application/json
```

```json
{
  "token": "degistir-beni",
  "text": "Merhaba, mesajinizi sesli olarak birakin.",
  "filename": "welcome.wav"
}
```

### Cagri bilgisini getir

```http
GET /api/v1/calls/<call_id>
```

### Cagri secimi isle

Bu uc nokta backend tarafinda `1 / 2 / 3` secim mantigini hazir tutar.
DTMF veya sesli secim algisi geldiginde bu uc nokta cagrilir.

```http
POST /api/v1/calls/<call_id>/menu
Content-Type: application/json
```

```json
{
  "token": "degistir-beni",
  "digit": "1"
}
```

### Cagri promptu uret

```http
POST /api/v1/calls/<call_id>/prompt
Content-Type: application/json
```

```json
{
  "token": "degistir-beni"
}
```

Bu istek, ilgili akisin karsilama anonsunu TTS ile uretir.

### Cagri prompt sesini indir

```http
GET /api/v1/calls/<call_id>/prompt-audio?token=...
```

Bu uc nokta, ilgili cagrinin hazirlanmis anons sesini dogrudan ses dosyasi olarak verir.
Android ajan bu ucu kullanarak prompt dosyasini indirip oynatir.

## Smoke test

Calisan santrali APK olmadan dogrulamak icin:

```bash
python3 araçlar/santral_smoke_test.py \
  --server-url http://127.0.0.1:8767 \
  --token degistir-beni \
  --call-id smoke-test-001
```

Bu test su katmanlari yoklar:
- `GET /health`
- `POST /api/v1/events`
- `POST /api/v1/calls/<call_id>/prompt`
- `GET /api/v1/calls/<call_id>/prompt-audio`
- `POST /api/v1/calls/<call_id>/menu`
- `GET /api/v1/calls/<call_id>`

## Akis dosyasi

`santral_akislari.ornek.json` dosyasi santralin menu mantigini tanimlar.

Ornek akista:
- `1` -> Telegram bildirimi
- `2` -> sesli not
- `3` -> geri arama talebi

Yani Asterisk olmadan da `1 / 2 / 3` mantigi backend tarafinda hazir.
Eksik olan tek katman, bu secimi cagri sirasinda telefondan guvenilir sekilde okumak.

## Android ajan

`android/zk_santral_android_ajan.sh` ag fallback'li bir shell ajandir.

Beklentiler:
- root veya yeterli shell erisimi
- `curl`
- `dumpsys telephony.registry`
- `input`

Baslatma ornegi:

```sh
export SUNUCU_URL="http://192.168.1.43:8767"
export ERISIM_TOKENI="degistir-beni"
export CIHAZ_ID="j2-prime"
sh android/zk_santral_android_ajan.sh
```

ADB ile telefona kurma:

```bash
./kur_android_santral_ajan.sh "http://127.0.0.1:8767" "degistir-beni-uzun-rastgele-token" "j2-prime"
```

Not:
- Android cihazin PC'ye dogrudan IP erisimi yoksa `adb reverse tcp:8767 tcp:8767` kullanilir.
- `kur_android_santral_ajan.sh` ve `deploy_remote_android_ajan.sh` bunu otomatik dener.

## Android Agent App

`android-agent/` klasoru, shell ajan disinda daha dogru uzun vadeli yol olan Android uygulama iskeletini icerir.

Bu uygulamanin amaci:
- gelen cagrilari framework seviyesinde izlemek
- backend'e olay gondermek
- `/prompt-audio` ucundan anonsu alip `MediaPlayer` ile oynatmak

Ilk inceleme dosyalari:
- [android-agent/README.md](/home/yabutsa06/zk/android-agent/README.md)
- [android-agent/app/src/main/java/com/zihinkoprusu/santral/agent/CallAgentService.java](/home/yabutsa06/zk/android-agent/app/src/main/java/com/zihinkoprusu/santral/agent/CallAgentService.java)
- [android-agent/app/src/main/java/com/zihinkoprusu/santral/agent/SantralApi.java](/home/yabutsa06/zk/android-agent/app/src/main/java/com/zihinkoprusu/santral/agent/SantralApi.java)

Telefonda tek seferlik olay testi:

```bash
adb shell su -c 'TEK_SEFERLIK_TEST=1 sh /data/local/tmp/zk_santral_android_ajan_wrapper.sh'
```

Bu ajan:
- cagrı durumunu poll eder
- `incoming`, `answered`, `hangup` olaylarini yollar
- gelen cagrida otomatik cevap denemesi yapar

## STT/TTS

STT:
- Vosk model dizini `santral_ayar.json` icinden okunur
- ses dosyasi gerekiyorsa `ffmpeg` ile 16k mono WAV'a cevrilir

TTS:
- once `piper`
- sonra `edge-tts`
- sonra `gtts-cli`

## GitHub'a hazirlama

Bu klasor su an git deposu olmak zorunda degil. GitHub'a tasimadan once:

```bash
git init
git add .
git commit -m "Zihin Koprusu Santral ilk surum"
```

Asagidaki dosyalari repoya koyma:
- `santral_ayar.json`
- gercek `telegram_ayar.json`
- `veri/santral/`

`.gitignore` buna gore guncellendi.
