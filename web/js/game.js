/* game.js — RoundManager.cs durum makinesi + attract seçim + bağlama.
   Otoriter kurallar Unity'den. Tasarım (Sci-Fi HUD) bunun üzerine giydirilir. */
(function () {
  const MA = (window.MA = window.MA || {});
  const Q = MA.questions, world = MA.world;

  // ---- Otoriter kurallar (RoundManager.cs) ----
  const RULES = {
    totalQuestions: 5, roundSeconds: 120, correctCopies: 3, totalTokens: 36,
    decoyVariety: 14, lowTimeThreshold: 10, resolveDelay: 0.85, endSummarySeconds: 6,
    // Puan: her doğru sabit puan + kalan süre bonusu. Bonus doğruluk oranıyla
    // çarpılır -> hızlı ama yanlış = bonus yok; hızlı ve doğru = maksimum.
    pointsPerCorrect: 100, timeBonusPerSec: 5,
  };
  const ARM_ATTRACT = 0.13 * world.W; // prototip 0.13*width -> dünya birimi (~2.31)
  const ARM_RESET = 1.6;

  const selector = new MA.LensHunt();

  const G = {
    screen: "attract",
    difficulty: "kolay",
    problem: null,
    qNum: 0, correct: 0, score: 0, timeLeft: 0, running: false, locked: false,
    _prevFist: false, _armedDiff: null, _armedReset: false,
    _endTimer: null, _resolveTimer: null,
    _diffWorld: [], _resetWorld: null,  // buton merkezleri (cache; resize'da yenilenir)
  };
  MA.game = G;

  // ---- DOM ----
  const $ = (id) => document.getElementById(id);
  const screens = { attract: null, playing: null, result: null };

  function setScreen(name) {
    G.screen = name;
    for (const k in screens) screens[k].classList.toggle("active", k === name);
  }

  // DOM elemanı merkezini normalize sahne koordinatına çevir
  function centerNorm(el) {
    const s = $("stage").getBoundingClientRect();
    const r = el.getBoundingClientRect();
    return { x: ((r.left + r.width / 2) - s.left) / s.width, y: ((r.top + r.height / 2) - s.top) / s.height };
  }
  function centerWorld(el) { const n = centerNorm(el); return world.normToWorld(n.x, n.y); }

  // Buton dünya-merkezlerini cache'le (her kare getBoundingClientRect = layout thrash).
  function computeDiffCenters() {
    G._diffWorld = Array.from(document.querySelectorAll("#mh-diffs .diff")).map((el) => {
      const c = centerWorld(el);
      return { el, diff: el.getAttribute("data-diff"), wx: c.x, wy: c.y };
    });
  }
  function computeResetCenter() { const c = centerWorld($("mh-reset")); G._resetWorld = { wx: c.x, wy: c.y }; }

  // ---- durumlar ----
  function enterAttract() {
    if (G._endTimer) { clearTimeout(G._endTimer); G._endTimer = null; }
    if (G._resolveTimer) { clearTimeout(G._resolveTimer); G._resolveTimer = null; }
    G.running = false; G.locked = false; G._armedDiff = null; G._armedReset = false;
    selector.suspend();
    MA.tokens.clearField();
    setScreen("attract");
    MA.leaderboard.render($("mh-lb-list"), G._lbHighlight || 0);  // tabloyu güncelle, yeni kaydı vurgula
    G._lbHighlight = 0;
    computeDiffCenters();
  }

  function startGame(d) {
    if (G.screen === "playing") return;
    G.difficulty = d;
    setScreen("playing");
    computeResetCenter();
    beginRound();
  }

  function beginRound() {
    G.qNum = 1; G.correct = 0; G.score = 0; G.timeLeft = RULES.roundSeconds; G.running = true; G.locked = false;
    updateCorrect(); updateLiveScore(0, false); updateTimer();
    nextQuestion();
  }

  function nextQuestion() {
    G.problem = Q.next(G.difficulty);
    const decoys = Q.makeDecoys(G.problem, RULES.decoyVariety);
    const tokens = MA.tokens.genField(G.problem, decoys, RULES.correctCopies, RULES.totalTokens);
    selector.setTokens(tokens);
    G.locked = false;
    $("mh-prompt").textContent = G.problem.prompt;
    $("mh-progress").innerHTML = `SORU ${G.qNum}/${RULES.totalQuestions} · <span class="lvl">${d2name(G.difficulty)}</span>`;
  }
  function d2name(d) { return d === "orta" ? "ORTA" : d === "zor" ? "ZOR" : "KOLAY"; }

  function onAnswer(ok) {
    if (G.screen !== "playing" || !G.running) return;
    if (ok) { G.correct++; flash("Doğru!", "var(--green)"); }
    else { flash("Yanlış", "var(--red)"); }
    updateCorrect();
    updateLiveScore(G.correct * RULES.pointsPerCorrect, ok); // taban puan = doğru × 100; bonus bitişte eklenir
    G.locked = true;
    G._resolveTimer = setTimeout(() => {
      G._resolveTimer = null;
      if (G.screen !== "playing" || !G.running) return; // pause sırasında reset/timeout olduysa
      G.qNum++;
      if (G.qNum > RULES.totalQuestions) endRound(false);
      else nextQuestion();
    }, RULES.resolveDelay * 1000);
  }

  function computeScore() {
    const remaining = Math.max(0, G.timeLeft);
    const accuracy = RULES.totalQuestions > 0 ? G.correct / RULES.totalQuestions : 0;
    const timeBonus = Math.round(remaining * RULES.timeBonusPerSec * accuracy);
    return G.correct * RULES.pointsPerCorrect + timeBonus;
  }
  function fmtTime(sec) {
    sec = Math.max(0, Math.floor(sec));
    return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0");
  }

  function endRound(timeout) {
    G.running = false;
    if (G._resolveTimer) { clearTimeout(G._resolveTimer); G._resolveTimer = null; } // sarkan resolve'u temizle
    selector.suspend();
    MA.tokens.clearField();

    G.score = computeScore();
    const base = G.correct * RULES.pointsPerCorrect;   // oyun içi gösterilen taban puan
    const elapsed = RULES.roundSeconds - G.timeLeft;   // oyunu tamamlama süresi

    $("mh-result-msg").textContent = timeout ? "Süre doldu!" : "Bitti!";
    $("mh-result-num").textContent = `${G.correct}/${RULES.totalQuestions}`;
    $("mh-result-time").textContent = fmtTime(elapsed);
    setScreen("result");
    animateScore(G.score, base);   // taban puandan başlat -> zaman bonusu eklenirken say

    const lb = MA.leaderboard.add(G.score);   // isimsiz kayıt + sıralama
    G._lbHighlight = lb.top3 ? lb.rank : 0;    // attract'a dönünce vurgulanacak satır
    showResultRank(lb);

    G._endTimer = setTimeout(enterAttract, RULES.endSummarySeconds * 1000);
  }

  // Final puanı 0'dan hedefe say (easeOutCubic). Yeni tur eski animasyonu iptal eder.
  let _scoreGen = 0;
  function animateScore(target, from) {
    from = from || 0;
    const el = $("mh-result-score");
    if (!el) return;
    el.textContent = String(from);
    const gen = ++_scoreGen, dur = 900, t0 = performance.now();
    (function step(now) {
      if (gen !== _scoreGen) return;                     // sonraki tur devraldı
      const k = Math.min(1, (now - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      el.textContent = String(Math.round(from + (target - from) * e));
      if (k < 1) requestAnimationFrame(step);
      else el.textContent = String(target);
    })(performance.now());
  }

  // Sonuç ekranı: skor ilk 3'e girdiyse kutlama, değilse sade sıralama satırı.
  function showResultRank(lb) {
    const el = $("mh-result-rank");
    if (!el) return;
    el.classList.remove("show", "celebrate");
    void el.offsetWidth;                                  // sınıfı sıfırla -> animasyon tekrar tetiklensin
    if (lb.top3) {
      const medal = lb.rank === 1 ? "🥇" : lb.rank === 2 ? "🥈" : "🥉";
      el.textContent = lb.rank === 1
        ? `${medal} En yüksek puanı yaptın!`
        : `${medal} En yüksek ${lb.rank}. puanı yaptın!`;
      el.classList.add("show", "celebrate");
    } else if (lb.score > 0) {
      el.textContent = `Sıralaman: ${lb.rank}.`;
      el.classList.add("show");
    } else {
      el.textContent = "";
    }
  }

  // ---- her kare (lens.js çağırır) ----
  function onFrame(ctx) {
    const fistEdge = ctx.fist && !G._prevFist;

    if (G.screen === "playing") {
      // timer
      if (G.running) {
        G.timeLeft -= ctx.dt;
        if (G.timeLeft <= 0) { G.timeLeft = 0; updateTimer(); endRound(true); G._prevFist = ctx.fist; return; }
        updateTimer();
      }
      // token seçimi (LensHunt)
      const res = selector.update(ctx.lx, ctx.ly, ctx.present, ctx.fist, ctx.dt);
      if (res) onAnswer(res.ok);

      // RESET butonu (sadece token armed değilken — Unity gate)
      let armR = false;
      if (!selector.hasArmed && !G.locked && ctx.present && G._resetWorld) {
        if (world.dist(ctx.lx, ctx.ly, G._resetWorld.wx, G._resetWorld.wy) <= ARM_RESET) {
          armR = true;
          if (fistEdge) { MA.lens.playSelect(); enterAttract(); }
        }
      }
      $("mh-reset").classList.toggle("armed", armR);
      G._armedReset = armR;

    } else if (G.screen === "attract") {
      // zorluk butonu seçimi (cache'li merkezler, en-yakın-yarıçap)
      let best = null, bestD = ARM_ATTRACT;
      for (const b of G._diffWorld) {
        const d = world.dist(ctx.lx, ctx.ly, b.wx, b.wy);
        if (ctx.present && d <= bestD) { bestD = d; best = b; }
      }
      for (const b of G._diffWorld) b.el.classList.toggle("armed", !!best && b.el === best.el);
      G._armedDiff = best ? best.diff : null;
      if (fistEdge && G._armedDiff) { MA.lens.playSelect(); startGame(G._armedDiff); }
    }

    G._prevFist = ctx.fist;
  }

  // ---- attract ghost demo: fantom mercek butonlar arasında gezer (fist YOK) ----
  let _ghostA = 0, _ghostB = 1, _ghostT = 0;
  function ghostTarget(timeSec) {
    const diffs = document.querySelectorAll("#mh-diffs .diff");
    if (diffs.length < 2) return { x: 0.5, y: 0.5, present: true, fist: false };
    const period = 3.0; // her butonda ~3s
    _ghostT += 1 / 60;
    if (_ghostT >= period) { _ghostT = 0; _ghostA = _ghostB; _ghostB = (_ghostB + 1) % diffs.length; }
    const a = centerNorm(diffs[_ghostA]), b = centerNorm(diffs[_ghostB]);
    const k = Math.min(_ghostT / 2.0, 1); // ilk 2s'de geç, sonra beklet
    const e = k * k * (3 - 2 * k); // smoothstep
    return { x: a.x + (b.x - a.x) * e, y: a.y + (b.y - a.y) * e, present: true, fist: false };
  }

  // ---- UI ----
  function updateCorrect() { $("mh-score").textContent = String(G.correct).padStart(2, "0"); }
  function updateLiveScore(val, bump) {
    const el = $("mh-live-score");
    if (!el) return;
    el.textContent = String(val);
    if (bump) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); } // reflow -> animasyonu yeniden tetikle
  }
  function updateTimer() {
    const s = Math.ceil(G.timeLeft);
    $("mh-timer").textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    $("mh-timer").classList.toggle("low", G.running && G.timeLeft <= RULES.lowTimeThreshold);
  }
  let _flashTimer = null;
  function flash(msg, color) {
    const f = $("mh-flash");
    f.textContent = msg; f.style.color = color;
    f.style.transition = "none"; f.style.transform = "scale(1.25)"; f.style.opacity = "1";
    void f.offsetWidth; // reflow
    f.style.transition = "transform 0.5s cubic-bezier(0.2,0,0.2,1), opacity 0.3s";
    f.style.transform = "scale(1)";
    if (_flashTimer) clearTimeout(_flashTimer);
    _flashTimer = setTimeout(() => { f.style.opacity = "0"; }, 760);
  }

  G.onFrame = onFrame;
  G.ghostTarget = ghostTarget;

  // ---- başlat ----
  function init() {
    screens.attract = $("screen-attract");
    screens.playing = $("screen-playing");
    screens.result = $("screen-result");
    MA.tokens.drawStars();
    MA.tokens.buildFloaters();
    window.addEventListener("resize", () => {
      MA.tokens.drawStars();
      if (G.screen === "attract") computeDiffCenters();
      else if (G.screen === "playing") computeResetCenter();
    });
    MA.input.start();
    MA.lens.start();
    // ESC -> oyunu/kiosk penceresini kapat (launcher arka süreçleri de durdurur)
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { try { window.close(); } catch (_) {} }
    });
    enterAttract();   // ekranı kur + buton merkezlerini cache'le
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
