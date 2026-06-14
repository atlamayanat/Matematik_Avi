# Unity Kurulum Kılavuzu

Bu klasördeki `Assets/Scripts/*.cs` dosyaları oyunun tüm mantığını içerir.
Aşağıdaki adımlar bir Unity sahnesini sıfırdan kurup scriptleri bağlamak içindir.
(Unity 6 / 2022 LTS / 2023 — hepsi uyumlu.)

---

## 1. Proje oluştur
- Unity Hub → **New Project → 2D (Built-in veya URP 2D)** → oluştur.
- Bu repodaki `unity/Assets/Scripts` klasörünü yeni projenin `Assets/` altına
  kopyala (veya bu `unity/` klasörünü doğrudan proje olarak aç).

## 2. OscJack paketini kur (OSC alıcı)
Önce `Packages/manifest.json` dosyasına **scoped registry**'yi ekle (mevcut
`"dependencies"` bloğunun yanına):

```jsonc
{
  "scopedRegistries": [
    {
      "name": "Keijiro",
      "url": "https://registry.npmjs.com",
      "scopes": [ "jp.keijiro" ]
    }
  ],
  "dependencies": {
    // ... mevcut bağımlılıkların ...
  }
}
```

Sonra Unity'de **Window → Package Manager → + → Add package by name →**
`jp.keijiro.osc-jack` yaz, **Add**. (Sürümü boş bırak — UPM en güncel uyumlu
sürümü kendi yazar; böylece elle yanlış sürüm sabitlemezsin.)

> Performans notu: çok yüksek mesaj hızında GC takılması görürsen alternatif
> olarak VRChat'in **OscCore** (zero-alloc) fork'una geçilebilir; bu projedeki
> 60 Hz tek-mesaj akışı için OscJack fazlasıyla yeterli.

## 3. Kamera (projeksiyon görünümü)
- Sahnedeki **Main Camera**'yı seç → **Projection = Orthographic**.
- **Background** = siyah (projeksiyonda siyah = duvarda görünmez → "el feneri"
  hissi buradan gelir).
- `Size` ile görünürlüğü ayarla (örn. 5). Oyun alanı bu kameranın gördüğü
  dikdörtgendir.

## 4. Gizli "dünya" + reveal (SpriteMask) — mekaniğin kalbi
Amaç: sahne siyah; fare yalnızca elin olduğu dairenin içinde görünür.

1. **Sorting Layer** ekle: **Edit → Project Settings → Tags and Layers →
   Sorting Layers → +** `Revealed` (Default'un üstünde).
2. **Spotlight (maske) objesi:**
   - `GameObject → 2D Object → Sprite Mask` oluştur, adı **Spotlight**.
   - Sprite alanına yumuşak kenarlı bir **daire** sprite'ı koy (Unity'nin
     `Knob` built-in sprite'ı iş görür; daha iyisi: kendi yumuşak daire PNG'n).
   - Ölçeğiyle büyüteç çapını ayarla.
   - (İsteğe bağlı) Görünür kırmızı/beyaz **halka** için Spotlight'ın altına bir
     child `SpriteRenderer` koy (Sorting Layer = `Revealed`, en üstte).
3. **Mouse (fare) objesi:**
   - `GameObject → 2D Object → Sprite`, adı **Mouse**, fare+peynir sprite'ını ata.
   - **Sorting Layer = `Revealed`.**
   - SpriteRenderer → **Mask Interaction = Visible Inside Mask**. (Artık fare
     yalnızca Spotlight maskesinin içinde görünür.)
   - (İsteğe bağlı) Bir **Animator** ekleyip "peynir yeme" idle animasyonunu
     loop'a al.
4. Test: Play'e bas, Spotlight'ı elle Scene view'da gezdir → fare sadece dairenin
   altındayken görünmeli.

## 5. Ağ (net) objesi
- Bir **Sprite** oluştur, adı **Net**, ağ sprite'ını ata.
- Sorting Layer = `Revealed`, **Mask Interaction = Visible Inside Mask** (ağ da
  büyüteç içinde görünsün) veya istersen maske dışında da görünür bırak.
- Başlangıçta `SetActive(false)` olacak (script yönetir); sahnede yukarıda park et.

## 6. Sayaç (UI)
- `GameObject → UI → Canvas` (otomatik EventSystem gelir).
- Canvas'a `UI → Text` (veya TextMeshPro) ekle, **sol üst köşeye** yasla
  (anchor top-left), font boyutunu büyüt.
- (TMP kullanırsan `ScoreManager.cs` içindeki yorumda anlatıldığı gibi alanı
  `TMP_Text` yap.)

## 7. Scriptleri bağla
Boş bir GameObject oluştur, adı **GameSystems**, üstüne şu bileşenleri ekle ve
inspector alanlarını doldur:

- **HandReceiver** → `Port = 9000` (Python `config.json` → `osc.port` ile aynı).
- **SpotlightController** → **Spotlight** objesine ekle:
  - `Target Camera` = Main Camera
  - `Flip Y` = açık (genelde doğru)
  - `Follow Speed` = 25 (Python zaten yumuşatıyor)
  - `Visual Root` = (varsa) görünür halka objesi
- **MouseController** → **Mouse** objesine ekle:
  - `Target Camera` = Main Camera, `Margin X/Y` ≈ 0.14, `Animator` = (varsa)
- **ScoreManager** → GameSystems'e ekle, `Label` = sayaç Text'i.
- **NetCatch** → GameSystems'e ekle:
  - `Spotlight` = Spotlight (SpotlightController)
  - `Mouse` = Mouse (MouseController)
  - `Score` = ScoreManager
  - `Net Visual` = Net objesinin Transform'u
  - `Catch Radius` = büyüteç çapına göre ayarla (örn. 0.9 dünya birimi)
  - `Catch Sfx` = (varsa) AudioSource

## 8. Çalıştır
1. Python tarafını başlat: `cd python && python main.py`
2. Unity'de **Play**.
3. Elini oynat → büyüteç takip etmeli; fareyi bulup **yumruk** yapınca ağ
   düşmeli, sayaç artmalı, fare yeni yere kaçmalı.

> İlk testte kamera/projeksiyon kalibre değilse koordinatlar ham gelir ama
> sistem çalışır. Fiziksel kurulumdan sonra `python main.py --calibrate` ile
> daireyi duvara birebir oturtursun.

## 9. Sergi (kiosk) build
- **File → Build Settings → Windows** → Build.
- **Project Settings → Player → Resolution and Presentation:**
  - `Fullscreen Mode = Fullscreen Window` (veya Exclusive)
  - Çok ekranlıysa projeksiyon ekranını hedefle (Display 1'i projeksiyona ata).
- Python detektörünü `--no-preview` ile başlatan bir `.bat`/PowerShell launcher
  yaz; önce Python'u, sonra Unity build'ini aç.

---

## İnce ayar ipuçları
- **Daire ters yönde gidiyor:** `SpotlightController.flipY`'yi veya Python
  `camera.flip_horizontal`'ı değiştir (ikisini birden değil). Flip değişirse
  kalibrasyonu tekrar yap.
- **Yakalama çok kolay/zor:** `NetCatch.catchRadius` (Scene view'da sarı çember
  olarak görünür) ile büyütecin çapını eşleştir.
- **Daire hafif geç kalıyor:** `followSpeed`'i artır; asıl yumuşatma Python'da.
- **Yumruğu algılayıp tekrar tekrar yakalıyor:** zaten edge-trigger; sorun olursa
  Python `gesture_fsm.stable_frames_fist`'i artır.
