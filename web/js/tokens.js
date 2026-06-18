/* tokens.js — MathField.cs portu + token görselleri + dünya koordinatları + atmosfer.
   Oynanış matematiği Unity dünya birimlerinde (ortho size 5 -> 17.78 x 10). */
(function () {
  const MA = (window.MA = window.MA || {});
  const { ri, rv } = MA.questions;

  // ---- Dünya koordinatları (Unity kamera ortho size 5, 16:9) ----
  const HALF_H = 5, HALF_W = 5 * 16 / 9; // 8.8889
  const W = HALF_W * 2, H = HALF_H * 2;  // 17.7778 x 10
  const world = {
    W, H, HALF_W, HALF_H,
    // dünya -> sahne yüzdesi
    toPct(wx, wy) { return { left: (wx + HALF_W) / W * 100, top: (HALF_H - wy) / H * 100 }; },
    // normalize el [0,1] -> dünya
    normToWorld(nx, ny) { return { x: nx * W - HALF_W, y: HALF_H - ny * H }; },
    dist(ax, ay, bx, by) { return Math.hypot(ax - bx, ay - by); },
  };
  MA.world = world;

  // ---- MathField rect (Unity birebir) ----
  const F = { xMin: -7.5, xMax: 7.5, yMin: -4.3, yMax: 3.0, cell: 1.6, jitter: 0.42 };
  const EXC = { x: 7.5, y: 4.2, r: 2.4 }; // RESET dışlama bölgesi

  function insideUnitCircle(scale) { // Unity Random.insideUnitCircle * scale
    const r = Math.sqrt(rv()) * scale, t = rv() * Math.PI * 2;
    return { x: r * Math.cos(t), y: r * Math.sin(t) };
  }

  function shuffle(list) {
    for (let i = list.length - 1; i > 0; i--) { const j = ri(0, i + 1); [list[i], list[j]] = [list[j], list[i]]; }
    return list;
  }

  // Greedy farthest-point sampling (MathField.PickSpread portu)
  function pickSpread(pts, k) {
    const result = [];
    if (k <= 0 || pts.length === 0) return result;
    result.push(ri(0, pts.length));
    while (result.length < k) {
      let best = -1, bestD = -1;
      for (let i = 0; i < pts.length; i++) {
        if (result.includes(i)) continue;
        let dmin = Infinity;
        for (const r of result) dmin = Math.min(dmin, world.dist(pts[i].x, pts[i].y, pts[r].x, pts[r].y));
        if (dmin > bestD) { bestD = dmin; best = i; }
      }
      if (best < 0) break;
      result.push(best);
    }
    return result;
  }

  // ---- Token nesnesi (AnswerToken.cs eşdeğeri) ----
  const GOLD_GLOW = "radial-gradient(circle,rgba(255,200,61,0.55),transparent 68%)";
  const CYAN_GLOW = "radial-gradient(circle,rgba(120,210,255,0.5),transparent 68%)";

  function makeToken(parent, glyph, wx, wy, correct) {
    const el = document.createElement("div");
    el.className = "token";
    const pos = world.toPct(wx, wy);
    el.style.left = pos.left.toFixed(3) + "%";
    el.style.top = pos.top.toFixed(3) + "%";
    el.innerHTML = '<div class="t-glow"></div><div class="t-ring"></div><div class="t-glyph"></div>';
    const glow = el.querySelector(".t-glow");
    const ring = el.querySelector(".t-ring");
    const tg = el.querySelector(".t-glyph");
    tg.textContent = glyph;
    parent.appendChild(el);

    let confirmed = false, mode = "", lastR = -1;

    // Sönük (reveal) moduna geçişte SABİT stilleri bir kez yaz (her kare değil).
    // Böylece her karede 36 token × ~8 stil yazma (paint/recalc thrash) ortadan kalkar.
    function enterReveal() {
      if (mode === "reveal") return;
      mode = "reveal";
      el.style.transition = "none";
      glow.style.background = CYAN_GLOW;
      ring.style.border = "1.5px solid transparent";
      ring.style.boxShadow = "none";
      tg.style.color = "var(--token-text)";
      lastR = -1;   // opacity/transform yeniden yazılsın
    }

    const T = {
      el, wx, wy, correct,
      setReveal(r) {
        if (confirmed) return;
        enterReveal();
        if (Math.abs(r - lastR) < 0.008) return;   // anlamlı değişim yoksa DOM'a dokunma
        lastR = r;
        el.style.opacity = r.toFixed(3);
        el.style.transform = `translate(-50%,-50%) scale(${(0.8 + 0.2 * r).toFixed(3)})`;
        glow.style.opacity = (r * 0.85).toFixed(3);
      },
      setArmed(on) {
        if (confirmed || !on || mode === "armed") return;   // zaten armed -> tekrar yazma
        mode = "armed";
        el.style.transition = "none";
        el.style.opacity = 1;
        el.style.transform = "translate(-50%,-50%) scale(1.2)";
        glow.style.opacity = 0.95;
        glow.style.background = GOLD_GLOW;
        ring.style.border = "1.5px solid rgba(255,200,61,0.9)";
        ring.style.boxShadow = "0 0 18px rgba(255,200,61,0.7)";
        tg.style.color = "var(--gold-text)";
      },
      confirm(ok) {
        confirmed = true; mode = "confirmed";
        const glowC = ok ? "rgba(52,245,166,0.55)" : "rgba(255,84,112,0.5)";
        const ringC = ok ? "rgba(52,245,166,0.95)" : "rgba(255,84,112,0.9)";
        el.style.transition = "transform 0.16s cubic-bezier(0.34,1.6,0.6,1)";
        el.style.opacity = 1;
        el.style.transform = `translate(-50%,-50%) scale(${ok ? 1.45 : 1.3})`;
        glow.style.opacity = 1;
        glow.style.background = `radial-gradient(circle,${glowC},transparent 68%)`;
        ring.style.border = `2px solid ${ringC}`;
        ring.style.boxShadow = `0 0 24px ${ringC}`;
        tg.style.color = ok ? "var(--green-text)" : "var(--red-text)";
        setTimeout(() => {
          el.style.transform = `translate(-50%,-50%) scale(${ok ? 1.18 : 1.05})`;
        }, 170);
      },
      // Havuz: aynı DOM öğesini yeni soru için yeniden kullan (her soruda sil+yarat YOK -> GC azalır).
      reset(g, nx, ny, isCorrect) {
        T.wx = nx; T.wy = ny; T.correct = isCorrect;
        const p = world.toPct(nx, ny);
        el.style.left = p.left.toFixed(3) + "%";
        el.style.top = p.top.toFixed(3) + "%";
        tg.textContent = g;
        confirmed = false; mode = ""; lastR = -1;
        el.style.transition = "none";
        el.style.opacity = 0;
        el.style.transform = "translate(-50%,-50%) scale(0.8)";
        glow.style.opacity = 0; glow.style.background = CYAN_GLOW;
        ring.style.border = "1.5px solid transparent"; ring.style.boxShadow = "none";
        tg.style.color = "var(--token-text)";
        el.style.display = "";
      },
      hide() { confirmed = false; mode = ""; lastR = -1; el.style.transition = "none"; el.style.opacity = 0; },
    };
    return T;
  }

  let _live = [], _pool = [];                  // _pool: yeniden kullanılan token DOM havuzu (en fazla totalTokens)
  function clearField() {
    for (const t of _pool) if (t) t.hide();    // DOM'u SİLME; sadece gizle -> sonraki soruda yeniden kullan
    _live = [];
  }

  // MathField.Spawn portu — token DOM'u havuzdan yeniden kullanılır (sil+yarat yerine reset).
  function genField(problem, decoys, correctCopies, totalTokens) {
    const field = document.getElementById("mh-field");

    const cells = [];
    for (let x = F.xMin; x <= F.xMax + 0.001; x += F.cell)
      for (let y = F.yMin; y <= F.yMax + 0.001; y += F.cell) {
        const o = insideUnitCircle(F.jitter);
        const cp = { x: x + o.x, y: y + o.y };
        if (world.dist(cp.x, cp.y, EXC.x, EXC.y) < EXC.r) continue; // RESET için temiz alan
        cells.push(cp);
      }
    shuffle(cells);

    const count = Math.min(totalTokens, cells.length);
    const correctN = Math.max(1, Math.min(correctCopies, count));
    const chosen = cells.slice(0, count);
    const correctIdx = new Set(pickSpread(chosen, correctN));

    _live = [];
    let decoyPtr = 0;
    for (let i = 0; i < count; i++) {
      const isCorrect = correctIdx.has(i);
      const val = isCorrect
        ? problem.answer
        : (decoys && decoys.length > 0 ? decoys[(decoyPtr++) % decoys.length] : "?");
      let t = _pool[i];
      if (!t) { t = makeToken(field, val, chosen[i].x, chosen[i].y, isCorrect); _pool[i] = t; }
      else t.reset(val, chosen[i].x, chosen[i].y, isCorrect);
      _live.push(t);
    }
    for (let i = count; i < _pool.length; i++) _pool[i].hide();   // bu soruda kullanılmayan fazlalıkları gizle
    return _live.slice();
  }

  // ---- Yıldız alanı (320 yıldız, tam-ekran canvas) ----
  function drawStars() {
    const cv = document.getElementById("mh-stars-page");
    if (!cv) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    cv.width = Math.floor(window.innerWidth * dpr);
    cv.height = Math.floor(window.innerHeight * dpr);
    cv.style.width = window.innerWidth + "px";
    cv.style.height = window.innerHeight + "px";
    const ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, cv.width, cv.height);
    for (let i = 0; i < 320; i++) {
      const x = rv() * cv.width, y = rv() * cv.height;
      const r = rv() * 1.3 * dpr;
      ctx.globalAlpha = 0.1 + rv() * 0.5;
      ctx.fillStyle = "#cfe0ff";
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  // ---- Floater'lar (26 sürüklenen matematik sembolü) ----
  const FLOAT_GLYPHS = ["√","π","²","½","¾","×","÷","+","−","=","%","∞","3","7","9","²","¼","8"];
  const FLOAT_COLORS = ["#00EBFF","#9F5FFF","#FF4AD6","#FFC83D","#34F5A6","#7df3ff","#b98cff","#ff8fe4","#cfe9ff"];
  // JS parçacık sistemi: her sembol yavaşça rastgele yönde süzülür (uzay hissi),
  // kendi ömrü dolunca yumuşakça kaybolur ve yeni konumda yeniden doğar.
  // cqmin koordinat uzayı (sahne sabit 16:9 -> cqmin = sahne yüksekliğinin %1'i)
  const W_CQ = 100 * 16 / 9, H_CQ = 100;       // ~177.8 x 100 cqmin
  const FLOATERS = [];
  let _floatStarted = false, _floatLast = 0;

  function _resetFloater(f, ageFrac) {
    const size = 3 + rv() * 5;
    f.size = size; f.r = size * 0.55;           // çarpışma yarıçapı (cqmin)
    f.x = f.r + rv() * (W_CQ - 2 * f.r);
    f.y = f.r + rv() * (H_CQ - 2 * f.r);
    const ang = rv() * Math.PI * 2, spd = 1.4 + rv() * 2.2;  // cqmin/s — canlı, simetrik yön
    f.vx = Math.cos(ang) * spd; f.vy = Math.sin(ang) * spd;
    f.rot = rv() * 360; f.vrot = (rv() * 2 - 1) * 8;
    f.peak = 0.16 + rv() * 0.30;
    f.life = 12 + rv() * 10;                     // 12-22 sn ömür
    f.tw = 0.25 + rv() * 0.45; f.phase = rv() * Math.PI * 2;
    f.age = (ageFrac != null ? ageFrac : rv()) * f.life;
    f.el.textContent = FLOAT_GLYPHS[ri(0, FLOAT_GLYPHS.length)];
    f.el.style.color = FLOAT_COLORS[ri(0, FLOAT_COLORS.length)];
    f.el.style.fontSize = size.toFixed(2) + "cqmin";
  }

  const FADE_IN = 1.8, FADE_OUT = 2.4;
  function _floatFrame(now) {
    const dt = _floatLast ? Math.min((now - _floatLast) / 1000, 0.05) : 0.016;
    _floatLast = now;
    requestAnimationFrame(_floatFrame);
    if (!(window.MA.game && window.MA.game.screen === "attract")) return; // sadece attract'ta

    const t = now / 1000;

    // hareket + ömür + duvardan sekme
    for (const f of FLOATERS) {
      f.age += dt;
      if (f.age >= f.life) { _resetFloater(f, 0); continue; }  // kaybol -> yeniden doğ
      f.x += f.vx * dt; f.y += f.vy * dt; f.rot += f.vrot * dt;
      if (f.x < f.r) { f.x = f.r; f.vx = Math.abs(f.vx); }
      else if (f.x > W_CQ - f.r) { f.x = W_CQ - f.r; f.vx = -Math.abs(f.vx); }
      if (f.y < f.r) { f.y = f.r; f.vy = Math.abs(f.vy); }
      else if (f.y > H_CQ - f.r) { f.y = H_CQ - f.r; f.vy = -Math.abs(f.vy); }
    }

    // birbirine elastik çarpma (eşit kütle) -> üst üste binmeyi engeller, sektirir
    for (let i = 0; i < FLOATERS.length; i++) {
      const a = FLOATERS[i];
      for (let j = i + 1; j < FLOATERS.length; j++) {
        const b = FLOATERS[j];
        const dx = b.x - a.x, dy = b.y - a.y, min = a.r + b.r;
        const d2 = dx * dx + dy * dy;
        if (d2 > 0.0001 && d2 < min * min) {
          const d = Math.sqrt(d2), nx = dx / d, ny = dy / d, push = (min - d) / 2;
          a.x -= nx * push; a.y -= ny * push;
          b.x += nx * push; b.y += ny * push;
          const rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
          if (rel < 0) {                         // yaklaşıyorlarsa normal hızları değiş-tokuş et
            a.vx += rel * nx; a.vy += rel * ny;
            b.vx -= rel * nx; b.vy -= rel * ny;
          }
        }
      }
    }

    // render
    for (const f of FLOATERS) {
      let fade = 1;
      if (f.age < FADE_IN) fade = f.age / FADE_IN;
      else if (f.age > f.life - FADE_OUT) fade = (f.life - f.age) / FADE_OUT;
      const tw = 0.78 + 0.22 * Math.sin(t * f.tw * 6.283 + f.phase);
      f.el.style.opacity = (f.peak * fade * tw).toFixed(3);
      f.el.style.transform =
        `translate(${f.x.toFixed(2)}cqmin,${f.y.toFixed(2)}cqmin) translate(-50%,-50%) rotate(${f.rot.toFixed(1)}deg)`;
    }
  }

  function buildFloaters() {
    const host = document.getElementById("mh-floaters");
    if (!host) return;
    host.innerHTML = "";
    FLOATERS.length = 0;
    for (let i = 0; i < 34; i++) {               // daha kalabalık
      const el = document.createElement("span");
      el.className = "floater";
      host.appendChild(el);
      const f = { el };
      _resetFloater(f, rv());   // dağınık başlangıç yaşı -> senkron olmayan döngü
      FLOATERS.push(f);
    }
    if (!_floatStarted) { _floatStarted = true; requestAnimationFrame(_floatFrame); }
  }

  MA.tokens = { genField, clearField, drawStars, buildFloaters };
})();
