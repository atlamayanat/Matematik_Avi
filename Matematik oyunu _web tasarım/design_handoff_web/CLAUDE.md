# CLAUDE.md — READ THIS FIRST

This folder is the **design handoff** for the **web version** of the museum game
**"Matematik Avı" (Math Lens-Hunt)**. The game was prototyped/specced in Unity; we are now
**rebuilding it for the web** (HTML + CSS + JavaScript, runs in a browser, projected on a wall).

Your job: build the web game so it **looks and behaves like the design reference**, while keeping
the game's logic and rules intact.

## 🔴 GOLDEN RULES
1. **The HTML reference is the source of truth for the LOOK.** `Matematik Avı.dc.html` is real,
   working HTML/CSS/JS that already shows the exact visual system, motion, and interactions. Match it.
   You may reuse its CSS values, timings, and structure directly — but ship clean production code
   (see "Output" below), not the prototype's authoring wrapper.
2. **`GAME_DESIGN.md` is the source of truth for the LOGIC.** Flow (attract→playing→result),
   scoring, timer, question pools, difficulty content, and the §8 constraints must be respected.
   If the HTML and GAME_DESIGN ever disagree on *logic*, GAME_DESIGN wins; on *visuals*, the HTML wins.
3. **Keep the input contract swappable, don't hardcode the source.** The game is driven by a hand:
   normalized `{ x:0..1, y:0..1, present:bool, gesture:'open'|'fist' }`. Build ONE input module behind
   this interface. Ship with **mouse input** (move = hand, mousedown = fist) so it runs anywhere, and
   leave a clear seam to plug in real hand tracking later (in-browser **MediaPipe Hands** via webcam,
   OR a WebSocket bridge from the existing Python/OSC detector). Do not scatter mouse/webcam code
   through the game — game logic only ever reads the normalized hand state.
4. **Keep it running at every step.** After each change the page must load with no console errors and
   the attract→playing→result loop must work. Test with the mouse.
5. **Fit the design to the game, not the reverse.** Don't invent new screens, content, or mechanics.
   If something seems to need a logic change, **stop and ask.**
6. **No heavy frameworks unless asked.** This is a single full-screen kiosk page. Vanilla JS (or a
   tiny build) is preferred. No backend required for the core game.

## Read order
1. **`CLAUDE.md`** (this file) — rules & scope.
2. **`GAME_DESIGN.md`** — authoritative game logic, flow, §8 constraints.
3. **`README.md`** — visual spec + web translation: design tokens, typography, sizes, motion
   timings, per-screen breakdown, and the lens/token reveal math (with the exact constants).
4. **`Matematik Avı.dc.html`** — open in a browser (keep `support.js` beside it) to see/feel the target.

## What to build (web)
A single full-screen page, 16:9, designed for a **wall projection**, that runs the whole game:
- **Attract screen:** title, "Seviyeni seç", 3 large neon difficulty buttons (KOLAY/ORTA/ZOR),
  drifting math-symbol background, the lens as cursor. Pick a difficulty by landing the lens + fist.
- **Gameplay:** dark field; question at top; HUD counters (SORU x/5, DOĞRU, timer); RESET top-right;
  ~30 answer tokens hidden in the dark, **revealed by proximity to the lens**; nearest = armed (gold);
  fist selects; correct=green / wrong=red; one shot per question; 5 questions; 2:00 timer.
- **Result:** score N/5, auto-returns to attract (~4.4s).

Everything must read **from across a room**: large type, high contrast, generous hit targets, one
clearly-nearest selectable target at a time.

## Tech mapping (Unity terms → web)
- HDR + Bloom glow  → CSS `box-shadow` / `text-shadow` / `filter: drop-shadow` (already in the HTML).
- Sprites/particles → DOM elements + CSS, or `<canvas>` for the starfield / many particles.
- TMP fonts         → web fonts: **Baloo 2** (display/numbers) + **JetBrains Mono** (telemetry),
  loaded from Google Fonts. (Math glyphs `√ ² ³ ½ × ÷ −` and Turkish `İ ı ğ ş ç ö ü` come from the
  web font / system fallback — verify they render, no tofu boxes.)
- Screen-space UI   → absolutely-positioned HUD; size everything in `vmin`/`cqmin`-style ratios so it
  scales to any projector. Anchor RESET to the true top-right corner.

## Output (production code, not the prototype wrapper)
- Deliver a normal static site: `index.html` + `styles.css` + `js/` (e.g. `game.js`, `lens.js`,
  `tokens.js`, `input.js`, `questions.js`). No build step required is ideal.
- Strip the prototype's authoring runtime (`support.js`, the `.dc.html` wrapper). Reuse its **values**
  (colors, sizes, timings, the reveal math) — not its framework.
- Persist nothing the player shouldn't keep; the round resets cleanly for the next walk-up player.

When unsure whether something is "logic" vs "visual": treat it as logic and ask.
