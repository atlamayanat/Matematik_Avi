# -*- coding: utf-8 -*-
"""rapor.py — Matematik Avı festival/sergi telemetri raporu.

Girdi:
  data/telemetry/events_*.jsonl   (oyun olayları; web/js/telemetry.js üretir)
  logs/detector_*.out.log         (dedektör [stats] satırları + hata kayıtları)

Çıktı:
  data/rapor.html                 (kendi başına açılan, çevrimdışı Türkçe rapor)
  + konsola kısa özet

Kullanım:  python tools\\rapor.py            (kök Rapor.bat bunu çağırır)
           python tools\\rapor.py --out baska\\yer.html

Sadece stdlib; internet/paket gerektirmez.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "telemetry"
LOG_DIR = ROOT / "logs"

# ---------------------------------------------------------------- veri okuma

def load_events():
    """Tüm events_*.jsonl dosyalarını oku; bozuk satırları say, atla.

    Aynı olay iki kez teslim edilmiş olabilir (fetch sürerken sayfa gizlenince
    beacon aynı olayları yeniden gönderebilir) -> (sid, seq) ile tekilleştir.
    """
    events, bad, seen = [], 0, set()
    for path in sorted(DATA_DIR.glob("events_*.jsonl")):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        if not isinstance(ev, dict):
                            bad += 1
                            continue
                        key = (ev.get("sid"), ev.get("seq"))
                        if key[0] is not None and key[1] is not None:
                            if key in seen:
                                continue
                            seen.add(key)
                        events.append(ev)
                    except ValueError:
                        bad += 1
        except OSError:
            continue
    events.sort(key=lambda e: e.get("t") or (e.get("srv_t", 0) * 1000))
    return events, bad


def ev_dt(ev):
    """Olayın yerel zamanı (istemci saati; yoksa sunucu saati)."""
    t = ev.get("t")
    if isinstance(t, (int, float)) and t > 1e12:
        return datetime.fromtimestamp(t / 1000.0)
    st = ev.get("srv_t")
    if isinstance(st, (int, float)) and st > 1e9:
        return datetime.fromtimestamp(st)
    return None


# ---------------------------------------------------------- soru sınıflaması

def kategori(prompt):
    """Soru metninden konu kategorisi (rapor 'nerede zorlanıyorlar' bölümü)."""
    p = str(prompt)
    if "x" in p and "=" in p:
        return "Denklem (x'i bul)"
    if "!" in p:
        return "Faktöriyel"
    if "√" in p:
        return "Karekök"
    if "(" in p:
        return "İşlem önceliği (parantezli)"
    if "+" in p and "×" in p:
        return "İşlem önceliği (çarpma+toplama)"
    if "²" in p or "³" in p:
        return "Üs (kare/küp)"
    if any(f in p for f in ("½", "¼", "¾")):
        return "Kesir"
    if "×" in p:
        return "Çarpma"
    if "÷" in p:
        return "Bölme"
    if "−" in p or "-" in p:
        return "Çıkarma"
    if "+" in p:
        return "Toplama"
    return "Diğer"


# ------------------------------------------------------------- log tarayıcı

STATS_RE = re.compile(
    r"\[stats\] fps=([\d.]+) results=(\d+) hands_pct=(\d+) "
    r"locked_pct=(\d+) cam_fail=(\d+)")


def scan_detector_logs():
    """detector_*.out.log: [stats] satırları + beklenmedik hata sayısı."""
    out = {"stats": [], "crashes": 0, "files": 0}
    if not LOG_DIR.exists():
        return out
    for path in sorted(LOG_DIR.glob("detector_*.out.log")):
        out["files"] += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out["crashes"] += text.count("BEKLENMEDIK HATA")
        for m in STATS_RE.finditer(text):
            out["stats"].append({
                "fps": float(m.group(1)), "results": int(m.group(2)),
                "hands_pct": int(m.group(3)), "locked_pct": int(m.group(4)),
                "cam_fail": int(m.group(5)),
            })
    return out


# ---------------------------------------------------------------- analizler

def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def analyze(events):
    A = {}

    # Fare/test oturumlarını ayıkla: app_start.mode oturumun (sid) girdi modunu
    # söyler. Gerçek (ws) veri varsa fare oturumları rapora karışmasın — görevlinin
    # tarayıcıda yaptığı deneme oyunu ziyaretçi sayılmasın. Hiç ws verisi yoksa
    # (ev testleri) her şey kullanılır.
    sid_mode = {}
    for ev in events:
        if ev.get("type") == "app_start":
            sid_mode[ev.get("sid")] = ev.get("mode", "?")
    ws_sids = {s for s, m in sid_mode.items() if m == "ws"}
    excluded = 0
    if ws_sids:
        kept = []
        for ev in events:
            m = sid_mode.get(ev.get("sid"))
            if m is not None and m != "ws":
                excluded += 1
            else:
                kept.append(ev)   # ws + app_start'ı kaybolmuş (bilinmeyen) oturumlar kalır
        events = kept
    A["excluded_test"] = excluded

    by_type = defaultdict(list)
    for ev in events:
        by_type[ev.get("type", "?")].append(ev)

    # --- huni (ziyaretçi akışı) ---
    # carry=true: kalibrasyon açıldığında önceki oyuncunun eli hâlâ kadrajdaydı;
    # yeni "yaklaşan ziyaretçi" değildir, sayılmaz.
    resets = by_type.get("reset", [])
    A["funnel"] = {
        "app_start": len(by_type.get("app_start", [])),
        "calib_enter": len(by_type.get("calib_enter", [])),
        "hand_seen": sum(1 for e in by_type.get("calib_hand_seen", []) if not e.get("carry")),
        "scan_start": len(by_type.get("calib_scan_start", [])),
        "calib_done": len(by_type.get("calib_done", [])),
        "game_start": len(by_type.get("game_start", [])),
        "round_end": len(by_type.get("round_end", [])),
        "reset_mid": sum(1 for e in resets if e.get("running")),
        "reset_all": len(resets),
    }

    # --- cevap analizi ---
    answers = by_type.get("answer", [])
    A["ans_total"] = len(answers)
    A["ans_ok"] = sum(1 for a in answers if a.get("ok"))
    ms_ok = [a["ms"] for a in answers if a.get("ok") and isinstance(a.get("ms"), (int, float))]
    ms_bad = [a["ms"] for a in answers if not a.get("ok") and isinstance(a.get("ms"), (int, float))]
    A["ms_ok"] = sum(ms_ok) / len(ms_ok) / 1000 if ms_ok else 0
    A["ms_bad"] = sum(ms_bad) / len(ms_bad) / 1000 if ms_bad else 0

    diff = {}
    for d in ("kolay", "orta", "zor"):
        da = [a for a in answers if a.get("diff") == d]
        ok = sum(1 for a in da if a.get("ok"))
        ms = [a["ms"] for a in da if isinstance(a.get("ms"), (int, float))]
        diff[d] = {"n": len(da), "ok": ok, "pct": pct(ok, len(da)),
                   "avg_s": (sum(ms) / len(ms) / 1000) if ms else 0}
    A["diff"] = diff

    # kategori bazında doğruluk
    cats = defaultdict(lambda: {"n": 0, "ok": 0, "ms": []})
    for a in answers:
        c = cats[kategori(a.get("prompt", "?"))]
        c["n"] += 1
        c["ok"] += 1 if a.get("ok") else 0
        if isinstance(a.get("ms"), (int, float)):
            c["ms"].append(a["ms"])
    A["cats"] = sorted(
        ({"ad": k, "n": v["n"], "pct": pct(v["ok"], v["n"]),
          "avg_s": (sum(v["ms"]) / len(v["ms"]) / 1000) if v["ms"] else 0}
         for k, v in cats.items() if v["n"] > 0),
        key=lambda r: r["pct"])

    # soru bazında en çok yanlış (en az 2 deneme)
    per_q = defaultdict(lambda: {"n": 0, "wrong": 0, "picks": Counter()})
    for a in answers:
        q = per_q[a.get("prompt", "?")]
        q["n"] += 1
        if not a.get("ok"):
            q["wrong"] += 1
            q["picks"][str(a.get("picked", "?"))] += 1
    worst = [{"prompt": p, "n": v["n"], "wrong": v["wrong"],
              "pct": pct(v["wrong"], v["n"]),
              "picks": ", ".join(f"{w}({c}×)" for w, c in v["picks"].most_common(3))}
             for p, v in per_q.items() if v["wrong"] > 0]
    worst.sort(key=lambda r: (r["wrong"], r["pct"]), reverse=True)
    A["worst_q"] = worst[:15]

    # --- tur (oyun) analizi ---
    rounds = by_type.get("round_end", [])
    A["rounds"] = rounds
    if rounds:
        A["avg_score"] = sum(r.get("score", 0) for r in rounds) / len(rounds)
        A["max_score"] = max(r.get("score", 0) for r in rounds)
        A["avg_correct"] = sum(r.get("correct", 0) for r in rounds) / len(rounds)
        A["avg_seen"] = sum(r.get("seen", 0) for r in rounds) / len(rounds)
    lost_rounds = [r for r in rounds if r.get("lost_n", 0) > 0]
    A["lost_rounds"] = len(lost_rounds)
    A["lost_total_s"] = sum(r.get("lost_s", 0) for r in rounds)

    # sorularda takılma: soru gösterildi ama cevaplanmadan tur bitti/reset oldu
    q_shown = len(by_type.get("question", []))
    A["q_shown"] = q_shown
    A["q_unanswered"] = max(0, q_shown - len(answers))

    # --- günlük / saatlik dağılım ---
    daily = defaultdict(lambda: {"hand": 0, "start": 0, "end": 0, "ans": 0, "ok": 0})
    hourly = Counter()
    for ev in events:
        dt = ev_dt(ev)
        if not dt:
            continue
        day = dt.strftime("%Y-%m-%d")
        typ = ev.get("type")
        if typ == "calib_hand_seen":
            daily[day]["hand"] += 1
        elif typ == "game_start":
            daily[day]["start"] += 1
            hourly[dt.hour] += 1
        elif typ == "round_end":
            daily[day]["end"] += 1
        elif typ == "answer":
            daily[day]["ans"] += 1
            daily[day]["ok"] += 1 if ev.get("ok") else 0
    A["daily"] = dict(sorted(daily.items()))
    A["hourly"] = hourly

    # --- teknik sağlık ---
    # Her sayfa açılışı bir kez boot->disconnected("BAĞLANIYOR") geçişi loglar;
    # bu gerçek kopma DEĞİLDİR. Kopma sayısı prev=="boot" olanları atlar; kesinti
    # süresi de açılış bağlanmasını değil, canlıyken yaşanan kopuşları toplar.
    conns = by_type.get("conn", [])
    A["conn_stale"] = sum(1 for c in conns if c.get("state") == "stale")
    A["conn_drop"] = sum(1 for c in conns
                         if c.get("state") == "disconnected" and c.get("prev") != "boot")
    outage = 0.0
    last_bad_prev = {}   # sid -> son stale/disconnected olayının 'prev' alanı
    for c in conns:      # olaylar zaman sıralı
        sid, stt = c.get("sid"), c.get("state")
        if stt in ("stale", "disconnected"):
            if last_bad_prev.get(sid) is None:
                last_bad_prev[sid] = c.get("prev")
        elif stt == "live" and c.get("prev") in ("stale", "disconnected"):
            if last_bad_prev.get(sid) != "boot":
                outage += c.get("prev_s", 0) or 0
            last_bad_prev[sid] = None
    A["conn_outage_s"] = outage
    perf = by_type.get("perf", [])
    fps_vals = [p["fps"] for p in perf if isinstance(p.get("fps"), (int, float))]
    A["fps_min"] = min(fps_vals) if fps_vals else None
    A["fps_avg"] = sum(fps_vals) / len(fps_vals) if fps_vals else None
    A["fps_low"] = sum(1 for v in fps_vals if v < 30)
    A["watchdog"] = len(by_type.get("watchdog_reload", []))
    errs = Counter((e.get("msg") or "?")[:160] for e in by_type.get("js_error", []))
    A["js_errors"] = errs.most_common(10)
    A["js_err_total"] = sum(errs.values())
    A["dropped"] = sum(e.get("n", 0) for e in by_type.get("_dropped", []))
    return A


# ------------------------------------------------------------------- HTML

CSS = """
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1226;color:#e8eefc;
     margin:0;padding:24px;line-height:1.45}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:19px;margin:34px 0 10px;color:#7df3ff;border-bottom:1px solid #26305c;
   padding-bottom:6px}
