# Devam Notlari

Tarih: 2026-04-23

## Mevcut Durum

- Proje cekirdegi calisiyor.
- Urun odagi tekrar "merkez komuta + uzuv agi" eksenine cekilmeye baslandi.
- `kur.sh`, `baslat.sh`, `tani.py`, `KURTARMA_PLANI.md` mevcut ve kullanilabilir.
- Vosk modeli ve Piper modeli akisi yerlestirildi.
- STT/TTS eksik sistem paketlerinde cekirdek dusmeden pasif moda geciyor.
- Komut veritabani yukleme ve tetik esleme sorunlari duzeltildi.
- Tehlikeli komutlar icin ikinci onay mekanizmasi eklendi.
- `KEYLO` karakteri eklendi.
- Kisisel izlerin buyuk kismi temizlendi.
- Uzuv veri modeli artik coklu baglanti biliyor:
  - birincil baglanti
  - en az bir yedek baglanti
- Uzuv GUI editoru buna gore guncellendi.
- Telegram artik merkez panel gibi davranabiliyor:
  - `/panel`
  - `/bilincler`
  - `/bilinc ABLA`
  - `/wake ac|kapat`
  - `/onay ac|kapat`
  - `/uzuv uzuv_id komut`
  - `/ekran`
  - `/log`
  - `/yedek`
  - `/tani`
- Telegram dosya/foto gonderimi eklendi.
- `yedek` yoksa Telegram isteginde otomatik yedek uretiliyor.
- Uzuv failover mantigi eklendi:
  - ping
  - komut calistirma
  - dosya gonderme
  - X11 baslatma
  yollarinda birincil -> yedek sirasi deneniyor.
- `tor_http` / `tor_https` icin HTTP ajan uretimi eklendi.
- HTTP ajan artik:
  - `GET /health`
  - `POST /komut`
  endpointlerini destekliyor.
- HTTP ajan icin `X-ZK-Token` destegi eklendi.
- Linux, Windows ve Android icin HTTP ajan stub uretimi syntax olarak dogrulandi.
- Lokal uctan uca test gecildi:
  - lokal HTTP ajan calistirildi
  - merkezden `ping` basarili oldu
  - merkezden `printf test_http` komutu basarili dondu

## Su Anki Sinirlar

- `telegram` baglanti turu uzuv yonetiminde veri modelinde var ama gercek komut koprusu olarak henuz uygulanmadi.
- `tor_http` ve `tor_https` artik runtime tarafinda aktif ama gercek `.onion` / Tor socks bagimliligi gercek ortamda ayrica test edilmeli.
- Canli mikrofon STT icin sistem paketleri hala eksik olabilir.
- TTS tarafinda `gtts`, `sounddevice`, oynatici araclari olmayan ortamlarda fallback sinirli.
- Docker calismasi bilerek bekletiliyor.

## Son Dogrulanan Nokta

- `zihin/uzuv_yoneticisi.py` icindeki failover hattinda ADB hata ciktisi artik basari sayilmiyor.
- Test sonucu:
  - `reader` uzvu icin `adb` basarisizsa artik sahte cikti donmuyor.
  - Sistem dogru olarak `Tüm bağlantı yolları başarısız oldu.` diyor.
- HTTP e2e test sonucu:
  - lokal `tor_http` ajan ayaga kalkti
  - merkez `PING True`
  - merkez `KOMUT test_http`
- Telegram uzuv gorev protokolu ilk asamada aktif:
  - merkez gorev ID uretiyor
  - bot `/uzuv_gorevler` ile bekleyenleri listeliyor
  - bot `/uzuv_cevap gorev_id ok|hata cikti` ile gorev kapatabiliyor
  - yerel duman testinde gorev yaniti alindi ve bekleme akisi gecti
  - gorev mesajlarina ajanlar icin okunabilir `ZK_TASK|gorev_id|uzuv_id|tur` etiketi eklendi
- `.onion` HTTP hattinda kritik bagimlilik notu:
  - `requests` SOCKS destegi icin `PySocks` gerekiyor
  - `gereksinimler.txt`, `kur.sh`, `tani.py` buna gore guncellendi
  - `uzuvlar.json` icine `ornek_tor_http` kaydi eklendi
- Telegram ekran akisi genislestirildi:
  - `/ekran` yerel merkezi ekran gonderebiliyor
  - `/ekran uzuv_id` secili uzuvdan ekran almaya calisiyor
  - ilk surumde `ssh/tor_ssh` ve `adb` dosya cekme yolu hazir
  - `tor_http` ekran endpointi eklendi ve merkez bunu okumayi biliyor
  - Windows HTTP ajanina da ekran goruntusu endpointi eklendi
  - bu ortamda ekran araci olmadigi icin lokal test `Ekran goruntusu alinamadi.` ile sonlandi
  - `telegram` uzuv ekran aktarma hatti ilk surumde aktif:
    - merkez ekran gorevi aciyor
    - bot `/uzuv_ekran_gorevler` ile bekleyenleri listeleyebiliyor
    - foto veya dosya basligina `/uzuv_ekran_cevap gorev_id` yazilarak ekran geri gonderilebiliyor
    - yerel duman testinde dosya tabanli ekran yaniti basarili oldu
