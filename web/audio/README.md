# Ses kaynakları

Bu klasördeki dosyalar oyunla birlikte **çevrimdışı** kullanılır; sergi
makinesinde internet gerekmez. Üretim tek seferliktir ve geliştirme makinesinde
yapılır.

## Üretim

Tümü **ElevenLabs** ile üretildi (ses efektleri: `eleven_text_to_sound_v2`,
müzik: `music_v2`). Üretici script ve tüm prompt'lar:

    python tools\gen_audio.py --dry-run     # once kredi dokumu
    python tools\gen_audio.py               # uretim (3 varyant + 2 muzik adayi)
    python tools\gen_audio.py --pick        # sec.html'den yapilan secimi uygula

API anahtarı kök dizindeki `key.txt`ten okunur (git'e girmez). Bir sesi
beğenmezsen prompt'unu `tools/gen_audio.py` içindeki `SPEC` tablosunda düzelt,
`web/audio/gen/` altındaki ilgili `_v*.mp3` dosyalarını sil ve
`--only <ad>` ile yalnız onu yeniden üret.

Karışım seviyeleri (hangi ses ne kadar yüksek) `web/js/audio.js` içindeki
`LEVEL` tablosundadır — sesleri yeniden üretmeden oradan ayarlanır.

## Dosyalar

| Dosya | Süre | Nerede çalar |
|---|---|---|
| `sfx-correct.mp3` | 1.5s | doğru cevap |
| `sfx-wrong.mp3` | 0.8s | yanlış cevap (kısa, net, inen iki nota) |
| `sfx-select.mp3` | 1.0s | yumruk onayı (token + BAŞLA/RESET) |
| `sfx-hover.mp3` | 1.0s | mercek bir token'a kilitlendi |
| `sfx-btn-arm.mp3` | 1.0s | BAŞLA / RESET butonu armed |
| `countdown-tick.mp3` | 1.0s | 3 · 2 · 1 |
| `countdown-go.mp3` | 1.5s | "BAŞLA!" |
| `urgency-tick.mp3` | 0.5s | **son 10 saniye** — saniyede bir tek tik |
| `urgency-enter.mp3` | 1.5s | son 10 saniyeye giriş |
| `time-up.mp3` | 2.5s | süre doldu |
| `round-end.mp3` | 2.5s | tur elle bitti / sonuç ekranı |
| `score-tick.mp3` | 1.0s | final puan sayımı |
| `celebrate-top3.mp3` | 3.0s | ilk 3'e girme |
| `calib-scan-loop.mp3` | 4.0s | biyometrik tarama sürerken (döngü) |
| `calib-complete.mp3` | 2.0s | "ERİŞİM SAĞLANDI" |
| `calib-cancel.mp3` | 1.0s | tarama iptal |
| `transition-whoosh.mp3` | 1.2s | ekran geçişleri |
| `attract-accent.mp3` | 2.0s | attract ekranında seyrek davet pingi |
| `ambient-loop.mp3` | 90s | sürekli sakin arka plan müziği |

## Tasarım notu — geri sayım sesi

En eski sürümde son 10 saniye **gerçek kalp atışı + hızlanan duvar saati**
kaydıyla veriliyordu (kayıt hızı 0.74x→1.0x, saat 0.92x→1.20x). Sergi ortamında
panik yaratıyordu. Bir ara sürümde yerine alçak bir bas nabız döngüsü kondu; o
da fazla "gerici" bulundu.

Şu anki çözüm: `urgency-tick.mp3`, **ekrandaki sayaç her saniye değiştiğinde bir
kez** çalar (`audio.js` `setUrgent`). Sürekli bir yatak sesi yoktur.

- Duyulan ritim, görülen rakamla birebir aynı karede değişir.
- Tempo sabit 1 Hz; hızlanma yok.
- Son 3 saniyede aynı örnek `gain ×1.3` ve `playbackRate ×1.06` ile çalınır —
  ayrı dosya gerekmeden hafif bir sıkışma hissi verir, tempo yine bozulmaz.
- 10. saniyeyi `urgency-enter.mp3` işaretler, tikler 9'dan başlar.

Aynı anda `ambient-loop.mp3` %45'e kısılıyor (`audio.js` `duck()`), böylece
geri sayım toplam ses seviyesi yükseltilmeden öne çıkıyor.

## Gizli ses ayarı menüsü

Oyun ekranındayken klavyeden **S** tuşu bir ayar paneli açar/kapatır (sağ alt
köşe). Ekranda hiçbir ipucu yoktur; ziyaretçi görmesin diye bilinçli olarak
gizlidir. `web/js/settings.js`.

- Ana ses / Müzik / Efektler için genel kaydırıcılar + Sessiz kutusu
- **EFEKTLER — TEK TEK** bölümü (açılır liste): 18 efektin her biri için ayrı
  kaydırıcı ve ▶ dinleme düğmesi. Kaydırıcıyı bıraktığında o ses otomatik
  çalar, böylece hoparlörde dinleyerek ayarlanır.
- Değerler tarayıcının `localStorage`'ında saklanır (`ma.audio.v1`): sergi
  makinesinde bir kez ayarla, her açılışta korunur
- Menü açıkken el/fare girdisi oyuna geçmez — operatör ayar yaparken
  kameradaki el yanlışlıkla BAŞLA/RESET'e basamaz
- `Escape` kioskı kapattığı için kapatma tuşu olarak kullanılmadı; tekrar `S`
  veya paneldeki **Kapat**

Seviye zinciri: `LEVEL[efekt]` (tasarım) × efekt kaydırıcısı × Efektler
kaydırıcısı × Ana ses. Yani `LEVEL` tablosu **tasarım varsayılanı**, menü onun
üzerine kullanıcı çarpanı uygular. Menüde ayarladığın bir değeri kalıcı
varsayılan yapmak istersen `LEVEL`'ı düzelt ve menüden "Varsayılana dön" de.

Kaydırıcı aralığı **%0-200**'dür (`audio.js` içinde `MAX_VOL`); %100 tasarım
seviyesidir ve kaydırıcı üzerinde turuncu bir çizgiyle işaretlidir. Üstüne
çıkılan değerler turuncu yazılır. Zincirin sonundaki limiter (`ensureContext`
içindeki `DynamicsCompressor`) kırpılmayı engeller, ama birkaç ses aynı anda
%150+ seviyedeyken dinamikler sıkışır ve karışım yassılaşır — gerçekten gerekmedikçe
%100'ün çok üstüne çıkma. Salon kalıcı olarak gürültülüyse önce hoparlörün
kendi seviyesini yükselt.

## Kullanımdan kalkan dosyalar

`urgency-loop.mp3` (4 sn bas nabız döngüsü) tik sesine geçilince kaldırıldı.
Üç varyantı `web/audio/gen/urgency-loop_v*.mp3` altında duruyor; geri dönmek
istenirse oradan alınabilir.

Aşağıdaki üç CC0 kaydı da artık hiçbir yerden referans edilmiyor; A/B
karşılaştırma istenmiyorsa silinebilir.

- `countdown-heartbeat.mp3` — "Heartbeat", JonasTisell / Andy Jack —
  https://freesound.org/people/JonasTisell/sounds/670465/
- `countdown-clock.mp3` — "Clock Tick-Tock.wav", Lynx_5969 —
  https://freesound.org/people/Lynx_5969/sounds/418896/
- `calibration-rise.mp3` — "Reverse Cymbal Shiny", loganzsound —
  https://freesound.org/people/loganzsound/sounds/774635/

## Lisans / kullanım hakkı

ElevenLabs çıktısının ticari kullanım hakkı **ücretli plan** gerektirir; sergi/
festival kurulumu bu kapsama girer. Ücretsiz planda üretilen seslerde atıf
zorunludur. Üretimin hangi planla yapıldığını kayıt altında tut.
