# Matematik Avı — Festival Operasyon Rehberi

Bu tek sayfa, sergi/festival sırasında ihtiyacın olan HER ŞEY: başlatma, durdurma,
müdahale noktaları ve ziyaretçi verisi. Teknik detay için: [KIOSK.md](KIOSK.md).

---

## 1. Günlük açılış

**Otomatik kurulu ise** (önerilen; `Otomatik-Baslatma-Kur.bat` bir kez çalıştırıldıysa):
PC'yi aç → oturum açılınca oyun kendiliğinden başlar, çöken bileşen kendiliğinden
yeniden başlatılır. Hiçbir şey yapmana gerek yok.

**Elle başlatmak için:** `Matematik-Avi-Baslat.bat`'a çift tıkla.

> Elektrik kesintisi sonrası otomatik açılması için kiosk hesabına **otomatik
> oturum açma** ayarlı olmalı (Netplwiz) — kontrol listesine bak (madde 5).

---

## 2. Müdahale ve çıkış noktaları (KİLİTLEME YOK)

Sistem bilerek tamamen kilitlenmedi; PC'ye her zaman müdahale edebilirsin:

| Ne yapmak istiyorsun | Nasıl |
|---|---|
| **Oyunu tamamen durdurmak** (supervise modunda) | Kökteki **`Kiosk-Durdur.bat`**'a çift tıkla. Tarayıcı + dedektör + sunucu temiz kapanır. Masaüstünden erişmek istersen **kısayol** oluştur (sağ tık → Kısayol); dosyayı **kopyalama** — kopya yanlış yere bayrak yazar ve kiosk durmaz (bat bunu fark edip uyarır). **ESC supervise modunda kalıcı kapatmaz** (tarayıcı kapansa da gözetimci yeniden açar). |
| Oyunu durdurmak (elle başlattıysan, `Matematik-Avi-Baslat.bat`) | Klavyede **ESC** (veya Alt+F4). Arka süreçler de kapanır. |
| Oyun penceresinden Windows'a geçmek (kapatmadan) | **Win tuşu** veya **Alt+Tab** — engellenmedi, çalışır. Oyun arkada açık kalır. |
| Acil durum / her şey donmuş | **Ctrl+Alt+Del** her zaman çalışır → Görev Yöneticisi → `chrome/msedge`, `python` süreçlerini sonlandır. |
| Otomatik başlatmayı tamamen kaldırmak | Yönetici PowerShell: `Unregister-ScheduledTask -TaskName 'MatematikAvi-Kiosk' -Confirm:$false` |
| Sadece bu oyuncuyu sıfırlamak | Oyundaki **RESET** butonu (el ile) — sistemi durdurmaz, kalibrasyon ekranına döner. |

> Not: `Kiosk-Durdur.bat` aslında kökte `KIOSK-DURDUR.flag` adlı bir dosya oluşturur;
> gözetimci bunu görüp kapanır. Bat çalışmazsa bu dosyayı elle oluşturman da yeterli.

---

## 3. Ziyaretçi verisi (telemetri)

Oyun, arka planda **her şeyi** kaydeder — oyuncuyu hiç etkilemez, internet gerektirmez:

- Kaç kişi yaklaştı / kalibrasyonu geçti / oyuna başladı / bitirdi / yarıda bıraktı
- Her soru + verilen cevap + doğru/yanlış + cevap süresi + seçilen yanlış değer
- Kamera/bağlantı sorunları, el kaybı, FPS düşüşleri, oyun hataları, dedektör çökmeleri

**Raporu görmek için:** kökteki **`Rapor.bat`**'a çift tıkla → Türkçe HTML rapor
tarayıcıda açılır (oyun çalışırken de yapabilirsin; günün ortasında ara rapor almak
serbest).

> Fare ile test etmen rapora zarar vermez: rapor, fare/test oturumlarını gerçek
> ziyaretçi (el takibi) verisinden otomatik ayırır.

**Ham veri:** `data\telemetry\events_YYYYMMDD.jsonl` (her satır bir olay, JSON).
Excel'e almak istersen bu dosyaları sakla. **Gün sonunda `data\` klasörünü USB'ye
kopyalamanı öneririm** (yedek).

Sistem logları (dedektör/sunucu çıktıları, çökme kanıtları): `logs\` klasörü.

---

## 4. Hızlı sorun giderme

| Belirti | Yapılacak |
|---|---|
| Ekranda "BAĞLANTI KESİLDİ / VERİ GELMİYOR" rozeti | 10-15 sn bekle (kendini toparlar). Düzelmezse: `Kiosk-Durdur.bat` → `Matematik-Avi-Baslat.bat`. Kamera USB kablosunu kontrol et. |
| El hiç bulunmuyor | Işık yeterli mi? Oyuncu 2-3 m'de ve zemindeki işarette mi? Kamera oynadıysa **`Kalibrasyon.bat`** ile yeniden kalibre et. |
| İmleç hedefin yanına düşüyor / kaymış | Kamera veya projektör oynamış → **`Kalibrasyon.bat`**. |
| Ekran donuk ama sistem açık | 6 sn içinde oyun kendini yeniler (watchdog). Yenilemezse `Kiosk-Durdur.bat` + yeniden başlat. |
| Hiçbir şey açılmıyor | PC'yi yeniden başlat (otomatik başlatma kuruluysa oyun kendisi gelir). |

Daha fazlası: [KIOSK.md](KIOSK.md) bölüm 5.

---

## 5. Festival ÖNCESİ kontrol listesi

1. **`Sergi-Ayarlari.bat`** çalıştır (bir kez): uyku + ekran kapanması + ekran
   koruyucu kapatılır. (Festival sonrası **`Sergi-Ayarlari-GeriAl.bat`** ile geri al.)
2. **Bildirimleri sustur:** Ayarlar → Sistem → Bildirimler → "Rahatsız etmeyin"i aç
   (script bilerek dokunmuyor; sergi PC'sinde başka yazılım olabilir).
3. **Windows Update:** Ayarlar → Windows Update → "7 gün duraklat" (festival ortasında
   yeniden başlatma sürprizi olmasın).
4. **Saat/tarih doğru mu?** (Telemetri zaman damgaları ve rapor buna dayanır.)
5. **Otomatik oturum açma:** `Win+R` → `netplwiz` → kiosk kullanıcısı için
   "Kullanıcıların... parola girmesi gereksin" kutusunu KALDIR.
6. **Otomatik başlatma:** `Otomatik-Baslatma-Kur.bat` (bir kez, yönetici ister).
7. Kamera + projektör sabitle, zemine oyuncu çizgisi/işareti koy, **`Kalibrasyon.bat`**.
8. **Prova:** Bir oyun oyna → `Rapor.bat` → rapor açılıyor ve oyunun göründüğünden emin ol.
9. PC'yi yeniden başlatıp her şeyin ELLE DOKUNMADAN geldiğini bir kez doğrula.

---

## 6. Festival SONRASI

- `data\` klasörünü (telemetri + rapor) güvenli bir yere kopyala.
- `Sergi-Ayarlari-GeriAl.bat` ile güç ayarlarını geri al.
- Otomatik başlatma kalksın istiyorsan: bölüm 2'deki `Unregister-ScheduledTask` komutu.
