/* telemetry.js — arka plan ziyaretçi/oyun telemetrisi (kiosk analitiği).
   Amaç: festival boyunca "kaç kişi denedi, nerede hata yaptı, oyun/kamera
   nerede sorun çıkardı" sorularına VERİ ile cevap vermek. Olaylar toplanır,
   5 sn'de bir aynı sunucudaki POST /telemetry ucuna gönderilir; sunucu
   (serve_nocache.py) bunları data\telemetry\events_YYYYMMDD.jsonl'a yazar.
   Rapor: kökteki Rapor.bat (tools/rapor.py).

   TASARIM KURALI: telemetri OYUNU ASLA BOZMAZ. Her şey try/catch içinde,
   sunucu yoksa/ulaşılamıyorsa olaylar bellekte bekler (tavanlı), oyun akışı
   hiçbir zaman telemetriye BEKLEMEZ. file:// (mouse testi) altında POST
   kapalıdır ama API aynı kalır (no-op'a yakın). */
(function () {
  const MA = (window.MA = window.MA || {});

  const MAX_QUEUE = 600;     // bellek tavanı (sunucu uzun süre kapalıysa en eskiler düşer)
  const FLUSH_MS = 5000;     // gönderim aralığı
  const BEACON_LAST = 120;   // pagehide beacon'ına sığdırılacak son olay sayısı (64KB sınırı)

  // Sayfa-oturumu kimliği: aynı sayfa yüklemesindeki tüm olayları bağlar.
  const sid = Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
  const canPost = /^https?:$/.test(location.protocol);
  const url = canPost ? location.origin + "/telemetry" : null;

  let seq = 0;
  let queue = [];
  let dropped = 0;      // tavan aşımında düşen olay sayısı (bir sonraki partiye not edilir)
  let inflight = false;

  function log(type, data) {
    try {
      const ev = { t: Date.now(), sid: sid, seq: ++seq, type: String(type) };
      if (data) for (const k in data) if (Object.prototype.hasOwnProperty.call(data, k)) ev[k] = data[k];
      queue.push(ev);
      if (queue.length > MAX_QUEUE) { queue.splice(0, queue.length - MAX_QUEUE); dropped++; }
    } catch (_) { /* telemetri asla oyunu bozmaz */ }
  }

  function payload(events) {
    const body = { sid: sid, sent: Date.now(), events: events };
    if (dropped > 0) { body.dropped = dropped; }
    return JSON.stringify(body);
  }

  function flush() {
    if (!url || inflight || queue.length === 0) return;
    const batch = queue.slice(0, 200);   // parti tavanı; kalan sonraki turda gider
    inflight = true;
    try {
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload(batch),
        keepalive: false,
      }).then(function (res) {
        inflight = false;
        if (res && res.ok) {
          queue.splice(0, batch.length);   // teslim edildi
          dropped = 0;
        }
      }).catch(function () { inflight = false; /* sunucu yok/kapalı: olaylar bekler */ });
    } catch (_) { inflight = false; }
  }

  // Sayfa kapanırken/yeniden yüklenirken (watchdog reload, ESC-çıkış) son olaylar
  // fetch'e yetişemez; sendBeacon tarayıcı kapanışında bile teslim eder.
  // DİKKAT: sendBeacon'ın true dönüşü "tarayıcı kuyruğuna alındı" demektir, teslim
  // garantisi DEĞİLDİR (sunucu kapalıyken bile true döner). Bu yüzden kuyruk
  // SİLİNMEZ: sayfa ölüyorsa kuyruğun kaderi zaten belli; sayfa geri görünür
  // olursa normal fetch akışı aynı olayları yeniden teslim eder ve rapor tarafı
  // (sid, seq) ile tekilleştirdiği için çift kayıt zararsızdır.
  function flushBeacon() {
    try {
      if (!url || queue.length === 0 || !navigator.sendBeacon) return;
      const batch = queue.slice(-BEACON_LAST);   // 64KB beacon sınırı: son olaylar öncelikli
      // text/plain: preflight tetiklemez; sunucu gövdeyi içerik türünden bağımsız JSON okur.
      navigator.sendBeacon(url, new Blob([payload(batch)], { type: "text/plain" }));
    } catch (_) {}
  }

  window.addEventListener("pagehide", flushBeacon);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flushBeacon();
  });
  setInterval(flush, FLUSH_MS);

  // index.html'deki inline hata yakalayıcı bu modülden ÖNCE kurulur; oradaki
  // erken hataları devral (yükleme sırası hatası bile kayda geçsin).
  try {
    const early = window.__earlyErrors;
    if (early && early.length) {
      for (const e of early) log("js_error", e);
      early.length = 0;
    }
  } catch (_) {}

  // Sayfa açılışı: girdi modu + ekran bilgisi (hangi kurulumda koştuğunu raporda ayırt etmek için).
  try {
    const q = new URLSearchParams(location.search);
    log("app_start", {
      mode: (q.get("input") || "mouse").toLowerCase(),
      w: window.innerWidth, h: window.innerHeight,
      dpr: window.devicePixelRatio || 1,
      ua: (navigator.userAgent || "").slice(0, 120),
    });
  } catch (_) {}

  MA.telemetry = { log: log, flush: flush, flushBeacon: flushBeacon, sid: sid };
})();
