# Python Detektörü

Web kamerasından eli algılar, aktif oyuncuyu seçer, jesti (açık/yumruk) ve
konumu çıkarır, homografi ile duvara eşler, yumuşatır ve Unity'ye OSC ile
gönderir.

## Kurulum

> **Not (Python sürümü):** `mediapipe==0.10.35` bu makinedeki **Python 3.13**
> ile uyumlu bir wheel sunuyor (test edildi). Eğer kendi makinende `import
> mediapipe` aşamasında hata alırsan, MediaPipe'ın resmi olarak desteklediği
> **Python 3.12** ile bir sanal ortam kur:
> ```
> py -3.12 -m venv .venv
> .\.venv\Scripts\Activate.ps1
> ```

```powershell
cd python
pip install -r requirements.txt
python download_model.py        # models/gesture_recognizer.task indirir
```

(İsteğe bağlı ama önerilir — sanal ortam:)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Çalıştırma

```powershell
python main.py                 # önizleme penceresiyle
python main.py --no-preview    # sergi modunda (penceresiz)
python main.py --calibrate     # 4 köşe projeksiyon kalibrasyonu
python main.py --config x.json # farklı config dosyası
```

**Önizleme kısayolları:** `ESC` çıkış, `C` yeniden kalibrasyon.

### Hızlı doğrulama (kamera + jest)
`python main.py` çalıştır. Önizlemede:
- En büyük (sana en yakın) el **yeşil** kutuyla işaretlenir = kilitlenen oyuncu.
- Diğer eller gri kalır (arka plan/izleyici) — kilitlenmez.
- Elini açınca durum `searching`, yumruk yapınca `fist` olur (sol üstte).
- `NOT CALIBRATED` yazıyorsa koordinatlar ham gönderiliyordur; kalibrasyondan
  sonra `CALIBRATED` olur.

## Kalibrasyon

Kamera + projeksiyon fiziksel olarak yerine kurulduktan sonra bir kez:
```powershell
python main.py --calibrate
```
Ekrandaki yönergeye göre **işaret parmağınla** sırayla 4 köşeyi (SOL-ÜST,
SAĞ-ÜST, SAĞ-ALT, SOL-ALT) duvardaki yansıma köşelerine getir ve her birinde
`SPACE` bas. `calib.json` kaydedilir; sonraki açılışlarda otomatik yüklenir.
Sadece kamera/projeksiyon **fiziksel olarak oynarsa** yeniden kalibre et.

## Ayarlama (config.json)

Tüm parametreler `config.json` içinde. En çok dokunacakların:

| Bölüm | Anahtar | Ne işe yarar |
|---|---|---|
| `osc` | `port` | Unity'deki `HandReceiver` portu ile aynı olmalı (varsayılan 9000). |
| `camera` | `device_index` | Birden çok kamera varsa hangisi (0,1,...). |
| `camera` | `flip_horizontal` | Ayna düzeltmesi. El sağa giderken daire sola kayıyorsa değiştir. |
| `detection` | `num_hands` | Kalabalıkta aday el sayısı (2–4 önerilir). |
| `active_player` | `max_size` | Sadece üst sınır (lense yapışan el reddi). **Mesafe (alt) kilidi yok** — tek el uzaktan da seçilir; menzili artık MediaPipe `detection`/`tracking` güveni belirler. |
| `active_player` | `roi_*` | Etkileşim bölgesi; kenardaki izleyici ellerini ele. |
| `active_player` | `steal_ratio`/`steal_frames` | 2 el varken yakındakine geçiş ne kadar zor (titremeyi önleyen histerezis). |
| `gesture_fsm` | `stable_frames_*` | Jest titremesini önleme (artır = daha kararlı, daha yavaş). |
| `smoothing` | `min_cutoff`/`beta` | Bkz. aşağıdaki One Euro ayarı. |

### One Euro yumuşatma ayarı (önerilen prosedür)
1. `beta = 0` yap, `min_cutoff`'u, el sabitken titreme kaybolana kadar **düşür**.
2. Sonra elini hızlı oynat; gecikme (lag) kabul edilebilir olana kadar `beta`'yı
   **artır** (~0.001'den başlayıp ×10 adımlarla).
`beta` burada **normalize** koordinata göre ayarlı; piksel uzayında filtrelersen
çok güçlü olur.

## Sorun giderme

- **`Hand model not found`** → `python download_model.py` çalıştır.
- **El belli bir uzaklıktan sonra algılanmıyor** → mesafe kilidi kaldırıldı; menzil artık MediaPipe güvenine bağlı. Daha uzağı için `detection.min_hand_detection_confidence` ve `min_tracking_confidence`'ı düşür (ör. 0.45→0.3); çok düşürmek hayalet algılama yapar.
- **Kamera açılmıyor** → başka uygulama kamerayı kullanıyor olabilir; `device_index`'i dene.
- **Daire ters yönde** → `camera.flip_horizontal`'ı veya Unity'de `SpotlightController.flipY`'yi değiştir; kalibrasyonu flip değiştikten sonra **tekrar** yap.
- **`import mediapipe` hatası** → yukarıdaki Python 3.12 sanal ortam notuna bak.
- **Daire titriyor / geç kalıyor** → One Euro ayarı (yukarı).
- **Daire arka plandaki birine atlıyor** → `active_player.steal_ratio`'yu artır (yakındaki elin devralması zorlaşır), `roi_*` bölgesini daralt. (Not: mesafe kilidi kaldırıldığı için uzaktaki tek el de seçilir; tek oyuncu senaryosunda bu istenen davranıştır.)
