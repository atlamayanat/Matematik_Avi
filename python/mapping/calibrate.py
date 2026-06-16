"""Interactive N-point calibration for the "camera faces the players" setup.

Run:  python main.py --calibrate

Physical model: the camera sits on top of the screen looking AT the players, so
it CANNOT see the projected image. The player stands at a fixed distance and
plays in the air, so their hand sweeps a single plane -> camera<->screen is an
exact 2D homography (see mapping/homography.py).

Flow (everything is shown FULL-SCREEN on the projector, which is what the player
looks at):

  1. A target dot appears at a known screen position (a 3x3 grid by default).
  2. A LIVE cursor follows the player's hand (provisional raw mapping). The
     player MOVES the cursor onto the target -- closed-loop, so they don't have
     to guess where to reach.
  3. They hold still; a ring fills over ``dwell_seconds`` and the point is
     captured automatically. (A helper at the PC can also press SPACE.)
  4. After all points: a VERIFICATION screen shows the real calibrated cursor
     tracking the targets, plus the reprojection error. A = accept & save,
     R = redo, ESC = cancel.

Capture uses the PALM CENTROID of the LARGEST visible hand (the operator
standing closest), the SAME point the live detector maps during play
(main.py: sel.locked.centroid_px) -- so there is no systematic offset between
calibration and gameplay.
"""

from __future__ import annotations

import math
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from camera import create_camera
from detection import HandRecognizer
from detection.types import HandObservation
from mapping.homography import Homography

# ---- colours (BGR) ----
_BG = (12, 8, 20)
_TARGET = (60, 230, 255)       # amber target ring
_TARGET_DONE = (90, 200, 90)   # captured targets (faint green)
_CURSOR = (255, 220, 60)       # cyan-ish live cursor
_DWELL = (120, 255, 180)       # dwell progress ring
_TEXT = (235, 235, 235)
_GOOD = (110, 230, 120)
_BAD = (90, 90, 240)


def _largest_hand(hands: List[HandObservation]) -> Optional[HandObservation]:
    """Closest operator = largest apparent hand; ignores bystanders."""
    return max(hands, key=lambda h: h.span01) if hands else None


def _grid_targets(gx: int, gy: int, inset: float) -> List[Tuple[float, float]]:
    """Row-major normalized target positions, inset from the screen edges."""
    xs = np.linspace(inset, 1.0 - inset, gx)
    ys = np.linspace(inset, 1.0 - inset, gy)
    return [(float(x), float(y)) for y in ys for x in xs]


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def _put(canvas, text, org, scale=1.0, color=_TEXT, thick=2):
    cv2.putText(canvas, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick,
                cv2.LINE_AA)


def _put_center(canvas, text, cy, scale=1.0, color=_TEXT, thick=2):
    w = canvas.shape[1]
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    _put(canvas, text, (int((w - tw) / 2), cy), scale, color, thick)


