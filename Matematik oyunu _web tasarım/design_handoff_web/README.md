# Matematik Avı — Web Build · Visual Spec & Handoff

> Read **`CLAUDE.md`** first (rules & scope), then **`GAME_DESIGN.md`** (game logic), then this file
> (the look), with **`Matematik Avı.dc.html`** open in a browser as the living reference.

## What this is
**Matematik Avı (Math Lens-Hunt)** — a hands-free, gesture-controlled math game for a museum
**wall projection**. A question shows at the top of a dark screen; ~30 answer tokens are hidden in the
dark and **revealed by a glowing circular "lens"** that follows the player's hand. Land the lens on the
correct answer, **close the hand into a fist** to select. 5 questions, one 2:00 timer, 3 difficulty
levels. We are building the **web version** (HTML/CSS/JS).

The bundled `.dc.html` is **real working HTML/CSS/JS** in the exact target style — treat it as the
canonical visual reference and reuse its values. Ship clean production code (see `CLAUDE.md` → Output).

## Visual system: "Sinematik Sci-Fi HUD"
Deep indigo-black space, neon cyan/magenta/violet accents, hairline corner brackets, glass panels,
soft glow (via CSS shadows), rounded warm display type over mono telemetry labels. Difficulty colors
are a **hybrid**: buttons use the neon palette; green/red are reserved strictly for correct/wrong.

---

## Design Tokens

### Colors
| Token | Hex | Role |
|---|---|---|
| `--space` | `#04030D` | Page background (near-black indigo) |
| `--space-2` | `#06040F` | Field gradient base |
| `--ink-0` | `#EEF1FF` | Primary text |
| `--ink-1` | `#A9A4D6` | Secondary text |
| `--ink-2` | `#8B86BF` | Mono telemetry labels |
| `--cyan` | `#00EBFF` | **KOLAY** · lens ring · accent 1 |
| `--violet` | `#9F5FFF` | **ORTA** · bridge accent |
| `--magenta`| `#FF4AD6` | **ZOR** · RESET · accent 2 |
| `--gold` | `#FFC83D` | **Armed** token ring/halo |
| `--gold-text`| `#FFE08A`| Armed token glyph |
| `--green` | `#34F5A6` | **Correct** flash + token |
| `--green-text`| `#7DFFC4`| Correct token glyph |
| `--red` | `#FF5470` | **Wrong** + low-time timer |
| `--red-text` | `#FF8095`| Wrong token glyph |
| `--token-text`| `#E6F4FF`| Revealed (not armed) token glyph |
| `--hairline` | `rgba(150,130,255,0.16)` | Borders / grid lines |

### Typography (Google Fonts)
- **Display / headings / numbers:** `Baloo 2` (rounded, warm), weights 600–800.
- **Telemetry / labels:** `JetBrains Mono`, 400–700, **UPPERCASE**, letter-spacing `0.2em`–`0.36em`.
- (Optional body) `Space Grotesk`.
- **Verify glyphs render** (no tofu): Turkish `İ ı ğ Ğ Ş ş ç Ç ö ü Ö Ü` and math `√ ² ³ ½ ¼ ¾ × ÷ − = ( ) !`.

### Sizing — scale to the projector
Size everything in viewport-relative units so it fills any 16:9 projector. In the prototype `1cqmin`
= 1% of the frame's smaller side; for a full-screen page use **`vmin`** (or a container query). Targets:
| Element | Size (≈ vmin) |
|---|---|
| Attract title "MATEMATİK AVI" | ~9.8, Baloo 800, one line |
| Attract subtitle "Seviyeni seç" | ~5.8 |
| Difficulty button label | ~5.4 (padding ~3.6 × 8) |
| Difficulty caption (mono) | ~2.2 |
| In-game question prompt | ~8, one line |
| Timer (M:SS) | ~5.4 (largest counter) |
| Counter labels (SORU/DOĞRU) | ~2 mono |
| Answer token glyph | ~5.2 |
| Result headline | ~9 |

### Motion / timing (exact)
| Effect | Spec |
|---|---|
| Lens follow | exponential smoothing per frame: `pos += (target - pos) * 0.22` (≈ what the prototype uses) |
| Reveal falloff | `r = clamp01(1 - dist/REVEAL_R)`, then smoothstep `r = r*r*(3-2*r)`; token `opacity=r`, `scale=0.8+0.2*r` |
| `REVEAL_R` | **0.235 × frame width** |
| `ARM_R` (selectable) | **0.095 × frame width** for gameplay tokens; **0.13 × width** for the bigger attract buttons; RESET uses the gameplay radius |
| Iris-close (fist) | lens iris scales to ~0.4 then back to 1 over ~0.18s (ease `cubic-bezier(0.5,0,0,1)`); never fully closes |
| Token confirm pop | scale punch ~1.45 (correct) / ~1.3 (wrong), back-out, settle ~1.1–1.2 |
| Center flash | "Doğru!"/"Yanlış" scale 1.25→1.0 over ~0.5s, hold, fade after ~0.76s |
| Difficulty idle | breathing scale 1.0↔1.035 over ~3–4s |
| Low-time timer (≤10s) | red, pulse scale 1.0↔1.07 + glow ~0.9s |
| Result screen | hold ~4.4s then auto-return to attract |
| Next-question pause | ~1.05s after a confirm |

