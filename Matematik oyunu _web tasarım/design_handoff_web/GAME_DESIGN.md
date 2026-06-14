# Matematik Mercek‑Avı (Math Lens‑Hunt) — Design Brief

> A hands‑free, gesture‑controlled math game for a **museum / exhibition wall projection**.
> This document explains the whole game — its logic, flow, screens and every visual
> element — so a designer (human or AI) can **redesign the look** without breaking how
> the game works. Read §8 (“Must‑respect constraints”) before changing anything.

---

## 1. What it is (one paragraph)

A math question appears at the top of a **dark** screen. The dark lower area is secretly
filled with dozens of possible answers (numbers and math symbols). The player can’t see
them — until they sweep a glowing circular **“lens / flashlight”** over the dark, which
**reveals** the answers near it. The lens is moved with the player’s **bare hand**, tracked
by a camera. When the player finds the correct answer and **closes their hand into a fist**,
the answer under the lens is selected. It’s a “hunt for the right answer in the dark with a
flashlight” game. 5 questions, one countdown timer. No mouse, no controller, no touch.

**Audience:** everyone, ages ~6 to 60+. A child and an adult should both be able to walk up
and play in seconds. Difficulty (Easy / Medium / Hard) is chosen up front so the math fits
the player.

**Display:** projected large on a **wall or screen**. Everything must read from a distance.

---

## 2. The core mechanic (the soul of the game — do not remove)

Three things define the experience. A redesign may restyle them, but must keep them:

1. **Dark field + flashlight reveal.** The background is near‑black. Answer tokens are
   invisible in the dark and **fade in by proximity** to the lens. The further a token is
   from the lens center, the more hidden it is. This “reveal in the dark” is the game.
   *→ The background must stay dark/low‑key. A bright/busy background kills the mechanic.*

2. **Hand‑driven lens.** A circular lens follows the player’s hand position 1:1 across the
   screen. Motion is smooth and fluid.

3. **Fist = select.** Open hand = search/move. Closed hand (fist) = “pick the answer the
   lens is on.” The lens gives a satisfying **iris‑close** animation toward the chosen
   answer on selection.

Everything interactive (answer tokens, menu buttons) must therefore be **selectable by a
circular lens**: generously spaced, with a clear single “nearest” target, and with obvious
**hover → armed → select** feedback.

---

## 3. How a player plays (flow / state machine)

```
        ┌─────────────────────────────────────────────┐
        │  ATTRACT (Start screen)                      │
        │  Pick a difficulty with the lens + a fist    │
        └───────────────┬─────────────────────────────┘
                        │  (KOLAY / ORTA / ZOR chosen)
                        ▼
        ┌─────────────────────────────────────────────┐
        │  PLAYING                                     │
        │  5 questions · one 120s countdown            │
        │  reveal tokens → fist on the right answer    │
        │  RESET button (top‑right) → back to ATTRACT  │
        └───────────────┬─────────────────────────────┘
                        │  (5 answered  OR  timer hits 0)
                        ▼
        ┌─────────────────────────────────────────────┐
        │  RESULT  (brief summary, ~4s)                │
        │  "Bitti! / Süre doldu!  Doğru: N/5"          │
        └───────────────┬─────────────────────────────┘
                        │  (auto)
                        ▼
                   back to ATTRACT  (fresh player starts clean)
```

**Per question:** a new prompt appears at top; the dark field re‑fills with tokens. The
player reveals tokens, lands the lens on the correct one, and fists. One shot per question:
- **Correct** → a green “Doğru!” flash, the token punches + flashes gold.
- **Wrong** → a red “Yanlış”, the token flashes red.
- Either way, a short pause, then the next question. Score increments only on correct.

The **correct answer appears 2–3 times** among the decoys (well spread out) so the game
isn’t frustratingly hard to find.

---

## 4. Screens & layout

