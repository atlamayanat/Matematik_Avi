/* settings.js — gizli ses ayarı menüsü (operatör için).
   Klavyeden S ile açılır/kapanır. Ekranda hiçbir ipucu yoktur: ziyaretçi
   görmesin, sergi görüntüsü bozulmasın diye bilinçli olarak gizlidir.

   Değerler audio.js'te localStorage'a yazılır -> sergi makinesinde bir kez
   ayarlanır, her açılışta korunur.

   Kendi kendine yeter: kendi <style>'ını enjekte eder, styles.css'e dokunmaz. */
(function () {
  const MA = (window.MA = window.MA || {});

  let panel = null, open = false;

  function audio() { return MA.audio || null; }

  // Kaydırıcı tavanı audio.js'in MAX_VOL'ünden gelir (tek doğruluk kaynağı):
  // orada değişirse menü kendiliğinden uyar.
  function maxPct() {
    const a = audio();
    const m = a && typeof a.getMaxVolume === "function" ? a.getMaxVolume() : 1;
    return Math.round((Number(m) || 1) * 100);
  }

  // ---- stil ----
  function injectStyle() {
    if (document.getElementById("ma-set-style")) return;
    const st = document.createElement("style");
    st.id = "ma-set-style";
    st.textContent = `
#ma-set{position:fixed;right:22px;bottom:22px;z-index:99998;width:388px;
  max-height:calc(100vh - 44px);overflow-y:auto;
  font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12.5px;color:#eaf6ff;
  background:linear-gradient(180deg,rgba(14,20,46,.97),rgba(7,9,24,.97));
  border:1px solid rgba(125,243,255,.42);border-radius:12px;padding:15px 16px 13px;
  box-shadow:0 0 0 1px rgba(0,0,0,.5),0 18px 48px rgba(0,0,0,.62),
    inset 0 0 34px rgba(0,235,255,.07);
  opacity:0;transform:translateY(10px);pointer-events:none;
  transition:opacity .18s ease,transform .18s cubic-bezier(.2,.9,.25,1)}
#ma-set.show{opacity:1;transform:translateY(0);pointer-events:auto}
#ma-set h3{margin:0 0 12px;font-size:11.5px;letter-spacing:.26em;color:#7df3ff;
  font-weight:700;display:flex;justify-content:space-between;align-items:center}
#ma-set h3 kbd{font:inherit;letter-spacing:0;color:#7f8db8;border:1px solid rgba(125,243,255,.3);
  border-radius:4px;padding:1px 6px;font-size:10.5px}
#ma-set .row{display:flex;align-items:center;gap:10px;margin-bottom:9px}
#ma-set .row label{width:74px;color:#b7cbe8;flex:none}
#ma-set .row output{width:38px;text-align:right;color:#7df3ff;flex:none;font-variant-numeric:tabular-nums}
#ma-set input[type=range]{flex:1;-webkit-appearance:none;appearance:none;height:4px;
  border-radius:3px;background-color:rgba(125,243,255,.19);outline:none;cursor:pointer;margin:0;
  /* --unity: %100'ün (tasarım seviyesi) izdüşümü; üstü "yükseltilmiş" bölgedir */
  background-image:linear-gradient(90deg,transparent calc(var(--unity,100%) - 1px),
    rgba(255,200,61,.6) calc(var(--unity,100%) - 1px),
    rgba(255,200,61,.6) var(--unity,100%),transparent var(--unity,100%));
  background-repeat:no-repeat}
#ma-set input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;
  border-radius:50%;background:#00EBFF;box-shadow:0 0 10px rgba(0,235,255,.85);cursor:pointer;border:0}
#ma-set input[type=range]::-moz-range-thumb{width:14px;height:14px;border:0;border-radius:50%;
  background:#00EBFF;box-shadow:0 0 10px rgba(0,235,255,.85);cursor:pointer}
#ma-set input[type=range]:focus-visible{box-shadow:0 0 0 2px rgba(0,235,255,.45)}
#ma-set .mute{display:flex;align-items:center;gap:8px;margin:12px 0 11px;cursor:pointer;
  color:#b7cbe8;user-select:none;width:max-content}
#ma-set .mute input{accent-color:#00EBFF;width:14px;height:14px;cursor:pointer;margin:0}
#ma-set .sep{height:1px;background:rgba(125,243,255,.16);margin:11px 0}
#ma-set .lab{font-size:10.5px;letter-spacing:.16em;color:#7f8db8;margin-bottom:7px}
#ma-set .btns{display:flex;flex-wrap:wrap;gap:6px}
#ma-set button{font:inherit;font-size:11px;padding:6px 10px;border-radius:6px;cursor:pointer;
  background:rgba(0,235,255,.09);border:1px solid rgba(125,243,255,.34);color:#cfeaff;
  transition:background .14s,border-color .14s}
#ma-set button:hover{background:rgba(0,235,255,.2);border-color:#00EBFF}
#ma-set button.wide{flex:1}
#ma-set .foot{margin-top:11px;font-size:10.5px;color:#66739a;line-height:1.5}
#ma-set details{margin-top:2px}
#ma-set summary{cursor:pointer;list-style:none;font-size:10.5px;letter-spacing:.16em;
  color:#7f8db8;padding:5px 0;user-select:none;display:flex;align-items:center;gap:7px}
#ma-set summary::-webkit-details-marker{display:none}
#ma-set summary::before{content:"▸";color:#7df3ff;font-size:11px;transition:transform .15s}
#ma-set details[open] summary::before{transform:rotate(90deg)}
#ma-set summary:hover{color:#b7cbe8}
#ma-set .fxlist{max-height:238px;overflow-y:auto;padding:4px 6px 2px 0;margin-top:4px;
  border-top:1px solid rgba(125,243,255,.12)}
#ma-set .fxlist::-webkit-scrollbar{width:7px}
#ma-set .fxlist::-webkit-scrollbar-thumb{background:rgba(125,243,255,.28);border-radius:4px}
#ma-set .fxlist::-webkit-scrollbar-track{background:transparent}
#ma-set .fx{display:flex;align-items:center;gap:7px;margin:6px 0}
#ma-set .fx span.n{flex:1;min-width:0;color:#b7cbe8;font-size:11px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#ma-set .fx input[type=range]{flex:none;width:96px}
#ma-set .fx output{width:34px;text-align:right;color:#7df3ff;flex:none;font-size:11px;
  font-variant-numeric:tabular-nums}
#ma-set .fx button{flex:none;padding:3px 7px;font-size:10px;line-height:1.2}
#ma-set .fx.off span.n,#ma-set .fx.off output{color:#5a6484}
/* tasarım seviyesinin (%100) üstü: turuncu -> operatör yükselttiğini görsün */
#ma-set output.hot{color:#FFC83D}
#ma-set .row output,#ma-set .fx output{width:40px}
@media (prefers-reduced-motion:reduce){#ma-set{transition:none}}`;
    document.head.appendChild(st);
  }

  // ---- panel ----
  const SLIDERS = [
    { key: "master", label: "Ana ses" },
    { key: "music",  label: "Müzik" },
    { key: "sfx",    label: "Efektler" },
  ];
  // Efekt listesi audio.js'ten gelir (tek doğruluk kaynağı: anahtarlar ve
  // Türkçe etiketler orada, burada yalnız çizilir).
  function effects() {
    const a = audio();
    return (a && typeof a.getEffects === "function") ? a.getEffects() : [];
  }

  // HTML'e gömülen etiketler için; liste kod içinden gelse de kaçırmak doğrusu.
  function esc(s) {
    return String(s).replace(/[&<>"]/g, c =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function build() {
    injectStyle();
    panel = document.createElement("div");
    panel.id = "ma-set";

    const MAX = maxPct();

    const fxRows = effects().map(f =>
      `<div class="fx" data-key="${esc(f.key)}">` +
      `<span class="n" title="${esc(f.label)}">${esc(f.label)}</span>` +
      `<input type="range" min="0" max="${MAX}" step="5" aria-label="${esc(f.label)}">` +
      `<output>—</output><button data-fn="${esc(f.key)}" title="Dinle">▶</button></div>`
    ).join("");

    panel.innerHTML =
      "<h3>SES AYARLARI<kbd>S</kbd></h3>" +
      SLIDERS.map(s =>
        `<div class="row"><label for="ma-set-${s.key}">${s.label}</label>` +
        `<input type="range" id="ma-set-${s.key}" min="0" max="${MAX}" step="5">` +
        `<output id="ma-set-${s.key}-o">—</output></div>`).join("") +
      '<label class="mute"><input type="checkbox" id="ma-set-mute">Sessiz</label>' +
      '<div class="sep"></div>' +
      '<details id="ma-set-fx"><summary>EFEKTLER — TEK TEK</summary>' +
      `<div class="fxlist">${fxRows}</div></details>` +
      '<div class="sep"></div><div class="btns">' +
      '<button class="wide" id="ma-set-reset">Varsayılana dön</button>' +
      '<button class="wide" id="ma-set-close">Kapat</button></div>' +
      `<div class="foot">▶ ile dinleyerek ayarla. “Efektler” kaydırıcısı hepsini ` +
      `birlikte, alttaki liste tek tek kısar. %100 tasarım seviyesidir; ` +
      `%${MAX}'e kadar yükseltilebilir (turuncu değerler tasarımın üstünde — ` +
      `uçlarda ses sıkışabilir). Ayarlar bu tarayıcıda saklanır; menü açıkken ` +
      `el/fare girdisi oyuna geçmez.</div>`;
    // Tasarım seviyesi (%100) kaydırıcının neresine düşüyor: iz çizgisi buradan.
    panel.style.setProperty("--unity", (100 / MAX * 100).toFixed(1) + "%");
    document.body.appendChild(panel);

    // Efekt satırları: kaydırıcı anında uygulanır, ▶ o efekti yeni seviyesiyle çalar.
    panel.querySelectorAll(".fx").forEach(row => {
      const key = row.dataset.key;
      const el = row.querySelector("input[type=range]");
      el.addEventListener("input", () => {
        const a = audio();
        if (a) a.setEffectVolume(key, Number(el.value) / 100);
        paintFxRow(row);
      });
      // Kaydırıcıyı bırakınca otomatik dinlet: ayarlarken her seferinde ▶'ye
      // basmak gerekmesin (döngü sesi hariç; o tek atış olarak anlamsız).
      if (key !== "calibScan") {
        el.addEventListener("change", () => { const a = audio(); if (a) a.preview(key); });
      }
    });

    // Menü açıkken paneldeki tıklamalar oyuna SIZMAZ: input.js window üzerinde
    // dinlediği için burada baloncuğu kesmek "yumruk" sayılmasını engeller.
    for (const type of ["pointerdown", "pointerup", "mousedown", "mouseup", "click"]) {
      panel.addEventListener(type, e => e.stopPropagation());
    }

    for (const s of SLIDERS) {
      const el = panel.querySelector("#ma-set-" + s.key);
      el.addEventListener("input", () => {
        const v = Number(el.value) / 100;
        if (audio()) audio().setVolume(s.key, v);
        paint();
      });
    }
    panel.querySelector("#ma-set-mute").addEventListener("change", e => {
      if (audio()) audio().setMuted(e.target.checked);
      paint();
    });
    panel.querySelectorAll("button[data-fn]").forEach(b => {
      b.addEventListener("click", () => {
        const a = audio();
        if (a && typeof a.preview === "function") a.preview(b.dataset.fn);
      });
    });
    panel.querySelector("#ma-set-reset").addEventListener("click", () => {
      const a = audio();
      if (!a) return;
      a.resetVolumes();          // efekt başına ayarları da 100'e döndürür
      paint();
    });
    panel.querySelector("#ma-set-close").addEventListener("click", () => setOpen(false));
  }

  // Panelin göstergelerini audio.js'teki gerçek değerlerden tazeler (tek doğruluk
  // kaynağı orasıdır; menü yalnızca bir görünümdür).
  function paint() {
    if (!panel) return;
    const a = audio();
    const v = a && typeof a.getVolumes === "function"
      ? a.getVolumes() : { master: 1, music: 1, sfx: 1, muted: false };
    for (const s of SLIDERS) {
      const pct = Math.round((v[s.key] != null ? v[s.key] : 1) * 100);
      const out = panel.querySelector("#ma-set-" + s.key + "-o");
      panel.querySelector("#ma-set-" + s.key).value = String(pct);
      out.textContent = pct + "%";
      out.classList.toggle("hot", pct > 100);
    }
    panel.querySelector("#ma-set-mute").checked = !!v.muted;

    const cur = {};
    for (const f of effects()) cur[f.key] = f.vol;
    panel.querySelectorAll(".fx").forEach(row => {
      const val = cur[row.dataset.key];
      row.querySelector("input[type=range]").value =
        String(Math.round((val != null ? val : 1) * 100));
      paintFxRow(row);
    });
  }

  // Tek satırın yüzdesi + "kapalı" görünümü. Kaydırıcı çekilirken her karede
  // çağrıldığı için audio.js'e gitmez, doğrudan input değerini okur.
  function paintFxRow(row) {
    const pct = Number(row.querySelector("input[type=range]").value);
    const out = row.querySelector("output");
    out.textContent = pct + "%";
    out.classList.toggle("hot", pct > 100);
    row.classList.toggle("off", pct === 0);
  }

  function setOpen(on) {
    if (!panel) build();
    open = !!on;
    panel.classList.toggle("show", open);
    if (open) {
      paint();
      if (MA.telemetry) MA.telemetry.log("settings_open", {});
    } else if (document.activeElement && panel.contains(document.activeElement)) {
      document.activeElement.blur();   // odak panelde kalmasın (ok tuşları oyuna dönsün)
    }
  }

  // S: aç/kapat. Escape kioskı kapattığı için (game.js) bilinçli olarak
  // kapatma tuşu yapılmadı.
  window.addEventListener("keydown", function (e) {
    if (e.key !== "s" && e.key !== "S") return;
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    e.preventDefault();
    setOpen(!open);
  });

  MA.settings = { isOpen: function () { return open; }, setOpen: setOpen };
})();
