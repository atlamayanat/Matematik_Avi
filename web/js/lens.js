/* lens.js — rAF döngüsü + mercek takibi/görseli + LensHunt.cs (token seçim beyni) portu.
   Dünya birimleri (Unity). Sahne sabit 16:9 letterbox -> yarıçaplar aspect'ten bağımsız (Q4). */
(function () {
  const MA = (window.MA = window.MA || {});
  const world = MA.world;

  const LENS_SMOOTH = 0.22; // tasarım değeri (pos += (target-pos)*0.22 / kare)

  // ---- LensHunt: token seçim beyni (Unity birebir) ----
  class LensHunt {
    constructor() {
      this.revealRadius = 2.4; this.revealFull = 0.7;  // aydınlanan alan genişletildi (Unity 1.8/0.5)
      this.armRadius = 1.05; this.disarmRadius = 1.30;
      this.switchMargin = 0.35; this.switchDwell = 0.12; this.disarmGrace = 0.10;
      this._tokens = []; this._armed = null;
      this._switchTimer = 0; this._disarmTimer = 0; this._cooldown = 0;
      this._prevFist = false; this._suspended = true;
    }
    get hasArmed() { return this._armed != null; }

    setTokens(tokens) {
      this._tokens = tokens ? tokens.slice() : [];
      this._armed = null; this._switchTimer = 0; this._disarmTimer = 0;
      this._cooldown = 0.2;     // ilk seçimden önce kısa oturma
      this._prevFist = true;    // (re)spawn sonrası taze open->fist şart
      this._suspended = this._tokens.length === 0;
    }
    suspend() { this._suspended = true; this._armed = null; }

    // dönüş: null | {ok:bool}  (bir token onaylandıysa)
    update(lx, ly, present, fist, dt) {
      if (this._suspended) return null;
      if (this._cooldown > 0) this._cooldown -= dt;

      if (!present) {
        for (const t of this._tokens) if (t) { t.setReveal(0); t.setArmed(false); }
        this._armed = null; this._switchTimer = 0; this._disarmTimer = 0; this._prevFist = false;
        return null;
      }

      // Pass 1: yakınlığa göre reveal, en yakını ve armed mesafesini bul
      let nearest = null, dN = Infinity, dA = Infinity;
      for (const t of this._tokens) {
        if (!t) continue;
        const d = world.dist(lx, ly, t.wx, t.wy);
        t.setReveal(invLerp(this.revealRadius, this.revealFull, d));
        t.setArmed(false);
        if (d < dN) { dN = d; nearest = t; }
        if (t === this._armed) dA = d;
      }

      // Pass 2: arming histerezisi (cooldown'da donuk)
      if (this._cooldown <= 0) {
        if (this._armed != null && dA > this.disarmRadius) {
          this._disarmTimer += dt;
          if (this._disarmTimer >= this.disarmGrace) { this._armed = null; this._switchTimer = 0; }
        } else this._disarmTimer = 0;

        if (this._armed == null) {
          if (nearest != null && dN <= this.armRadius) { this._armed = nearest; this._switchTimer = 0; }
        } else if (nearest != null && nearest !== this._armed && dN <= this.armRadius) {
          if (dN < dA - this.switchMargin) this._switchTimer += dt; else this._switchTimer = 0;
          if (this._switchTimer >= this.switchDwell) { this._armed = nearest; this._switchTimer = 0; }
        }
      }
      if (this._armed != null) this._armed.setArmed(true);

      // Yumruk yükselen kenarında onay
      let result = null;
      if (this._cooldown <= 0 && fist && !this._prevFist) {
        if (this._armed != null) {
          const ok = this._armed.correct;
          this._armed.confirm(ok);
          MA.lens.playSelect(this._armed.wx, this._armed.wy);
          this._armed = null;
          this._suspended = true;
          result = { ok };
        } else {
          this._cooldown = 0.15;
        }
      }
      this._prevFist = fist;
      return result;
    }
  }
  function invLerp(a, b, v) { const t = (v - a) / (b - a); return t < 0 ? 0 : t > 1 ? 1 : t; }
  MA.LensHunt = LensHunt;

  // ---- Mercek görseli + döngü ----
  let lensEl, irisEl, lx = 0.5, ly = 0.5, lastT = 0, started = false;
  let idle = 0; // attract'ta el yokken geçen süre (ghost demo için)

  function playSelect(wx, wy) {
    if (!irisEl) return;
    let off = "";
    if (typeof wx === "number" && typeof wy === "number") {
      // iris'i seçilen token'a doğru kaydır (Unity: iris-onto-pick), tavanla
      const st = document.getElementById("stage").getBoundingClientRect();
      const p = world.toPct(wx, wy);
      let dx = (p.left / 100 - lx) * st.width;
      let dy = (p.top / 100 - ly) * st.height;
      const cap = st.height * 0.16, m = Math.hypot(dx, dy);
      if (m > cap) { dx *= cap / m; dy *= cap / m; }
      off = `translate(${dx.toFixed(1)}px,${dy.toFixed(1)}px) `;
    }
    irisEl.style.transform = off + "translate(-50%,-50%) scale(0.4)";
    setTimeout(() => { if (irisEl) irisEl.style.transform = "translate(-50%,-50%) scale(1)"; }, 200);
  }

  function frame(t) {
    const dt = lastT ? Math.min((t - lastT) / 1000, 0.05) : 0.016;
    lastT = t;
    const hand = MA.input.hand;

    // ghost demo attract'ta el yokken devreye girer
    const ghosting = MA.game && MA.game.screen === "attract" && !hand.present;
    if (ghosting) idle += dt; else idle = 0;

    let tx = hand.x, ty = hand.y, present = hand.present;
    if (ghosting && idle > 5 && MA.game.ghostTarget) {
      const g = MA.game.ghostTarget(t / 1000); // {x,y,present,fist}
      tx = g.x; ty = g.y; present = g.present;
      hand._ghostFist = g.fist; // game kendi ghost-fist'ini okur
    }

    // üstel yumuşatma (frame-rate bağımsız: 0.22 = 60Hz/kare faktörü -> 120/144Hz'de de aynı his)
    const a = 1 - Math.pow(1 - LENS_SMOOTH, dt / (1 / 60));
    lx += (tx - lx) * a;
    ly += (ty - ly) * a;

    if (lensEl) {
      lensEl.style.left = (lx * 100) + "%";
      lensEl.style.top = (ly * 100) + "%";
      lensEl.style.opacity = present ? 1 : 0;
      lensEl.classList.toggle("ghost", !!(ghosting && idle > 5));
    }

    const w = world.normToWorld(lx, ly);
    if (MA.game && MA.game.onFrame) {
      MA.game.onFrame({ lx: w.x, ly: w.y, present, fist: !!hand_fist(present, ghosting), dt, t: t / 1000 });
    }
    requestAnimationFrame(frame);
  }

  function hand_fist(present, ghosting) {
    const hand = MA.input.hand;
    if (ghosting && hand._ghostFist) return true;
    return present && hand.gesture === "fist";
  }

  function start() {
    if (started) return; started = true;
    lensEl = document.getElementById("mh-lens");
    irisEl = document.getElementById("mh-iris");
    requestAnimationFrame(frame);
  }

  MA.lens = { start, playSelect, get smoothed() { return { x: lx, y: ly }; } };
})();
