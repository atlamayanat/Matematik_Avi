/* game.js — RoundManager.cs durum makinesi + attract seçim + bağlama.
   Otoriter kurallar Unity'den. Tasarım (Sci-Fi HUD) bunun üzerine giydirilir. */
(function () {
  const MA = (window.MA = window.MA || {});
  const Q = MA.questions, world = MA.world;

  // ---- Otoriter kurallar (RoundManager.cs) ----
  const RULES = {
    roundSeconds: 120, correctCopies: 3, totalTokens: 36,
    decoyVariety: 14, lowTimeThreshold: 10, resolveDelay: 0.85, endSummarySeconds: 6,
  };
  // Puan (çocuk-dostu dopamin): zorluğa göre taban × ardışık doğruda büyüyen kombo çarpanı.
  // Yanlışta puan DÜŞMEZ; sadece kombo sıfırlanır (cesaret kırıcı olmasın).
  const SCORE = { base: { kolay: 20, orta: 40, zor: 80 }, comboCap: 5 };
  const ARM_ATTRACT = 0.13 * world.W; // prototip 0.13*width -> dünya birimi (~2.31)
  const ARM_RESET = 1.6;

  // Adaptif zorluk: her doğru +1 seviye, her yanlış -1 (en az 0).
  // Eşik = bu seviyeden itibaren ilgili basamak. Kolayca ayarlanır.
  const RAMP = { orta: 3, zor: 6 };

  const selector = new MA.LensHunt();

  const G = {
    screen: "attract",
    difficulty: "kolay",
    problem: null,
    seen: 0, correct: 0, level: 0, combo: 0, score: 0, timeLeft: 0,
    running: false, locked: false, counting: false,
    _prevFist: false, _armedStart: false, _armedReset: false,
    _endTimer: null, _resolveTimer: null, _countTimer: null, _pendingTokens: null,
    _startWorld: null, _resetWorld: null,  // buton merkezleri (cache; resize'da yenilenir)
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

  // Buton dünya-merkezini cache'le (her kare getBoundingClientRect = layout thrash).
  function computeStartCenter() { const c = centerWorld($("mh-start")); G._startWorld = { wx: c.x, wy: c.y }; }
  function computeResetCenter() { const c = centerWorld($("mh-reset")); G._resetWorld = { wx: c.x, wy: c.y }; }

  // ---- durumlar ----
  function enterAttract() {
    if (G._endTimer) { clearTimeout(G._endTimer); G._endTimer = null; }
    if (G._resolveTimer) { clearTimeout(G._resolveTimer); G._resolveTimer = null; }
    if (G._countTimer) { clearTimeout(G._countTimer); G._countTimer = null; }
    G.running = false; G.locked = false; G.counting = false; G._armedStart = false; G._armedReset = false;
    selector.suspend();
    MA.tokens.clearField();
    const cd = $("mh-countdown"); if (cd) cd.classList.remove("show");
    setScreen("attract");
    MA.leaderboard.render($("mh-lb-list"), G._lbHighlight || 0);  // tabloyu güncelle, yeni kaydı vurgula
    G._lbHighlight = 0;
    computeStartCenter();
  }

  // BAŞLA -> oyun ekranına geç, ilk soruyu arkada sönük göster, 3-2-1 say, sonra canlandır.
  function startCountdown() {
    if (G.screen === "playing") return;
    setScreen("playing");
    computeResetCenter();
    // tur durumu sıfırla (geri sayım boyunca donuk)
    G.correct = 0; G.seen = 0; G.level = 0; G.combo = 0; G.score = 0;
    G.timeLeft = RULES.roundSeconds;
    G.running = false; G.locked = true; G.counting = true;
    updateCorrect(); updateLiveScore(0, false); updateTimer();
    spawnQuestion(false);                 // ilk soruyu arka planda göster (sönük), seçim kapalı

    const seq = ["3", "2", "1", "BAŞLA!"];
    let i = 0;
    const step = () => {
      if (G.screen !== "playing" || !G.counting) return;   // RESET/çıkış olduysa iptal
      if (i < seq.length) {
        const isGo = i === seq.length - 1;
        showCount(seq[i], isGo);
        i++;
        G._countTimer = setTimeout(step, isGo ? 650 : 1000);
      } else {
        const cd = $("mh-countdown"); if (cd) cd.classList.remove("show");
        G._countTimer = null;
        goLive();
      }
    };
    step();
  }

  function showCount(txt, isGo) {
    const cd = $("mh-countdown");
    if (!cd) return;
    cd.classList.add("show");
    let span = cd.querySelector(".cd-num");
    if (!span) { span = document.createElement("div"); span.className = "cd-num"; cd.appendChild(span); }
    span.textContent = txt;
    span.classList.toggle("go", !!isGo);
    span.classList.remove("anim"); void span.offsetWidth; span.classList.add("anim");  // animasyonu yeniden tetikle
  }

  // Geri sayım bitti: sayaç + token seçimi başlasın.
  function goLive() {
    if (G.screen !== "playing") return;
    G.counting = false; G.running = true; G.locked = false;
    if (G._pendingTokens) { selector.setTokens(G._pendingTokens); G._pendingTokens = null; }
    updateTimer();
  }

  // Seviye -> zorluk basamağı (doğru bildikçe yükselir, yanlışta bir kademe iner).
  function tierFromLevel(lv) {
    if (lv >= RAMP.zor) return "zor";
    if (lv >= RAMP.orta) return "orta";
    return "kolay";
  }

  // activate=true: seçim açık. activate=false: soruyu hazırla ama cevaplar gizli (geri sayım), seçim kapalı.
  function spawnQuestion(activate) {
    G.difficulty = tierFromLevel(G.level);
    G.problem = Q.next(G.difficulty);
    const decoys = Q.makeDecoys(G.problem, RULES.decoyVariety);
    const tokens = MA.tokens.genField(G.problem, decoys, RULES.correctCopies, RULES.totalTokens);
    G.seen++;
    $("mh-prompt").innerHTML = Q.promptHTML(G.problem.prompt);
    $("mh-progress").innerHTML = `SORU ${G.seen} · <span class="lvl">${d2name(G.difficulty)}</span>`;
    if (activate) {
      selector.setTokens(tokens);
      G.locked = false;
    } else {
      selector.suspend();
      G._pendingTokens = tokens;   // geri sayımda cevaplar GİZLİ kalır (oyun mantığı); yalnızca soru görünür
    }
  }
  function d2name(d) { return d === "orta" ? "ORTA" : d === "zor" ? "ZOR" : "KOLAY"; }

  function onAnswer(ok) {
    if (G.screen !== "playing" || !G.running) return;
    if (ok) {
      G.correct++; G.level++; G.combo++;                          // zora doğru; kombo çarpanı GİZLİ büyür
      const mult = Math.min(G.combo, SCORE.comboCap);
      G.score += (SCORE.base[G.difficulty] || SCORE.base.kolay) * mult;  // yanlışta puan DÜŞMEZ
      flash("Doğru!", "var(--green)");                            // merkezde sadece olumlama (puan/kombo gösterilmez)
    } else {
      G.combo = 0;                                                // kombo sıfırlanır
      G.level = Math.max(0, G.level - 1);                         // bir kademe kolaya
      flash("Yanlış", "var(--red)");
    }
    updateCorrect();
    updateLiveScore(G.score, ok);
    G.locked = true;
    G._resolveTimer = setTimeout(() => {
      G._resolveTimer = null;
      if (G.screen !== "playing" || !G.running) return; // pause sırasında reset/timeout olduysa
      spawnQuestion(true);   // soru sınırı yok: süre dolana kadar yeni soru gelir
    }, RULES.resolveDelay * 1000);
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

    const elapsed = RULES.roundSeconds - G.timeLeft;   // oyunu tamamlama süresi

    $("mh-result-msg").textContent = timeout ? "Süre doldu!" : "Bitti!";
    $("mh-result-num").textContent = `${G.correct}/${G.seen}`;
    $("mh-result-time").textContent = fmtTime(elapsed);
    setScreen("result");
    animateScore(G.score, 0);   // 0'dan say -> tatmin edici final reveal

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
      // tek BAŞLA butonu: yarıçap içindeyse armed, yumrukta geri sayımı başlat
      let armed = false;
      if (ctx.present && G._startWorld &&
          world.dist(ctx.lx, ctx.ly, G._startWorld.wx, G._startWorld.wy) <= ARM_ATTRACT) {
        armed = true;
      }
      const sb = $("mh-start"); if (sb) sb.classList.toggle("armed", armed);
      G._armedStart = armed;
      if (fistEdge && armed) { MA.lens.playSelect(); startCountdown(); }
    }

    G._prevFist = ctx.fist;
  }

  // ---- attract ghost demo: fantom mercek BAŞLA üzerinde hafifçe salınır (fist YOK) ----
  function ghostTarget(timeSec) {
    const el = $("mh-start");
    if (!el) return { x: 0.5, y: 0.5, present: true, fist: false };
    const c = centerNorm(el);
    const bx = Math.sin(timeSec * 0.9) * 0.018;   // yumuşak salınım
    const by = Math.cos(timeSec * 1.3) * 0.012;
    return { x: c.x + bx, y: c.y + by, present: true, fist: false };
  }

  // ---- UI ----
  function updateCorrect() { $("mh-score").textContent = String(G.correct).padStart(2, "0"); }
  function updateLiveScore(val, bump) {
    const el = $("mh-live-score");
    if (!el) return;
    el.textContent = String(val);
    if (bump) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); } // reflow -> animasyonu yeniden tetikle
  }
  let _lastTimerStr = "";
  function updateTimer() {
    const s = Math.ceil(G.timeLeft);
    const str = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    if (str !== _lastTimerStr) { $("mh-timer").textContent = str; _lastTimerStr = str; }  // saniye değişmedikçe DOM'a yazma
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
      if (G.screen === "attract") computeStartCenter();
      else if (G.screen === "playing") computeResetCenter();
    });
    MA.input.start();
    MA.lens.start();
    // ESC -> oyunu/kiosk penceresini kapat (launcher arka süreçleri de durdurur)
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { try { window.close(); } catch (_) {} }
    });

    // İlk karşılama: biyometrik kalibrasyon ekranı (yalnızca açılışta gösterilir).
    // Tamamlanınca ana ekrana (BAŞLA) geçilir. ?calib=off ile atlanır (test).
    const calibOff = new URLSearchParams(location.search).get("calib") === "off";
    if (MA.calib && !calibOff) {
      setScreen("calibration");        // 3 oyun ekranı da gizli kalır -> onFrame no-op
      MA.calib.boot(enterAttract);     // tarama bitince attract'a geç + overlay'i gizle
    } else {
      if (MA.calib) MA.calib.hide();
      enterAttract();                  // ekranı kur + buton merkezlerini cache'le
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
