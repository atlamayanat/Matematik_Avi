# Matematik Avı — El Takibi İyileştirmeleri: Saha Ayar Rehberi

Bu belge, `ANALIZ-VE-ONERILER.md` içindeki el-takibi önerilerinin **hepsinin** `son`
branch'ine uygulanmış halini ve **her birini nasıl deneyip ayarlayacağını** anlatır.

> **Önemli:** Her ayar `config.json`'dan açılıp kapatılabilir. Yeni davranışlar
> **kod desteği** ister ama hepsi geri alınabilir. Bir şey ters giderse ilgili
> anahtarı eski değerine döndür — kod eski yola düşer.

> **Altın kural:** Aynı anda **tek** parametre değiştir → `[stats]` / `MA_DEBUG` /
> önizleme penceresi / `?fps=1` ile etkisini ölç → sonra bir sonrakine geç.
> Ayarları masaüstünde değil, **gerçek çadırda, hedef PC'de, 2-3 m mesafede** yap.

---

## 0. Nasıl ölçerim? (ayar yaparken bunları kullan)

| Araç | Nasıl | Ne gösterir |
|---|---|---|
| **Önizleme penceresi** | Dedektörü normal çalıştır (pencere açık) | Her elin `z{...}m` derinliği, `sz` boyutu, jest, **FPS**, kilitli el (yeşil) |
| **`[stats]` satırı** | `logs\detector_*.out.log` (dakikada bir) | `fps`, `hands_pct`, `locked_pct`, `cam_fail` |
| **`MA_DEBUG`** | Ortam değişkeni bir log yoluna ayarla (ör. `set MA_DEBUG=C:\ma_dbg.log`) | İki el varken `z` değerleri + kilit/steal kararı — **yanlış-el atlamasını** izler |
| **`?fps=1`** | Tarayıcı URL'sine ekle (ör. `...index.html?input=ws&fps=1`) | Web tarafı canlı FPS + en kötü kare süresi |
| **`Rapor.bat`** | Prova sonrası çalıştır | `[stats]`'tan derlenmiş sağlık özeti |

---

## 1. Derinlik sertleştirme (`config.json > camera`)

Amaç: z-gate'e **dolu, gürültüsü azaltılmış** derinlik ver → kalabalıkta doğru el.

```jsonc
"depth_visual_preset": "high_density",  // yanlış-steal görülürse "high_accuracy"
"laser_power": 225,                      // 0-360, default 150; sıcak çadırda 200-250 orta yol
"emitter_enabled": 1,
"depth_gain": 16,
"decimation_magnitude": 2,               // 1 = KAPALI. Asıl gürültü/delik azaltıcı
"disparity_transform": true,             // spatial/temporal'ı disparity uzayında sarar
"spatial":  { "enabled": true,  "magnitude": 2, "alpha": 0.5, "delta": 20, "holes_fill": 0 },
"temporal": { "enabled": false, "alpha": 0.4, "delta": 20, "persistency": 3 },
"hole_filling": false
```

**Ayar sırası:**
1. Dedektörü aç, önizlemede ellere bak. `MA_DEBUG` ile **`z=None` oranını** izle
   (iki el varken `z...None` görünürse derinlik boş demektir).
2. `z=None` çoksa: önce `temporal.enabled=true` yap (persistency=1 dene). Hâlâ boşsa
   `laser_power`'ı 300'e kadar çıkar (**ama çadır ısınıyorsa dikkat**).
3. **Uçan-piksel / sahte-yakın okuma (yanlış steal)** görürsen: preset'i
   `"high_accuracy"` yap.
4. `hole_filling`'i **açma** (el kenarı deliklerini uzak arka planla doldurup
   z-gate'i bozar).

> **Filtre sorun çıkarırsa (kamera "kare vermiyor" derse):** Filtre zinciri donanımda
> renk karesini düşürüyor olabilir. Kod bunu yakalayıp ham derinliğe düşer, ama emin
> olmak için `decimation_magnitude: 1` + `spatial.enabled: false` + `temporal.enabled:
> false` yaparak zinciri tamamen kapat (o zaman eski davranış = sadece align).

