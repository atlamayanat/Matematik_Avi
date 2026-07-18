/* input.js — TEK normalize girdi modülü (seam).
   Oyun mantığı SADECE { x:0..1, y:0..1, present:bool, gesture:'open'|'fist' } okur.
   Sürücüler: mouse (varsayılan, geliştirme) + websocket (prod, Python köprüsü).
   Kullanım: ?input=ws&host=192.168.1.50&port=8765   (varsayılan: mouse) */
(function () {
  const MA = (window.MA = window.MA || {});

  // Paylaşılan normalize durum — tüm tüketiciler bunu okur.
  // approaching: derinlik-blob "yaklaşan ziyaretçi" bayrağı (yalnızca ws sürücüsü
  // ve Python net.send_approaching=true iken dolar; attract'ı uyandırmak için).
  const hand = { x: 0.5, y: 0.5, present: false, gesture: "open", approaching: false };

  const params = new URLSearchParams(location.search);
  const mode = (params.get("input") || "mouse").toLowerCase();

  function stageRect() {
    const s = document.getElementById("stage");
    return s ? s.getBoundingClientRect() : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
  }
  const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

  // ---------------- MOUSE sürücüsü ----------------
  function startMouse() {
    window.addEventListener("mousemove", (e) => {
      const r = stageRect();
      hand.x = clamp01((e.clientX - r.left) / r.width);
      hand.y = clamp01((e.clientY - r.top) / r.height);
      hand.present = e.clientX >= r.left && e.clientX <= r.left + r.width &&
                     e.clientY >= r.top && e.clientY <= r.top + r.height;
    });
    window.addEventListener("mousedown", () => { hand.gesture = "fist"; });
    window.addEventListener("mouseup", () => { hand.gesture = "open"; });
    document.addEventListener("mouseleave", () => { hand.present = false; });
  }

  // ---------------- WEBSOCKET sürücüsü ----------------
  // Yarı-açık / takılı soket koruması: köprü FIN göndermeden asılırsa onclose
  // ATEŞLENMEZ; eski hand.present=true + son x/y sonsuza kadar kalıp imleci
  // "canlı ama donuk" bırakır. Uygulama-seviyesi bayatlık zamanlayıcısı: son
  // mesajdan bu yana STALE_MS geçtiyse eli YOK say (imleç park) + görünür rozet.
  const _now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());
  const STALE_MS = 600;   // ~35 kayıp kare @58Hz -> kesin bayat

  let connEl = null, connState = "", connSince = _now();
  function setConn(state, text) {
    if (!connEl) connEl = document.getElementById("mh-conn");
    if (!connEl || state === connState) return;
    // Telemetri: her durum geçişi + önceki durumda geçen süre. Rapor "kamerada
    // sorun oldu mu, toplam ne kadar kesinti yaşandı" sorusunu bundan çıkarır.
    if (MA.telemetry) {
      MA.telemetry.log("conn", {
        state: state, prev: connState || "boot",
        prev_s: Math.round((_now() - connSince) / 100) / 10,
      });
    }
    connSince = _now();
    connState = state;
    connEl.classList.toggle("show", state !== "live");   // canlıyken gizli (çocuğu rahatsız etmez)
    connEl.classList.toggle("ok", state === "live");
    connEl.classList.toggle("warn", state === "stale");
    connEl.innerHTML = '<span class="cdot"></span>' + (text || "");
  }

  function startWs() {
    const host = params.get("host") || location.hostname || "127.0.0.1";
    const port = params.get("port") || "8765";
    const url = `ws://${host}:${port}`;
    let backoff = 1000;
    let lastMsg = 0;
    setConn("disconnected", "BAĞLANIYOR");

    function connect() {
      let ws;
      try { ws = new WebSocket(url); }
      catch (e) { setConn("disconnected", "BAĞLANTI YOK"); return retry(); }

      ws.onopen = () => { backoff = 1000; };
      ws.onmessage = (ev) => {
        lastMsg = _now();
        setConn("live");
        try {
          const m = JSON.parse(ev.data);
          if (typeof m.x === "number") hand.x = clamp01(m.x);
          if (typeof m.y === "number") hand.y = clamp01(m.y);
          hand.present = !!m.present;
          hand.gesture = m.gesture === "fist" ? "fist" : "open";
          hand.approaching = !!m.approaching;   // alan yoksa false (geriye uyumlu)
        } catch (_) { /* bozuk kare yoksay */ }
      };
      ws.onclose = () => { hand.present = false; setConn("disconnected", "BAĞLANTI KESİLDİ"); retry(); };
      ws.onerror = () => { try { ws.close(); } catch (_) {} };
    }
    function retry() {
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 1.7, 5000); // üstel backoff, ~5s tavan
    }

    // Bayatlık watchdog: bağlıyken veri kesilirse imleci park et + rozeti göster.
    setInterval(() => {
      if (connState === "disconnected") return;   // zaten kopuk, retry sürüyor
      if (lastMsg && _now() - lastMsg > STALE_MS) {
        hand.present = false;                      // donuk imleci gizle
        setConn("stale", "VERİ GELMİYOR");
      }
    }, 200);

    connect();
  }

  function start() {
    if (mode === "ws") startWs();
    else startMouse();
  }

  MA.input = { hand, start, mode };
})();
