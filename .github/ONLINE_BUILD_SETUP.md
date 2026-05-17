# Android Agent Online Build Setup

Bu repo icin Android agent APK'si GitHub Actions ile online derlenir.

## 1. Secret ve variable ekle

Repo:

- `Settings`
- `Secrets and variables`
- `Actions`

Ekle:

### Secret

- `ZK_AGENT_TOKEN`

### Variables

- `ZK_AGENT_SERVER_URL`
- `ZK_AGENT_DEVICE_ID`

Ornek:

```text
ZK_AGENT_SERVER_URL = http://192.168.1.43:8767
ZK_AGENT_DEVICE_ID  = j2-prime-agent
```

## 2. Workflow calistir

- `Actions`
- `android-agent-build`
- `Run workflow`

Istersen `server_url` ve `device_id` alanlarini formdan override edebilirsin.

## 3. Artifact al

Workflow bittiginde artifact:

- `zk-santral-agent-debug-apk`

Icerik:

- `zk-santral-agent-debug.apk`
- `build-info.txt`
- `sha256.txt`
- `zk-santral-agent-bundle.zip`

## 4. Telefona kur

```bash
ADB_BIN=/home/yabutsa06/android-sdk/platform-tools/adb ./android-agent/install_apk.sh /path/to/zk-santral-agent-debug.apk
```
