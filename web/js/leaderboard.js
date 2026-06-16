/* leaderboard.js — isimsiz, yerel (localStorage) skor tablosu.
   Her tamamlanan tur bir kayıt olur; ana (attract) ekranda ilk 3 sergilenir.
   İsim girişi YOK — kayıtlar yalnızca {score, ts}. */
(function () {
  const MA = (window.MA = window.MA || {});
  const KEY = "mh.leaderboard.v1";
  const MAX = 20;            // saklanan kayıt (tabloda ilk 3 gösterilir)
  let _mem = [];             // localStorage yoksa (file://, gizli mod) bellek yedeği

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      const arr = raw ? JSON.parse(raw) : null;
      if (Array.isArray(arr)) {
        return arr.filter((e) => e && typeof e.score === "number")
                  .sort((a, b) => b.score - a.score);
      }
    } catch (_) { /* localStorage erişilemedi -> bellek yedeği */ }
    return _mem.slice().sort((a, b) => b.score - a.score);
  }

  function save(list) {
    _mem = list.slice();
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (_) {}
  }

  // Yeni skoru ekle; sıralamasını (1-tabanlı) + ilk-3 bilgisini döndür.
  // Eşitlikte yeni skor mevcut eşitlerin ALTINA girer (yeri almak için geçmek gerek).
  function add(score) {
    score = Math.max(0, Math.round(score));
    const list = load();
    let i = 0;
    while (i < list.length && list[i].score >= score) i++;
    list.splice(i, 0, { score: score, ts: Date.now() });
    save(list.slice(0, MAX));
    const rank = i + 1;
    return { rank: rank, score: score, top3: rank <= 3 && score > 0 };
  }

  function top(n) { return load().slice(0, n || 3); }

  // İlk 3'ü <ol> içine render et. highlightRank (1..3) verilirse o satırı vurgular.
  function render(listEl, highlightRank) {
    if (!listEl) return;
    const rows = top(3);
    const medals = ["🥇", "🥈", "🥉"];
    let html = "";
    for (let r = 0; r < 3; r++) {
      const e = rows[r];
      const hl = highlightRank && (r + 1) === highlightRank ? " flash" : "";
      const cls = "lb-row" + (r === 0 ? " gold" : "") + (e ? "" : " empty") + hl;
      const scoreTxt = e ? String(e.score) : "—";
      html += '<li class="' + cls + '">' +
                '<span class="lb-medal">' + medals[r] + '</span>' +
                '<span class="lb-rank">' + (r + 1) + '</span>' +
                '<span class="lb-score">' + scoreTxt + '</span>' +
              '</li>';
    }
    listEl.innerHTML = html;
  }

  function clear() { _mem = []; try { localStorage.removeItem(KEY); } catch (_) {} }

  MA.leaderboard = { load: load, add: add, top: top, render: render, clear: clear };
})();
