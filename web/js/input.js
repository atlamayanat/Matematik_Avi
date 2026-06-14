/* input.js — TEK normalize girdi modülü (seam).
   Oyun mantığı SADECE { x:0..1, y:0..1, present:bool, gesture:'open'|'fist' } okur.
   Sürücüler: mouse (varsayılan, geliştirme) + websocket (prod, Python köprüsü).
   Kullanım: ?input=ws&host=192.168.1.50&port=8765   (varsayılan: mouse) */
(function () {
  const MA = (window.MA = window.MA || {});

  // Paylaşılan normalize durum — tüm tüketiciler bunu okur.
  const hand = { x: 0.5, y: 0.5, present: false, gesture: "open" };

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
  function startWs() {
    const host = params.get("host") || location.hostname || "127.0.0.1";
    const port = params.get("port") || "8765";
    const url = `ws://${host}:${port}`;
    let backoff = 1000;

    function connect() {
      let ws;
      try { ws = new WebSocket(url); }
      catch (e) { return retry(); }

      ws.onopen = () => { backoff = 1000; };
      ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data);
          if (typeof m.x === "number") hand.x = clamp01(m.x);
          if (typeof m.y === "number") hand.y = clamp01(m.y);
          hand.present = !!m.present;
          hand.gesture = m.gesture === "fist" ? "fist" : "open";
        } catch (_) { /* bozuk kare yoksay */ }
      };
      ws.onclose = () => { hand.present = false; retry(); };
      ws.onerror = () => { try { ws.close(); } catch (_) {} };
    }
    function retry() {
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 1.7, 5000); // üstel backoff, ~5s tavan
    }
    connect();
  }

  function start() {
    if (mode === "ws") startWs();
    else startMouse();
  }

  MA.input = { hand, start, mode };
})();
