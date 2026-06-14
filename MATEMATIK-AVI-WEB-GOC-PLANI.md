# Matematik Avı — Unity'den Web'e (HTML/CSS/JS + Python WebSocket Köprüsü) Taşıma Planı

> Bu belge, sadece **Matematik Avı (MathLens)** oyununu Unity'den çıkarıp, **mevcut Python CV dedektörünü koruyarak** bir WebSocket köprüsüyle beslediğimiz **statik web ön yüzüne** taşımak için kesin, adım adım uygulanabilir yol haritasıdır. Kod değil, **plandır**; ama uygulamayı belirsizlik bırakmayacak kadar somuttur. Tüm dosya yolları mutlaktır.

---

## 0. Kararlar & düzeltmeler (2026-06-14) — BU BÖLÜM ÖNCELİKLİDİR

> Sahip onayıyla netleşen 4 karar ve kritik bir kaynak düzeltmesi. Aşağıdaki bölümlerde (özellikle §6/§7/§11) çelişen ifade olursa **bu bölüm geçerlidir**.

**KRİTİK: Oyun mantığının kaynağı = mevcut Unity MathLens oyunu.** Prototip (`support.js`/`.dc.html`) yalnızca **görsel ve yapısal referanstır**; oyun mantığında (soru üretimi, decoy, token sayısı, histerezis, zamanlama) Unity scriptleri otoritedir. **Tasarımı mevcut oyuna uyarlıyoruz**, oyunu tasarıma değil. Prototipin basitleştirdiği yerler (8 sabit soru, 7-sembol decoy, smoothstep reveal) **kullanılmaz** — Unity'nin gerçek mantığı port edilir.

**Otoriter Unity sabitleri** (kaynak: `RoundManager.cs`, `QuestionGenerator.cs`, `MathField.cs`, `LensHunt.cs`):
- `totalQuestions=5`, `roundSeconds=120`, `correctCopies=3`, `totalTokens=36`, `decoyVariety=14`, `lowTimeThreshold=10`, `resolveDelay=0.85`, `endSummarySeconds=4`.
- Soru üretimi **prosedürel** (Easy 6 tip / Medium 6 / Hard 7) — bkz. güncellenmiş §6.1.
- Decoy: sayısal yakın-ıska + kesir glyph'leri + zorla tuzaklar (sembol-only DEĞİL) — bkz. §6.1.
- Reveal: **linear** `InverseLerp(revealRadius=1.8, revealFull=0.5)` dünya birimi (smoothstep değil).
- Arming Schmitt-trigger: `armRadius=1.05`, `disarmRadius=1.30`, `switchMargin=0.35`, `switchDwell=0.12`, `disarmGrace=0.10`, `cooldown=0.2`.
- Dünya uzayı: kamera ortho size 5 → Y∈[−5,5], X∈[−8.89,8.89] (16:9). Field rect: x∈[−7.5,7.5], y∈[−4.3,3.0], `cell=1.6`, `jitter=0.42`. RESET dışlama: merkez (7.5,4.2), yarıçap 2.4.

**4 karar:**
1. **Decoy/glyph & tüm oyun mantığı → Unity'den** (yukarıdaki gibi). Prototipin azaltılmış seti kullanılmaz.
2. **Attract auto-loop → EVET.** Unity'de yok ama eklenecek: sergide kimse yokken başlangıç ekranı kendi çekim döngüsünü oynar (idle demo / nabız).
3. **CheeseHunt/MouseTrap/_Recovery → en sonda SİLİNECEK.** Arşivlenmez. Nihai hedef: **Unity'den tamamen çıkmak** — web kanıtlandıktan sonra ilgisiz Unity dosyaları (ve sonunda gerekirse tüm Unity projesi) silinir. Silme **en son adımda, doğrulama sonrası, onayla** yapılır (geri dönüşü zor).
4. **Aspect-ratio → `min(w,h)` tabanı.** reveal/arm yarıçapları genişlik yerine `min(w,h)` ile ölçeklenir; 16:9 dışında daire elipsleşmez. Unity dünya-birimi yarıçapları `min(w,h)` oranına çevrilir (height=10 dünya birimi referans): revealStart `0.18`, revealFull `0.05`, arm `0.105`, disarm `0.13`, switchMargin `0.035`.

---

## 1. Amaç & kapsam

**Amaç:** "Matematik Avı" oyununu Unity bağımlılığından kurtarıp, tarayıcıda çalışan statik bir web uygulamasına (build adımı yok: `index.html` + `styles.css` + `js/`) dönüştürmek. El girişi, **olduğu gibi korunan** Python bilgisayarlı görü (CV) hattından bir **WebSocket köprüsü** üzerinden gelir. **Oyun mantığı mevcut Unity oyunundan port edilir; sadece tasarım (Sci-Fi HUD) uyarlanır** (bkz. §0).

**Kapsam içinde:**
- Sadece **Matematik Avı / MathLens** oyunu.
- Görsel kaynak-of-truth: `Matematik Avı.dc.html` prototipi (DC/React çerçevesi soyularak).
- Python tarafında **minimal** ekleme: yeni `net/ws_sender.py`, transport seçim bayrağı, `requirements.txt`'e tek bağımlılık.

**Kapsam DIŞINDA (bu planın konusu değil):**
- **CheeseHunt**, **MouseTrap**, **_Recovery** sahneleri/oyunları — dokunulmuyor (akıbeti için bkz. §11).
- Python CV hattının yeniden yazımı. **Homografi, aktif-oyuncu seçimi, One-Euro yumuşatma, gesture FSM Python'da KALIR.** Tarayıcı yalnızca son ürünü tüketir.
- Tarayıcı-içi landmark/kalibrasyon matematiği (opsiyonel MediaPipe sürücüsü ileride, bkz. §3).

