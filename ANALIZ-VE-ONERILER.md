# Matematik Avı — Kapsamlı Analiz ve Değişiklik Önerileri

> **Bağlam:** Konya Bilim Festivali, **kapalı çadır**, Intel RealSense **D435f** (dahili IR band-pass filtreli aktif stereo RGB-D), projektör, Windows 11 PC. El/jest ile oynanan eğitici matematik sergisi. İnceleme `deneme` branch'i üzerinde yapıldı.
>
> **Yöntem:** Kod tabanı aşama aşama okundu + her aşama için endüstri/best-practice araştırması yapıldı + öneriler festival koşuluna göre sentezlendi + bağımsız bir **fizibilite kritiği** ile çelişkiler ayıklandı. Bu belge o kritiğin bulduğu çelişkileri **çözülmüş** haliyle sunar (Bölüm A.4).
>
> **Bu belge bir DEĞİŞİKLİK değil, ANALİZ + ÖNERİ belgesidir.** Kod değiştirilmedi.

---

## 0. Yönetici Özeti

**Ana bulgu: mimari zaten olgun.** Boru hattı (RGB-D yakalama → MediaPipe HandLandmarker → derinlik-öncelikli aktif oyuncu seçimi → world-landmark yumruk FSM → homografi → One Euro → WebSocket → tarayıcı kiosk) best-practice ile birebir, bazı yerlerde üstünde. Arka-plan yakalama thread'i, `result_id` ile yalnız-yeni-çıkarım işleme, timestamp-eşli depth ring, coast + ghost-fist koruması, watchdog'lu kiosk süpervizörü, kapsamlı JSONL telemetri — hepsi doğru kurulmuş. **Yani "sıfırdan ne yapmalı" değil, "doğru yerlerinden nasıl güçlendirilir" sorusundayız.**

**En yüksek getirili 3 kaldıraç:**

1. **Derinlik sensörünü sertleştir (Aşama 1).** Bugün derinlik akışına **hiçbir** kalite ayarı uygulanmıyor (preset yok, laser/emitter ayarı yok, filtre yok). Aktif oyuncu seçiminin tüm gücü z (derinlik) verisinin dolu gelmesine bağlı; z boşsa sistem sessizce zayıf "boyut" yedeğine düşüp yanlış ele atlıyor. Bu en ucuz, en yüksek etkili düzeltme.
2. **60 Hz tahminli imleç (Aşama 8 + 6).** Şu an 60 Hz heartbeat çıkarımlar arasında **aynı konumu tekrar gönderiyor** → imleç görünüşte 60 fps, gerçekte 20-30 Hz basamaklı. Üstelik Python One Euro + web üstel yumuşatma **çift low-pass** ile gecikme bindiriyor. Hız-tabanlı ekstrapolasyon + web filtresini tekile indirme → "hep canlı imleç" hedefinin gerçek eksiği budur.
3. **Kapalı-çadır RGB koruması (Bölüm B).** Kritiğin yakaladığı en önemli nokta: **el TESPİTİ derinlikte değil, RGB renk görüntüsünde çalışır.** Projektör kontrastı için çadırı karartmak RGB'yi bozar → 2-3 m'deki küçük/hızlı çocuk eli kaçar. Kapalı çadırda güneş sorunu yok (senin netleştirdiğin gibi), ama bu **kendi kendine yarattığımız** karartma-vs-RGB gerilimi kalıyor ve çözülmesi şart.

**Model değişimi gerekmiyor.** YOLO-pose, RTMPose, GestureRecognizer, Kalman, ByteTrack, TPS, BlazePose — hepsi tek tek değerlendirildi; her biri ya net kazanç getirmiyor ya da bu senaryonun kök gücünü (RGB-D derinliği + yönelim-değişmez world-landmark yumruk) feda ediyor. **6 aşamada aynı modelde kal-ince ayar yap; yalnız 2 aşamada (1 ve 8) gerçek yeni bileşen ekle.**

**Genel tavsiye:** Odak yeni özellik değil, **saha dayanıklılığı ve sessiz-arıza görünürlüğü**. Tüm eşik/gain ayarları masaüstünde değil **gerçek 2-3 m mesafede ve hedef PC'de** doğrulanmalı.

---

# BÖLÜM A — ALGORİTMA / MODEL YIĞINI (ASIL ODAK)

## A.0 Felsefe: "değiştirme, güçlendir"

Sekiz aşamanın hepsi tek sonuca yakınsıyor: mevcut mimariyi koru, iki yere gerçek bileşen ekle (derinlik filtresi + tahminli üst-örnekleme), kalanı parametreyle kalabalık/çocuk sağlamlığına ayarla.

## A.1 Önerilen Uçtan Uca Akış

