# Zihin Köprüsü Kurtarma Planı

Bu belge kurtarılan kod tabanını çalışır, kurulabilir ve Docker ile paketlenebilir hale getirmek için takip listesidir.

## 1. Mevcut Durum

- Proje git deposu olarak gelmemiş; çalışma geçmişi yok.
- Python kaynakları syntax olarak derleniyor.
- `komutlar.json` geçerli JSON, fakat `__meta__` kaydı eski loader'ı düşürüyordu.
- `modeller/` klasörü eksik; `beyin.yaml` Vosk modelini `modeller/vosk-tr/vosk-model-small-tr-0.3` altında bekliyor.
- Hatalı `{zihin,dil,eklentiler,modeller` klasörü eski kurulum kalıntısıydı; `yedekler/kalintilar/brace_hatasi` altına taşındı.
- `gereksinimler.txt` ile `kur.sh` aynı bağımlılık listesini kurmuyor.
- Piper klasörü açılıyor ama Piper binary/model kurulumu yapılmıyor.
- `gTTS` ve `edge-tts` internet ister; offline TTS için Piper hattı tamamlanmalı.
- Wake word ve normal dinleme aynı Vosk modelini eş zamanlı kullanıyor; loglarda Vosk assertion hatası görülmüş.
- Minimal/full kurulum venv ve model indirme adımlarını tamamlıyor; sudo yoksa sistem paketleri atlanıyor.
- Mevcut ortamda STT için kalan blokaj PortAudio sistem kütüphanesi: `sounddevice` importu `PortAudio library not found` veriyor.
- Offline Piper TTS modeli indirildi ve WAV üretim testi geçti.

## 2. Öncelik Sırası

1. Komut veritabanı, dil yer tutucuları ve temel komut yanıtlarını çalışır hale getir. `[ilk yama tamamlandı]`
2. `kur.sh` dosyasını idempotent ve doğrulanabilir yap. `[ilk yama tamamlandı]`
3. Vosk model indirme/varlık kontrolünü sağlamlaştır. `[ilk yama tamamlandı]`
4. TTS motorlarını modlara ayır: internetli `gtts/edge-tts`, offline `piper`. `[ilk yama tamamlandı, Piper model indi]`
5. Model yokken GUI'nin düşmesini engelle, ses motorunu pasif modda başlat. `[ilk yama tamamlandı]`
6. Wake word akışını tek mikrofon/tek recognizer çakışması olmayacak şekilde düzelt. `[beklemede: PortAudio kurulunca canlı test]`
7. Uzuv stubları için Linux, Windows ve Android istemci üretimini test edilebilir hale getir. `[CLI eklendi, 3 platform syntax testi geçti]`
8. Docker hedeflerini ayır: `headless` servis ve `desktop-local` geliştirme/GUI modu. `[ilk Dockerfile/compose eklendi]`

## 3. Kurulum Hedefi

- `./kur.sh --minimal`: Python ortamı, temel paketler, Vosk modeli, GUI/ses minimumu.
- `./kur.sh --full`: minimal + Playwright Chromium + Piper + Tor + ekran/uzuv araçları.
- `./baslat.sh --gui`: model eksikse bile GUI açılmalı.
- `./baslat.sh --ses`: model/mikrofon yoksa açık hata vermeli, crash atmamalı.

## 4. Doğrulama

- `python3 -m compileall -q zihin eklentiler`
- `./baslat.sh --tani`
- JSON/YAML parse kontrolü
- `KomutVeritabani` yükleme testi
- Çekirdek model yokken kontrollü başlatma testi
- Kurulum scripti kuru koşu veya shellcheck benzeri statik kontrol
