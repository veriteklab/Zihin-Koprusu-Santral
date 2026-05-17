# ZK Santral Android Agent

Bu klasor, Zihin Koprusu Santral icin Android yardimci uygulama iskeletidir.

Amac:
- gelen cagriyi Android framework tarafindan algilamak
- backend'e `incoming`, `answered`, `hangup` olaylarini gondermek
- answered olduktan sonra backend'den `prompt-audio` almak
- cihazda `MediaPlayer` ile anonsu oynatmak
- ayni cihazda tam ekran bir `Santral Core Panel` kiosk arayuzu gostermek

## Su anki durum

Bu ilk iskelet:
- Java tabanli Android app yapisi kurar
- PHONE_STATE receiver ekler
- root ile otomatik cevap denemesi yapar
- backend'den ses dosyasi cekip `MediaPlayer` ile calmayi dener
- `file:///android_asset/dashboard/index.html` uzerinden tam ekran panel acar
- `immersive sticky` ve `lock task` ile kiosk davranisi dener
- boot sonrasi uygulamayi tekrar kaldirir

## Gerekli duzenlemeler

Derlemeden once [app/src/main/java/com/zihinkoprusu/santral/agent/AgentConfig.java](./app/src/main/java/com/zihinkoprusu/santral/agent/AgentConfig.java)
icindeki yer tutucular build zamaninda doldurulur:

- `SERVER_URL`
- `TOKEN`
- `DEVICE_ID`

## Online build oncelikli yol

Bu ajan icin oncelikli yol GitHub Actions ile online build'dir.

Workflow:

- `.github/workflows/android-agent-build.yml`

Repo ayarlari:

- Actions secret: `ZK_AGENT_TOKEN`
- Actions variable: `ZK_AGENT_SERVER_URL`
- Actions variable: `ZK_AGENT_DEVICE_ID`

Ayrica:

- [`.github/ONLINE_BUILD_SETUP.md`](/home/yabutsa06/zk/.github/ONLINE_BUILD_SETUP.md)

Sonra:

- `Actions -> android-agent-build -> Run workflow`

Artifact adi:

- `zk-santral-agent-debug-apk`

Artifact icinde:

- `zk-santral-agent-debug.apk`
- `build-info.txt`
- `sha256.txt`
- `zk-santral-agent-bundle.zip`

## Lokal build fallback

```bash
cd santral/android-agent
chmod +x build_apk.sh install_apk.sh
./build_apk.sh
```

Build zamaninda env ile deger basabilirsin:

```bash
ZK_SERVER_URL="http://192.168.1.43:8767" \
ZK_TOKEN="degistir-beni" \
ZK_DEVICE_ID="j2-prime-agent" \
./build_apk.sh
```

APK kurmak icin:

```bash
./install_apk.sh
```

Gerekirse `adb` yolu ver:

```bash
ADB_BIN=/home/yabutsa06/android-sdk/platform-tools/adb ./install_apk.sh
```

## Backend baglantisi

Bu ajan su uc noktalari kullanir:

- `POST /api/v1/events`
- `GET /api/v1/calls/<call_id>/prompt-audio?token=...`
- `GET /api/status`

## Panel verisi

Panel, backend'den `GET /api/status` ile veri ceker.

Ek olarak istenirse backend veri dizininde su dosya tutularak birden fazla sunucu da
ayni ekranda gosterilebilir:

- `veri/santral/panel_servers.json`

Ornek:

```json
{
  "servers": [
    {
      "name": "db-main",
      "host": "10.0.0.12",
      "cpu": 54,
      "ram": 71,
      "disk": 82,
      "net": "RX 3.4 MB | TX 2.1 MB",
      "uptime": "14d 6h",
      "load": 1.82
    }
  ]
}
```

Daha temiz yol, her Linux sunucuda merkezi santrale metrik itmek:

```bash
python3 -m santral.main --config santral_ayar.json panel-push \
  --server-url http://MERKEZ_IP:8767 \
  --token zk-santral-yerel-test
```

Bu komut `cpu`, `ram`, `disk`, `load`, `uptime` ve `net` verisini
`POST /api/panel/servers` ile merkeze yollar.

## Not

Bu uygulama iskelet olarak dogrudur, ancak cihaz davranisina gore su alanlarda sertlestirme gerekebilir:

- Android 6 izin akisi
- arka plan servis kaliciligi
- telefonun `STREAM_VOICE_CALL` oynatma davranisi
- cagri sirasinda hoparlor/earpiece yonlendirmesi
- DTMF veya sesli komut algilama