```
┌─────────────────────────────────────────────────────────────────────┐
│ [1] KAMERA & DERİNLİK ÖN-İŞLEME — Intel RealSense D435f              │
│   Renk 960x540@60  +  Derinlik 848x480@60  (KORU)                   │
│   EKLE: High Density preset · emitter=1 · laser ~200-250mW          │
│   Filtre (disparity uzayında, capture thread'de STATEFUL, MİNİMAL): │
│     Decimation(2) → [Spatial hafif] → align(color)                  │
│     (Temporal varsayılan KAPALI; z_m=None hâlâ yüksekse persist=1)  │
│   Örnekleme: palm-merkez 11x11 yama, 25. persentil  (DEĞİŞME)       │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼  renk + hizalı metrik derinlik
┌─────────────────────────────────────────────────────────────────────┐
│ [2] EL TESPİTİ & LANDMARK — MediaPipe HandLandmarker (Tasks API)     │
│   hand_landmarker.task · LIVE_STREAM async · delegate=CPU (Win'de   │
│   GPU YOK) · num_hands=3(ölç) · detect=0.4 presence=0.5 track=0.3   │
│   Çıktı: 21 landmark + hand_world_landmarks(3B) + handedness        │
│   Girdi downscale = SON ÇARE (bkz. A.4/çelişki-1)                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼  main.py timestamp-ring: z_m AYNI kareden
┌─────────────────────────────────────────────────────────────────────┐
│ [3] JEST (yumruk) — 3B world-landmark geometrik curl (GR DEĞİL)      │
│   curl_ratio=0.7 · min_curled=3 · başparmak yok sayılır             │
│   Kayan-pencere çoğunluk oyu FSM: window=9 fist=6 open=4            │
│   Yalnız yeni çıkarım + coast-DEĞİL karede tıklanır                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ [4] AKTİF OYUNCU SEÇİMİ — depth-first nearest-hand (MOT DEĞİL)       │
│   Engagement zone (dar merkezi ROI) + z-gate + tutucu steal        │
│   acquire_frames=4 histerezis(YENİ) · eşikler SANİYE-tabanlı(YENİ)  │
│   steal_z=0.35 · steal~0.8s · lost~1.0s · assoc_max_dz=0.35        │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ [5] POZ/GÖVDE — EKLENMEZ. Attract için ~0-maliyet depth-blob tetiği  │
│   merkezi ROI'de z<1.2m piksel oranı>0.04 → "yaklaşıyor"           │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ [6+8] YUMUŞATMA & GECİKME MASKELEME — One Euro + tahmin              │
│   One Euro KORU (min_cutoff=1.0, beta 0.6→0.8-1.0 ölç)             │
│   + sabit-hız dead-reckoning ekstrapolasyon (heartbeat'te ileri)   │
│     predict_lead_ms=24 · horizon_cap=50 · fist'te DAMPED (tam-donma │
│     değil; oy oranına göre; bkz. A.4/çelişki-3)                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ [7] KALİBRASYON & EŞLEME — tek 9-nokta homografi (TPS DEĞİL)         │
│   findHomography method=0 → RANSAC(thr=proj_w*0.02)                 │
│   + faktori RGB intrinsics ile undistortPoints ÖN-İŞLEM             │
│   Drift → operatöre UYARI (sessiz oto-recal DEĞİL)                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ [ÇIKIŞ] WebSocket 60Hz — fire-and-forget latest-wins + TCP_NODELAY  │
│   Web: lens.js LENS_SMOOTH 0.22→0.5-0.7 (çift-filtreyi kaldır)      │
│   stale watchdog 600ms + backoff reconnect (KORU)                   │
└─────────────────────────────────────────────────────────────────────┘
```

## A.2 Aşama-Karar Tablosu

| Aşama | Mevcut | Karar | Öneri (model/algoritma) | Efor |
|---|---|---|---|---|
| **1. Kamera & Derinlik** | Sadece `align`; filtre/preset/emitter yok | **EKLE** | Decimation(2)+HighDensity+emitter+laser~200-250mW; spatial hafif, temporal kapalı | Orta |
| **2. El Modeli** | HandLandmarker CPU, ilk eşikler | **KAL+ayar** | Aynı bundle; num_hands=3 (ölç), eşik ayarı, delegate=CPU açık | Düşük |
| **3. Jest (yumruk)** | world-curl + FSM (7/4/4) | **KAL+ayar** | Aynı geometri; FSM 9/6/4 | Düşük |
| **4. Aktif Oyuncu** | depth-first, kare-tabanlı eşik | **KAL+güçlendir** | num_hands↑, saniye-tabanlı eşik, acquire histerezisi | Düşük |
| **5. Poz/Gövde** | Yok | **EKLEME** | Poz modeli koyma; depth-blob attract tetiği | Düşük |
| **6. Yumuşatma** | One Euro, çıkarım hızında | **KAL+tahmin** | One Euro + hız ekstrapolasyonu | Düşük |
| **7. Kalibrasyon** | tek homografi, method=0 | **KAL+güçlendir** | RANSAC + intrinsics undistort ön-işlem | Düşük |
| **8. Pipeline/Gecikme** | heartbeat aynı değeri tekrarlar, çift low-pass | **EKLE** | 60Hz tahminli üst-örnekleme + web filtre passthrough + TCP_NODELAY | Düşük |

## A.3 Aşama Aşama Derinlemesine

### Aşama 1 — Kamera & Derinlik Ön-İşleme  ⚠️ *eksik-eklenmeli*
**Mevcut:** `depth.py` her frameset için yalnız `rs.align(color)` yapıp z16'yı metreye çeviriyor. Hiçbir post-processing, preset, laser/emitter/gain ayarı yok. Örnekleme (`base.py` `sample_depth`) 11x11 yamada 25. persentil — **bu zaten best-practice, dokunma.**

**Neden kritik:** z-gate'in en büyük zafiyeti derinliğin **bulunamaması** (`z_m=None`). O zaman seçici el/gövde ayrımını kaybedip boyut-oranı yedeğine düşüyor → kalabalıkta yanlış el. Decimation delik/uçan pikseli öldürür **ve** align girdisini 848×480→424×240 yaparak tek büyük maliyet kalemini (~2-3 ms align) yarıya indirir.

