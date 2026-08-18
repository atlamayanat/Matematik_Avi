# -*- coding: utf-8 -*-
"""gen_audio.py — Matematik Avı ses paketini ElevenLabs ile üretir.

Oyunun TÜM ses efektleri + sakin arka plan müziği buradan çıkar. Üretilen
dosyalar web/audio/ altına yazılır ve web/js/audio.js bunları çevrimdışı çalar
(sergi makinesinde internet YOK; üretim tek seferlik, burada yapılır).

Tasarım ilkesi: sergi ortamında saatlerce dönecek. Hiçbir ses "panik" veya
"ceza" hissi vermez; hepsi düşük parlaklıkta, kısa kuyruklu, cyan/neon HUD
temasıyla uyumlu. Eski kalp-atışı + hızlanan-saat sesi bilinçli olarak
kaldırıldı; yerine saniyede bir çalan tek tik geldi (bkz. SPEC "urgency-tick").

Kullanım
--------
  python tools\\gen_audio.py                 # her ses icin 3 varyant + 2 muzik adayi
  python tools\\gen_audio.py --dry-run       # istek atmadan kredi/maliyet dokumu
  python tools\\gen_audio.py --only sfx-wrong urgency-tick
  python tools\\gen_audio.py --variants 1    # tek varyant (ucuz tekrar uretim)
  python tools\\gen_audio.py --no-music      # sadece efektler
  python tools\\gen_audio.py --pick          # secim ekranini uygula (secim.json)

Akış
----
  1) --dry-run ile kredi kontrolü.
  2) Üretim: web/audio/gen/<ad>_v1.mp3 .. _v3.mp3  (+ web/audio/gen/sec.html)
     Varyant 1'ler aynı anda web/audio/<ad>.mp3 olarak kurulur -> oyun hemen çalışır.
  3) sec.html'i tarayıcıda aç, her ses için beğendiğin varyantı seç, "secim.json
     indir" de, dosyayı web/audio/gen/ içine koy, sonra: python tools\\gen_audio.py --pick

API anahtarı: kök dizindeki key.txt (tek satır) veya ELEVENLABS_API_KEY ortam
değişkeni. key.txt git'e girmez (.gitignore).

Sadece stdlib; ek paket gerektirmez.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "web" / "audio"
GEN_DIR = AUDIO_DIR / "gen"
KEY_FILE = ROOT / "key.txt"

SFX_URL = "https://api.elevenlabs.io/v1/sound-generation"
MUSIC_URL = "https://api.elevenlabs.io/v1/music"

# ElevenLabs ücretlendirmesi (2026-08):
#   ses efekti : saniyede 40 kredi (duration_seconds verildiginde)
#   muzik      : dakikada ~900 kredi
CREDITS_PER_SFX_SECOND = 40
CREDITS_PER_MUSIC_MINUTE = 900

# --------------------------------------------------------------------------
# Ses listesi.
#
#   name  : web/audio/<name>.mp3  -> audio.js ASSET_PATHS ile birebir aynı
#   dur   : saniye (0.5 - 30). Kredi bunun uzerinden hesaplanir.
#   loop  : kesintisiz donecek mi (API'nin loop bayragi)
#   infl  : prompt_influence 0-1. Yuksek = prompta harfi harfine uyar.
#           UI sesleri icin yuksek tutulur; ambiyans icin biraz dusuk.
# --------------------------------------------------------------------------
SPEC = [
    dict(
        name="sfx-correct", dur=1.5, loop=False, infl=0.7,
        note="dogru cevap (game.js onAnswer)",
        prompt=(
            "Soft glassy user interface confirmation chime, gentle two-note upward "
            "bell, warm sine tone with a light crystal shimmer, clean and friendly, "
            "short tail, futuristic holographic interface, encouraging, "
            "no harshness, no reverb wash, no music"
        ),
    ),
    dict(
        name="sfx-wrong", dur=0.8, loop=False, infl=0.8,
        note="yanlis cevap - kisa, net, iki nota; yanlis oldugu anlasilir ama cezalandirmaz",
        prompt=(
            "Two short descending notes, a clean simple minor second interval, "
            "soft rounded synth tone, crisp and clear, reads immediately as "
            "'not correct' but stays gentle and friendly, quick decay, "
            "no buzzer, no alarm, no error klaxon, no harsh distortion, "
            "not scary, no reverb, no music"
        ),
    ),
    dict(
        name="sfx-select", dur=1.0, loop=False, infl=0.75,
        note="yumruk onayi (lens.js playSelect)",
        prompt=(
            "Short crisp digital confirm click, dry tight electronic tick with a "
            "tiny snap and a very short bright tail, clean sci-fi interface button "
            "press, no reverb, no music"
        ),
    ),
    dict(
        name="sfx-hover", dur=1.0, loop=False, infl=0.75,
        note="token armed (lens.js LensHunt)",
        prompt=(
            "Very quiet tiny high pitched interface hover tick, delicate subtle "
            "blip, minimal and soft, holographic sci-fi cursor moving over a "
            "target, extremely short, no reverb, no music"
        ),
    ),
    dict(
        name="sfx-btn-arm", dur=1.0, loop=False, infl=0.65,
        note="BASLA / RESET butonu armed (game.js onFrame)",
        prompt=(
            "Soft electric energy hum swelling up quietly, holographic button "
            "charging and activating, smooth gradual onset with no attack "
            "transient, warm and low, sci-fi interface, no music"
        ),
    ),
    dict(
        name="countdown-tick", dur=1.0, loop=False, infl=0.75,
        note="3 - 2 - 1 (game.js startCountdown)",
        prompt=(
            "Clean single sine countdown blip, soft rounded electronic beep, calm "
            "and neutral, futuristic timer, one hit only, short decay, "
            "no harshness, no music"
        ),
    ),
    dict(
        name="countdown-go", dur=1.5, loop=False, infl=0.6,
        note='"BASLA!" (game.js startCountdown)',
        prompt=(
            "Bright opening synth chord swell with a light airy whoosh, uplifting "
            "futuristic game start signal, positive and energetic but smooth, "
            "clean sci-fi interface, no drums, no vocals"
        ),
    ),
    dict(
        name="urgency-tick", dur=0.5, loop=False, infl=0.8,
        note="SON 10 SANIYE - ekrandaki saniye her degistiginde TEK tik (bkz. audio.js setUrgent)",
        prompt=(
            "One single clean digital countdown tick, short dry click with a "
            "small pitched body, precise and calm, futuristic interface timer "
            "marking a second, crisp and quiet, "
            "one tick only, no repeats, no rhythm, no reverb, no bass rumble, "
            "not harsh, no alarm, no music"
        ),
    ),
    dict(
        name="urgency-enter", dur=1.5, loop=False, infl=0.7,
        note="son 10 saniyeye girildi (game.js updateTimer)",
        prompt=(
            "Single soft low notification tone, warm muted synth note fading "
            "gently, calm sci-fi heads up display advisory, one hit only, "
            "not alarming, no buzzer, no music"
        ),
    ),
    dict(
        name="time-up", dur=2.5, loop=False, infl=0.65,
        note="sure doldu (game.js endRound)",
        prompt=(
            "Soft descending closing tone, gentle synth powering down, warm smooth "
            "fade out, futuristic interface deactivating calmly, "
            "no buzzer, no alarm, no impact hit, no music"
        ),
    ),
    dict(
        name="round-end", dur=2.5, loop=False, infl=0.6,
        note="sonuc ekrani acilisi (game.js endRound)",
        prompt=(
            "Warm resolving synth chord, gentle satisfying completion pad blooming "
            "and fading, soft airy shimmer, futuristic interface summary screen, "
            "pleasant and calm, no drums, no vocals"
        ),
    ),
    dict(
        name="score-tick", dur=1.0, loop=False, infl=0.75,
        note="puan sayimi (game.js animateScore)",
        prompt=(
            "Tiny rapid digital counter ticks, small soft numeric blips counting "
            "up quickly, light and dry, sci-fi score readout, "
            "no reverb, no melody, no music"
        ),
    ),
    dict(
        name="celebrate-top3", dur=3.0, loop=False, infl=0.6,
        note="ilk 3'e girme (game.js showResultRank)",
        prompt=(
            "Bright cheerful rising synth arpeggio with sparkling crystal bells, "
            "magical shimmer, joyful achievement flourish for a children's game, "
            "futuristic and warm, short and clean, no drums, no vocals, no fanfare "
            "brass"
        ),
    ),
    dict(
        name="calib-scan-loop", dur=4.0, loop=True, infl=0.65,
        note="biyometrik tarama surerken (calibration.js startScan)",
        prompt=(
            "Smooth rotating scanner hum loop, soft sweeping biometric scan tone, "
            "gentle electronic whirr with a subtle high shimmer passing back and "
            "forth, sci-fi fingerprint reader working, seamless loop, calm and "
            "quiet, no percussion, no melody, no beeping"
        ),
    ),
    dict(
        name="calib-complete", dur=2.0, loop=False, infl=0.7,
        note='"ERISIM SAGLANDI" (calibration.js finishScan)',
        prompt=(
            "Access granted confirmation chord, clean sci-fi security lock "
            "releasing with a soft mechanical click followed by a bright positive "
            "two note swell, futuristic terminal, satisfying, no music"
        ),
    ),
    dict(
        name="calib-cancel", dur=1.0, loop=False, infl=0.75,
        note="tarama iptal (calibration.js sfx calibrationCancel)",
        prompt=(
            "Short soft cancel tone, gentle downward digital blip, interface "
            "dismissing quietly, neutral and unobtrusive, no reverb, no music"
        ),
    ),
    dict(
        name="transition-whoosh", dur=1.2, loop=False, infl=0.65,
        note="ekran gecisleri (game.js setScreen)",
        prompt=(
            "Airy filtered whoosh, soft synth sweep passing by smoothly, light and "
            "clean screen transition, gentle, no impact, no bass drop, no music"
        ),
    ),
    dict(
        name="attract-accent", dur=2.0, loop=False, infl=0.6,
        note="attract ekraninda seyrek davet pingi (game.js enterAttract)",
        prompt=(
            "Sparse gentle ambient ping, one soft bell note with a long shimmering "
            "tail, inviting and calm sci-fi idle sound, spacious, "
            "no melody, no drums, no music"
        ),
    ),
]

MUSIC = dict(
    name="ambient-loop",
    length_ms=90_000,
    note="surekli arka plan (audio.js music kanali, dusuk gain)",
    prompt=(
        "Calm ambient sci-fi background music for a children's science museum "
        "exhibit. Slow warm synth pads, a gentle floating arpeggio, soft airy "
        "textures and subtle sparkle. Peaceful, spacious and non-intrusive, "
        "designed to sit quietly under gameplay. Steady mood from start to finish "
        "with no build-ups, no drops and no dramatic changes. Loops smoothly. "
        "Warm cyan neon atmosphere. Instrumental only: no drums, no percussion, "
        "no vocals, no lead melody."
    ),
)

MP3_FORMAT = "mp3_44100_128"


# --------------------------------------------------------------------------
# yardimcilar
# --------------------------------------------------------------------------
def read_key() -> str:
    env = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if env:
        return env
    if KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8-sig").strip()
        if key:
            return key.splitlines()[0].strip()
    sys.exit(
        f"HATA: API anahtari bulunamadi.\n"
        f"  {KEY_FILE} icine tek satir olarak yapistir,\n"
        f"  ya da:  $env:ELEVENLABS_API_KEY = \"...\""
    )


def post(url: str, key: str, payload: dict, tries: int = 3) -> bytes:
    """JSON gonder, ham ses baytlarini dondur. 429/5xx'te geri cekilerek dener."""
    body = json.dumps(payload).encode("utf-8")
    last = ""
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            last = f"HTTP {e.code}: {detail}"
            # 401/402/422 kalicidir; tekrar denemek krediyi bosa harcar.
            if e.code in (400, 401, 403, 422):
                break
            if e.code == 402:
                last += "\n  -> kredi bitti veya plan bu ozelligi kapsamiyor"
                break
        except Exception as e:  # timeout, baglanti kopmasi
            last = f"{type(e).__name__}: {e}"
        if attempt < tries:
            wait = 3 * attempt
            print(f"    ! {last}  ({wait}s sonra tekrar)")
            time.sleep(wait)
    raise RuntimeError(last)