The play area is a **16:9** frame. Think of it as world coordinates with the center at
(0,0); the screen spans roughly **X ∈ [−8.9, +8.9]**, **Y ∈ [−5, +5]**. Positions below
are given in that space so you understand the composition.

### 4.1 Start / Attract screen

```
┌──────────────────────────────────────────────────────────────────┐
│   ✦  drifting, twinkling, rotating math symbols fill the whole     │
│      background (√ π ² ½ ¾ × ÷ + − = % ∞ and digits, 9 colors),    │
│      over a soft dark "nebula" of colored glows                    │
│                                                                    │
│                    ★  M A T E M A T İ K   A V I  ★   (glowing)     │
│                                                                    │
│                          Seviyeni seç                              │
│                                                                    │
│     ╭──────────╮        ╭──────────╮        ╭──────────╮          │
│     │  KOLAY   │        │   ORTA   │        │   ZOR    │           │
│     ╰──────────╯        ╰──────────╯        ╰──────────╯          │
│    ilkokul-ortaokul    ortaokul - lise     lise - üniversite      │
│      (green)              (amber)             (red)               │
│                                                                    │
│            Merceği bir seviyeye getir ve elini kapat               │
└──────────────────────────────────────────────────────────────────┘
```

Elements:
- **Backdrop:** layered soft colored glows (a calm dark “space”), intentionally low‑key.
- **Floating symbols:** ~40 math glyphs drifting upward, swaying, slowly spinning, gently
  twinkling in alpha. Decorative; sets the “math is playful” tone.
- **Title:** “MATEMATİK AVI” — big, warm, glowing. The hero.
- **Subtitle prompt:** “Seviyeni seç” (= “choose your level”).
- **Three difficulty buttons** (see §5.3) laid out in a row, color‑coded, each with a
  small school‑level **caption** underneath.
- **Gesture hint** at the bottom: “Merceği bir seviyeye getir ve elini kapat”
  (= “bring the lens onto a level and close your hand”).
- The **lens** is also visible here (it’s the cursor); the player drives it over a button.

### 4.2 Gameplay screen

```
┌──────────────────────────────────────────────────────────────────┐
│ Soru 1/5 (Orta)                12 × 5                    ╭──────╮ │
│ Doğru: 3                                                 │RESET │ │
│ 1:48                                                     ╰──────╯ │
│                                                                    │
│            (dark field — answers hidden until revealed)           │
│                                                                    │
│              7        ·       60 ✦       ·      48                  │
│                    ·     (lens glow reveals nearby)    ·            │
│         54   ·        ╭ ◯ ╮  the lens / flashlight        ·   63   │
│                       ╰───╯  follows the hand                       │
│              ·     61      ·       60      ·        58              │
│                                                                    │
│                       (more hidden tokens…)                        │
└──────────────────────────────────────────────────────────────────┘
```

Elements:
- **Question prompt** — top center, large. e.g. “12 × 5”, “√64”, “x² = 49”, “¾ − ¼”.
- **Counters** — top‑left, stacked so the eye reads them in one glance:
  - “Soru X/5” (question number) + “(level)” tag,
  - “Doğru: N” (correct count),
  - the **timer** “M:SS”, the biggest of the three. In the **last 10 seconds** it turns
    **red and pulses** for urgency.
- **RESET button** — small pill pinned in the **top‑right corner**; sends the current
  player back to the start screen so the next person starts fresh.
- **The dark field of answer tokens** — the main stage (see §5.2).
- **The lens** — the moving flashlight (see §5.1).
- **Result flash** — on answer, a big centered “Doğru!” (green) / “Yanlış” (red) momentarily.

### 4.3 Result screen

A brief (~4s) centered summary over the dark field:
- “Bitti!” (finished) or “Süre doldu!” (time’s up)
- “Doğru: N/5”
Then it returns to the start screen automatically.

---

## 5. Interactive elements & their states

### 5.1 The Lens (flashlight / magnifier)