**Öneri (minimal-etkili):**
- `visual_preset = HIGH_DENSITY` (fill önceliği; z_m sürekli dolu). Uçan-piksel kaynaklı sahte-yakın okuma (yanlış steal) görülürse `HIGH_ACCURACY`.
- `emitter_enabled=1`, `laser_power ~200-250mW` (default 150; kapalı karanlık çadır + band-pass → yüksek emniyetli, **ama sıcak çadırda termal için 300 yerine ~200-250 orta yol** — bkz. A.4/çelişki-7).
- `decimation(magnitude=2)` — **asıl kaldıraç.**
- `spatial` yalnız hafif (mag=2, alpha=0.5, delta=20, holes_fill=0), disparity uzayında.
- `temporal` **varsayılan KAPALI.** z_m=None hâlâ yüksekse `persistency=1` ile aç — 3 KULLANMA (hızlı çocuk eli 2-3 m'de hayalet iz bırakır, gate okumasını geciktirir).
- `hole_filling` **KAPALI** (el kenarı deliklerini uzak arkaplanla doldurup z-gate'i tam da önlemek istediği yerde bozar).
- `gain=16` (min), pozlama önceliği.
- **Filtre nesneleri STATEFUL** → capture thread'inde bir kez oluştur, her karede yeniden yaratma (yoksa temporal geçmişi sıfırlanır).

> `1280x720@30`'a **geçme** — 60 fps canlı his + düşük hareket bulanıklığı > uzamsal detay.

### Aşama 2 — El Tespiti & Landmark  ✅ *iyi-ince-ayar-yeter*
**Karar: MediaPipe HandLandmarker'da KAL.**
- **Windows'ta MediaPipe Tasks GPU delegate YOK** (Ubuntu-sınırlı) → RTX'i bu framework'te kullanmanın yolu yok; GPU için komple framework değişimi gerekir ki bu `hand_world_landmarks`'ı (yönelim-değişmez yumruk için şart) atar. **Gerekmez:** tasarım çıkarımı (CPU ~20-30 Hz) zaten 60 Hz imleç heartbeat'inden ayırmış.
- Alternatifler elendi: eski `mp.solutions.hands` (deprecated), YOLO11-pose (el keypoint'i değil, world-lm yok), RTMPose-Hand (iki-aşama + TensorRT kırılganlığı). Dar boğaz doğruluk değil.
- **Öneri config:** `num_hands=3` (ölç — bkz. A.4/çelişki-2), `min_hand_detection=0.4`, `min_hand_presence=0.5`, `min_tracking=0.3` (düşük tut → hızlı süpürmede izleme sürer), `delegate=CPU` açıkça yaz (niyeti belgeler; GPU verirsen NotImplementedError → çökme döngüsü).

### Aşama 3 — Jest Tanıma (yumruk)  ✅ *iyi-ince-ayar-yeter*
**Karar: world-landmark geometrik curl'ü KORU; GestureRecognizer'a GEÇME.** Canned Closed_Fist kafası "kameraya uzanan yarım çocuk yumruğu"nda çoğu kez `None` dönüp **sessizce kaçırır**; world-landmark oyun pozunu doğru ele alıyor.
- Bu koşulda pahalı hata **yanlış-yakalama** (yanlış matematik cevabı = eğitim zararı). İmleç konumu FSM'den ayrık (60 Hz coast) olduğu için girişi ~200-240 ms'ye sağlamlaştırmak **bedava**.
- **Öneri FSM:** `window=9`, `fist_votes=6` (giriş sıkı → ghost-net'i boğar), `open_votes=4` (bırakma hızlı; `fist+open>window` kısıtı: 10>9 ✔). `curl_ratio=0.7` KORU (gevşek eşik çocuk yarım-yumruğunu yakalar), `min_curled=3` KORU — "işaret ederken seçildi" ghost'u görülürse **istisnaen** 4.
- **Alternatif (daha tepkisel) set:** `window=8, fist=5, open=4`.

### Aşama 4 — Aktif Oyuncu Seçimi  ✅ *iyi-ince-ayar-yeter*
**Karar: derinlik-öncelikli heuristiği KORU; ByteTrack/SORT'a GEÇME.** Tek-aktif-oyuncu probleminde z-gate, IoU/appearance-MOT'tan hem daha güçlü hem daha ucuz; boşta/bystander eli "yapısal olarak" arkada olduğu için z-margin ile kökten elenir. Müze/Kinect standardı da kalabalığı dense-MOT ile değil **engagement zone + en-yakın-kullanıcı + fiziksel yerleşim** ile çözer.
- **Asıl kalabalık darboğazı bu dosyada değil:** kilitli el `num_hands=2` kapısından düşünce seçici kurtaramaz. → `num_hands` yükselt (en yüksek kaldıraç).
- **Öneri:** `steal_z_margin=0.35`, `assoc_max_dz=0.35`, **eşikleri saniye-tabanlı yap** (`steal_seconds=0.8`, `lost_seconds=1.0`) — sıcak çadırda termal throttle fps'i düşürünce kare-sayımlı eşikler kayar; saniyeyle tanımla, effective-fps ile kareye çevir. **YENİ `acquire_frames=4`** histerezisi (merkezden geçen bystander'a anlık yanlış-latch'i keser). Engagement ROI'yi (`0.35-0.65 / 0.25-0.75`) KORU ama çocuk boyu için y-alt sınırını fazla yükseltme.

### Aşama 5 — Poz / Gövde Takibi  ✅ *iyi-ince-ayar-yeter (eklenmez)*
**Karar: poz/gövde takibi EKLEME.** BlazePose/Holistic **tek-kişi** (top-down) → kalabalıkta oyuncuyu değil ortadaki/en-güçlü kişiyi seçer, yani derinlik-gate'ten **daha kötü**. İkinci CPU modeli HandLandmarker ile yarışıp birleşik çıkarımı ~yarıya düşürerek imleci doğrudan bozar. Poz'un vaat ettiği iki fayda da zaten karşılanmış: (1) oyuncu kapama = derinlik z ile; (2) yaklaşma tespiti = iskelet gerektirmez.
- **Bunun yerine:** mevcut derinlik haritasından **~0 maliyetli** yaklaşma tetiği — merkezi ROI'de `z<attract_near_z=1.2m` piksel oranı `>0.04` → web'e "yaklaşıyor" sinyali (attract'ı `idle>5sn` yerine bununla besle, daha canlı).
- Ekip mutlaka iskelet isterse: **yalnız** `pose_landmarker_lite` (complexity 0), `num_poses=1`, ~5-8 Hz, **yalnız attract ekranında**, oyun/imleç hot-path'ine ASLA sokma.

### Aşama 6 — İmleç Yumuşatma  ✅ *iyi-ince-ayar-yeter (+tahmin ekle)*
**Karar: One Euro'da KAL** (Casiez CHI2012 & LaViola: eşit jitterde Kalman'dan **daha düşük lag**, 2 sezgisel parametre). Kalman CA çocuk yön değişiminde overshoot → seçim ıskası; çift-üstel gereksiz (One Euro zaten hız üretiyor).
- **EKLE:** One Euro'nun zaten hesapladığı `dx_hat/dy_hat` hızını dışarı verip heartbeat karelerinde `pos = last_euro + v·min(dt+lead, horizon)` sabit-hız ekstrapolasyonu.
- **Öneri:** `beta 0.6→0.8-1.0` (ekstrapolasyondan **sonra** ayarla), `min_cutoff=1.0` KORU, `predict_lead_ms=24`, `predict_horizon_cap_ms=50`, `predict_freeze_on_fist` → **tam-donma değil, DAMPED** (bkz. A.4/çelişki-3). Aşıldığında imleci **dondur** (ekrandan uçma yok). Lock değişiminde ekstrapolasyon hızını da resetle.

### Aşama 7 — Kalibrasyon & Eşleme  ✅ *iyi-ince-ayar-yeter*
**Karar: tek 9-nokta homografiyi KORU; TPS/polinoma GEÇME.** Kamera projeksiyonu görmüyor, oyuncu havada kapalı-döngü imleç sürüyor → ilişki gerçekten 2B projektif; homografi teorik olarak kesin. TPS 9 gürültülü noktada ağır overfit + dışbükey zarf dışında (tam da köşe token'larında) vahşi ekstrapolasyon = gözetimsiz kioskta kabul edilemez.
- **Not:** `grid=[3,3]` zaten 9 nokta topluyor ve least-squares'e besliyor — doğru, koru.
- **EKLE:** `findHomography method=0 → RANSAC` (thr=`proj_w*0.02`; titreyen çocuk outlier'ını reddeder) + **faktori RGB intrinsics ile `undistortPoints` ön-işlem** (homografinin modelleyemediği tek nonlineerlik = radyal distorsiyon; 9 noktaya fit etme, faktori katsayıyla kaldır). `accept_error 0.03→0.02`, per-nokta rezidüel raporu.
- **Drift:** kamera projeksiyonu göremediği için sessiz oto-recal **tehlikeli**; bunun yerine seçim-hatası medyanı / ROI-dışı oranı eşiği aşınca **operatöre uyarı**. En iyi drift önlemi: kamerayı mekanik sabitle.

### Aşama 8 — Gecikme & Pipeline  ⚠️ *eksik-eklenmeli*
**Mevcut tesisat best-practice (koru):** capture thread latest-wins, `result_id` gating, depth-ring timestamp eşleme, 60 Hz heartbeat, backoff reconnect.
**Eksik:** görünür gecikmeyi düşüren bileşen (tahmin) yok; heartbeat aynı `mapped`'i tekrarlıyor (basamak) + çift low-pass.
- **EKLE:** Aşama 6'daki ekstrapolasyon (heartbeat'i "hareket eden" 60 Hz sinyale çevirir), `lens.js LENS_SMOOTH 0.22→0.5-0.7` (Python artık düzgün sinyal yolladığı için bir gecikme katmanı silinir), `ws_sender.py` **TCP_NODELAY** (Nagle+gecikmeli-ACK localhost'ta nadir ama ~40 ms sinsi sıçrama yapar).
- **Uçtan-uca gecikme bütçesi (tahmini):** kamera+USB+align ~30-50 ms · async çıkarım ~40-60 ms · basamak/heartbeat ~33-50 ms · One Euro ~15-30 ms · WS ~1-5 ms · web üstel ~30-60 ms · render ~16 ms → **~150-250 ms**. Önerilen değişiklikler en indirilebilir iki dilimi (basamak-tutma + web filtre) hedefler → **~60-100 ms düşüş** beklenir.

## A.4 Çözülen Çelişkiler (fizibilite kritiği → karar)

Kritik, aşamalar arası 7 gerçek çelişki/risk buldu. **Kararlar:**

1. **RGB downscale (640×360)?** — Aşama 8 "yap" (gecikme/hız), Aşama 2 "yapma" (2-3 m küçük/çocuk eli tespitini bozar). **KARAR: varsayılan olarak YAPMA.** Karanlık çadırda RGB zaten bozuk (Bölüm B); en zor vakayı (uzak küçük el) daha da kötüleştirme. Hız önce **termal/güç yönetiminden** gelsin (iki aşama da bunun daha büyük kaldıraç olduğunda hemfikir). Downscale = ölçülmüş **son çare** (FPS kabul edilemez **ve** menzil testi sorunsuzsa).
2. **num_hands 2 mi 3 mü?** — Gerçek darboğaz kilitli elin top-2'den düşmesi; ama her el FPS'e mal olur. **KARAR: `3` dene, hedef PC'de çadırda ÖLÇ.** El dalı FPS'i ~25 altına düşerse `2`'ye dön ve engagement-zone + fiziksel tek-oyuncu kontrolüne yaslan. Bu, num_hands↑ / downscale / termal üçlüsünün aynı CPU bütçesini çektiğini kabul eder — hepsi aynı anda yığılamaz, ölçülür.
3. **freeze_on_fist tam-donma mı damped mi?** — Aşama 6 tam `v→0`, Aşama 8 damped; kritik: tek geçici fist karesi imleci ~240 ms dondurabilir. **KARAR: DAMPED, oy oranına bağlı.** Ekstrapolasyon kazancını FSM fist-oy sayısı arttıkça kademeli düşür (tek geçici fist karesi neredeyse hiç sönümlemez; gerçek biriken yumruk dondurur). Süpürme ortası donmayı önler, seçim isabetini korur.
4. **Filtre zinciri fazla mı?** — Kritik: asıl kazanç decimation; spatial/temporal marjinal-ila-zararlı. **KARAR: decimation(2)+HighDensity+laser+emitter ile BAŞLA; spatial hafif, temporal KAPALI.** z_m=None oranını ölç; gerekirse temporal persist=1 ekle. (A.3/Aşama 1'e yansıtıldı.)
5. **En kritik: karanlık çadırda RGB yolu.** El tespiti RGB'de; derinlik ayarı yalnız z-gate'i besler, tespiti değil. **KARAR: Bölüm B'de P0 olarak ele alındı** (oyun bölgesini tam karartma; ellere difüz dolgu ışığı; RGB pozlama/WB kilidi).
6. **Ekstrapolasyon ufku param adı (40 vs 50 ms)?** — **KARAR: tek parametre:** `predict_horizon_cap_ms=50`, `predict_lead_ms=24`.
7. **Laser 300mW vs termal.** — Sıcak kapalı çadırda 300mW ısı ekler. **KARAR: `laser ~200-250mW` (orta yol) + havalandırmayı P0 yap.** Kapalı çadır + band-pass zaten iyi SNR verdiği için max laser şart değil.

## A.5 config.json — Önerilen Değerler Bloğu (çelişkiler çözülmüş)

> Yalnız **değişen/eklenen** anahtarlar. `YENİ` etiketliler kod desteği de gerektirir. Belirtilmeyen her alan mevcut haliyle korunur.

```jsonc
{
  "camera": {
    "depth_visual_preset": "high_density",   // YENİ; yanlış-steal görülürse "high_accuracy"
    "laser_power": 225,                        // YENİ; 200-250 orta yol (termal), default 150
    "emitter_enabled": 1,                      // YENİ
    "decimation_magnitude": 2,                 // YENİ — ASIL kaldıraç (delik öldürür + align ~yarı)
    "disparity_transform": true,               // YENİ; spatial'ı disparity uzayında sarmala
    "spatial":  { "magnitude": 2, "alpha": 0.5, "delta": 20, "holes_fill": 0 }, // YENİ, hafif
    "temporal": { "enabled": false },          // YENİ; z_m=None yüksekse persistency:1 ile aç
    "hole_filling": false,                     // KULLANMA (z-gate'i bozar)
    "depth_gain": 16                           // YENİ; pozlama önceliği
    // depth 848x480@60 ve RGB auto_exposure_priority=0 KORUNUR
    // + RGB pozlama/WB kilidi: bkz. Bölüm B (P0)
  },
  "detection": {
    "num_hands": 3,                            // 2→3; hedef PC'de ÖLÇ, <25fps ise 2'ye dön
    "min_hand_detection_confidence": 0.4,      // 0.35→0.4
    "min_hand_presence_confidence": 0.5,       // 0.4→0.5
    "min_tracking_confidence": 0.3,            // 0.35→0.3
    "delegate": "cpu",                         // YENİ; Windows'ta açıkça CPU
    "fist_curl_ratio": 0.7,                    // KORU
    "fist_min_curled": 3                       // KORU (işaret-ghost'u görülürse 4)
  },
  "gesture_fsm": { "window": 9, "fist_votes": 6, "open_votes": 4 }, // 7/4/4 → 9/6/4
  "active_player": {
    "assoc_max_dz": 0.35,                       // 0.4→0.35
    "steal_z_margin": 0.35,                     // 0.30→0.35
    "acquire_frames": 4,                        // YENİ (3-5 kare latch histerezisi)
    "steal_seconds": 0.8,                       // YENİ (kare yerine saniye)
    "lost_seconds": 1.0,                        // YENİ (kare yerine saniye)
    "attract_near_z_m": 1.2,                    // YENİ (Aşama 5 depth-blob)
    "attract_pixel_frac": 0.04                  // YENİ
  },
  "smoothing": {
    "min_cutoff": 1.0,                          // KORU
    "beta": 0.9,                                // 0.6→0.8-1.0 (ekstrapolasyondan SONRA ayarla)
    "d_cutoff": 1.0,                            // KORU
    "predict_enabled": true,                    // YENİ
    "predict_lead_ms": 24,                      // YENİ
    "predict_horizon_cap_ms": 50,              // YENİ (tek ufuk parametresi)
    "predict_freeze_on_fist": "damped",         // YENİ; tam-donma DEĞİL, oy oranına bağlı
    "predict_gain": 1.0                         // YENİ; overshoot'ta 0.5-0.8
  },
  "calibration": {
    "grid": [3, 3],                             // KORU (9 nokta zaten least-squares'e gidiyor)
    "fit_method": "ransac",                     // YENİ; method=0 yerine
    "ransac_reproj_frac": 0.02,                 // YENİ (thr = proj_w*0.02 px)
    "undistort_rgb": true,                      // YENİ; faktori intrinsics ile undistortPoints
    "accept_error": 0.02,                       // 0.03→0.02
    "target_inset": 0.06,                       // KORU
    "cursor_gain": 4.0                          // KORU — AMA calib.json'a KAYDET! (Bölüm C, deneme tuzağı)
  },
  "net": {
    "transport": "ws",                          // KORU (tarayıcı için zorunlu)
    "tcp_nodelay": true,                        // YENİ (Nagle kapalı)
    "send_approaching": true                    // YENİ (attract bayrağı)
  }
}
```

**Web (config dışı):** `lens.js` `LENS_SMOOTH: 0.22 → 0.5-0.7`; stale watchdog 600 ms + backoff reconnect KORU.

---

# BÖLÜM B — KAPALI ÇADIR, RGB & AYDINLATMA (kritik kesişim)

Kapalı çadır **güneş/gündüz IR sorununu ortadan kaldırıyor** — bu senin lehine ve derinlik kalitesini stabilize ediyor. Ama en önemli fizibilite bulgusu şu **kendi kendine yarattığımız** gerilim:

**El tespiti (MediaPipe) RGB renk görüntüsünde çalışır, derinlikte değil.** Projektör kontrastı için çadırı karartmak → RGB kararır → `auto_exposure_priority=0` (sabit fps için, doğru) düşük ışıkta uzun pozlama/yüksek gain'e zorlar → 2-3 m'deki **küçük, hızlı çocuk elinde hareket bulanıklığı + gain gürültüsü** → tespit kaçması/jitter. **Aşağı akıştaki hiçbir ayar (derinlik, filtre, ekstrapolasyon) bunu kurtarmaz** — kaynak sinyal bozuksa her şey bozulur.

**Çözüm (P0, hem yazılım hem yerleşim):**
1. **Oyun bölgesini tam karartma.** Difüz LED **dolgu ışığı** — ellere/oyuncu düzlemine yönelik, **perdeye vurmayan** (perde kontrastını korur, elleri aydınlatır). Kapalı çadır bunu kolaylaştırır: dolgu ışığıyla yarışan güneş yok.
2. **RGB pozlama + white balance sabitle.** `enable_auto_exposure=0`, sabit exposure/gain/WB; auto-exposure ROI'yi oyun bölgesine kilitle. Otomatik pozlamanın av aramasını (hunting) durdur.
3. **Projektör tarafında karartma ihtiyacını azalt:** kapalı çadırda daha yüksek ANSI lumen / kısa mesafe / ALR (ambient-light-rejecting) perde → daha az karartma → RGB rahatlar. Kapalı ortamda bu çok daha ulaşılabilir.
4. **Kamera yerleşimi:** çadır girişine/ışık sızıntısına baktırma; lense kısa hood/baffle; arka planı sade/mat tut. (Aktif-stereonun kalan tek zaafı doğrudan parlak kaynak.)
5. **İç aydınlatma tekdüzeliği:** LED/spot titremesi (özellikle ucuz sürücüler + kamera pozlaması etkileşimi) el takibinde jitter yapar → titremesiz (flicker-free/yüksek frekanslı) sürücü kullan.

**Termal & toz (kapalı çadır gerçeği):** Kapalı çadır + PC + projektör + laser = ısı. CPU-bound MediaPipe termal throttle'da FPS düşürür (aynı zamanda saniye-tabanlı eşiklerin gerekçesi). **Yüksek-performans güç planı + aktif havalandırma/soğutma**, çözünürlük düşürmekten daha etkili FPS kazancıdır. Toz için kamera/projektör hava yolu filtresi + günlük lens temizliği.

---

# BÖLÜM C — OPERASYON, UX & TELEMETRİ (destekleyici bulgular)

Geniş analiz (21 ajan) algoritma dışı önemli, çoğu **düşük efor / yüksek etki** kalemler buldu:

### 🔴 `deneme` branch'inin sessiz kalibrasyon tuzağı (senin sorduğun test branch!)
`deneme`, `cursor_gain`'i **1.5→4.0** yaptı ve ROI'leri daralttı. Ama `cursor_gain` **`calib.json`'da saklanmıyor** ve `warn_if_environment_changed` bunu kontrol etmiyor. Operatör yeniden kalibre etmezse **köşe token'ları tüm gün sessizce erişilemez kalır**, hiçbir hata çıkmaz.
- **Öneri:** `cursor_gain`'i `calib.json`'a kaydet; açılışta `config.gain != calib.gain` ise yeniden-kalibrasyon uyar; festival `calib.json`'unu gain=4.0 ile **yeniden üret**.

### 🔴 Testler sessizce koşmuyor
`detection/__init__.py` mediapipe import'u collection'da patlıyor → seçici/geometri testleri hiç çalışmıyor. **Öneri:** mediapipe import'unu tembelleştir + `pytest.importorskip`. Kritik yollar (homografi, aktif oyuncu, smoothing) gerçekten test edilsin.

### 🔴 Onboarding boşluğu
Seçim jesti (**yumruk = seç**) oyun ekranında hiç anlatılmıyor. **Öneri:** kalıcı "YUMRUK YAP = SEÇ" ipucu/ikonu.

### Eğitim / Çocuk UX
- **Yanlış cevapta doğruyu göster** + mesajı yumuşat (puan-düşürmeme'yi koru — cesaret kırıcı olmasın). Öğrenme anı burada.
- **Renk körü yedekliliği:** doğru/yanlış'a ✓/✗ ikon + şekil ekle (yalnız yeşil/kırmızı WCAG'a yetersiz).
- **Yaşa uygun giriş bandı:** adaptif rampanın taban+tavanını KOLAY/ORTA/ZOR seçimine bağla (herkes level=0'dan başlamasın).
- **Adaptif zorluğu %85 doğruluk hedefine** göre kur (kayan pencere + `answer.ms` + histerezis) — mevcut +1/-1 iyi ama hedef-tabanlı daha stabil.
- **Throughput:** her turda tam kalibrasyon tekrarını hafiflet ("yakında kalibre edildiyse atla") — kısa temas/kuyruk için.

### Kiosk dayanıklılığı
- **Soğuk-boot tarayıcı yarışı:** sabit `Start-Sleep 2` yerine 8000/8765 **port-poll** + ölü-sayfa tespiti + reload guard.
- **Güç-kurtarma zinciri:** oto-oturum (Netplwiz) + BitLocker askıya alma + görev `-User/-Principal` scriptleştir (gece kesintisi sonrası sabaha kadar ölü kalmasın).
- **UPS (pure-sine + AVR):** brownout / soğuk-boot / USB re-enumeration zincirlerinin ortak kök-çözümü.
- **Unity build (.exe) yedeği** festival PC'de bulunsun (`transport=ws` iken yanlışlıkla Unity açılırsa ölü ekran).
- **WebSocket protokolüne `"v":1` + opsiyonel `seq`** (sessiz uyumsuzluk koruması).

### Web mi Unity mi?
**Web'de kal.** `deneme`'de aktif hedef web; telemetri, kalibrasyon onboarding, göç planı web'e yönelmiş. Unity'yi **acil yedek** olarak koru (.exe bulundur), ama festival hattı web + Python detektör.

---

# BÖLÜM D — ÖNCELİKLİ YOL HARİTASI

### 🔴 P0 — Festival öncesi ZORUNLU
| # | Madde | Efor |
|---|---|---|
| 1 | Derinlik sertleştir: HighDensity + emitter + laser~225mW + decimation(2) [+spatial hafif] (`depth.py`) | Orta |
| 2 | **Kapalı-çadır RGB koruması:** ellere difüz dolgu ışığı (perdeye vurmayan) + RGB pozlama/gain/WB **kilidi** | Orta |
| 3 | Kamera yerleşimi: ışık sızıntısına baktırma, arka plan mat, lens hood; zemine 1.5-2.5 m oyuncu işareti | Düşük |
| 4 | `calib.json`'a `cursor_gain` kaydet + drift uyarısı; festival calib'ini gain=4.0 ile yeniden üret (**deneme tuzağı**) | Düşük |
| 5 | Test collection hatasını gider (`importorskip`) → seçici/geometri/smoothing testleri koşsun | Düşük |
| 6 | Oyun ekranına kalıcı "YUMRUK YAP = SEÇ" talimatı | Düşük |
| 7 | Yanlış cevapta doğruyu göster + mesajı yumuşat | Düşük |
| 8 | Soğuk-boot tarayıcı yarışını gider (port-poll + ölü-sayfa tespiti) | Orta |
| 9 | Güç-kurtarma zinciri (oto-oturum + BitLocker + görev principal) | Orta |
| 10 | Termal/havalandırma çözümü + yüksek-performans güç planı (kapalı çadır) | Orta |
| 11 | Fiziksel tek-oyuncu kontrolü (zemin işareti/alçak bariyer) + kamera rijit sabitleme | Düşük |
| 12 | Gölgesiz projeksiyon geometrisi (arka/üst mount) | Yüksek |
| 13 | Unity .exe yedeğini festival PC'de bulundur | Düşük |

### 🟠 P1 — Önemli
`num_hands 2→3` (FPS ölç) · 60 Hz tahminli ekstrapolasyon + `LENS_SMOOTH` düşür + TCP_NODELAY · FSM 9/6/4 · saniye-tabanlı steal/lost + acquire histerezisi · RANSAC + undistort kalibrasyon · yaklaşan-ziyaretçi depth-blob tetiği · renk körü ✓/✗ · yaşa uygun giriş bandı · UPS · `Sergi-Ayarlari.bat`'a USB selective-suspend kapat + High Performance.

### 🟡 P2 — İyileştirme
Steal/release sahada ayarla + `depth_fallback` sayacını **telemetriye logla** (sessiz düşüşü görünür kıl) · On-Chip Self-Cal health-check + ≤2 m sertifikalı USB3 kablo · `Rapor.bat`'a walk-up metrikleri (attract/completion/throughput) · attract oto-sıfırlama (30-60 sn idle) · web kalibrasyon tiyatrosunu kısalt · protokole `"v":1`/`seq`.

### 🟢 P3 — Gelecek
Hedef-tabanlı adaptif zorluk motoru · depth+intrinsics 3B unprojection (boy farkı ciddi olursa) · çok-dilli arayüz · gelişmiş telemetri panosu.

---

# BÖLÜM E — GÖZDEN KAÇMASINLAR (eksiklik kritiği)

Algoritma dışında, festival bağlamında ihmal edilmemesi gerekenler:
- **Ses / işitilebilirlik:** gürültülü festival ortamında sesli geri bildirim (doğru/yanlış, seçim onayı) duyulmayabilir → görsel + (mümkünse) titreşimsiz güçlü görsel vurgu; ses varsa yüksek/net.
- **Çocuk verisi & KVKK:** telemetri anonim olsa da "ziyaretçi verisi topluyoruz" şeffaflığı (çadırda kısa bilgilendirme) + hiçbir kişisel tanımlayıcı/görüntü kaydedilmediğinin garantisi (kamera görüntüsü **diske yazılmamalı**).
- **Erişilebilirlik:** tekerlekli sandalye/kısa boy için etkileşim yüksekliği; engagement-zone y-sınırı ve istasyon yüksekliği çocuk + tekerlekli sandalye erişimini birlikte gözetsin.
- **Dil:** arayüz Türkçe; gerek/mümkünse basit ikonografi ile dilden-bağımsız onboarding.
- **Personel eğitimi:** operatöre 1 sayfalık "başlat/durdur/yeniden-kalibre/sorun-giderme" (var: `FESTIVAL-REHBERI.md` — genişlet: RGB-ışık ve termal maddelerini ekle).
- **Yedek donanım / Plan-B:** yedek kamera + USB kablo + (mümkünse) yedek PC; Unity .exe yedeği; "kamera ölürse fare ile demo" modu.
- **Acil durum & hijyen:** temassız oynanış hijyen açısından avantaj (dokunmatik yok); acil kapatma (`Kiosk-Durdur.bat`) operatörde hazır; kablo/geçiş güvenliği.
- **Kuyruk / sıra & çok-oyuncu:** tek-oyuncu tasarım doğru; ama sırayı fiziksel yönet (zemin işareti/şerit) — "yan yana iki kişi aynı derinlikte" senaryosunu sıfır kodla kapatır.

---

# BÖLÜM F — SAHA AYAR PROTOKOLÜ (uygulama sırası)

Ayarları masaüstünde değil, **gerçek çadırda, hedef PC'de, 2-3 m oyuncu mesafesinde** yap. Sıra:

1. **Fiziksel:** projektör + kamera + oyuncu geometrisini kur, kamerayı rijit sabitle, dolgu ışığını ayarla, çadırı gerektiği kadar (fazla değil) karart.
2. **RGB pozlama/WB kilidi** → önizlemede el net/donuk mu, hareket bulanıklığı var mı bak.
3. **Derinlik:** decimation + preset + laser aç; `_dbg_log` (MA_DEBUG) ve `[stats]` ile **`z_m=None` oranını** ölç. Yüksekse laser↑ / temporal persist=1.
4. **FPS ölç:** `num_hands=3` ile el dalı FPS'i `[stats]`'tan oku. <25 ise 2'ye dön (çelişki-2).
5. **Ekstrapolasyon aç** (`predict_enabled`) → basamak kayboldu mu, overshoot var mı; sonra `LENS_SMOOTH` düşür; sonra `beta` ayarla.
6. **FSM/jest:** gerçek çocuk yumruklarıyla ghost-net vs geç-tepki dengesini `window/votes` ile sabitle; "işaret-ghost'u" görülürse `min_curled=4`.
7. **Kalibrasyon:** RANSAC + undistort ile kalibre et; per-nokta rezidüel bak; köşe token'ı erişimini gerçek çocuk boyuyla test et.
8. **Prova:** bir tam oyun oyna → `Rapor.bat` → telemetri geliyor mu doğrula. PC'yi yeniden başlatıp elle dokunmadan geldiğini gör.

> **Altın kural:** her seferinde **tek** parametre değiştir, `_dbg_log`/`[stats]`/telemetri ile etkisini ölç, sonra bir sonrakine geç. Kapalı sıcak çadırda **termal yönetim**, tek tek parametre ayarından daha çok FPS kazandırır.

---

*Bu analiz iki çok-ajanlı workflow (algoritma/model yığını deep-dive + geniş kapsamlı analiz) + bağımsız fizibilite kritiğinin sentezidir. Öneriler kod referanslarına (dosya:satır) ve endüstri kaynaklarına dayanır; çelişkiler Bölüm A.4'te çözülmüştür.*