def fmt_credits(c: float) -> str:
    return f"{c:,.0f}".replace(",", ".")


def estimate(specs: list, variants: int, with_music: bool, music_takes: int):
    sfx_sec = sum(s["dur"] for s in specs) * variants
    sfx_cr = sfx_sec * CREDITS_PER_SFX_SECOND
    mus_min = (MUSIC["length_ms"] / 60_000) * music_takes if with_music else 0
    mus_cr = mus_min * CREDITS_PER_MUSIC_MINUTE
    return sfx_sec, sfx_cr, mus_min, mus_cr


# --------------------------------------------------------------------------
# secim ekrani
# --------------------------------------------------------------------------
def write_picker(specs: list, variants: int, music_takes: int) -> Path:
    rows = []
    for s in specs:
        opts = "".join(
            f'<label class="opt"><input type="radio" name="{s["name"]}" value="{v}"'
            f'{" checked" if v == 1 else ""}> v{v}'
            f'<audio controls preload="none" src="{s["name"]}_v{v}.mp3"></audio></label>'
            for v in range(1, variants + 1)
        )
        rows.append(
            f'<section><h2>{s["name"]}'
            f'<em>{s["dur"]}s{" · loop" if s["loop"] else ""}</em></h2>'
            f'<p class="note">{s["note"]}</p><div class="opts">{opts}</div></section>'
        )
    if music_takes:
        opts = "".join(
            f'<label class="opt"><input type="radio" name="{MUSIC["name"]}" value="{v}"'
            f'{" checked" if v == 1 else ""}> v{v}'
            f'<audio controls preload="none" loop src="{MUSIC["name"]}_v{v}.mp3"></audio></label>'
            for v in range(1, music_takes + 1)
        )
        rows.append(
            f'<section class="music"><h2>{MUSIC["name"]}'
            f'<em>{MUSIC["length_ms"] // 1000}s · arka plan</em></h2>'
            f'<p class="note">{MUSIC["note"]}</p><div class="opts">{opts}</div></section>'
        )

    html = """<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<title>Matematik Avı — ses seçimi</title><style>
:root{color-scheme:dark}
body{margin:0;padding:32px;background:#070918;color:#eaf6ff;
  font:15px/1.5 system-ui,"Segoe UI",sans-serif}
h1{font-size:22px;letter-spacing:.04em;margin:0 0 4px}
.lead{color:#9fc3e8;margin:0 0 28px;max-width:70ch}
section{border:1px solid rgba(125,243,255,.22);border-radius:10px;
  padding:14px 16px;margin-bottom:14px;background:rgba(18,26,58,.5)}
section.music{border-color:rgba(255,143,228,.35)}
h2{font-size:15px;margin:0 0 2px;color:#7df3ff;letter-spacing:.06em;
  display:flex;gap:10px;align-items:baseline}
h2 em{font-style:normal;font-size:12px;color:#7f8db8;letter-spacing:.02em}
.note{margin:0 0 10px;font-size:12.5px;color:#8fa4cc}
.opts{display:flex;flex-wrap:wrap;gap:10px}
.opt{display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:8px;
  background:rgba(0,0,0,.32);border:1px solid transparent;cursor:pointer}
.opt:has(:checked){border-color:#00EBFF;background:rgba(0,235,255,.10)}
audio{height:32px}
#bar{position:sticky;bottom:0;margin-top:22px;padding:14px 0;
  background:linear-gradient(transparent,#070918 24%);display:flex;gap:12px;align-items:center}
button{font:inherit;font-weight:600;padding:11px 20px;border-radius:8px;border:0;
  background:#00EBFF;color:#04121c;cursor:pointer}
code{background:rgba(0,0,0,.4);padding:2px 6px;border-radius:4px;color:#7df3ff}
</style></head><body>
<h1>Ses seçimi</h1>
<p class="lead">Her ses için beğendiğin varyantı işaretle, sonra <b>secim.json indir</b>'e bas.
İnen dosyayı bu klasöre (<code>web/audio/gen/</code>) koy ve çalıştır:
<code>python tools\\gen_audio.py --pick</code></p>
__ROWS__
<div id="bar"><button onclick="save()">secim.json indir</button>
<span id="msg" style="color:#8fa4cc"></span></div>
<script>
function save(){
  const out={};
  document.querySelectorAll('input[type=radio]:checked').forEach(r=>out[r.name]=+r.value);
  const b=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(b); a.download='secim.json'; a.click();
  document.getElementById('msg').textContent=Object.keys(out).length+' seçim kaydedildi.';
}
</script></body></html>"""
    html = html.replace("__ROWS__", "\n".join(rows))
    out = GEN_DIR / "sec.html"
    out.write_text(html, encoding="utf-8")
    return out