def _draw_thumb(canvas, frame_rgb, hand: Optional[HandObservation]):
    """Small camera preview (top-right) so a helper at the PC can confirm
    the hand is being detected, even though the PLAYER looks at the targets."""
    H, W = canvas.shape[:2]
    tw = max(240, W // 6)
    fh, fw = frame_rgb.shape[:2]
    th = int(tw * fh / fw)
    thumb = cv2.cvtColor(cv2.resize(frame_rgb, (tw, th)), cv2.COLOR_RGB2BGR)
    if hand is not None:
        cx = int(hand.centroid01[0] * tw)
        cy = int(hand.centroid01[1] * th)
        cv2.circle(thumb, (cx, cy), 7, _CURSOR, 2)
    x0, y0 = W - tw - 24, 24
    canvas[y0:y0 + th, x0:x0 + tw] = thumb
    cv2.rectangle(canvas, (x0, y0), (x0 + tw, y0 + th),
                  (80, 80, 80) if hand is None else _TARGET_DONE, 2)


def run_calibration(cfg) -> bool:
    """Returns True if a new calibration was saved, False if cancelled."""
    cal = cfg.calibration
    proj_w, proj_h = int(cal.proj_w), int(cal.proj_h)
    grid = cal.get("grid", [3, 3])
    gx, gy = int(grid[0]), int(grid[1])
    inset = float(cal.get("target_inset", 0.06))
    dwell_s = float(cal.get("dwell_seconds", 1.5))
    dwell_r = float(cal.get("dwell_radius", 0.05))   # stillness radius (normalized)
    off_x = int(cal.get("display_offset_x", 0))       # move window onto the projector
    accept_err = float(cal.get("accept_error", 0.03))
    # Cursor gain: amplify hand motion around centre so the player reaches the
    # corner targets with a COMFORTABLE, IN-FRAME hand motion (their hand exits
    # the camera frame long before the frame edge). Capture still uses the RAW
    # centroid_px, so this only changes how far they physically reach -- and the
    # fitted homography then keeps the whole stage reachable in-frame during play.
    gain = float(cal.get("cursor_gain", 1.5))
    sa = cal.get("stage_aspect", [16, 9])
    aw, ah = float(sa[0]), float(sa[1])

    # The web game renders into a CENTERED, letterboxed 16:9 "stage" inside the
    # projector frame (styles.css #stage). So the game's [0,1] coord space is the
    # STAGE, not the full frame. We draw targets inside that same stage rect and
    # map the homography into STAGE-normalized coords -> the live detector then
    # emits exactly what input.js consumes, on ANY projector aspect ratio.
    # (On a 16:9 projector the stage fills the frame, so this is a no-op.)
    frame_w, frame_h = proj_w, proj_h             # config = projector NATIVE resolution
    stage_w = min(float(frame_w), frame_h * aw / ah)
    stage_h = stage_w * ah / aw
    sx0 = (frame_w - stage_w) / 2.0
    sy0 = (frame_h - stage_h) / 2.0

    targets01 = _grid_targets(gx, gy, inset)
    n = len(targets01)
    dst_px = [(tx * stage_w, ty * stage_h) for (tx, ty) in targets01]   # stage-local px

    homography = Homography(cfg)
    # Homography output space = the stage, so map_point returns stage-normalized.
    homography.proj_w = int(round(stage_w))
    homography.proj_h = int(round(stage_h))
    win = "Kalibrasyon"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    if off_x:
        cv2.moveWindow(win, off_x, 0)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    cam = create_camera(cfg)
    recognizer = HandRecognizer(cfg)
    flip = bool(cfg.camera.flip_horizontal)

    captured_src: List[Tuple[float, float]] = []   # camera-px palm centroids
    idx = 0
    phase = "capture"            # "capture" -> "verify"
    dwell_anchor: Optional[Tuple[float, float]] = None
    dwell_t0 = 0.0
    flash_until = 0.0
    ts = 0
    pulse = 0
    fit_err: Optional[float] = None

    def scale_pt(nx, ny):
        """Stage-normalized [0,1] -> canvas px (inside the letterboxed stage rect)."""
        return (int(sx0 + nx * stage_w), int(sy0 + ny * stage_h))

    # Allocate the canvas ONCE and refill it each frame. Re-allocating a ~6 MB
    # 1080p array every loop (at hundreds of fps with no cap) churns memory and
    # starves the MediaPipe worker thread -> the cursor "freezes". See _show().
    canvas = np.empty((proj_h, proj_w, 3), dtype=np.uint8)

    try:
        while True:
            frame = cam.read()
            if frame is None:
                if (cv2.waitKey(15) & 0xFF) == 27:   # 15ms: pump GUI, don't busy-spin
                    return False
                continue
            ts += 33
            recognizer.submit(frame.rgb, ts)
            hand = _largest_hand(recognizer.get_observations())
            now = time.monotonic()
            pulse += 1

            canvas[:] = _BG
            _draw_thumb(canvas, frame.rgb, hand)
            # Outline of the game's letterboxed stage = the actual play area.
            cv2.rectangle(canvas, (int(sx0), int(sy0)),
                          (int(sx0 + stage_w), int(sy0 + stage_h)), (45, 40, 70), 2)
            if now < flash_until:   # brief "captured!" border flash
                cv2.rectangle(canvas, (0, 0), (proj_w - 1, proj_h - 1), _TARGET_DONE, 14)

            # ---------------- CAPTURE PHASE ----------------
            if phase == "capture":
                # past targets (captured) faint green
                for j in range(idx):
                    cv2.circle(canvas, scale_pt(*targets01[j]), 14, _TARGET_DONE, 2)

                # current target: pulsing amber ring + crosshair
                tx, ty = targets01[idx]
                tc = scale_pt(tx, ty)
                rad = int(34 + 10 * math.sin(pulse * 0.15))
                cv2.circle(canvas, tc, rad, _TARGET, 3)
                cv2.drawMarker(canvas, tc, _TARGET, cv2.MARKER_CROSS, 26, 2)

                # provisional live cursor: raw hand position AMPLIFIED around centre
                # (closed loop). Display uses the gained point; dwell + capture use
                # the RAW centroid so the homography stays accurate.
                progress = 0.0
                if hand is not None:
                    cur = hand.centroid01                       # raw (dwell + capture)
                    disp = (_clamp01(0.5 + (cur[0] - 0.5) * gain),
                            _clamp01(0.5 + (cur[1] - 0.5) * gain))
                    cc = scale_pt(disp[0], disp[1])
                    cv2.circle(canvas, cc, 16, _CURSOR, -1)
                    cv2.circle(canvas, cc, 16, (20, 20, 20), 2)

                    # Warn when the hand is about to leave the camera frame.
                    if min(cur[0], cur[1], 1.0 - cur[0], 1.0 - cur[1]) < 0.04:
                        _put_center(canvas, "Elini cerceve icinde tut", proj_h - 120,
                                    0.9, _BAD, 2)

                    # dwell = hold still anywhere; player chooses to hold ON the target
                    if dwell_anchor is None or math.dist(cur, dwell_anchor) > dwell_r:
                        dwell_anchor = cur
                        dwell_t0 = now
                    progress = min(1.0, (now - dwell_t0) / dwell_s)
                    if progress > 0.02:
                        cv2.ellipse(canvas, cc, (26, 26), 0, -90,
                                    -90 + int(360 * progress), _DWELL, 4)
                    captured_now = progress >= 1.0
                else:
                    dwell_anchor = None
                    _put_center(canvas, "El bulunamadi - eli kameraya goster",
                                proj_h - 80, 1.0, _BAD, 2)
                    captured_now = False

                _put(canvas, f"[{idx + 1}/{n}]  Imleci HEDEFE getir ve sabit tut",
                     (40, 60), 1.1, _TEXT, 2)
                _put(canvas, "SPACE: yakala   B: geri   R: bastan   ESC: iptal",
                     (40, proj_h - 30), 0.7, (170, 170, 170), 2)

                key = _show(win, canvas)

                if key == 27:                       # ESC
                    return False
                if key in (ord('r'), ord('R')):
                    captured_src.clear(); idx = 0; dwell_anchor = None; continue
                if key in (ord('b'), ord('B')) and idx > 0:
                    idx -= 1; captured_src.pop(); dwell_anchor = None; continue

                manual = key == 32 and hand is not None
                if (captured_now or manual) and hand is not None:
                    captured_src.append((float(hand.centroid_px[0]),
                                         float(hand.centroid_px[1])))
                    print(f"[calibrate] captured point {idx + 1}/{n} at "
                          f"{tuple(round(v) for v in hand.centroid_px)}")
                    idx += 1
                    dwell_anchor = None
                    flash_until = now + 0.15
                    if idx >= n:
                        fit_err = homography.fit(captured_src, dst_px)
                        print(f"[calibrate] fit done, error = {fit_err * 100:.2f}% of screen")
                        phase = "verify"
                continue

            # ---------------- VERIFY PHASE ----------------
            for (tx, ty) in targets01:
                cv2.circle(canvas, scale_pt(tx, ty), 16, _TARGET_DONE, 2)

            if hand is not None:
                nx, ny = homography.map_point(hand.centroid_px[0],
                                              hand.centroid_px[1], hand.centroid01)
                cc = scale_pt(nx, ny)
                cv2.circle(canvas, cc, 18, _CURSOR, -1)
                cv2.circle(canvas, cc, 18, (20, 20, 20), 2)
            else:
                _put_center(canvas, "El bulunamadi", proj_h - 80, 1.0, _BAD, 2)

            good = fit_err is not None and fit_err <= accept_err
            verdict = "IYI" if good else "KOTU - tekrar dene (R)"
            err_col = _GOOD if good else _BAD
            _put(canvas, "DOGRULAMA: imleci hedeflerin uzerinde gezdir, otursun mu bak.",
                 (40, 60), 1.0, _TEXT, 2)
            _put(canvas, f"Hata: {fit_err * 100:.2f}%  ({verdict})", (40, 110), 1.0,
                 err_col, 2)
            _put(canvas, "A / ENTER: KAYDET     R: BASTAN     ESC: iptal",
                 (40, proj_h - 30), 0.8, (190, 190, 190), 2)

            key = _show(win, canvas)
            if key == 27:
                return False
            if key in (ord('r'), ord('R')):
                captured_src.clear(); idx = 0; phase = "capture"
                dwell_anchor = None; homography.clear(); continue
            if key in (ord('a'), ord('A'), 13, 10):   # A / ENTER
                homography.save(captured_src, dst_px, cam.resolution, flip)
                print("[calibrate] DONE.")
                return True
    finally:
        cam.close()
        recognizer.close()
        cv2.destroyWindow(win)


_last_show_t = [0.0]


def _show(win, canvas, target_fps: int = 60) -> int:
    """Show a frame, cap the loop to ~target_fps, and return the pressed key.

    The wait is done with cv2.waitKey (not time.sleep): it BOTH pumps the OpenCV
    window's event loop (so the fullscreen window stays responsive) AND yields the
    CPU to the MediaPipe worker thread. A flat waitKey(1) here let the loop spin at
    hundreds of fps, starving inference until the cursor appeared to freeze."""
    cv2.imshow(win, canvas)
    budget = 1.0 / float(target_fps)
    wait_ms = int((budget - (time.monotonic() - _last_show_t[0])) * 1000)
    key = cv2.waitKey(max(1, wait_ms)) & 0xFF
    _last_show_t[0] = time.monotonic()
    return key