- A **soft circular light pool** + a **glowing ring** that together follow the hand.
- Hidden when no hand is present; appears when a hand is detected.
- **Selection feedback (“iris‑close”)**: when the player fists, the circle **contracts and
  slides toward the chosen answer**, holds briefly, then re‑opens — a tactile “I picked
  THIS” moment. It never fully closes.
- Motion is smoothed so it feels fluid even though the camera updates ~30×/sec.
- *Design opportunity:* the look of the flashlight/magnifier and the select animation are
  prime candidates for a richer treatment (lens flare, chromatic edge, particles, etc.) —
  as long as it still reads as “a light revealing the dark.”

### 5.2 Answer Token

A single number or symbol in the field. States:

| State | Meaning | Current look |
|------|---------|--------------|
| **Hidden** | far from the lens | invisible (alpha ~0) in the dark |
| **Revealed** | lens is near | fades in (soft white), brighter the closer it is |
| **Armed** | the single nearest‑to‑center token (the one a fist would pick) | grows, glows **gold**, gets a soft halo |
| **Confirmed (correct)** | selected & right | gold punch + flash, then fades |
| **Confirmed (wrong)** | selected & wrong | red flash, then fades |

- ~36 tokens per question on a jittered grid (never overlapping; always a clear “nearest”).
- Glyphs used: digits, `× ÷ − √ ² ³ ¼ ½ ¾ ( ) ! =` (all covered by the game font).
- *Design opportunity:* token typography, the reveal falloff, the armed glow/halo, and the
  correct/wrong confirmation moments.

### 5.3 Gesture Button (menu pill)

Used for the 3 difficulty buttons and the in‑game RESET. Selected the same way as a token:
move the lens over it, fist to press.

| State | Current look |
|------|--------------|
| **Idle** | a colored **pill** with a white rim, gently pulsing (breathing) |
| **Hover** (lens over it) | brightens + grows + the glow halo intensifies |
| **Press** (fist) | a quick punch; triggers the iris‑close on the lens |

- Difficulty buttons are color‑coded and carry a **caption** under the pill (the age/school
  range). Labels auto‑fit so text never overflows.
- *Design opportunity:* button shape, material, hover/press juice, the caption treatment.

---

## 6. Difficulty system (content, not visuals — for context)

Chosen on the start screen; sets the question pool for all 5 questions.

| Button | Caption | Question style (examples) |
|--------|---------|---------------------------|
| **KOLAY** (Easy) | ilkokul‑ortaokul | times tables, +/−, exact division, small squares/roots, ¼ ½ ¾ |
| **ORTA** (Medium) | ortaokul‑lise | bigger products, squares/roots, cubes, order of operations, negatives |
| **ZOR** (Hard) | lise‑üniversite | solve‑for‑x, x²=n, big squares/roots, factorials, power sums, parentheses |

All questions are designed to be solvable **at a glance** (no long working). Wrong answers
include the classic “trap” mistakes as decoys.

---

## 7. Current visual language (your starting palette — change freely)

- **Mood:** playful, friendly, “math is an adventure,” museum‑grade but warm.
- **Background:** dark (near‑black) with subtle colored glows. **Stays dark.**
- **Accent / semantic colors:**
  - Correct = **green**, Wrong = **red**, Armed/selected highlight = **gold/amber**.
  - Difficulty: KOLAY **green**, ORTA **amber**, ZOR **red**.
- **Typography:** a rounded, friendly display face (currently “Fredoka”, patched to cover
  Turkish letters **İ ğ Ş ç ö ü** and math symbols **√ π ∞ ² ³ ½ ¼ ¾**). Big, high‑contrast.
- **Motion:** everything eases; nothing pops. Idle elements breathe; the timer pulses when
  low; symbols drift; the lens glides.

---

## 8. Must‑respect constraints (read before designing)

1. **Keep the field dark.** The reveal‑in‑the‑dark mechanic needs a low‑key background. No
   bright full‑screen art behind the gameplay tokens.
2. **Everything interactive must be lens‑selectable.** Buttons and tokens need generous
   spacing and a clear single nearest target. Don’t cram selectable items together.
