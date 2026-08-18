/* audio.js — ElevenLabs ile üretilmiş ses paketi + sakin arka plan müziği.
   Tüm dosyalar web/audio/ altında yereldir (sergi makinesinde internet YOK).
   Yeniden üretmek/değiştirmek için: python tools\gen_audio.py

   Tasarım: hiçbir ses panik ya da ceza hissi vermez. Osilatörle üretilen eski
   "doğru/yanlış" tonları ve hızlanan kalp-atışı + duvar-saati geri sayımı
   kaldırıldı; yerine sabit tempolu, alçak, kesintisiz bir nabız geldi. Süre
   baskısı görsel olarak (#mh-timer.low) zaten veriliyor.

   Ses hataları oyunu ASLA durdurmaz: dosya eksikse/decode edilemezse ilgili
   çağrı sessizce hiçbir şey yapmaz. */
(function () {
  const MA = (window.MA = window.MA || {});
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;

  let ctx = null, master = null, sfxBus = null, musicBus = null, resumeJob = null;

  // ---- varlıklar ----
  const scriptURL = document.currentScript && document.currentScript.src;
  const webRoot = scriptURL ? new URL("../", scriptURL) : new URL("./", location.href);
  const V = "?v=2";  // dosyaları yenilediğinde artır (tarayıcı önbelleği)
  const ASSETS = {
    correct:      "audio/sfx-correct.mp3",
    wrong:        "audio/sfx-wrong.mp3",
    select:       "audio/sfx-select.mp3",
    hover:        "audio/sfx-hover.mp3",
    btnArm:       "audio/sfx-btn-arm.mp3",
    tick:         "audio/countdown-tick.mp3",
    go:           "audio/countdown-go.mp3",
    urgencyTick:  "audio/urgency-tick.mp3",
    urgencyEnter: "audio/urgency-enter.mp3",
    timeUp:       "audio/time-up.mp3",
    roundEnd:     "audio/round-end.mp3",
    scoreTick:    "audio/score-tick.mp3",
    celebrate:    "audio/celebrate-top3.mp3",
    calibScan:    "audio/calib-scan-loop.mp3",
    calibDone:    "audio/calib-complete.mp3",
    calibCancel:  "audio/calib-cancel.mp3",
    whoosh:       "audio/transition-whoosh.mp3",
    accent:       "audio/attract-accent.mp3",
    music:        "audio/ambient-loop.mp3",
  };

  // Sergi ortamına göre her sesin kendi seviyesi (0-1). Karışımı tek yerden
  // ayarlamak için: bir ses baskınsa yalnızca bu tabloyu değiştir.
  const LEVEL = {
    correct: 0.85, wrong: 0.70, select: 0.50, hover: 0.20, btnArm: 0.28,
    tick: 0.50, go: 0.80, urgencyTick: 0.55, urgencyEnter: 0.55, timeUp: 0.75,
    roundEnd: 0.80, scoreTick: 0.28, celebrate: 0.90, calibScan: 0.45,
    calibDone: 0.80, calibCancel: 0.40, whoosh: 0.32, accent: 0.38,
  };
  const MASTER_LEVEL = 0.24;   // laptop hoparlöründe duyulur, sergide rahatsız etmez
  const MUSIC_LEVEL = 0.30;    // müzik yatağı efektlerin altında kalır
  const MUSIC_DUCK = 0.45;     // son 10 sn / kutlama sırasında müziğe uygulanan çarpan

  // ---- kullanıcı ses ayarları (gizli S menüsü; web/js/settings.js) ----
  // Hepsi 0-MAX_VOL çarpandır: 1 = yukarıdaki tasarım seviyeleri, 2 = iki katı.
  // Tarayıcıda kalıcıdır; sergi makinesinde bir kez ayarlanır, her açılışta korunur.
  //
  // 1'in üstü kasıtlı olarak serbest: gürültülü salonda tasarım seviyesi yetmezse
  // yükseltilebilsin. Zincirin sonundaki limiter (bkz. ensureContext) kırpılmayı
  // engeller, ama uçlarda dinamikler sıkışır — bu bilinçli bir ödünleşme.
  const MAX_VOL = 2;
  const STORE_KEY = "ma.audio.v1";
  const vol = { master: 1, music: 1, sfx: 1, muted: false };

  // Efekt başına ayrı çarpan. Menüdeki sıra da budur; müzik burada YOK (kendi
  // kaydırıcısı var). Etiketler tek kaynaktan gelsin diye burada tutulur.
  const FX = [
    { key: "correct",      label: "Doğru cevap" },
    { key: "wrong",        label: "Yanlış cevap" },
    { key: "select",       label: "Seçim onayı" },
    { key: "hover",        label: "Token üzerinde" },
    { key: "btnArm",       label: "Buton hedefte" },
    { key: "tick",         label: "Geri sayım 3·2·1" },
    { key: "go",           label: "BAŞLA!" },
    { key: "urgencyEnter", label: "Son 10 sn girişi" },
    { key: "urgencyTick",  label: "Sayaç tik" },
    { key: "timeUp",       label: "Süre doldu" },
    { key: "roundEnd",     label: "Tur sonu" },
    { key: "scoreTick",    label: "Puan sayımı" },
    { key: "celebrate",    label: "İlk 3 kutlaması" },
    { key: "calibScan",    label: "Tarama (döngü)" },
    { key: "calibDone",    label: "Erişim sağlandı" },
    { key: "calibCancel",  label: "Tarama iptal" },
    { key: "whoosh",       label: "Ekran geçişi" },
    { key: "accent",       label: "Attract pingi" },
  ];
  const fxVol = {};
  for (const f of FX) fxVol[f.key] = 1;

  (function loadPrefs() {
    try {
      const p = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
      for (const k of ["master", "music", "sfx"]) {
        const n = Number(p[k]);
        if (Number.isFinite(n) && n >= 0 && n <= MAX_VOL) vol[k] = n;
      }
      vol.muted = !!p.muted;
      if (p.fx && typeof p.fx === "object") {
        for (const f of FX) {
          const n = Number(p.fx[f.key]);
          if (Number.isFinite(n) && n >= 0 && n <= MAX_VOL) fxVol[f.key] = n;
        }
      }
    } catch (_) {}
  })();

  function savePrefs() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({
        master: vol.master, music: vol.music, sfx: vol.sfx,
        muted: vol.muted, fx: fxVol,
      }));
    } catch (_) {}
  }

  // Bir efektin gerçek seviyesi: tasarım değeri × kullanıcı çarpanı.
  // play() ve döngüler bunun üzerinden gider, tek bir yerden.
  function fxLevel(name) {
    const base = LEVEL[name] != null ? LEVEL[name] : 0.5;
    const user = fxVol[name] != null ? fxVol[name] : 1;
    return base * user;
  }

  const assetBytes = {}, decodedAssets = {}, decodeJobs = {};

  for (const name of Object.keys(ASSETS)) {
    const url = new URL(ASSETS[name] + V, webRoot).href;
    assetBytes[name] = fetch(url, { cache: "force-cache" })
      .then(function (response) {
        if (!response.ok) throw new Error("Ses dosyası yüklenemedi: " + response.status);
        return response.arrayBuffer();
      })
      .catch(function () { return null; });
  }

  function loadBuffer(name, context) {
    if (Object.prototype.hasOwnProperty.call(decodedAssets, name)) {
      return Promise.resolve(decodedAssets[name]);
    }
    if (!decodeJobs[name]) {
      decodeJobs[name] = assetBytes[name]
        .then(function (bytes) {
          if (!bytes) return null;
          return context.decodeAudioData(bytes.slice(0));
        })
        .then(function (buffer) { decodedAssets[name] = buffer; return buffer; })
        .catch(function () { decodedAssets[name] = null; return null; });
    }
    return decodeJobs[name];
  }

  // ---- graf ----
  function ensureContext() {
    if (!AudioContextClass) return null;
    try {
      if (!ctx) {
        ctx = new AudioContextClass({ latencyHint: "interactive" });
        master = ctx.createGain();
        master.gain.value = MASTER_LEVEL * vol.master * (vol.muted ? 0 : 1);

        // Birkaç efekt çakıştığında ani yüksekliği yumuşatır.
        const limiter = ctx.createDynamicsCompressor();
        limiter.threshold.value = -18;
        limiter.knee.value = 12;
        limiter.ratio.value = 8;
        limiter.attack.value = 0.003;
        limiter.release.value = 0.18;

        sfxBus = ctx.createGain();
        sfxBus.gain.value = vol.sfx;
        musicBus = ctx.createGain();
        musicBus.gain.value = MUSIC_LEVEL * vol.music;

        sfxBus.connect(master);
        musicBus.connect(master);
        master.connect(limiter);
        limiter.connect(ctx.destination);

        for (const name of Object.keys(ASSETS)) loadBuffer(name, ctx);
      }
      if (ctx.state === "suspended" && !resumeJob) {
        resumeJob = Promise.resolve(ctx.resume())
          .catch(function () {})
          .then(function () { resumeJob = null; maybeStartMusic(); });
      }
      // Askıdayken ses programlamak, izin sonradan açıldığında eski efektin
      // gecikmeli patlamasına yol açar. Yalnız gerçekten çalışıyorsa çal.
      return ctx.state === "running" ? ctx : null;
    } catch (_) {
      return null;
    }
  }

  // ---- tek atışlık efekt ----
  // Aynı ses üst üste binebilir (hızlı seçimler); her çağrı kendi düğümünü kurar
  // ve bittiğinde kendini söker.
  function play(name, opts) {
    const c = ensureContext();
    if (!c || !sfxBus) return null;
    opts = opts || {};
    const buffer = decodedAssets[name];
    // Henüz decode edilmediyse: bu tetiklemeyi atla (gecikmeli patlama olmasın),
    // bir sonraki çağrı hazır bulacak.
    if (buffer === undefined) { loadBuffer(name, c); return null; }
    if (!buffer) return null;
    try {
      const now = c.currentTime + 0.005;
      const source = c.createBufferSource();
      const gain = c.createGain();
      source.buffer = buffer;
      source.playbackRate.value = opts.rate || 1;
      gain.gain.value = (opts.gain != null ? opts.gain : 1) * fxLevel(name);
      source.connect(gain);
      gain.connect(sfxBus);
      source.onended = function () {
        try { source.disconnect(); } catch (_) {}
        try { gain.disconnect(); } catch (_) {}
      };
      source.start(now);
      return { source, gain };
    } catch (_) {
      return null;
    }
  }

  // ---- döngü (urgency, kalibrasyon taraması, müzik) ----
  // Ortak yaşam döngüsü: yumuşak fade-in ile başlar, fade-out ile durur;
  // çift başlatmaya karşı korumalıdır.
  function startLoop(name, destination, level, fadeIn) {
    const c = ensureContext();
    if (!c || !destination) return null;
    const buffer = decodedAssets[name];
    if (!buffer) return null;
    try {
      const now = c.currentTime + 0.01;
      const source = c.createBufferSource();
      const gain = c.createGain();
      source.buffer = buffer;
      source.loop = true;
      source.loopStart = 0;
      source.loopEnd = buffer.duration;
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, level), now + (fadeIn || 0.35));
      source.connect(gain);
      gain.connect(destination);
      source.start(now);
      return { source, gain, ctx: c };
    } catch (_) {
      return null;
    }
  }

  function stopLoop(node, fadeOut) {
    if (!node || !ctx) return;
    try {
      const now = ctx.currentTime;
      const g = node.gain.gain;
      holdParam(g, now, 0.0001);
      const t = now + (fadeOut || 0.25);
      g.exponentialRampToValueAtTime(0.0001, t);
      try { node.source.stop(t + 0.02); } catch (_) {}
      setTimeout(function () {
        try { node.source.disconnect(); } catch (_) {}
        try { node.gain.disconnect(); } catch (_) {}
      }, ((fadeOut || 0.25) + 0.1) * 1000);
    } catch (_) {}
  }

  function holdParam(param, now, floor) {
    if (typeof param.cancelAndHoldAtTime === "function") {
      param.cancelAndHoldAtTime(now);
    } else {
      const value = Math.max(floor, Number(param.value) || floor);
      param.cancelScheduledValues(now);
      param.setValueAtTime(value, now);
    }
  }

  // ---- arka plan müziği ----
  // Autoplay izni yoksa context "running" olmaz; musicWanted bayrağı sayesinde
  // izin sonradan açıldığında (unlock/resume) müzik kendiliğinden başlar.
  let musicNode = null, musicWanted = false, ducked = 0;

  function maybeStartMusic() {
    if (!musicWanted || musicNode) return;
    const c = ensureContext();
    if (!c || !musicBus) return;
    if (decodedAssets.music === undefined) {
      loadBuffer("music", c).then(function () { maybeStartMusic(); });
      return;
    }
    if (!decodedAssets.music) return;   // dosya yok: sessiz geç
    musicNode = startLoop("music", musicBus, 1, 3.0);   // uzun fade: ani girmesin
  }

  function musicStart() { musicWanted = true; maybeStartMusic(); }

  function musicStop() {
    musicWanted = false;
    stopLoop(musicNode, 1.2);
    musicNode = null;
  }

  // Efekt duyulurken müziği kısar; ses seviyesini yükseltmeden netlik kazandırır.
  // Sayaç (ducked) sayesinde üst üste binen kısmalar birbirini bozmaz.
  function duck(on) {
    ducked = Math.max(0, ducked + (on ? 1 : -1));
    applyGains(ducked > 0 ? 0.5 : 1.2);
  }

  // Tasarım seviyeleri × kullanıcı ayarı × duck durumu -> canlı kazançlar.
  // Ses ayarı değişince de, duck değişince de tek yerden uygulanır.
  function rampTo(param, value, now, dur) {
    holdParam(param, now, 0.0001);
    param.linearRampToValueAtTime(Math.max(0, value), now + dur);
  }

  function applyGains(dur) {
    if (!ctx || !master || !sfxBus || !musicBus) return;
    const d = dur == null ? 0.08 : dur;
    try {
      const now = ctx.currentTime;
      rampTo(master.gain, MASTER_LEVEL * vol.master * (vol.muted ? 0 : 1), now, d);
      rampTo(sfxBus.gain, vol.sfx, now, d);
      rampTo(musicBus.gain, MUSIC_LEVEL * vol.music * (ducked > 0 ? MUSIC_DUCK : 1), now, d);
    } catch (_) {}
  }

  // ---- ses ayarı API'si (settings.js kullanır) ----
  function getVolumes() { return { master: vol.master, music: vol.music, sfx: vol.sfx, muted: vol.muted }; }

  function setVolume(which, value) {
    if (!Object.prototype.hasOwnProperty.call(vol, which) || which === "muted") return;
    const n = Number(value);
    if (!Number.isFinite(n)) return;
    vol[which] = Math.max(0, Math.min(MAX_VOL, n));
    ensureContext();
    applyGains(0.06);
    savePrefs();
  }

  function setMuted(on) {
    vol.muted = !!on;
    ensureContext();
    applyGains(0.06);
    savePrefs();
  }

  // Efekt başına ayar. Anında etki eder: bir sonraki tetiklemede yeni değer
  // kullanılır (kazanç play() içinde okunur, önceden hesaplanmaz).
  function getEffects() {
    return FX.map(function (f) { return { key: f.key, label: f.label, vol: fxVol[f.key] }; });
  }

  function setEffectVolume(key, value) {
    if (!Object.prototype.hasOwnProperty.call(fxVol, key)) return;
    const n = Number(value);
    if (!Number.isFinite(n)) return;
    fxVol[key] = Math.max(0, Math.min(MAX_VOL, n));
    savePrefs();
  }

  function resetVolumes() {
    vol.master = 1; vol.music = 1; vol.sfx = 1; vol.muted = false;
    for (const f of FX) fxVol[f.key] = 1;
    ensureContext();
    applyGains(0.06);
    savePrefs();
  }

  // Sergi öncesi "her şey yerinde mi" kontrolü + ayar menüsündeki test düğmeleri.
  function preview(name) { ensureContext(); play(name); }

  // ---- oyun sesleri ----
  function correct() { play("correct"); }
  function wrong() { play("wrong"); }
  function select() { play("select"); }
  function countdownTick() { play("tick"); }
  function countdownGo() { play("go"); }
  function timeUp() { play("timeUp"); }
  function roundEnd() { play("roundEnd"); }
  function celebrate() { play("celebrate"); }
  function transition() { play("whoosh"); }
  function attractAccent() { play("accent"); }

  // Hover/arm her karede tetiklenebilir: kısa aralıkla sınırla, yoksa uğultuya döner.
  function throttled(fn, ms) {
    let last = 0;
    return function () {
      const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
      if (now - last < ms) return;
      last = now;
      fn();
    };
  }
  const hover = throttled(function () { play("hover"); }, 110);
  const btnArm = throttled(function () { play("btnArm"); }, 400);
  const scoreTick = throttled(function () { play("scoreTick"); }, 70);

  // ---- son 10 saniye ----
  // Sürekli bir bas yatağı YOK: ekrandaki sayaç her saniye değiştiğinde tek bir
  // temiz tik çalar. Böylece duyulan şey görülenle birebir aynı ritimde olur ve
  // gerginlik hızlanmadan, ses seviyesi yükselmeden kurulur.
  //
  // game.js updateTimer() bunu HER KARE çağırır (~60 Hz); tik yalnızca tam
  // saniye değiştiğinde çıkar. Sayaç ekranda Math.ceil ile yazıldığı için burada
  // da Math.ceil kullanılır -> rakam ile ses aynı karede değişir.
  let urgency = null;

  function setUrgent(value) {
    const numeric = typeof value === "number" && Number.isFinite(value);
    const on = numeric ? value > 0 : !!value;
    if (!on) { stopUrgency(); return; }
    const remaining = numeric ? value : 10;
    const sec = Math.ceil(remaining);

    if (!urgency) {
      // Eşiğe giriş: yumuşak uyarı tonu 10. saniyeyi işaretler, tikler 9'dan başlar.
      urgency = { lastSec: sec };
      play("urgencyEnter");
      duck(true);
      return;
    }
    if (sec === urgency.lastSec || sec <= 0) return;
    urgency.lastSec = sec;
    // Son 3 saniye: aynı örnek biraz daha belirgin ve bir tık tiz. Yeni dosya
    // gerekmeden hafif bir sıkışma hissi verir; tempo yine değişmez.
    const last3 = sec <= 3;
    play("urgencyTick", { gain: last3 ? 1.3 : 1, rate: last3 ? 1.06 : 1 });
  }

  function stopUrgency() {
    if (!urgency) return;
    urgency = null;
    duck(false);
  }

  // ---- kalibrasyon ----
  let calibration = null;

  function calibrationStart() {
    calibrationCancel(true);
    calibration = { node: null, tries: 0, done: false };
    beginCalibration();
  }

  function beginCalibration() {
    const active = calibration;
    if (!active || active.node || active.done) return;
    const c = ensureContext();
    if (!c) {
      if (active.tries++ < 30) setTimeout(function () { if (calibration === active) beginCalibration(); }, 100);
      return;
    }
    if (decodedAssets.calibScan === undefined) {
      loadBuffer("calibScan", c).then(function () { if (calibration === active) beginCalibration(); });
      return;
    }
    if (!decodedAssets.calibScan) return;
    active.node = startLoop("calibScan", sfxBus, fxLevel("calibScan") * 0.6, 0.25);
  }

  // calibration.js her karede eased ilerlemeyi (0-1) yollar: tarama sesi
  // ilerledikçe hafifçe açılır. Geç decode/resume için ayrıca retry görevi görür.
  function calibrationProgress(e) {
    if (!calibration) return;
    if (!calibration.node) { beginCalibration(); return; }
    if (!ctx) return;
    const p = Math.max(0, Math.min(1, Number(e) || 0));
    try {
      const now = ctx.currentTime;
      holdParam(calibration.node.gain.gain, now, 0.0001);
      calibration.node.gain.gain.linearRampToValueAtTime(
        fxLevel("calibScan") * (0.6 + 0.4 * p), now + 0.12);
    } catch (_) {}
  }

  function calibrationComplete() {
    const active = calibration;
    calibration = null;
    if (active) { active.done = true; stopLoop(active.node, 0.18); }
    play("calibDone");
  }

  function calibrationCancel(silent) {
    const active = calibration;
    calibration = null;
    if (!active) return;
    active.done = true;
    stopLoop(active.node, 0.2);
    if (!silent) play("calibCancel");
  }

  function stopAll() {
    stopUrgency();
    calibrationCancel(true);
  }

  // Mouse/klavye testinde autoplay izni için yedek. Kamera kiosku ayrıca
  // launcher'daki autoplay-policy bayrağını kullanır.
  function unlock() { ensureContext(); maybeStartMusic(); }
  window.addEventListener("pointerdown", unlock, { capture: true });
  window.addEventListener("keydown", unlock, { capture: true });
  window.addEventListener("touchstart", unlock, { capture: true, passive: true });
  window.addEventListener("pagehide", function () { stopAll(); musicStop(); });

  MA.audio = {
    unlock, correct, wrong, select, hover, btnArm,
    countdownTick, countdownGo, setUrgent, timeUp, roundEnd, scoreTick,
    celebrate, transition, attractAccent,
    calibrationStart, calibrationProgress, calibrationComplete, calibrationCancel,
    musicStart, musicStop, duck,
    getVolumes, setVolume, setMuted, preview,
    getEffects, setEffectVolume, resetVolumes,
    getMaxVolume: function () { return MAX_VOL; },   // menü kaydırıcı tavanını buradan alır
    // Geriye dönük ad: eski çağrı yerleri kırılmasın.
    stopFeedback: function () {},
    stopAll,
  };
})();