def apply_picks() -> None:
    sel = GEN_DIR / "secim.json"
    if not sel.exists():
        sys.exit(f"HATA: {sel} yok. sec.html'den indirip bu klasore koy.")
    picks = json.loads(sel.read_text(encoding="utf-8-sig"))
    n = 0
    for name, v in picks.items():
        src = GEN_DIR / f"{name}_v{int(v)}.mp3"
        if not src.exists():
            print(f"  ATLANDI {name}: {src.name} yok")
            continue
        shutil.copyfile(src, AUDIO_DIR / f"{name}.mp3")
        print(f"  {name}.mp3  <- v{v}")
        n += 1
    print(f"\n{n} dosya web/audio/ altina kuruldu.")
    print("Tarayici onbellegi icin web/index.html'de audio.js?v= numarasini artir.")


# --------------------------------------------------------------------------
# uretim
# --------------------------------------------------------------------------
def generate(specs: list, key: str, variants: int, with_music: bool,
             music_takes: int, delay: float) -> None:
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    failed = []

    for s in specs:
        for v in range(1, variants + 1):
            out = GEN_DIR / f'{s["name"]}_v{v}.mp3'
            if out.exists():
                print(f'  = {out.name} zaten var, atlaniyor')
                continue
            print(f'  + {out.name}  ({s["dur"]}s{" loop" if s["loop"] else ""})', flush=True)
            try:
                data = post(SFX_URL, key, {
                    "text": s["prompt"],
                    "duration_seconds": s["dur"],
                    "loop": s["loop"],
                    "prompt_influence": s["infl"],
                    "model_id": "eleven_text_to_sound_v2",
                    "output_format": MP3_FORMAT,
                })
            except RuntimeError as e:
                print(f"    HATA: {e}")
                failed.append(out.name)
                continue
            out.write_bytes(data)
            spent += s["dur"] * CREDITS_PER_SFX_SECOND
            # Varyant 1 dogrudan kurulur -> secim yapilmasa bile oyun calisir.
            if v == 1:
                shutil.copyfile(out, AUDIO_DIR / f'{s["name"]}.mp3')
            time.sleep(delay)

    if with_music:
        secs = MUSIC["length_ms"] // 1000
        for v in range(1, music_takes + 1):
            out = GEN_DIR / f'{MUSIC["name"]}_v{v}.mp3'
            if out.exists():
                print(f'  = {out.name} zaten var, atlaniyor')
                continue
            print(f'  + {out.name}  ({secs}s muzik, uzun surebilir)', flush=True)
            try:
                data = post(f"{MUSIC_URL}?output_format={MP3_FORMAT}", key, {
                    "prompt": MUSIC["prompt"],
                    "music_length_ms": MUSIC["length_ms"],
                    "model_id": "music_v2",
                    "force_instrumental": True,
                })
            except RuntimeError as e:
                print(f"    HATA: {e}")
                failed.append(out.name)
                continue
            out.write_bytes(data)
            spent += (MUSIC["length_ms"] / 60_000) * CREDITS_PER_MUSIC_MINUTE
            if v == 1:
                shutil.copyfile(out, AUDIO_DIR / f'{MUSIC["name"]}.mp3')
            time.sleep(delay)

    picker = write_picker(specs, variants, music_takes if with_music else 0)
    print(f"\nHarcanan (tahmini): {fmt_credits(spent)} kredi")
    if failed:
        print(f"BASARISIZ ({len(failed)}): {', '.join(failed)}")
        print("  Ayni komutu tekrar calistir: mevcut dosyalar atlanir, sadece eksikler uretilir.")
    print(f"Secim ekrani: {picker}")
    print("Varyant 1'ler web/audio/ altina kuruldu; oyun simdiden calisir.")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Matematik Avi ses paketi ureticisi")
    ap.add_argument("--variants", type=int, default=3, help="ses efekti basina varyant (varsayilan 3)")
    ap.add_argument("--music-takes", type=int, default=2, help="muzik adayi sayisi (varsayilan 2)")
    ap.add_argument("--no-music", action="store_true", help="muzigi atla (sadece efektler)")
    ap.add_argument("--only", nargs="+", metavar="AD", help="sadece bu sesleri uret")
    ap.add_argument("--dry-run", action="store_true", help="istek atma, sadece kredi dokumu")
    ap.add_argument("--pick", action="store_true", help="secim.json'u uygula")
    ap.add_argument("--delay", type=float, default=0.8, help="istekler arasi bekleme (sn)")
    a = ap.parse_args()

    if a.pick:
        apply_picks()
        return

    specs = SPEC
    with_music = not a.no_music
    if a.only:
        want = set(a.only)
        specs = [s for s in SPEC if s["name"] in want]
        with_music = with_music and MUSIC["name"] in want
        missing = want - {s["name"] for s in specs} - {MUSIC["name"]}
        if missing:
            sys.exit(f"HATA: bilinmeyen ses: {', '.join(sorted(missing))}")

    takes = a.music_takes if with_music else 0
    sfx_sec, sfx_cr, mus_min, mus_cr = estimate(specs, a.variants, with_music, takes)

    print(f"Ses efekti : {len(specs)} ses x {a.variants} varyant = {sfx_sec:.1f} sn"
          f"  -> {fmt_credits(sfx_cr)} kredi")
    if with_music:
        print(f"Muzik      : {takes} aday x {MUSIC['length_ms'] // 1000} sn = {mus_min:.1f} dk"
              f"  -> {fmt_credits(mus_cr)} kredi")
    print(f"TOPLAM     : {fmt_credits(sfx_cr + mus_cr)} kredi"
          f"  (~${sfx_sec / 60 * 0.12 + mus_min * 0.15:.2f} dolar bazli API)")

    if a.dry_run:
        print("\n--dry-run: istek atilmadi.")
        return

    key = read_key()
    print(f"\nAnahtar okundu ({len(key)} karakter). Uretim basliyor...\n")
    generate(specs, key, a.variants, with_music, takes, a.delay)


if __name__ == "__main__":
    main()
