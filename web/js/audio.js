/* audio.js — yerel gerçek kayıtlar + doğru/yanlış geri bildirim sesleri.
   Tamamen çevrimdışıdır; ses hataları oyunu asla durdurmaz. */
(function () {
  const MA = (window.MA = window.MA || {});
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;

  let ctx = null, master = null, resumeJob = null;
  let feedback = null;
  let urgency = null;
  let calibration = null;

  // Saf osilatör yerine gerçek CC0 kayıtlar. Dosyalar modül yüklenirken okunmaya
  // başlar; AudioContext ilk açıldığında bir kez decode edilip tekrar kullanılır.
  const scriptURL = document.currentScript && document.currentScript.src;
  const webRoot = scriptURL ? new URL("../", scriptURL) : new URL("./", location.href);
  const ASSET_PATHS = {
    heartbeat: "audio/countdown-heartbeat.mp3?v=1",
    clock: "audio/countdown-clock.mp3?v=1",
    calibration: "audio/calibration-rise.mp3?v=1",
  };
  const assetBytes = {};
  const decodedAssets = {};
  const decodeJobs = {};

  for (const name of Object.keys(ASSET_PATHS)) {
    const url = new URL(ASSET_PATHS[name], webRoot).href;
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
        .then(function (buffer) {
          decodedAssets[name] = buffer;
          return buffer;
        })
        .catch(function () {
          decodedAssets[name] = null;
          return null;
        });
    }
    return decodeJobs[name];
  }

  function ensureContext() {
    if (!AudioContextClass) return null;
    try {
      if (!ctx) {
        ctx = new AudioContextClass({ latencyHint: "interactive" });
        master = ctx.createGain();
        // Laptop hoparlöründe de duyulacak, ama sergi ortamında rahatsız etmeyecek ana seviye.
        master.gain.value = 0.24;

        // Birkaç efekt çakıştığında ani yüksekliği yumuşatır.
        const limiter = ctx.createDynamicsCompressor();
        limiter.threshold.value = -18;
        limiter.knee.value = 12;
        limiter.ratio.value = 8;
        limiter.attack.value = 0.003;
        limiter.release.value = 0.18;
        master.connect(limiter);
        limiter.connect(ctx.destination);
        for (const name of Object.keys(ASSET_PATHS)) loadBuffer(name, ctx);
      }
      if (ctx.state === "suspended" && !resumeJob) {
        resumeJob = Promise.resolve(ctx.resume())
          .catch(function () {})
          .then(function () { resumeJob = null; });
      }
      // Askıdayken ses programlama: izin daha sonra açıldığında eski efektin
      // gecikmeli patlamasına neden olabilir. Yalnız gerçekten çalışıyorsa çal.
      return ctx.state === "running" ? ctx : null;
    } catch (_) {
      return null;
    }
  }

  function stopFeedback() {
    const active = feedback;
    feedback = null;
    if (!active || !ctx) return;
    try {
      const now = ctx.currentTime;
      active.bus.gain.cancelScheduledValues(now);
      active.bus.gain.setValueAtTime(1, now);
      active.bus.gain.exponentialRampToValueAtTime(0.0001, now + 0.035);
      for (const osc of active.oscillators) {
        try { osc.stop(now + 0.045); } catch (_) {}
      }
      clearTimeout(active.clearTimer);
      const bus = active.bus;
      setTimeout(function () { try { bus.disconnect(); } catch (_) {} }, 80);
    } catch (_) {}
  }

  function addTone(c, destination, note) {
    const start = c.currentTime + (note.delay || 0) + 0.008;
    const end = start + note.duration;
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = note.type || "triangle";
    osc.frequency.setValueAtTime(note.frequency, start);
    if (note.endFrequency) {
      osc.frequency.exponentialRampToValueAtTime(note.endFrequency, end);
    }
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(note.gain, start + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, end);
    osc.connect(gain);
    gain.connect(destination);
    osc.start(start);
    osc.stop(end + 0.025);
    return osc;
  }

  function playFeedback(notes) {
    const c = ensureContext();
    if (!c || !master) return;
    try {
      stopFeedback();
      const bus = c.createGain();
      bus.gain.value = 1;
      bus.connect(master);
      const oscillators = notes.map(note => addTone(c, bus, note));
      const totalMs = 1000 * Math.max.apply(null, notes.map(
        note => (note.delay || 0) + note.duration)) + 100;
      const active = { bus, oscillators, clearTimer: null };
      active.clearTimer = setTimeout(function () {
        try { bus.disconnect(); } catch (_) {}
        if (feedback === active) feedback = null;
      }, totalMs);
      feedback = active;
    } catch (_) {}
  }

  function correct() {
    playFeedback([
      { frequency: 523.25, delay: 0.00, duration: 0.16, gain: 0.16 },
      { frequency: 659.25, delay: 0.07, duration: 0.19, gain: 0.14 },
      { frequency: 783.99, delay: 0.14, duration: 0.24, gain: 0.12 },
    ]);
  }

  function wrong() {
    playFeedback([
      { frequency: 330, endFrequency: 247, delay: 0.00, duration: 0.22, gain: 0.14 },
      { frequency: 247, endFrequency: 196, delay: 0.10, duration: 0.24, gain: 0.11 },
    ]);
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

  function connectSample(context, active, buffer, gainValue) {
    const source = context.createBufferSource();
    const gain = context.createGain();
    source.buffer = buffer;
    gain.gain.value = gainValue;
    source.connect(gain);
    gain.connect(active.bus);
    active.sources.add(source);
    source.onended = function () {
      active.sources.delete(source);
      try { source.disconnect(); } catch (_) {}
      try { gain.disconnect(); } catch (_) {}
    };
    return { source, gain };
  }

  function maybeStartUrgency(active) {
    if (urgency !== active || active.loading || active.started || active.failed) return;
    const c = ensureContext();
    if (!c || !master) return;
    active.loading = true;

    Promise.all([loadBuffer("heartbeat", c), loadBuffer("clock", c)])
      .then(function (buffers) {
        active.loading = false;
        if (urgency !== active) return;
        // Decode sırasında sekme/context askıya alındıysa gecikmeli ses programlamadan çık.
        // Bir sonraki oyun karesi context gerçekten çalışınca tekrar dener.
        if (c !== ctx || c.state !== "running") return;
        const heartbeat = buffers[0], clock = buffers[1];
        if (!heartbeat && !clock) { active.failed = true; return; }

        const now = c.currentTime + 0.01;
        const elapsed = Math.max(0, Math.min(10, 10 - active.remaining));
        const remaining = Math.max(0.04, 10 - elapsed);
        const bus = c.createGain();
        bus.gain.setValueAtTime(0.0001, now);
        bus.gain.exponentialRampToValueAtTime(1, now + 0.045);
        bus.connect(master);
        active.bus = bus;
        active.started = true;

        if (heartbeat) {
          // Gerçek kayıt 10 saniyeye yayılır; kalp ritmi 0.74x'ten yaklaşık
          // 1.0x'e doğal biçimde hızlanır ve tam sayaç sonunda biter.
          const part = connectSample(c, active, heartbeat, 0.42 + 0.03 * elapsed);
          const endRate = Math.max(0.90, (2 * heartbeat.duration / 10) - 0.74);
          const rateSlope = (endRate - 0.74) / 10;
          const startRate = 0.74 + rateSlope * elapsed;
          const offset = 0.74 * elapsed + 0.5 * rateSlope * elapsed * elapsed;
          part.source.playbackRate.setValueAtTime(startRate, now);
          part.source.playbackRate.linearRampToValueAtTime(endRate, now + remaining);
          part.gain.gain.setValueAtTime(0.42 + 0.03 * elapsed, now);
          part.gain.gain.linearRampToValueAtTime(0.72, now + remaining);
          part.source.start(now, Math.min(offset, Math.max(0, heartbeat.duration - 0.02)));
          part.source.stop(now + remaining + 0.08);
        }

        if (clock) {
          // Gerçek duvar saati döngüsü altta kalır; sonlara doğru biraz hızlanıp
          // yükselir ama perde/ritim hâlâ fiziksel bir saat gibi duyulur.
          const part = connectSample(c, active, clock, 0.08 + 0.02 * elapsed);
          const startRate = 0.92 + 0.028 * elapsed;
          const offset = (0.92 * elapsed + 0.014 * elapsed * elapsed) % clock.duration;
          part.source.loop = true;
          part.source.loopStart = 0;
          part.source.loopEnd = clock.duration;
          part.source.playbackRate.setValueAtTime(startRate, now);
          part.source.playbackRate.linearRampToValueAtTime(1.20, now + remaining);
          part.gain.gain.setValueAtTime(0.08 + 0.02 * elapsed, now);
          part.gain.gain.linearRampToValueAtTime(0.28, now + remaining);
          part.source.start(now, offset);
          part.source.stop(now + remaining + 0.08);
        }
      })
      .catch(function () { active.loading = false; active.failed = true; });
  }

  function stopUrgency() {
    const active = urgency;
    urgency = null;
    if (!active) return;
    if (!ctx || !active.bus) return;
    try {
      const now = ctx.currentTime;
      holdParam(active.bus.gain, now, 0.0001);
      active.bus.gain.exponentialRampToValueAtTime(0.0001, now + 0.045);
      for (const source of active.sources) {
        try { source.stop(now + 0.055); } catch (_) {}
      }
      active.sources.clear();
      const bus = active.bus;
      setTimeout(function () { try { bus.disconnect(); } catch (_) {} }, 90);
    } catch (_) {}
  }

  // updateTimer bunu her kare çağırır: aktif döngü yeniden kurulmaz, yalnız süre güncellenir.
  function setUrgent(value) {
    const numeric = typeof value === "number" && Number.isFinite(value);
    const on = numeric ? value > 0 : !!value;
    if (!on) { stopUrgency(); return; }
    const remaining = numeric ? Math.max(0, value) : 10;
    if (urgency) {
      urgency.remaining = remaining;
      maybeStartUrgency(urgency);
      return;
    }
    const active = {
      remaining, loading: false, started: false, failed: false,
      bus: null, sources: new Set(),
    };
    urgency = active;
    maybeStartUrgency(active);
  }

  function calibrationStart(durationMs) {
    calibrationCancel();
    const active = {
      durationMs: Math.max(1000, Number(durationMs) || 2500),
      startedAt: performance.now(), loading: false, started: false,
      failed: false, completing: false, source: null, bus: null,
      cleanupTimer: null,
    };
    calibration = active;
    maybeStartCalibration(active);
  }

  function maybeStartCalibration(active) {
    if (calibration !== active || active.loading || active.started ||
        active.failed || active.completing) return;
    const c = ensureContext();
    if (!c || !master) return;
    active.loading = true;
    loadBuffer("calibration", c).then(function (buffer) {
      active.loading = false;
      if (calibration !== active || active.completing) return;
      if (c !== ctx || c.state !== "running") return;
      if (!buffer) { active.failed = true; return; }

      const elapsed = Math.max(0, (performance.now() - active.startedAt) / 1000);
      const total = active.durationMs / 1000 + 0.35;
      if (elapsed >= total) { active.failed = true; return; }
      try {
        const now = c.currentTime + 0.01;
        const rate = buffer.duration / total;
        const bus = c.createGain();
        const source = c.createBufferSource();
        bus.gain.setValueAtTime(0.0001, now);
        bus.gain.exponentialRampToValueAtTime(0.68, now + 0.04);
        source.buffer = buffer;
        source.playbackRate.value = rate;
        source.connect(bus);
        bus.connect(master);
        active.bus = bus;
        active.source = source;
        active.started = true;
        source.onended = function () {
          if (active.source === source) active.source = null;
          try { source.disconnect(); } catch (_) {}
          try { bus.disconnect(); } catch (_) {}
          if (calibration === active && active.completing) calibration = null;
        };
        source.start(now, Math.min(buffer.duration - 0.01, elapsed * rate));
      } catch (_) {
        active.failed = true;
      }
    }).catch(function () { active.loading = false; active.failed = true; });
  }

  // Kayıt kendi doğal yükselişini taşıyor; progress yalnız geç decode/resume için retry'dır.
  function calibrationProgress() {
    if (calibration) maybeStartCalibration(calibration);
  }

  function calibrationCancel() {
    const active = calibration;
    calibration = null;
    if (!active || !ctx || !active.source || !active.bus) return;
    clearTimeout(active.cleanupTimer);
    try {
      const now = ctx.currentTime;
      holdParam(active.bus.gain, now, 0.0001);
      active.bus.gain.exponentialRampToValueAtTime(0.0001, now + 0.06);
      try { active.source.stop(now + 0.07); } catch (_) {}
      const bus = active.bus;
      setTimeout(function () { try { bus.disconnect(); } catch (_) {} }, 100);
    } catch (_) {}
  }

  function calibrationComplete() {
    const active = calibration;
    if (!active || active.completing) return;
    active.completing = true;
    if (!ctx || !active.source || !active.bus) {
      calibration = null;
      return;
    }
    try {
      const now = ctx.currentTime;
      // Ayrı bir bitiş notası yok: gerçek yükseliş kaydının son 350 ms'lik kuyruğu
      // görsel %100'e ulaştıktan sonra akarak söner.
      holdParam(active.bus.gain, now, 0.0001);
      active.bus.gain.exponentialRampToValueAtTime(0.0001, now + 0.38);
      try { active.source.stop(now + 0.42); } catch (_) {}
      active.cleanupTimer = setTimeout(function () {
        try { active.bus.disconnect(); } catch (_) {}
        if (calibration === active) calibration = null;
      }, 480);
    } catch (_) {
      calibrationCancel();
    }
  }

  function stopAll() {
    stopUrgency();
    calibrationCancel();
    stopFeedback();
  }

  // Mouse/klavye testinde autoplay izni için yedek. Kamera kiosku ayrıca
  // launcher'daki autoplay-policy bayrağını kullanır.
  function unlock() { ensureContext(); }
  window.addEventListener("pointerdown", unlock, { capture: true });
  window.addEventListener("keydown", unlock, { capture: true });
  window.addEventListener("touchstart", unlock, { capture: true, passive: true });
  window.addEventListener("pagehide", stopAll);

  MA.audio = {
    unlock, correct, wrong, setUrgent,
    calibrationStart, calibrationProgress, calibrationComplete, calibrationCancel,
    stopFeedback, stopAll,
  };
})();
