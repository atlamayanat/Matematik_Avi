# Gesture Exhibit — El Hareketiyle Fare Yakalama Sergisi

İnteraktif sergi: bir web kamerası kullanıcının elini izler; Unity'de dairesel
bir **büyüteç/el feneri** elin konumunu takip eder; duvara yansıtılan sahnede
**gizli bir fare** (peynir yerken) yalnızca dairenin içinde görünür; kullanıcı
**yumruk** yapınca yukarıdan bir **ağ** düşüp fareyi yakalar, skor +1 olur ve
fare yeni rastgele bir konuma kaçar. Sol üstte sayaç. El **açıkken** arama
durumuna dönülür.

## Mimari

```
  Webcam ─► [PYTHON: detector]                         [UNITY: oyun]
            MediaPipe GestureRecognizer                HandReceiver (OscJack)
            → aktif oyuncu seçimi (lock-on)            → SpotlightController
            → jest FSM (açık/yumruk)        OSC/UDP    → SpriteMask reveal
            → homografi (kamera→duvar)  ─────/hand────► → MouseController
            → One Euro yumuşatma                       → NetCatch + ScoreManager
```

- **İki süreç, tek mesaj:** Python tüm görüyü yapar, Unity'ye tek bir atomik
  `/hand` paketi gönderir → `(float nx, float ny, int present, string gesture)`.
- **Unity saf renderer:** homografi ve yumuşatma Python'da; Unity'yi yeniden
  derlemeden kalibre edebilirsin.
- **Kamera-bağımsız:** `camera/` katmanı soyut. İleride kalabalık sorun çıkarırsa
  derinlik kamerasına (Orbbec Femto Bolt / RealSense) geçiş **Unity'ye
  dokunmadan**, sadece `config.camera.source` ve `camera/depth.py` ile yapılır.

## Hızlı başlangıç

1. **Python detektörü** — `python/` klasörüne gir, bağımlılıkları kur, modeli
   indir, çalıştır. Detaylar: [python/README.md](python/README.md)
   ```
   cd python
   pip install -r requirements.txt
   python download_model.py
   python main.py
   ```
   Önizleme penceresinde elini açıp yumruk yaptığında kutu yeşile döner ve durum
   `searching`/`fist` olarak değişir → Python tarafı çalışıyor demektir.

2. **Unity oyunu** — yeni 2D proje, OscJack kur, sahneyi kur, scriptleri bağla.
   Adım adım: [unity/README.md](unity/README.md)

3. **Kalibrasyon** — projeksiyon + kamera yerine kurulunca:
   ```
   python main.py --calibrate
   ```
   4 köşeyi parmakla işaretle; `calib.json` kaydedilir ve sonraki açılışlarda
   otomatik yüklenir.

## Yol haritası durumu

| Adım | Durum |
|---|---|
| 1. Python: konum + jest tespiti | ✅ |
| 2. Aktif oyuncu seçimi (kalabalık dayanıklılığı) | ✅ |
| 3. Unity: OSC alıcı + eli takip eden daire | ✅ (scriptler + kurulum kılavuzu) |
| 4. Kalibrasyon (4 nokta homografi) | ✅ |
| 5. Reveal mekaniği (gizli fare + maske) | ✅ (script + kurulum) |
| 6. Yakalama (yumruk → ağ → skor → respawn) | ✅ (script) |
| 7. Cila (partikül, ses, geçişler) | ⏳ sahada ayarlanacak |

## Klasör yapısı

```
GestureExhibit/
├─ python/                 # Görü/algılama süreci
│  ├─ main.py              # Ana döngü (camera→detect→select→fsm→map→smooth→OSC)
│  ├─ config.json          # TÜM ayarlanabilir parametreler
│  ├─ download_model.py    # gesture_recognizer.task indirir
│  ├─ camera/              # Kamera soyutlama (webcam | depth-stub)
│  ├─ detection/           # GestureRecognizer sarmalayıcı + tipler
│  ├─ selection/           # Aktif oyuncu seçimi + lock-on histerezisi
│  ├─ gesture/             # Jest debounce FSM
│  ├─ smoothing/           # One Euro filtresi
│  ├─ mapping/             # Homografi + 4 köşe kalibrasyon
│  └─ net/                 # OSC gönderici (python-osc)
└─ unity/Assets/Scripts/   # Oyun tarafı (C#)
   ├─ HandReceiver.cs       # OscJack alıcı (thread-safe)
   ├─ SpotlightController.cs# Büyüteç eli takip eder
   ├─ MouseController.cs     # Fare spawn/respawn
   ├─ NetCatch.cs           # Yumruk → ağ → skor → respawn
   └─ ScoreManager.cs       # Sayaç UI
```