.sub{color:#9fb2d8;font-size:13px;margin-bottom:18px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.card{background:#161d3d;border:1px solid #26305c;border-radius:10px;
      padding:12px 18px;min-width:150px}
.card .v{font-size:26px;font-weight:700;color:#fff}
.card .l{font-size:12px;color:#9fb2d8;margin-top:2px}
.card.warn .v{color:#ffc83d}
.card.bad .v{color:#ff5470}
.card.good .v{color:#34f5a6}
table{border-collapse:collapse;width:100%;max-width:980px;font-size:14px}
th,td{padding:6px 10px;text-align:left;border-bottom:1px solid #222b52}
th{color:#9fb2d8;font-weight:600;font-size:12px;text-transform:uppercase}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.bar{background:#26305c;border-radius:4px;height:14px;min-width:120px;overflow:hidden}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#00ebff,#7df3ff)}
.bar.red>i{background:linear-gradient(90deg,#ff5470,#ff8fa9)}
.note{color:#9fb2d8;font-size:13px;margin:6px 0}
.mono{font-family:'Consolas',monospace}
.empty{color:#67719a;font-style:italic}
"""


def bar(p, red=False):
    p = max(0.0, min(100.0, p))
    cls = "bar red" if red else "bar"
    return f'<div class="{cls}"><i style="width:{p:.0f}%"></i></div>'


def esc(s):
    return html.escape(str(s))


def build_html(A, det, bad_lines, n_events):
    f = A["funnel"]
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    H = []
    H.append(f"<h1>Matematik Avı — Ziyaretçi &amp; Sağlık Raporu</h1>")
    H.append(f'<div class="sub">Oluşturma: {now} · {n_events} olay · '
             f'kaynak: <span class="mono">data\\telemetry\\</span>'
             + (f" · {bad_lines} bozuk satır atlandı" if bad_lines else "")
             + (f" · {A['excluded_test']} olay fare/test oturumlarından (rapor dışı)"
                if A.get("excluded_test") else "") + "</div>")

    # --- özet kartları ---
    tamam_pct = pct(f["round_end"], f["game_start"])
    H.append("<h2>Özet</h2><div class='cards'>")
    H.append(f'<div class="card"><div class="v">{f["hand_seen"]}</div>'
             f'<div class="l">Yaklaşan ziyaretçi (kalibrasyonda el görüldü)</div></div>')
    H.append(f'<div class="card"><div class="v">{f["game_start"]}</div>'
             f'<div class="l">Başlatılan oyun</div></div>')
    H.append(f'<div class="card good"><div class="v">{f["round_end"]}</div>'
             f'<div class="l">Tamamlanan oyun (%{tamam_pct:.0f})</div></div>')
    H.append(f'<div class="card warn"><div class="v">{f["reset_mid"]}</div>'
             f'<div class="l">Yarıda bırakılan (RESET)</div></div>')
    H.append(f'<div class="card"><div class="v">{A["ans_total"]}</div>'
             f'<div class="l">Verilen cevap (%{pct(A["ans_ok"], A["ans_total"]):.0f} doğru)</div></div>')
    if A.get("avg_score") is not None and A["rounds"]:
        H.append(f'<div class="card"><div class="v">{A["avg_score"]:.0f}</div>'
                 f'<div class="l">Ortalama puan (en yüksek {A["max_score"]})</div></div>')
    H.append("</div>")

    # --- huni ---
    H.append("<h2>Ziyaretçi hunisi</h2>")
    top = max(f["calib_enter"], 1)
    rows = [
        ("Kalibrasyon ekranı açıldı", f["calib_enter"]),
        ("El görüldü (ziyaretçi yaklaştı)", f["hand_seen"]),
        ("Tarama başlattı (yumruk yaptı)", f["scan_start"]),
        ("Kalibrasyonu tamamladı", f["calib_done"]),
        ("Oyunu başlattı", f["game_start"]),
        ("Oyunu tamamladı (süre doldu)", f["round_end"]),
    ]
    H.append("<table><tr><th>Aşama</th><th class='num'>Sayı</th><th></th></tr>")
    for label, n in rows:
        H.append(f"<tr><td>{esc(label)}</td><td class='num'>{n}</td>"
                 f"<td>{bar(pct(n, top))}</td></tr>")
    H.append("</table>")
    H.append("<div class='note'>Aşamalar arasındaki düşüş, ziyaretçinin nerede "
             "vazgeçtiğini/zorlandığını gösterir. Kalibrasyon ekranı her oyuncu "
             "değişiminde tekrar açıldığı için sayılar tekil kişi değil "
             "<b>deneme</b> sayısıdır. Aynı oyuncu arka arkaya oynarsa eli "
             "kadrajda kaldığı için yeniden \"el görüldü\" sayılmaz; bu yüzden "
             "sonraki aşamalar bu basamağı aşabilir.</div>")

    # --- günlük ---
    H.append("<h2>Günlük dağılım</h2>")
    if A["daily"]:
        H.append("<table><tr><th>Gün</th><th class='num'>Yaklaşan</th>"
                 "<th class='num'>Başlanan</th><th class='num'>Tamamlanan</th>"
                 "<th class='num'>Cevap</th><th class='num'>Doğru %</th></tr>")
        for day, d in A["daily"].items():
            H.append(f"<tr><td>{day}</td><td class='num'>{d['hand']}</td>"
                     f"<td class='num'>{d['start']}</td><td class='num'>{d['end']}</td>"
                     f"<td class='num'>{d['ans']}</td>"
                     f"<td class='num'>%{pct(d['ok'], d['ans']):.0f}</td></tr>")
        H.append("</table>")
        if A["hourly"]:
            mx = max(A["hourly"].values())
            H.append("<h2>Saatlik yoğunluk (oyun başlatma)</h2><table>")
            for h in range(24):
                n = A["hourly"].get(h, 0)
                if n == 0:
                    continue
                H.append(f"<tr><td>{h:02d}:00</td><td class='num'>{n}</td>"
                         f"<td>{bar(pct(n, mx))}</td></tr>")
            H.append("</table>")
    else:
        H.append("<div class='empty'>Henüz veri yok.</div>")

    # --- zorluk & konu ---
    H.append("<h2>Zorluk basamakları</h2>")
    if A["ans_total"]:
        H.append("<table><tr><th>Zorluk</th><th class='num'>Cevap</th>"
                 "<th class='num'>Doğru %</th><th class='num'>Ort. süre</th><th></th></tr>")
        for d, ad in (("kolay", "KOLAY"), ("orta", "ORTA"), ("zor", "ZOR")):
            v = A["diff"][d]
            H.append(f"<tr><td>{ad}</td><td class='num'>{v['n']}</td>"
                     f"<td class='num'>%{v['pct']:.0f}</td>"
                     f"<td class='num'>{v['avg_s']:.1f} sn</td><td>{bar(v['pct'])}</td></tr>")
        H.append("</table>")
        H.append(f"<div class='note'>Ortalama cevap süresi: doğruda "
                 f"{A['ms_ok']:.1f} sn, yanlışta {A['ms_bad']:.1f} sn. "
                 f"Gösterilip cevaplanmadan kalan soru: {A['q_unanswered']} "
                 f"(süre bitti / RESET).</div>")

        H.append("<h2>Konu bazında doğruluk (en zorlanılandan kolaya)</h2>")
        H.append("<table><tr><th>Konu</th><th class='num'>Cevap</th>"
                 "<th class='num'>Doğru %</th><th class='num'>Ort. süre</th><th></th></tr>")
        for c in A["cats"]:
            H.append(f"<tr><td>{esc(c['ad'])}</td><td class='num'>{c['n']}</td>"
                     f"<td class='num'>%{c['pct']:.0f}</td>"
                     f"<td class='num'>{c['avg_s']:.1f} sn</td>"
                     f"<td>{bar(100 - c['pct'], red=True)}</td></tr>")
        H.append("</table>")
        H.append("<div class='note'>Kırmızı çubuk = yanlış oranı. En üstteki "
                 "konularda çocuklar en çok zorlanıyor.</div>")

        H.append("<h2>En çok yanlış yapılan sorular</h2>")
        if A["worst_q"]:
            H.append("<table><tr><th>Soru</th><th class='num'>Soruldu</th>"
                     "<th class='num'>Yanlış</th><th class='num'>Yanlış %</th>"
                     "<th>En çok seçilen yanlışlar</th></tr>")
            for q in A["worst_q"]:
                H.append(f"<tr><td class='mono'>{esc(q['prompt'])}</td>"
                         f"<td class='num'>{q['n']}</td><td class='num'>{q['wrong']}</td>"
                         f"<td class='num'>%{q['pct']:.0f}</td><td>{esc(q['picks'])}</td></tr>")
            H.append("</table>")
        else:
            H.append("<div class='empty'>Hiç yanlış cevap yok.</div>")
    else:
        H.append("<div class='empty'>Henüz cevap verisi yok.</div>")

    # --- teknik sağlık ---
    H.append("<h2>Teknik sağlık</h2><div class='cards'>")
    out_min = A["conn_outage_s"] / 60.0
    H.append(f'<div class="card{" bad" if A["conn_drop"] else ""}">'
             f'<div class="v">{A["conn_drop"]}</div><div class="l">Bağlantı kopması '
             f'(toplam ~{out_min:.1f} dk kesinti)</div></div>')
    H.append(f'<div class="card{" warn" if A["conn_stale"] else ""}">'
             f'<div class="v">{A["conn_stale"]}</div><div class="l">Veri duraksaması (stale)</div></div>')
    H.append(f'<div class="card{" bad" if A["watchdog"] else ""}">'
             f'<div class="v">{A["watchdog"]}</div><div class="l">Watchdog sayfa yenilemesi</div></div>')
    H.append(f'<div class="card{" bad" if A["js_err_total"] else ""}">'
             f'<div class="v">{A["js_err_total"]}</div><div class="l">JavaScript hatası</div></div>')
    if A["fps_avg"] is not None:
        H.append(f'<div class="card{" warn" if A["fps_low"] else ""}">'
                 f'<div class="v">{A["fps_avg"]:.0f}</div>'
                 f'<div class="l">Ort. FPS (en düşük {A["fps_min"]:.0f}; '
                 f'{A["fps_low"]} düşük-FPS dakikası)</div></div>')
    H.append(f'<div class="card{" warn" if A["lost_rounds"] else ""}">'
             f'<div class="v">{A["lost_rounds"]}</div>'
             f'<div class="l">El kaybı yaşanan tur (toplam {A["lost_total_s"]:.0f} sn)</div></div>')
    if det["files"]:
        H.append(f'<div class="card{" bad" if det["crashes"] else ""}">'
                 f'<div class="v">{det["crashes"]}</div>'
                 f'<div class="l">Dedektör çökmesi/yeniden başlatma</div></div>')
        if det["stats"]:
            st = det["stats"]
            avg_fps = sum(s["fps"] for s in st) / len(st)
            avg_hands = sum(s["hands_pct"] for s in st) / len(st)
            cam_fail = sum(s["cam_fail"] for s in st)
            H.append(f'<div class="card{" bad" if cam_fail else ""}">'
                     f'<div class="v">{cam_fail}</div>'
                     f'<div class="l">Kamera kare hatası (dedektör; ort. '
                     f'{avg_fps:.0f} fps, %{avg_hands:.0f} el gören kare)</div></div>')
    if A["dropped"]:
        H.append(f'<div class="card warn"><div class="v">{A["dropped"]}</div>'
                 f'<div class="l">Sunucuya ulaşamadan düşen olay partisi</div></div>')
    H.append("</div>")

    if A["js_errors"]:
        H.append("<h2>JavaScript hataları (en sık 10)</h2><table>"
                 "<tr><th>Hata</th><th class='num'>Sayı</th></tr>")
        for msg, n in A["js_errors"]:
            H.append(f"<tr><td class='mono'>{esc(msg)}</td><td class='num'>{n}</td></tr>")
        H.append("</table>")

    H.append("<h2>Ham veri</h2><div class='note'>Olaylar: "
             "<span class='mono'>data\\telemetry\\events_YYYYMMDD.jsonl</span> "
             "(her satır bir olay, JSON). Dedektör/sunucu logları: "
             "<span class='mono'>logs\\</span>. Bu raporu yeniden üretmek için "
             "kökteki <b>Rapor.bat</b>'a çift tıklayın.</div>")

    return ("<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
            "<title>Matematik Avı — Rapor</title>"
            f"<style>{CSS}</style></head><body>" + "".join(H) + "</body></html>")


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Matematik Avı telemetri raporu")
    ap.add_argument("--out", default=str(ROOT / "data" / "rapor.html"))
    args = ap.parse_args()

    events, bad = load_events()
    det = scan_detector_logs()
    A = analyze(events)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(A, det, bad, len(events)), encoding="utf-8")

    f = A["funnel"]
    print(f"[rapor] {len(events)} olay okundu ({DATA_DIR})")
    print(f"[rapor] yaklasan={f['hand_seen']}  baslanan={f['game_start']}  "
          f"tamamlanan={f['round_end']}  cevap={A['ans_total']} "
          f"(%{pct(A['ans_ok'], A['ans_total']):.0f} dogru)")
    print(f"[rapor] teknik: kopma={A['conn_drop']} stale={A['conn_stale']} "
          f"jshata={A['js_err_total']} watchdog={A['watchdog']} "
          f"dedektor_cokme={det['crashes']}")
    print(f"[rapor] HTML: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