---

## 2. El modeli (`config.json > detection`)

```jsonc
"num_hands": 3,                          // 2 -> 3
"min_hand_detection_confidence": 0.4,    // ⚠ dikkat, aşağıya bak
"min_hand_presence_confidence": 0.5,     // ⚠ dikkat
"min_tracking_confidence": 0.3,
"delegate": "cpu"                        // Windows'ta GPU yok; "gpu" verirsen CPU'ya düşer
```

**`num_hands: 3` (doğruluk kaldıracı):** Kalabalıkta kilitli oyuncunun eli ilk-2
elden düşmesin diye. **Bedeli FPS.** Hedef PC'de sıcak çadırda önizleme/`[stats]`
FPS'ini oku: **el dalı FPS'i ~15-20 altına inerse `2`'ye dön.**

> ⚠ **`min_hand_detection`/`min_hand_presence` yükseltmesi (0.35→0.4, 0.4→0.5):**
> Belge bunları öneriyor ama bu, 2-3 m'deki **soluk/küçük çocuk elini daha geç**
> tespit ettirir — yani "çocuk elini kaçırma" riskini **artırabilir**. Prova sırasında
> uzaktaki küçük eller geç yakalanıyorsa **bu ikisini eski değerine (0.35 / 0.4)
> geri al.** `min_tracking: 0.3` düşürmesi ise güvenli (hızlı süpürmede izleme sürer).

---

## 3. Jest FSM (`config.json > gesture_fsm`)

```jsonc
"window": 9, "fist_votes": 6, "open_votes": 4   // eski: 7/4/4
```

Giriş **bilinçle sertleşti** (hayalet yumruk = yanlış cevap riskini boğar). Commit
~6 çıkarım karesinde olur (~200-300 ms). İmleç FSM'den ayrık (60 Hz) olduğu için bu
gecikme **oyuncuya yansımaz**.
- **Kural:** `fist_votes + open_votes > window` (6+4=10 > 9 ✓). Bozarsan kod hata verir.
- Yumruk **geç yakalanıyor**sa: `8/5/4` dene (daha tepkisel).
- "**İşaret ederken seçildi**" hayaleti görürsen: `detection.fist_min_curled`'ı `4` yap
  (asıl çözüm budur, pencere değil).

---

## 4. Aktif oyuncu (`config.json > active_player`)

```jsonc
"assoc_max_dz": 0.35,      // 0.4 -> 0.35
"steal_z_margin": 0.35,    // 0.25 -> 0.35 (idle el daha zor çalar)
"acquire_frames": 4,       // YENİ: kilit için N kare stabil aday şart (bystander latch'i keser)
"steal_seconds": 0.8,      // YENİ: steal eşiği KARE yerine SANİYE (termal fps düşüşüne dayanıklı)
"lost_seconds": 1.0        // YENİ: release eşiği saniye
```

- `acquire_frames`: merkezden geçen seyirciye anlık yanlış-kilidi keser. Kilit
  **çok yavaş** geliyorsa `2-3`'e indir; **yanlış latch** hâlâ varsa `5-6`'ya çıkar.
- `steal_seconds`/`lost_seconds`: fps bilindiğinde otomatik kareye çevrilir. **0
  yaparsan** eski kare-bazlı `steal_frames`/`lost_frames_to_release` kullanılır.
- **El değiştirme çok zorsa** (öbür eli uzatınca geçmiyor): `steal_z_margin`'i
  `0.30`'a indir. **İstemeden çalıyorsa**: `0.40`'a çıkar.

---

## 5. Yaklaşan ziyaretçi / attract (`active_player` + `net`)

```jsonc
// active_player:
"attract_near_z_m": 1.2,     // bu mesafeden yakın gövde = "yaklaşıyor"
"attract_pixel_frac": 0.04,  // merkez ROI'nin en az %4'ü yakınsa tetikle
// net:
"send_approaching": true
```