---

## Screens

### 1. Attract / Start
Centered column on dark space (radial glows + faint perspective grid masked to center + drifting
math-symbol particles + starfield via `<canvas>`).
- **Title** "MATEMATİK AVI": Baloo 800, gradient white→cyan→violet, soft glow, slow glow-pulse, one line.
- **Subtitle** "Seviyeni seç": Baloo 600, light cyan-white.
- **3 difficulty buttons** (large, well-spaced glass pills, 2px neon rim + outer glow + faint inner glow, breathing):
  - **KOLAY** — cyan — caption `ilkokul · ortaokul`
  - **ORTA** — violet — caption `ortaokul · lise`
  - **ZOR** — magenta — caption `lise · üniversite`
- **Gesture hint** (bottom, mono + pulsing dot): "Merceği bir seviyeye getir ve elini kapat".
- Lens is the cursor. Button states: idle(breathing) → armed(lens near: ×1.12, brighter, stronger glow) → fist(punch + iris-close) → starts that difficulty.

### 2. Gameplay
Dark field (grid masked toward center; no bright art — the reveal depends on darkness).
- **Top-left counters** (mono, stacked): `SORU x/5 · <LEVEL>`, `DOĞRU NN`, then **timer M:SS** (largest). Last 10s → red + pulse.
- **Top-center**: small "SORU" kicker + large question (`13 × 7`, `√144`, `9²`, `x² = 49`…), one line.
- **Top-right RESET**: magenta-rimmed pill `↻ RESET`, anchored to the true corner; also lens-selectable → back to attract.
- **Tokens**: ~30 on a jittered 6×5 grid, non-overlapping, always one clear nearest. Each a Baloo 800 numeral/symbol.
  - hidden(far) opacity≈0 → revealed(near) fades in `--token-text`, brighter/larger closer, soft cyan halo →
    armed(single nearest within ARM_R) ×1.2, glyph `--gold-text`, gold ring+halo →
    correct glyph `--green-text` + green ring/halo + punch → wrong glyph `--red-text` + red ring/halo + punch.
  - The correct answer appears **2–3 times** among decoys, well spread (decoys = near-miss numbers + a few math symbols).
- **Lens (simplified — NO rotating element):** soft circular light pool (radial gradient) + bright white ring + small white core + optional faint cyan/magenta chromatic double-ring. Follows hand with smoothing; hidden when no hand. Fist → iris-close toward armed token.
- **Center flash**: big "Doğru!" (green) / "Yanlış" (red), momentary.

### 3. Result (~4.4s)
Over the dark field: "— TUR BİTTİ —" mono kicker, big "**Bitti!**" or "**Süre doldu!**" (Baloo 800),
then "Doğru **N/5**" (N/5 in green), footer "Başlangıç ekranına dönülüyor…". Auto-return to attract.

---

## Input (web) — one swappable module
Game logic reads only a normalized hand state: `{ x:0..1, y:0..1, present:bool, gesture:'open'|'fist' }`.
- **Ship default = mouse:** mousemove → x/y + present; mousedown (or hold) → `fist`; mouseleave → `present:false`.
- **Production hand tracking (later, behind same interface):** in-browser **MediaPipe Hands** (webcam) →
  map index/palm position to x/y, detect closed hand → `fist`; OR a **WebSocket** bridge feeding the
  same normalized object from the existing Python/OSC detector.
- Never let mouse/webcam specifics leak into game/lens/token code.

## State (see GAME_DESIGN.md §3)
`screen: attract|playing|result` · `difficulty: kolay|orta|zor` · `questionIndex 0..4` · `score 0..5` ·
`timeLeft` (120s) · `tokens[] {glyph,x,y,isCorrect}` (regenerated per question) ·
`lens {x,y,present,gesture}` (smoothed) · `armed` (nearest within ARM_R) · `locked` (true during confirm).

## Suggested build order
1. Full-screen 16:9 page shell + fonts + color vars + starfield canvas.
2. Input module (mouse) → normalized hand state + the lens visual following it.
3. Attract screen (title, buttons, breathing/arm/fist-select).
4. Question pools per difficulty + token field generator (grid jitter, 2–3 correct, decoys).
5. Reveal/arm math (REVEAL_R / ARM_R / smoothstep) on the token field.
6. Fist→judge→correct/wrong flash + score + next question + timer.
7. Result screen + auto-return + RESET.
8. Polish glow/timings to match the HTML; verify Turkish + math glyphs.
9. Leave the seam to swap mouse → MediaPipe/WebSocket hand input.

A developer who wasn't in this conversation should be able to build the web game from
`CLAUDE.md` + `GAME_DESIGN.md` + this README + the HTML reference alone.

## Files
- `CLAUDE.md` — rules & scope (read first).
- `GAME_DESIGN.md` — authoritative game logic/flow/constraints.
- `README.md` — this visual spec + web translation.
- `Matematik Avı.dc.html` — living visual reference (open with `support.js` beside it).
- `support.js` — prototype runtime (reference only; do not ship).