- Telegram ajan omurgasi hazirlandi:
  - `uzuv_stub_uret.py --baglanti-modu telegram_agent` eklendi
  - `zihin/istemci_uretici.py` Telethon tabanli Linux/Windows/Android ajan stubi uretebiliyor
  - ajan stubi `ZK_TASK|...` etiketini okuyup komut veya ekran gorevine cevap vermek uzere hazirlandi
  - syntax testi gecti, canli Telegram ortami olmadigi icin uc tan uca test yapilmadi
- GUI odakli kullanima gecis basladi:
  - uzuv ekle / duzenle penceresi kaydirilabilir hale getirildi
  - Telegram sekmesine `bot_username`, `api_id`, `api_hash`, `session_name`, `agent_chat` alanlari eklendi
  - uzuv istemci uret ekranina `Telegram Ajan` baglanti modu eklendi
  - Telegram ajan uretimi GUI'den yapilabilir hale getirildi
- Telegram `/log` artik ham son satirlar yerine filtreli ozet uretiyor:
  - seviye sayilari
  - en aktif kaynaklar
  - tekrarlayan sorunlar
  - son kritik/hata kayitlari
  - son operasyon olaylari
- Ham uzuv komut akisi sadeleştirildi:
  - GUI uzuv terminalinde komut modu secilebiliyor:
    - akilli komut
    - terminal
    - cmd
    - powershell
    - adb shell
  - merkez yazi kutusu ve Telegram tarafinda da dogal komutla ham uzuv komutu taniniyor:
    - `reader terminal komutu uptime`
    - `reader powershell Get-Process`
    - `tum uzuvlara terminal komutu hostname`
- Ana GUI metinleri kismen sadeleştirildi:
  - `MERKEZ KOMUTA`
  - `UZUV KOMUTA`
- Setup ve uzuv akisinda onion-zorunlulugu gevsetildi:
  - merkez erisim profilleri mantigi eklendi
  - `ssh_reverse` istemcileri artik host `.onion` degilse Tor dayatmiyor
  - Linux, Windows, Android/Termux istemci sablonlari:
    - yerel/clearnet hostta duz SSH
    - `.onion` hostta Tor proxy
  - setup paneli artik secilen baglantiya gore merkezi otomatik gosteriyor
- GUI setup geri bildirimi daha durust hale getirildi:
  - gercek `apk/exe` ciktiysa bunu acikca soyluyor
  - derleme basarisizsa `Kaynak setup hazir` olarak ayri durum gosteriyor
  - eski yaniltici `hazir`/`buildozer yok` dili zayiflatildi
- Uzuv ekleme akisi sihirbazlasmaya basladi:
  - pencere basligi `Yeni Uzuv Sihirbazi`
  - cihaz tipi ve baglanti tipleri artik kullanici dostu etiketlerle gorunuyor
  - `ID / simge / notlar` gelismis kimlik alanina tasindi
  - en az bir bilinc secilmeden kayit alinmiyor
  - setup panelinde de baglanti ve cihaz secimi insan diliyle gosteriliyor

## Bir Sonraki Adimlar

1. Uzuv ekleme ve setup uretimi tam sihirbaz akisina cevir:
   - tek ekranda cihaz tipi
   - atanacak bilincler
   - birincil/yedek baglanti
   - paket tipi
2. Android istemciyi ters SSH agirligindan cikarip daha urunsel bir ajan moduna cek:
   - HTTP ajan
   - Telegram ajan
   - sonra Tor bootstrap
3. Canli Telegram ajanini GUI uzerinden uretip gercek cihazda dogrula.
4. Gercek `.onion` HTTP ajan senaryosunu Tor socks ile uctan uca dene.
5. Sonra Docker oncesi final yerel calisma profillerini netlestir.

## Mevcut Blokaj

- Bu makinede `tor` binary su an kurulu degil.
- Bu makinede `telegram` Python modulu su an kurulu degil.
- Bu nedenle gercek `.onion` HTTP ve canli Telegram bot testi kod hazir olsa da ortamda tamamlanamiyor.
- `sounddevice` da eksik oldugu icin GUI modulu yalniz `python -c import ...` ile bu ortamda dogrudan acilmiyor;
  asıl dogrulama uygulamayi normal baslatinca yapilmali.

## Teknik Not

- Bir sonraki turda ilk bakilacak dosyalar:
  - `zihin/uzuv_yoneticisi.py`
  - `zihin/telegram_bot.py`
  - `zihin/cekirdek.py`
  - `zihin/arayuz.py`
- Ozellikle `telegram` baglanti tipini uzuv seviyesinde aktif etmek bir sonraki ana is.
- Telegram uzuv gorevleri icin ilgili dosyalar:
  - `zihin/telegram_bot.py`
  - `zihin/cekirdek.py`
