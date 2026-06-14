# Matematik Avı — Kiosk / Sergi Kurulumu (Windows)

Bu belge, oyunu bir sergi/müze kurulumunda (duvar projeksiyonu + webcam) çalıştırmak içindir.
Mimari: **Python detektörü** (el takibi) → **WebSocket** → **tarayıcı** (oyun, tam ekran).

---

## 1. Tek seferlik hazırlık

```powershell
cd python
pip install -r requirements.txt          # mediapipe, opencv, websockets, ...
python download_model.py                  # gesture_recognizer.task modelini indir
```

`python/config.json` içinde transport'u WebSocket'e al:
```json
"net": { "transport": "ws", "ws_host": "0.0.0.0", "ws_port": 8765 }
```
- `"ws"`  → sadece tarayıcı.
- `"both"` → hem tarayıcı hem Unity (geçiş dönemi; OSC de açık kalır).
- `"osc"` → eski Unity davranışı (tarayıcı veri ALMAZ).

**Kalibrasyon** (projeksiyon + kamera yerleştirildikten sonra, bir kez):
```powershell
cd python
python main.py --calibrate                # 4 köşeyi parmakla işaretle -> calib.json
```

---

## 2. Çalıştırma (tek makine — önerilen)

Detektör + kamera + projeksiyon aynı PC'de. **`Matematik-Avi-Baslat.bat`** dosyasına çift tıkla.
Bu otomatik olarak:
1. Web'i `http://localhost:8000` üzerinden servis eder,
2. Detektörü `python main.py --no-preview` ile başlatır,
3. Tarayıcıyı (Chrome → yoksa Edge) **kiosk (tam ekran)** modunda açar:
   `http://localhost:8000/?input=ws&host=127.0.0.1&port=8765`

**Çıkış:** **ESC** (veya Alt+F4) → tarayıcı kapanır ve arka süreçler (detektör + sunucu) da otomatik durur. Tarayıcı `--app` + tam ekran modunda açılır (ESC ile kapanabilsin diye; `--kiosk`'tan farklı olarak).

PowerShell'den parametreyle de çalıştırılabilir:
```powershell
.\start-kiosk.ps1                      # varsayılan
.\start-kiosk.ps1 -HttpPort 8080
.\start-kiosk.ps1 -NoDetector          # detektör başka yerde/zaten açık
.\start-kiosk.ps1 -KeepRunning         # tarayıcı kapanınca arka süreçleri durdurma
```

---

## 3. İki makineli kurulum (opsiyonel)

Detektör PC-A'da, projeksiyon/tarayıcı PC-B'de:
1. **PC-A** (detektör + web sunucu): `.\start-kiosk.ps1 -NoServer:$false -NoDetector:$false`
   — web sunucusu `0.0.0.0`'a bağlanır, yani LAN'dan erişilebilir. PC-A'nın IP'sini öğren: `ipconfig`.
2. **PC-B** (tarayıcı): kiosk tarayıcısını şu adrese aç:
   `http://<PC-A-IP>:8000/?input=ws&host=<PC-A-IP>&port=8765`
   (PC-B'de detektör/sunucu gerekmez; `-NoDetector -NoServer` ile sadece tarayıcı açabilir veya elle açarsın.)

Güvenlik duvarı: PC-A'da 8000 (HTTP) ve 8765 (WebSocket) portlarına LAN erişimine izin ver.

---

## 4. Açılışta otomatik başlatma (boot)

**Yöntem A — Başlangıç klasörü:** `Win+R` → `shell:startup` → `Matematik-Avi-Baslat.bat` için kısayol koy.

**Yöntem B — Görev Zamanlayıcı (önerilen, daha sağlam):**
- Task Scheduler → Create Task → Trigger: *At log on* → Action: Start a program →
  Program: `powershell.exe`,
  Arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\...\GestureExhibit-main\start-kiosk.ps1"`.
- "Run only when user is logged on" + otomatik oturum açma (kiosk hesabı) ayarla.

---

## 5. Sorun giderme

| Belirti | Kontrol |
|---|---|
| Tarayıcıda sağ-altta "Bağlantı kesildi" | Detektör çalışıyor mu? `config.json` transport `ws`/`both` mı? Port 8765 açık mı? |
| Hiç veri yok | `cd python; python tools\ws_sniff.py` → kare sayısı 0 ise detektör göndermiyor (transport/preview/present). |
| El bulunmuyor | Detektörü önizlemeyle aç (`python main.py`) — kutu yeşile dönüyor mu? Işık/mesafe yeterli mi? |
| Mercek yanlış yerde | Kalibrasyon yap: `python main.py --calibrate`. Homografi Python'da kalır. |
| Glyph'ler kutu (□) | Fontlar Google Fonts'tan gelir → **internet gerekir**. Çevrimdışı sergi için fontları yerel servis et (bkz. aşağıda). |
| Tarayıcı bulunamadı | Chrome veya Edge kurulu olmalı. |
| Mouse ile test | `http://localhost:8000/` (input parametresiz) → fare=el, tık=yumruk. |

**Çevrimdışı fontlar:** Müze internetsizse `index.html`'deki Google Fonts `<link>`'i kaldırıp
Baloo 2 + JetBrains Mono `.woff2` dosyalarını `web/fonts/`'a koyup `styles.css`'e `@font-face` ile
gömün (gelecek iş; şu an çevrimiçi varsayılıyor).

---

## 6. Hızlı referans

| Şey | Değer |
|---|---|
| Web (yerel) | `http://localhost:8000/?input=ws` |
| WebSocket | `ws://<host>:8765` |
| Mouse test | `http://localhost:8000/` |
| Teşhis | `python tools\ws_sniff.py` |
| Kamera seç/değiştir | `Kamera-Ayarlari.bat` (canlı önizleme + kaydet) |
| Çıkış | ESC (veya Alt+F4) |
| Detektör (elle) | `cd python; python main.py [--no-preview] [--calibrate]` |