Merkez bölgede yakın piksel oranı eşiği aşınca web'e `approaching` bayrağı gider ve
attract'taki hayalet demo **hemen** uyanır (çocuğu içeri çeker).
- **Hiç tetiklenmiyor:** `attract_pixel_frac`'ı `0.02`'ye indir veya `attract_near_z_m`'yi
  `1.5`'e çıkar.
- **Sürekli tetikleniyor / attract titriyor:** `attract_pixel_frac`'ı `0.08`'e çıkar.
- Tamamen kapatmak için `send_approaching: false` (oyun-içi el takibini etkilemez).

---

## 6. İmleç tahmini + yumuşatma (`config.json > smoothing` + web)

```jsonc
"beta": 0.9,                          // 0.6 -> 0.9 (ekstrapolasyondan SONRA ayarla)
"predict_enabled": true,              // 60Hz hız-tahminli imleç (basamağı siler)
"predict_lead_ms": 24,
"predict_horizon_cap_ms": 50,
"predict_freeze_on_fist": "damped",   // "freeze" | "off" de olur
"predict_gain": 1.0                   // overshoot'ta 0.5-0.8'e indir
```

Web tarafı (`web/js/lens.js`): `LENS_SMOOTH 0.22 -> 0.6`, `LENS_MAX_SMOOTH 0.6 -> 0.85`.

**Ayar sırası:**
1. `predict_enabled: true` ile basamak kayboldu mu, **overshoot** (imleç hedefi aşıp
   geri geliyor mu) bak. Aşıyorsa önce `predict_gain`'i `0.7`'ye indir.
2. Sonra web `LENS_SMOOTH`'u dene: çok titrekse `0.4-0.5`'e indir.
3. En son `beta`'yı ayarla (yüksek = hızlıda daha tepkisel ama daha titrek).
4. Yumruk anında imleç kayıyorsa `predict_freeze_on_fist: "freeze"` yap (tam dondurur).
5. **Gecikme senin için sorun değilse bu bölümün tamamını atlayabilirsin:**
   `predict_enabled: false` + web'de `LENS_SMOOTH`'u `0.3`'e döndür → eski, daha çok
   yumuşatılmış davranış.

---

## 7. Kalibrasyon (`config.json > calibration`)

```jsonc
"fit_method": "ransac",       // titreyen tek nokta outlier olarak reddedilir
"ransac_reproj_frac": 0.02,   // eşik = proj_w * 0.02 px
"accept_error": 0.02,         // 0.03 -> 0.02 (daha sıkı kabul)
"undistort_rgb": false        // ⚠ VARSAYILAN KAPALI — aşağıyı oku
```

- Kalibrasyon ekranında artık **nokta-başı rezidü** yazdırılır (`logs`'ta): hangi köşe
  kötü fit oldu görürsün.
- **`accept_error`** sık "KÖTÜ" veriyorsa `0.03`'e geri al (ya da `A`'ya iki kez basıp
  yine de kaydet).

> ⚠ **`undistort_rgb` (varsayılan KAPALI, bilinçli):** Lens bozulmasını fabrika
> intrinsics'i ile kaldırır (köşelerde etkili). **Denemek için:**
> 1. `"undistort_rgb": true` yap.
> 2. **YENİDEN KALİBRE ET** (`main.py --calibrate` veya oyunda `C`). Undistort bilgisi
>    `calib.json`'a gömülür; eski kalibrasyonla karışmaz.
> 3. RealSense yoksa (webcam) undistort sessizce **devre dışı** kalır (intrinsics yok).

### 🔴 cursor_gain tuzağı (düzeltildi)
`cursor_gain` artık `calib.json`'a **kaydediliyor**. Açılışta config'deki `cursor_gain`
kayıtlıdan farklıysa **"köşe token'ları erişilemez olabilir, yeniden kalibre et"**
uyarısı çıkar. `cursor_gain`'i değiştirdiysen **mutlaka yeniden kalibre et.**

---

## 8. RGB / aydınlatma kilidi (`config.json > camera > rgb_lock`) — ⚠ VARSAYILAN KAPALI

```jsonc
"rgb_lock": { "enabled": false, "exposure": 156, "gain": 16, "white_balance": 4600 }
```