**Çatışma kuralları (CLAUDE.md'den):** Mantık çatışmalarında `GAME_DESIGN.md` kazanır; görsel çatışmalarında `README.md`/`.dc.html` kazanır. Kapsamı değiştiren her kararda (ör. decoy glyph setini genişletmek) önce sahibine sor.

---

## 2. Mevcut vs hedef mimari

### Eski (Unity) akışı

```
+---------+    kamera    +------------------------------+   OSC /hand    +-------------------+
| Webcam  | -----------> |  Python (main.py)            |  UDP 9000      |  Unity            |
|         |   piksel     |  - HandRecognizer (MediaPipe)| -------------> |  OscJack listener |
+---------+              |  - ActivePlayerSelector      |  [nx,ny,       |  -> lens/oyun     |
                         |  - Homography (px->[0,1])    |   present(1|0),|  (MathLens sahne) |
                         |  - One-Euro smoothing        |   "searching"  |                   |
                         |  - GestureFSM (debounce)     |   |"fist"]      +-------------------+
                         |  - OscSender (net/osc_sender)|
                         +------------------------------+
```

### Yeni (Web) akışı

```
+---------+    kamera    +------------------------------+  WS JSON       +-----------------------+
| Webcam  | -----------> |  Python (main.py)            |  ws://ip:8765  |  Tarayıcı (statik)    |
|         |   piksel     |  - [AYNI CV HATTI değişmez]   | -------------> |  js/input.js (ws drv) |
+---------+              |  - GestureFSM (debounce)     |  {x,y,         |  -> js/lens.js        |
                         |  - One-Euro smoothing        |   present,     |  -> js/game.js        |
                         |  - Homography                |   gesture:     |  index.html + CSS     |
                         |  - create_sender(cfg):       |   'open'|'fist'}|  (16:9 kiosk)        |
                         |    OSC | WS | BOTH           |                +-----------------------+
                         |  + net/ws_sender.py (YENI)   |
                         +------------------------------+
```

### `/hand` sözleşmesinin web'e dönüşü

Tel üzerindeki OSC mesajı `/hand [float nx, float ny, int present(1|0), string gesture]` idi (kaynak: `python/net/osc_sender.py`, address `"/hand"`, tam 4 argüman). Web tarafına aynı semantik, **JSON çerçeve** olarak taşınır:

| OSC alanı | Değer | WS JSON alanı | Değer |
|---|---|---|---|
| arg0 `nx` | `mapped[0]` ∈ [0,1] | `x` | `float` ∈ [0,1] |
| arg1 `ny` | `mapped[1]` ∈ [0,1] | `y` | `float` ∈ [0,1] |
| arg2 `present` | `1` veya `0` | `present` | `true`/`false` (bool) |
| arg3 `gesture` | `"searching"` \| `"fist"` | `gesture` | `"open"` \| `"fist"` |

**Tek anlamsal fark:** gesture string'i web-kanonik forma çevrilir (`"searching"` → `"open"`, `"fist"` → `"fist"`). Bu eşleme yalnızca `ws_sender.py` içinde yapılır; Python iç durumu (`gesture/fsm.py` içinde `SEARCHING`/`FIST`) **değişmez**.

---

## 3. El girişi sözleşmesi & seam (dikiş noktası)

**Sabit sözleşme (README, CLAUDE — değiştirilemez):**
```
{ x: 0..1, y: 0..1, present: bool, gesture: 'open' | 'fist' }
```

Tüm oyun mantığı yalnızca bu normalize edilmiş nesneyi tüketir. Prototipte bu **YOK** — prototip `onMove` içinde ham *frame-local piksel* mouse koordinatı kullanıyor ve mouse `click`'ini doğrudan "fist" sayıyor (`.dc.html` satır 685-697). Üretimde bu, **tek bir input modülü** (`js/input.js`) arkasına alınır.

### Tek input modülü, üç sürücü (driver)

`js/input.js` her zaman aynı normalize nesneyi yayar; arkasındaki kaynak takılıp çıkarılabilir:

1. **Mouse sürücüsü (VARSAYILAN — geliştirme):**
   - `mousemove`: `x = clientX/innerWidth`, `y = clientY/innerHeight` (normalize), `present=true`.
   - `mousedown` → `gesture='fist'`, `mouseup` → `gesture='open'`.
   - `mouseleave` (pencere) → `present=false`.
   - Python çalışmadan tüm oyun geliştirilebilir.

2. **WebSocket sürücüsü (PROD — Python'dan):**
   - `new WebSocket('ws://<dedektor-ip>:8765')`.
   - `onmessage`: `JSON.parse(e.data)` → çerçeveyi doğrudan normalize nesneye yaz (zaten sözleşme formatında).
   - Yeniden bağlanma: `onclose`/`onerror` → `setTimeout(connect, 1000)`, üstel backoff ~2-5s tavanlı. Tek bağlantının hayatta kalacağını asla varsayma.

3. **Tarayıcı-içi MediaPipe sürücüsü (OPSİYONEL — ileride):**
   - Aynı normalize sözleşmeyi üretir; bu planın kapsamında **uygulanmaz**, sadece seam'in genişletilebilir kalması için yer bırakılır.

### Kritik seam kuralları

- **Normalize → frame-piksel dönüşümü TEK YERDE.** Modül `0..1` yayar; oyun motoru (`lens.js`) okurken çerçeve `getBoundingClientRect()` ile pikselle çarpar. Prototip her yerde piksel kullandığından, bu dönüşüm atlanırsa `reveal`/`arm` mesafeleri bozulur (bkz. §11 risk).
- **gesture yükselen-kenar (rising-edge) tespiti.** Mouse'ta `click` doğal olarak ayrık bir olaydır; ama sürekli `open`/`fist` akışında (WS/MediaPipe) `judge()` her karede tetiklenir. `input.js` `'open' → 'fist'` geçişinde **bir kez** "fist olayı" yayar (debounce/edge). Mevcut tek koruma `locked` bayrağı (1050ms sonra / `next()`'te temizlenir) — yeterli değildir, edge tespiti şarttır.
- **gesture eşlemesi.** Tel üzerinden zaten `'open'|'fist'` gelir (eşleme Python'da yapılır). Mouse sürücüsünde de aynı iki değer üretilir. `'searching' → 'open'` eşlemesi yalnızca Python `ws_sender`'ın sorumluluğudur; web hiçbir yerde `'searching'` görmez.
- **Tek commit yolu.** Prototipteki çift seçim yolu (`onFist`+`armedDiff` ve ayrıca her butona `onDiffClick`) üretimde **tek**e indirilir: yalnızca normalize gesture → armed durum üzerinden commit. Çift-start engellenir.

---

## 4. Python tarafı değişiklikleri (minimal, dosya dosya)

> İlke: CV hattı sıfır değişir. Yalnızca **gönderici (sender)** katmanına bir transport eklenir. Tüm satır numaraları doğrulandı (`python/main.py`).

### 4.1 `python/net/ws_sender.py` — YENİ DOSYA

`OscSender` ile **bire bir aynı arayüze** sahip `WsSender` sınıfı:
- `__init__(cfg)`, `send_hand(nx, ny, present, gesture)`, `send_absent(last_nx, last_ny)`.
- `gesture.SEARCHING`/`gesture.FIST` import edilir (string hardcode etme).
- Arka planda **daemon thread** içinde bir `asyncio` event loop. Thread hedefinde `asyncio.new_event_loop()` + `set_event_loop()` çağrılır (Windows'ta yeni thread'de `get_event_loop`'a güvenme — bkz. §11).
- Loop, `websockets.serve(self._on_client, cfg.net.ws_host, cfg.net.ws_port)` ile sunucu açar; bağlı istemcileri `self._clients` set'inde tutar (set'i **yalnızca loop thread'inde** mutate et).
- `_on_client(ws)`: set'e ekle, `await ws.wait_closed()`, `finally`'de çıkar.
- `send_hand`: JSON çerçeve `{'x': float(nx), 'y': float(ny), 'present': bool(present), 'gesture': 'fist' if gesture == FIST else 'open'}` üretir; `asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)` ile loop'a **fire-and-forget** atar (`.result()` ÇAĞIRMA — 60 Hz ana döngü yavaş istemcide kilitlenmesin).
- `_broadcast`: `await asyncio.gather(*(c.send(msg) for c in list(self._clients)), return_exceptions=True)`; istisna atan/kapanan istemcileri ayıkla. **Latest-value-wins** olduğundan kare düşürmek güvenli; asla sınırsız kuyruk tutma.
- `send_absent`: `osc_sender`'ı yansıt → `self.send_hand(last_nx, last_ny, False, SEARCHING)`.
- OPSİYONEL: istemci yoksa erken-dön (`json.dumps` israfını önle).
- `close()`: `self._loop.call_soon_threadsafe(self._loop.stop)` — temiz kapanış.

### 4.2 `python/net/__init__.py` — DÜZENLE

Şu an yalnızca `OscSender` export ediyor (`__all__ = ["OscSender"]`). Eklenecek:
- `WsSender` import/export.
- `create_sender(cfg)` factory ve `CompositeSender` (burada veya yeni `net/sender.py` içinde).
  - `CompositeSender([...])`: alttaki gönderici listesini tutar; `send_hand`/`send_absent`'i her birine forward eder.
  - `create_sender(cfg)`: `cfg.get('net', None)` defansif okur; `transport` değerine göre:
    - `'osc'` (varsayılan, geriye uyumlu) → `OscSender(cfg)`
    - `'ws'` → `WsSender(cfg)`
    - `'both'` → `CompositeSender([OscSender(cfg), WsSender(cfg)])`

### 4.3 `python/main.py` — 4 NOKTA (mantık değişmez)

| Yer | Şu an | Yeni |
|---|---|---|
| import (~satır 32) | `from net import OscSender` | `from net import create_sender` |
| construction (satır 100) | `osc = OscSender(cfg)` | `sender = create_sender(cfg)` |
| grab-failure (satır 127) | `osc.send_absent(*last_xy)` | `sender.send_absent(*last_xy)` |
| heartbeat (satır 168) | `osc.send_hand(mapped[0], mapped[1], True, committed)` | `sender.send_hand(...)` |
| heartbeat-absent (satır 170) | `osc.send_absent(*last_xy)` | `sender.send_absent(*last_xy)` |
| startup print (satır 118-119) | OSC host:port | opsiyonel olarak WS host:port da yaz |

**Üç gönderim çağrı noktası da köprüye bağlanmalı:** iki normal gönderim (167-170) **ve** kamera-grab hatası dalı (127). `frame_budget = 1/cfg.osc.send_rate_hz` (satır 103) değişmez — WS oranı bu döngüden otomatik miras alır, ayrı oran yok.

`finally` bloğunda (cam/recognizer kapanışıyla birlikte) `sender.close()` çağrılmalı; aksi halde recalibrate yeniden-başlatmaları (ana döngü ~satır 216-221) ikinci bir WS sunucusu sızdırıp aynı portu bağlamaya çalışır → `OSError` (bkz. §11).

### 4.4 `python/config.json` + `python/config.py`

- `config.json`'a yeni bölüm:
  ```json
  "net": { "transport": "osc", "ws_host": "0.0.0.0", "ws_port": 8765 }
  ```
  - `transport` varsayılan `"osc"` → mevcut Unity davranışı korunur.
  - `ws_host = "0.0.0.0"` → projeksiyon PC'si vs laptop gibi farklı makinedeki tarayıcı bağlanabilir; tarayıcı dedektör makinesinin LAN IP'sini çevirir.
- `config.py`: `load_config` (satır 47-50) zorunlu-bölüm listesini doğruluyor; `'net'` listede değil, bu yüzden **eklenmemeli** (eski `config.json`'lar kırılmasın). `create_sender` içinde `cfg.get('net')` ile defansif oku. `osc` bölümü (host/port/send_rate_hz) **aynen** kullanılır.

### 4.5 `python/requirements.txt`

Tek satır ekle:
```
websockets>=12.0  # tarayıcı WebSocket köprüsü (net/ws_sender.py asyncio sunucusu); yalnızca transport ws|both iken gerekli
```
Saf Python, native build yok, py3.10-3.13'te mediapipe ile uyumlu. `json/threading/asyncio` stdlib. `python-osc` **kalır** (OSC bir seçenek olarak durur).

### 4.6 `tools/ws_sniff.py` — YENİ (teşhis)

Mevcut `osc_sniff.py`'nin web karşılığı: `websockets.connect('ws://127.0.0.1:8765')` ile ~4s dinleyip alınan kare sayısı + örnek bir kare + görülen `gesture` değerleri kümesini bas. Aynı teşhis ruhu: "Kare alınmıyorsa → dedektör göndermiyor / yanlış transport."

---

## 5. Web proje yapısı

**Önerilen çalışma dizini (yeni klasör):**
```
C:/Users/mehme/Desktop/v1/v1/00-Inbox/GestureExhibit-main/web/
```
(Alternatif: mevcut `Matematik oyunu _web tasarım/` altında bir `prod/` klasörü — ama temizlik için ayrı `web/` daha iyi.)

```
web/
├── index.html        ← 16:9 kiosk shell + tek #mh-hero-frame + 3 ekran (attract/playing/result) DOM iskeleti
├── styles.css        ← .dc.html'in attract/playing/result blok CSS'i + keyframe'ler (cqmin -> vmin)
└── js/
    ├── input.js      ← normalize {x,y,present,gesture} modülü; mouse + websocket sürücüleri; rising-edge
    ├── lens.js       ← rAF loop, exponential smoothing, lens takip, reveal(), armAttract()
    ├── tokens.js     ← genField(), paintTokens(), drawStars(), buildFloaters(), shuffle()
    ├── questions.js  ← POOLS verisi, makeDecoys(), zorluk seçimi
    └── game.js       ← durum makinesi (attract/playing/result), RoundManager, judge(), timer, flash, skor
```

- **Build adımı YOK.** Saf statik dosyalar; `index.html` doğrudan açılır veya kiosk'ta basit bir HTTP sunucudan servis edilir (WebSocket için `file://` yerine `http://` önerilir).
- `support.js` ve `.dc.html` sarmalayıcı **gönderilmez** — yalnızca değerleri taşınır (README satır 148 ile teyitli).
- Google Fonts: Baloo 2, JetBrains Mono, Space Grotesk `<head>`'de yüklenir.

---

## 6. Taşınacak oyun mantığı (otoriter — Unity/GAME_DESIGN'dan, exact sabitlerle)

> Mantıkta `GAME_DESIGN.md` otorite; prototip JS bunun büyük kısmını zaten çerçeveden bağımsız uyguluyor. Sabitler `.dc.html`'den birebir alınır.

### 6.1 QuestionGenerator (soru havuzu + tuzak distractor kuralları)

- **Havuz:** `POOLS = { kolay, orta, zor }`, her biri 8 adet `{p: prompt, a: cevap}` (`.dc.html` satır 396-409). Statik, elle yazılmış; **prosedürel üretim yok**. Aynen veri olarak `questions.js`'e kopyalanır.
  - Promptlar matematik glyph'leri içerir: `13 × 7`, `√144`, `9²`, `x² = 49`, `5!`, `15² − 14²`.
- **Tur kurulumu:** `shuffle(POOLS[diff]).slice(0,5)` → tur başına **5 soru**.
- **makeDecoys(ans)** (satır 439-451): `ans` int'e parse → `A`.
  - Yakın-ıska tohumları: `A±1, A±2, A±3, A±9, A±10` (yalnız `v>0 && v!==A`); çok haneliyse `A`'nın **ters çevrilmiş rakamları**.
  - **15 farklı** sayısal decoy'a doldur: `A + round((rand*2-1) * max(9, |A|*0.45))`, guard `<60`.
  - Sonra **7 sembol decoy** her zaman eklenir: `['×','÷','√','=','²','+','−']`, karıştır.
  - `ans` sayısal değilse (isNaN): **yalnızca 7 sembol** döner.
  - **Spec sapması (karar gerekir):** README token glyph seti `³ ¼ ½ ¾ ( ) !` da listeler ama prototip decoy'larında bunlar **yok**. Decoy setini genişletmek mantık değişikliğidir → CLAUDE kuralı uyarınca **önce sor** (bkz. §11).

### 6.2 MathField — token alanı (`tokens.js`)

`genField(ans)` (satır 453-470):
- **Izgara:** `cols=6 × rows=5 = 30 token`.
- **Alan sınırları:** `x ∈ [8,92]%`, `y ∈ [33,92]%` (alt 2/3; üst HUD temiz kalır).
- **Hücre merkezi:** `xs + (c+0.5)*cw`; **jitter:** `±22% hücre w/h` = `(random*2-1)*cw*0.22` (ve `ch*0.22`).
- Hücreler karıştırılır.
- **Doğru kopya sayısı:** `nC = (random<0.5 ? 2 : 3)` — ilk `nC` hücre `glyph=ans, correct=true`; kalanı decoy'lar arasında döner (`di % dec.length`).
- Her token: `{id, glyph, x(2dp), y(2dp), correct}`. Sonda tekrar karıştır.
- **Sonuç:** 30 token, 2-3 doğru, gerisi decoy. Saf JS, tam yeniden kullanılabilir.

### 6.3 LensHunt histerezis sabitleri (`lens.js`)

- **REVEAL_R** = `rect.width * 0.235` — token opaklık düşüş mesafesi.
- **ARM_R (oyun)** = `rect.width * 0.095` — token ve RESET seçilebilir yarıçapı.
- **ARM_R (attract)** = `rect.width * 0.13` — daha büyük zorluk butonları için.
- **LENS_SMOOTH** = `0.22` (kare başı): `lx += (mouse.x - lx)*0.22`.
- **reveal düşüş eğrisi:** `r = max(0, 1 - d/REVEAL_R)`, sonra `r = r*r*(3 - 2*r)` (smoothstep).
- RESET, oyun ARM_R'si (`0.095`) ile silahlanır (reveal() reset'i ARM içinde kontrol eder — teyitli).

### 6.4 RoundManager akışı (`game.js`)

- **start(diff):** yalnızca ekran `attract` ise `attract→playing`. `shuffle(POOLS[diff]).slice(0,5)`, `qIndex=0`, `score=0`, `time=120`, `locked=false`, ilk prompt + qLabel `'1/5'` + `tokens=genField(q.a)`, `setInterval(tick, 250)`.
- **tick() / timer:** her tick `time -= 0.25` (250ms gerçek = 0.25s oyun, **1:1**). `time<=0` → `endRound('Süre doldu!')`. Başlangıç `time=120` (2:00).
  - **Düşük süre:** `time<=10` → `#mh-timer` rengi `#FF5470` + `mh-low 0.9s` nabız (scale 1.0↔1.07). Aksi `#eef1ff`, animasyon yok.
- **next():** `qIndex++`; `>=5` ise `endRound('Bitti!')`, değilse yeni prompt/qLabel/tokens, `locked=false`.
- **endRound(msg):** timer temizle, `locked=true`, ekran `result` (`resultMsg` + `scoreText`), `setTimeout(4400ms)` → ekran `attract` (locked/qIndex/score sıfırla). **result tutma = 4400ms.**
- **doReset() (RESET veto):** timer + result-timeout temizle, sıfırla, ekran `attract`. RESET sağ-üst köşeye gerçek anchor'lı; oyun ARM_R (`0.095`) ile silahlanır.
- **pause:** prototipte örtük — `locked` re-entry guard'ı judge sırasında girişi bloke eder; üretimde edge-detection ile birlikte tek koruma budur.

### 6.5 judge & FX zamanlamaları

- **judge(el)** (satır 563-581): `locked` guard → `locked=true`; `el.dataset.correct==='true'` oku; iris-close; token yeşil/kırmızı; punch scale; doğruysa `score++` + updateScore; `flash()`; `setTimeout(next, 1050)`.
- **next-question gecikmesi = 1050ms.**
- **iris-close:** `#mh-iris scale(0.4) → 1` (200ms sonra geri), transition `0.18s cubic-bezier(0.5,0,0,1)`.
- **confirm punch:** doğru `1.45` / yanlış `1.3`, settle `1.2`/`1.05` (170ms sonra), transition `0.16s cubic-bezier(0.34,1.6,0.6,1)`.
- **center flash:** `scale 1.25→1` over `0.5s cubic-bezier(0.2,0,0.2,1)`, 760ms sonra solar.
- **updateScore:** `#mh-score` 2 haneye sıfır-dolgulu.

---

## 7. Görsel sistem (`styles.css`)

> Görsel kaynak-of-truth: **`Matematik Avı.dc.html`** (README/HTML görselde kazanır). CSS, prototipin attract/playing/result blokları (satır 64-153) ve keyframe'lerinden (satır 22-31: `mh-spin/spin2/breathe/drift/twinkle/pulse-dot/low/titleglow/orbit/scan`) taşınır.

### Design tokens (CSS değişkenleri)

| Token | Değer | Anlam |
|---|---|---|
| `--space` | `#04030D` | sayfa arka planı (near-black indigo) |
| `--space-2` | `#06040F` | field gradient tabanı |
| `--ink-0` | `#EEF1FF` | birincil metin |
| `--ink-1` | `#A9A4D6` | ikincil metin |
| `--ink-2` | `#8B86BF` | mono telemetri etiketleri |
| `--cyan` | `#00EBFF` | KOLAY / lens ring / accent 1 |
| `--violet` | `#9F5FFF` | ORTA / köprü accent |
| `--magenta` | `#FF4AD6` | ZOR / RESET / accent 2 |
| `--gold` | `#FFC83D` | armed token ring/halo |
| `--gold-text` | `#FFE08A` | armed token glyph |
| `--green` | `#34F5A6` | doğru flash + token |
| `--green-text` | `#7DFFC4` | doğru token glyph |
| `--red` | `#FF5470` | yanlış + düşük-süre timer |
| `--red-text` | `#FF8095` | yanlış token glyph |
| `--token-text` | `#E6F4FF` | açığa çıkmış (armed değil) token glyph |
| `--hairline` | `rgba(150,130,255,0.16)` | kenarlık / ızgara |

- **armed gold ring:** `2px rgba(255,200,61,0.9)`, glow `rgba(255,200,61,0.7)`.
- **reveal cyan halo:** radial `rgba(120,210,255,0.5) → transparent 68%`.

### Fontlar

- **Baloo 2** (display/sayılar, 500-800) — token glyph'leri, promptlar.
- **JetBrains Mono** (telemetri, UPPERCASE, 400-700).
- **Space Grotesk** (gövde).
- Hepsi Google Fonts; **Türkçe + matematik glyph kapsaması zorunlu** (bkz. §10, §11).

### vmin ölçekleme (cqmin → vmin)

- Prototip tüm boyutları `cqmin` ile veriyor → `#mh-hero-frame` üzerinde `container-type:size` varsayar. Üretimde kiosk tam-ekran 16:9 olduğu için **vmin** kullan (README önerisi). `cqmin` ile `vmin` **karıştırma** — yoksa her şey yanlış boyutlanır.
- Frame aspect: **16:9** (yalnızca statik VAR C mockup 32:9 — atılıyor).

### reveal/arm matematiği & motion sabitleri

- Lens takip: `pos += (target - pos) * 0.22`.
- `REVEAL_R = 0.235 * width`; `ARM_R = 0.095 * width` (oyun) / `0.13 * width` (attract butonları).
- reveal düşüşü: `r = max(0, 1-d/REVEAL_R)` → smoothstep `r*r*(3-2*r)`.
- token: `opacity = r`, `scale = 0.8 + 0.2*r`, glow `opacity = r*0.85`.
- armed token override: `scale 1.2`, `opacity 1`, gold glow/ring, glyph `#FFE08A`.
- lens opacity transition: `0.25s` (present toggle'da).
- breathing (zorluk butonu idle): `scale 1.0 ↔ 1.035` (`mh-breathe`).
- düşük-süre nabız: `scale 1.0 ↔ 1.07` (`mh-low 0.9s`).
- iris-close `~0.4 over 0.18s cubic-bezier(0.5,0,0,1)`; confirm pop `~1.45`/`~1.3`; center flash `1.25→1.0 over 0.5s`; result hold `~4.4s`; next-soru duraklama `~1.05s`.

### Atmosfer

- **floaters:** 26 sürüklenen sembol; ranges: `left 1-97%, top 2-96%, size 3-8cqmin(→vmin), op 0.18-0.48, dur 7-13s, delay 0-4s, tw 4-8s`.
- **starfield:** `#mh-stars-page` canvas, **320 yıldız**, `r` ≤ 1.3, alpha 0.1-0.6.
- **DIFFS:** kolay cyan `#00EBFF` (rgb 0,235,255, breathing-dur 3.4) · orta violet `#b98cff` (rgb 159,95,255, dur 3.8) · zor magenta `#ff8fe4` (rgb 255,74,214, dur 3.1).

### Font yükleme

- `paintTokens` `document.fonts.ready`'e ertelenir, yoksa 300ms fallback — **koru** (tofu/yanlış metrik önler).

---

## 8. Prototipten ne yeniden kullanılır / ne atılır

### AYNEN kopyala (saf JS, çerçeveden bağımsız)
`shuffle()`, `makeDecoys()`, `genField()`, `buildFloaters()`, `drawStars()` → `questions.js`/`tokens.js`'e birebir.

### Küçük düzenleme ile (zaten ham-DOM; sadece `setState`'i at, normalize input ver)
`reveal()`, `armAttract()`, `judge()`, `flash()`, `updateTimer()`, `updateScore()`, rAF `loop()`, `paintTokens()`, judge içindeki iris-close. Bunlar zaten `[data-token]`/id ile ham DOM'a yazıyor.

### Veri olarak yeniden kullan
`POOLS`, `DIFFS`, `STATE_CARDS` (düz literal'ler).

### Görsel kaynak-of-truth olarak koru
attract/playing/result CSS blokları (satır 64-153), tüm keyframe'ler (22-31), tüm renk/boyut/zamanlama sabitleri.

### Yeniden yaz (REWRITE)
- 3× `<sc-if>` ekran geçişi → ekran state'ine göre DOM göster/gizle.
- 4× `<sc-for>` (tokens, floaters, diff butonları, state cards) → manuel element oluşturma.
- Tüm `{{ }}` binding'leri → doğrudan `textContent`/`style` yazımı.
- handler wiring (`onMove/onLeave/onFist/onDiffClick/onReset`) → `addEventListener`.

### TAMAMEN değiştir / ATILIR
- **`support.js`** (React-UMD DC runtime, 1466 satır): React 18.3.1 + ReactDOM'u unpkg'den yükler (satır 1377-1380), `<x-dc>` şablonunu parse eder, `{{ }}` binding derler, `sc-if`/`sc-for` işler, inline `DCLogic` sınıfını `new Function` ile eval eder (satır 675). **Hiçbir parçası gönderilmez** (README satır 148 teyitli). React ağ bağımlılığı tamamen kalkar.
- `DCLogic` `setState`/`renderVals`/lifecycle → düz state objesi + render/update fonksiyonları.

### YENİ inşa et
- Normalize input modülü (`{x:0..1,y:0..1,present,gesture}`) + mouse adapter + rising-edge + WS seam.
- Tam-ekran 16:9 kiosk shell.
- `cqmin → vmin` dönüşümü.

### DROP (gönderme)
- Statik gösteri bölümleri: **02** (3 start varyasyonu A/B/C), **03** (4 in-game mockup: Oynanış/Doğru/Yanlış+son saniyeler/Sonuç), **04** (lens anatomisi + token state cards). Bunlar sabit sayılarla (`'13 × 7'`, `'1:24'`, `'4/5'`) kodlanmış, mantığa bağlı değil — yalnızca tasarım galerisi.
- Muhtemel ölü kod: `drawDot()`/`drawStateCards()` (satır 492-518, 709-715) `[data-state-canvas]` hedefler ama section-04 markup'ı bunu içermiyor (`{{ s.* }}` CSS token kullanıyor) — **körü körüne taşıma**.

**Hangi mantık zaten JS'te var:** Bölüm 01 (`#mh-hero-frame`) **işlevsel** — tam attract→playing→result döngüsü, reveal, arm, judge, timer, reset. Yani oyun mantığının neredeyse tamamı prototipte çalışır halde; eksik olan yalnızca **input seam'i** + **kiosk shell** + **çerçeve soyma**.

---

## 9. Aşamalı yol haritası (sıralı milestone'lar + "biter" kriteri)

> Her milestone mouse sürücüsüyle test edilir; WebSocket köprüsü en sona bırakılır (oyun tek başına geliştirilebilir).

**M1 — İskelet + fontlar.** `index.html` (16:9 kiosk shell, `#mh-hero-frame`, 3 ekran iskeleti), `styles.css` (cqmin→vmin tokenları, keyframe'ler), Google Fonts.
- *Biter:* Tam-ekran 16:9 boş HUD görünür; fontlar Türkçe + matematik glyph'lerini tofu'suz render eder.

**M2 — Input modülü (mouse) + lens.** `js/input.js` mouse sürücüsü (normalize `{x,y,present,gesture}` + rising-edge), `js/lens.js` rAF loop + LENS_SMOOTH=0.22 takip + present opacity.
- *Biter:* Lens fareyi yumuşatılmış izler; pencereden çıkınca kaybolur; `mousedown` tek "fist" olayı (her karede değil) üretir.

**M3 — Attract.** Zorluk butonları (DIFFS), `armAttract()` (ARM_R=0.13), breathing.
- *Biter:* Lens butona yaklaşınca silahlanır (scale 1.12, brightness 1.25); fist → `start(armedDiff)`.

**M4 — Soru havuzu + token alanı.** `questions.js` (POOLS, makeDecoys), `tokens.js` (genField 6×5=30, x[8,92]/y[33,92], jitter ±22%, nC=2|3), `paintTokens` (fonts.ready).
- *Biter:* `start` sonrası 30 token doğru bölgede, 2-3 doğru kopya; promptta glyph'ler doğru.

**M5 — reveal/arm matematiği.** `reveal()` (REVEAL_R=0.235, smoothstep, opacity/scale/glow), oyun ARM_R=0.095, armed override (gold).
- *Biter:* Lens token üstünde geçtikçe açığa çıkış doğru; en yakın token altın silahlanır.

**M6 — fist → judge → skor + timer.** `judge()` (iris-close, punch, yeşil/kırmızı, skor, flash, next@1050ms), timer (tick 250ms, 120s, düşük-süre<=10 nabız), `next()`.
- *Biter:* 5 soruluk tur baştan sona oynanabilir; doğru/yanlış FX ve skor 2-haneli; timer 1:1 sayar, son 10sn kırmızı nabız.

**M7 — Result + RESET.** `endRound` (result hold 4400ms→attract), `doReset()` veto (sağ-üst, ARM_R=0.095).
- *Biter:* Tur bitince result 4.4s gösterilir, attract'a döner; RESET her an attract'a vetolar.

**M8 — Cila.** floaters (26), starfield (320), tüm motion/keyframe sabitleri, çift commit yolunu tek'e indir.
- *Biter:* Görsel prototiple birebir; tek commit yolu (çift-start yok).

**M9 — Python WebSocket köprüsü + seam.** `net/ws_sender.py`, `create_sender`/`CompositeSender`, `config.json` net bölümü, `requirements.txt`, `main.py` 4 nokta, `input.js` WS sürücüsü + yeniden bağlanma.
- *Biter:* `transport=ws` ile gerçek el girişi oyunu sürer; OSC `transport=osc`/`both` ile bozulmaz; bağlantı kopunca otomatik yeniden bağlanır.

**M10 — Kalibrasyon / kiosk.** Homografi Python'da; tam-ekran kiosk autostart; LAN IP yapılandırması.
- *Biter:* Duvar projeksiyonunda kalibre lens doğru konumda; makine açılışında kiosk otomatik başlar.

---

## 10. Test & doğrulama

1. **Mouse ile her adım (M1-M8):** Python çalışmadan, mouse sürücüsüyle her milestone'un "biter" kriterini doğrula. Rising-edge'i özellikle test et — `mousedown` basılı tutarken `judge()` yalnızca **bir kez** ateşlenmeli.
2. **WebSocket köprü doğrulama (M9):**
   - `tools/ws_sniff.py` ile ~4s kare sayısı + örnek kare + gesture kümesi (`{'open','fist'}` görülmeli). "Kare yok → dedektör göndermiyor / yanlış transport."
   - `transport=both` ile OSC sniff (`osc_sniff.py`, port 9000) **ve** ws_sniff aynı anda kare almalı (geriye uyumluluk kanıtı).
   - Yavaş/kapalı istemci testi: bir tarayıcı sekmesini dondur → 60 Hz döngü stall etmemeli (fire-and-forget kanıtı).
3. **Kalibrasyon:** Homografi **Python'da kalır** (`mapping/homography.py`, `mapping/calibrate.py`). Tarayıcı landmark/kalibrasyon matematiği yapmaz; sadece `(x,y)` kursoru taşır. Recalibrate sonrası WS portunun temiz serbest kaldığını doğrula (`sender.close()`; ikinci sunucu `OSError` vermemeli).
4. **Tam ekran kiosk:** F11/kiosk modu; `vmin` ölçeklemenin 16:9'da doğru olduğunu, `cqmin` artığı kalmadığını doğrula. Farklı aspect'te REVEAL_R/ARM_R'nin (sadece `width` ile ölçekli) elips bozulması yapmadığını kontrol et (CLAUDE kuralı 7).
5. **Glyph / Türkçe doğrulama:** Tüm prompt ve decoy glyph'leri (`× ÷ √ = ² + −` + Türkçe `İ ı ğ Ğ ş Ş ç Ç ö ü`) Baloo 2'de tofu'suz. `document.fonts.ready` beklendiğini teyit et.
6. **Çapraz tarayıcı:** Chrome/Edge (kiosk hedefi) + Firefox; rAF, WebSocket, font yükleme, fullscreen davranışı.

---

## 11. Riskler & açık sorular

| # | Risk / Soru | Not / Önlem |
|---|---|---|
| 1 | **Normalize→piksel dönüşümü** atlanırsa reveal/arm mesafeleri bozulur | Dönüşümü TEK yerde yap (lens okurken `getBoundingClientRect`). |
| 2 | **Fist rising-edge yok** | Sürekli `open/fist` akışında `judge()` her karede tetiklenir; `input.js`'te `open→fist` geçişinde tek olay üret. `locked` tek başına yetmez. |
| 3 | **cqmin bağımlılığı** | `container-type:size` olmadan cqmin kullanımı veya vmin ile karışım her şeyi yanlış boyutlar → tamamen vmin'e geç. |
| 4 | **REVEAL_R/ARM_R yalnızca `width` ile ölçekli** | Non-16:9'da reveal dairesi elipsleşir; CLAUDE kuralı 7 (diğer aspect'lerde hayatta kalmalı) ile doğrula; gerekirse `min(w,h)` tabanına geç (mantık değişikliği → sor). |
| 5 | **Glyph seti sapması (açık soru)** | README `³ ¼ ½ ¾ ( ) !` listeler; prototip decoy'ları `× ÷ √ = ² + −`. Decoy genişletmek mantık değişikliği → **sahibine sor** (CLAUDE kuralı 5). |
| 6 | **Font tofu (fatal)** | Baloo 2 Türkçe + matematik glyph'lerini render etmeli; `document.fonts.ready` beklemesini koru (GAME_DESIGN §8.5). |
| 7 | **Kalibrasyon dosyası yönetimi** | Homografi/kalibrasyon Python'da kalır; tarayıcı dokunmaz. Kalibrasyon dosyasının dedektör makinesinde tutulması ve recalibrate sonrası yüklenmesi sahibinin sorumluluğunda. |
| 8 | **Tarayıcı tam-ekran / kiosk (autostart)** | Kiosk modu + autostart (Chrome `--kiosk`) ve fullscreen autoplay kısıtları; kullanıcı jesti gerektirebilir — açılışta tek tıkla devreye al. |
| 9 | **WebSocket gecikme / yeniden bağlanma** | `onclose/onerror` → backoff'lu reconnect (1s, ~2-5s tavan); tek bağlantının hayatta kalacağını varsayma. |
| 10 | **Backpressure / yavaş istemci** | Fire-and-forget broadcast, `return_exceptions=True`, kapanan socket'leri ayıkla; latest-value-wins → kare düşürmek güvenli, sınırsız kuyruk YOK. |
| 11 | **Thread-safety** | `send_hand` senkron ana döngüden çağrılır; WS asyncio loop ayrı thread'te. Geçiş `run_coroutine_threadsafe` ile; doğrudan `ws.send` loop'u bozar. Future'ı bekleme (60 Hz stall). |
| 12 | **Temiz kapanış / port sızıntısı** | recalibrate yeniden-başlatmaları ikinci WS sunucu sızdırıp `OSError` verebilir; `finally`'de `sender.close()` + portun serbest kaldığını garanti et. |
| 13 | **0.0.0.0:8765 auth'suz LAN** | Kiosk/sergi LAN'ı için kabul edilebilir; not düş. Birden çok tarayıcı bağlanırsa hepsi aynı broadcast'i alır (zararsız). |
| 14 | **Geriye uyumluluk** | `net.transport` varsayılanı `'osc'` OLMALI; `create_sender` `net` bölümü olmayan eski `config.json`'u tolere etmeli — yoksa Unity koşuları kırılır. |
| 15 | **websockets API sürüm kayması** | `serve(handler, host, port)` imzası sürümler arası değişti; `>=12` pinle, kurulu sürümün handler imzasını doğrula. |
| 16 | **asyncio / Windows** | Yeni thread'de `asyncio.new_event_loop()` + `set_event_loop()`; `get_event_loop`'a güvenme. ProactorEventLoop websockets ile uyumlu. |
| 17 | **60 vs 30 Hz** | Döngü ~60 Hz heartbeat; MediaPipe ~20-30 Hz tamamlar. Pozisyon yalnızca taze inference'ta ilerler; WS oranı bunu otomatik miras alır — ek throttle gereksiz. |
| 18 | **Performans (DOM vs canvas)** | 30 token DOM ile sorunsuz; ama yıldız (320) ve floater (26) çoksa canvas'ta tut (zaten yıldızlar canvas). DOM token sayısı 30'da kalsın. |
| 19 | **Attract auto-timeout yok** | Sadece result 4400ms sonra döner; attract'ın idle döngüsü yok. Kiosk attract-loop isterse kapsam değişir → **sahibine sor**. |
| 20 | **Çift commit yolu** | `onFist+armedDiff` ve ayrıca `onDiffClick` iki ayrı seçim yolu; üretimde tek'e indir (çift-start riski). |
| 21 | **CheeseHunt/MouseTrap akıbeti (açık soru)** | Unity projesinde kalsınlar mı, arşivlensinler mi? Bu plan dokunmuyor; Python `transport=both` ile Unity oyunları OSC üzerinden çalışmaya devam edebilir. **Karar sahibinin.** |

---

## 12. Tahmini efor & öneri

> Kabaca, aşama bazlı (tek geliştirici, yarım/tam gün birimleriyle):

| Aşama | Milestone | Tahmini efor |
|---|---|---|
| Web iskelet + görsel | M1-M3 (shell, fontlar, input(mouse)+lens, attract) | ~1.5-2 gün |
| Çekirdek oyun | M4-M7 (token alanı, reveal/arm, judge+timer+skor, result+RESET) | ~2-3 gün |
| Cila | M8 (atmosfer, motion, tek commit yolu) | ~0.5-1 gün |
| Python köprüsü | M9 (ws_sender + factory + config + main.py 4 nokta + WS sürücüsü) | ~1-1.5 gün |
| Kalibrasyon/kiosk | M10 (kiosk autostart, LAN, alan testi) | ~0.5-1 gün |
| **Toplam** | | **~5.5-8.5 gün** |

**Öneri / sıralama gerekçesi:**
1. **Önce oyunu mouse ile bitir (M1-M8).** Python köprüsü olmadan tüm oyun mantığı geliştirilebilir/test edilebilir; bu en büyük belirsizliği erken kapatır. Prototip mantığının ~%90'ı zaten hazır — asıl iş **çerçeve soyma + input seam + kiosk shell**.
2. **Python köprüsünü en sona bırak (M9).** Değişiklik gerçekten minimal (yeni `ws_sender.py` + 4 satır `main.py` + config), `OscSender` arayüzünü aynen taklit ettiği için risk düşük. `transport='both'` ile Unity'yi bozmadan paralel test et.
3. **Açık soruları erken sor:** glyph seti genişletme (#5), attract auto-loop (#19), CheeseHunt/MouseTrap akıbeti (#21), aspect-ratio için `min(w,h)` tabanı (#4) — bunlar kapsam/mantık kararları; M4/M8 öncesi netleştir.
4. **`transport='both'` ile geçiş dönemi:** Web tam oturana kadar OSC açık kalsın; web kanıtlandıktan sonra `transport='ws'`e geç.

---

**İlgili dosya yolları (mutlak):**
- Python köprü çağrı noktaları: `C:/Users/mehme/Desktop/v1/v1/00-Inbox/GestureExhibit-main/python/main.py` (import ~32, construction 100, çağrılar 127/168/170, print 118-119, finally ~216-221)
- OSC sözleşme/arayüz: `C:/Users/mehme/Desktop/v1/v1/00-Inbox/GestureExhibit-main/python/net/osc_sender.py`
- net export (düzenlenecek): `C:/Users/mehme/Desktop/v1/v1/00-Inbox/GestureExhibit-main/python/net/__init__.py`
- gesture sabitleri: `C:/Users/mehme/Desktop/v1/v1/00-Inbox/GestureExhibit-main/python/gesture/fsm.py` (SEARCHING/FIST)
- Yeni: `python/net/ws_sender.py`, `tools/ws_sniff.py`, `python/config.json` (net bölümü), `python/requirements.txt`
- Görsel/mantık kaynak-of-truth: `C:/Users/mehme/Desktop/v1/v1/00-Inbox/GestureExhibit-main/Matematik oyunu _web tasarım/design_handoff_web/Matematik Avı.dc.html`
- Atılacak runtime: `.../design_handoff_web/support.js`
- Spec: `.../design_handoff_web/GAME_DESIGN.md`, `README.md`, `CLAUDE.md`
- Yeni web kök (öneri): `C:/Users/mehme/Desktop/v1/v1/00-Inbox/GestureExhibit-main/web/`