3. **Readable from across a room (wall projection).** Large type, strong contrast, no thin
   hairlines or tiny captions as the only signal.
4. **All‑ages, walk‑up‑and‑play.** Self‑explanatory; minimal text; obvious affordances.
5. **Glyph coverage.** All text uses **Turkish letters + math symbols**. If you introduce a
   new font, it must render: `İ ı ğ Ğ Ş ş ç Ç ö ü` and `√ π ∞ ² ³ ½ ¼ ¾ × ÷ − = ( ) !`.
   (Otherwise glyphs render as empty boxes — fatal for a math game.)
6. **Clear interaction states.** Hover / armed / select / correct / wrong must each be
   unmistakable at a glance.
7. **16:9, but flexible.** Design for 16:9; elements should also survive other aspect ratios
   (the RESET button, for instance, hugs the true top‑right corner on any aspect).

---

## 9. What to (re)design — the wishlist

Open targets, roughly in priority order:

1. **Start screen “wow.”** A memorable title treatment, a richer but still‑dark backdrop,
   and three difficulty buttons that look inviting and premium. This is the first
   impression at the exhibit.
2. **The lens / flashlight.** Make the magnifier feel magical — the reveal edge, the glow,
   and especially the **iris‑close selection** animation.
3. **Answer tokens.** Typography + the reveal falloff + the **armed** highlight + the
   **correct/wrong** confirmation moments (these are the “juice” of the game).
4. **Buttons** (difficulty + RESET): shape, material, hover/press feedback, captions.
5. **HUD:** the question prompt, the top‑left counters, and the **low‑time urgency** state.
6. **Result moment:** a more rewarding end‑of‑round summary.
7. **A cohesive color + type system** tying all of the above together.

---

## 10. Technical notes (so designs stay feasible)

- Engine: **Unity** (2D, orthographic camera, size 5). Most visuals are **world‑space**
  (lens, tokens, buttons, start‑screen art); only the question prompt, counters and result
  text are screen‑space UI.
- Current art is **generated at runtime** (soft circles, discs, rings) — there are no
  imported textures yet. You are free to propose **actual art assets** (sprites, textures,
  shaders, particle looks); they can be imported.
- Input is **OSC over UDP** from a Python hand‑tracking detector → Unity (normalized hand
  X/Y in [0,1], present flag, open/fist gesture). This contract is fixed; visuals don’t
  affect it.
- Layering is by sorting order (background glows behind, tokens in the field, lens glow as a
  reveal layer, UI/buttons on top).
- Performance budget is modest (single PC driving a projector); favor a handful of clean
  layers over heavy overdraw / hundreds of particles.

---

## 11. On‑screen Turkish strings (for reference / localization)

| String | Meaning | Where |
|--------|---------|-------|
| MATEMATİK AVI | “Math Hunt” (title) | Start |
| Seviyeni seç | “Choose your level” | Start |
| KOLAY / ORTA / ZOR | Easy / Medium / Hard | Start buttons |
| ilkokul‑ortaokul / ortaokul‑lise / lise‑üniversite | school‑level captions | Start buttons |
| Merceği bir seviyeye getir ve elini kapat | “Bring the lens onto a level and close your hand” | Start hint |
| Soru X/5 | “Question X/5” | Gameplay |
| Doğru: N | “Correct: N” | Gameplay |
| Doğru! / Yanlış | “Correct! / Wrong” | Answer flash |
| RESET | reset to start | Gameplay (top‑right) |
| Bitti! / Süre doldu! | “Finished! / Time’s up!” | Result |

---

### TL;DR for the designer
Keep the **dark flashlight‑reveal** game intact and **lens‑selectable**, make it **big and
readable for a wall**, cover **Turkish + math glyphs**, and pour the love into the **start
screen, the lens, the tokens’ reveal/armed/confirm states, and the buttons**. Everything
else — palette, typography, motion, art style — is yours to reinvent.
```