**Neden kapalı:** Denetimsiz kioskta pozlamayı yanlış kilitlersen gün boyu **sessizce
karanlık/patlamış görüntü** üretir — düzeltecek operatör yok, mevcut auto-exposure'dan
**daha kötü.** Bu yüzden asıl RGB koruması **fiziksel** olmalı:

1. **Ellere difüz dolgu ışığı** (perdeye vurmayan) — tespit RGB'de çalıştığı için en
   yüksek kaldıraç budur.
2. Titremesiz (flicker-free) LED sürücü.
3. Kamerayı ışık sızıntısından uzağa, arka planı mat tut, lense kısa hood.
4. Havalandırma/soğutma (termal throttle FPS düşürür).

**Kilidi denemek istersen (sadece nihai ışıkta):** `rgb_lock.enabled: true`, önizlemede
elin net/donuk olduğunu, hareket bulanıklığı olmadığını doğrula. Değerleri sahadaki
ışığa göre ayarla. Emin değilsen **kapalı bırak** (auto-exposure devrede kalsın).

---

## 9. Ağ (`config.json > net`)

```jsonc
"tcp_nodelay": true,       // Nagle kapalı; localhost'ta nadir ~40ms sıçramayı önler
"send_approaching": true   // bkz. Bölüm 5
```
Zararsız; sorun çıkarırsa `tcp_nodelay: false`.

---

## 10. Saha ayar protokolü (uygulama sırası)

1. **Fiziksel:** projektör + kamera + oyuncu geometrisi, kamerayı rijit sabitle, dolgu
   ışığı, çadırı gerektiği kadar (fazla değil) karart.
2. **Derinlik (Bölüm 1):** filtreleri aç, `MA_DEBUG` ile `z=None` oranını düşür.
3. **FPS (Bölüm 2):** `num_hands=3` ile el dalı FPS'ini oku; düşükse `2`'ye dön.
4. **Jest (Bölüm 3):** gerçek çocuk yumruklarıyla ghost-net vs geç-tepki dengesini kur.
5. **Aktif oyuncu (Bölüm 4):** `MA_DEBUG` ile yanlış steal/latch var mı bak.
6. **Tahmin (Bölüm 6):** `predict_enabled` aç → overshoot → `LENS_SMOOTH` → `beta`.
7. **Kalibrasyon (Bölüm 7):** RANSAC ile kalibre et, rezidülere bak, köşeleri **gerçek
   çocuk boyuyla** test et.
8. **Prova:** bir tam oyun oyna → `Rapor.bat` → telemetri geliyor mu. PC'yi yeniden
   başlatıp elle dokunmadan geldiğini gör.

> Kapalı sıcak çadırda **termal yönetim**, tek tek parametre ayarından daha çok FPS
> kazandırır.

---

## 11. Her şeyi geri almak

Ayrı `son` branch'indesin, güvendesin. Tümünü geri almak için:

```bash
git checkout -- python/ web/          # tüm çalışan değişiklikleri at
# veya sadece config'i eski değerlere döndür (kod eski yola düşer)
```

Tek tek geri almak için her bölümdeki anahtarları eski değerine döndürmen yeter:
`num_hands 2`, `gesture_fsm 7/4/4`, `assoc_max_dz 0.4`, `steal_z_margin 0.25`,
`acquire_frames 1`, `steal_seconds/lost_seconds 0`, `predict_enabled false`,
`fit_method "lsq"`, `undistort_rgb false`, `beta 0.6`, ve web `LENS_SMOOTH 0.22`.

---

## Özet: en yüksek getirili 2 madde

Analiz belgesinin de vurguladığı gibi, asıl kazanç algoritmada değil:
1. **Fiziksel RGB koruması + dolgu ışığı** (Bölüm 8) — tespit RGB'de çalışıyor.
2. **`num_hands: 3`** (Bölüm 2) — tek satır, geri alınabilir, kalabalıkta kilit kaybını azaltır.

Gerisi denemeye değer ama önce bu ikisini ve **termal/havalandırmayı** oturt.
