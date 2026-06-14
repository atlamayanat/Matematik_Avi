"""Gesture Exhibit - detection entry point.

Pipeline per frame:
    camera -> GestureRecognizer -> active-player selection -> gesture FSM
           -> homography map -> One Euro smoothing -> OSC /hand -> Unity

Usage (run from this 'python/' folder):
    python download_model.py        # once, fetch the model
    python main.py                  # run the detector
    python main.py --calibrate      # 4-corner projector calibration
    python main.py --no-preview     # headless (no OpenCV window)
    python main.py --config foo.json

Hotkeys in the preview window:  ESC = quit,  C = recalibrate.
"""

from __future__ import annotations

import argparse
import time

import cv2

from config import load_config
from camera import create_camera
from detection import HandRecognizer
from selection import ActivePlayerSelector
from gesture import GestureFSM, FIST
from smoothing import CursorSmoother
from mapping import Homography
from mapping.calibrate import run_calibration
from net import create_sender

_QUIT = "quit"
_RECALIBRATE = "recalibrate"


class MonotonicMs:
    """Strictly increasing millisecond clock for recognize_async timestamps."""
    def __init__(self):
        self._last = -1

    def now(self) -> int:
        ts = int(time.monotonic() * 1000)
        if ts <= self._last:
            ts = self._last + 1
        self._last = ts
        return ts


def _draw_overlay(bgr, cfg, observations, sel, committed, present,
                  mapped, fps, calibrated):
    h, w = bgr.shape[:2]
    ap = cfg.active_player

    # ROI rectangle (interaction zone).
    cv2.rectangle(bgr,
                  (int(ap.roi_x_min * w), int(ap.roi_y_min * h)),
                  (int(ap.roi_x_max * w), int(ap.roi_y_max * h)),
                  (80, 80, 80), 1)

    locked = sel.locked
    for obs in observations:
        xs = [p[0] for p in obs.landmarks_px]
        ys = [p[1] for p in obs.landmarks_px]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        is_locked = locked is not None and obs is locked
        color = (0, 255, 0) if is_locked else (130, 130, 130)
        cv2.rectangle(bgr, (x1, y1), (x2, y2), color, 2 if is_locked else 1)
        label = f"{obs.gesture} {obs.gesture_score:.2f} sz{obs.span01:.2f}"
        cv2.putText(bgr, label, (x1, max(y1 - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        if is_locked:
            cx, cy = int(obs.centroid_px[0]), int(obs.centroid_px[1])
            cv2.circle(bgr, (cx, cy), 6, (0, 255, 0), -1)

    # Status bar.
    state_color = (0, 0, 255) if committed == FIST else (0, 200, 255)
    lines = [
        f"FPS {fps:4.1f}   hands {len(observations)}   "
        f"{'CALIBRATED' if calibrated else 'NOT CALIBRATED (raw coords)'}",
        f"present={int(present)}  state={committed}  "
        f"mapped=({mapped[0]:.3f},{mapped[1]:.3f})",
        "ESC quit   C recalibrate",
    ]
    for i, line in enumerate(lines):
        cv2.putText(bgr, line, (12, 24 + 22 * i),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    state_color if i == 1 else (255, 255, 255), 2)


def run_detector(cfg, preview: bool) -> str:
    cam = create_camera(cfg)
    recognizer = HandRecognizer(cfg)
    homography = Homography(cfg)
    selector = ActivePlayerSelector(cfg)
    fsm = GestureFSM(cfg)
    smoother = CursorSmoother(cfg.smoothing.min_cutoff, cfg.smoothing.beta,
                              cfg.smoothing.d_cutoff)
    sender = create_sender(cfg)   # OSC | WebSocket | her ikisi (config.json net.transport)
    clock = MonotonicMs()

    frame_budget = 1.0 / float(cfg.osc.send_rate_hz)
    win = cfg.preview.window_name
    if preview:
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    last_xy = (0.5, 0.5)
    committed = "searching"
    mapped = (0.5, 0.5)
    present = False
    observations = []
    sel = None
    last_rid = -1
    fps = 0.0
    fps_t = time.monotonic()

    _net = cfg.get("net", None)
    _transport = str(getattr(_net, "transport", "osc") if _net is not None else "osc").lower()
    print(f"[detector] running. transport={_transport}  OSC -> {cfg.osc.host}:{cfg.osc.port}  "
          f"calibrated={homography.is_calibrated}")
    try:
        while True:
            loop_start = time.monotonic()

            frame = cam.read()
            if frame is None:
                # Transient grab failure; keep the cursor parked, don't busy-spin.
                sender.send_absent(*last_xy)
                if preview and (cv2.waitKey(1) & 0xFF) == 27:
                    return _QUIT
                time.sleep(0.01)
                continue

            recognizer.submit(frame.rgb, clock.now())

            # Run the pipeline only on a NEW inference result. The loop spins at
            # ~60 Hz but MediaPipe completes only ~20-30 Hz; feeding One Euro (and
            # ticking the selector/FSM frame counters) with duplicate frames is what
            # defeated the smoothing and made the lens step. We still emit an OSC
            # packet every loop (~60 Hz heartbeat) below so Unity never starves.
            rid = recognizer.result_id
            if rid != last_rid:
                last_rid = rid
                observations = recognizer.get_observations()
                sel = selector.update(observations)

                if sel.just_acquired:
                    smoother.reset()
                    fsm.reset()
                if sel.just_released:
                    fsm.reset()
                    smoother.reset()

                if sel.locked is not None:
                    committed = fsm.update(sel.locked.gesture)
                    raw = homography.map_point(
                        sel.locked.centroid_px[0], sel.locked.centroid_px[1],
                        sel.locked.centroid01)
                    t = time.monotonic()
                    mapped = smoother(t, raw[0], raw[1])
                    last_xy = mapped
                    present = True
                else:
                    committed = "searching"
                    present = False

            # ~60 Hz OSC heartbeat; position only advances on a fresh inference.
            if present:
                sender.send_hand(mapped[0], mapped[1], True, committed)
            else:
                sender.send_absent(*last_xy)

            # FPS (EMA).
            now = time.monotonic()
            inst = 1.0 / max(now - fps_t, 1e-6)
            fps = 0.9 * fps + 0.1 * inst if fps else inst
            fps_t = now

            if preview:
                bgr = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)
                _draw_overlay(bgr, cfg, observations, sel, committed, present,
                              mapped, fps, homography.is_calibrated)
                cv2.imshow(win, bgr)
                key = cv2.waitKey(1) & 0xFF
                if key == 27:               # ESC
                    return _QUIT
                if key in (ord('c'), ord('C')):
                    return _RECALIBRATE

            # Rate cap: never flood Unity faster than its render rate.
            sleep = frame_budget - (time.monotonic() - loop_start)
            if sleep > 0:
                time.sleep(sleep)
    finally:
        cam.close()
        recognizer.close()
        _close = getattr(sender, "close", None)
        if callable(_close):
            _close()   # WS sunucusunu kapat / portu serbest bırak (recalibrate yeniden-başlatması için)
        if preview:
            cv2.destroyAllWindows()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gesture Exhibit detector")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--calibrate", action="store_true",
                        help="run 4-corner projector calibration and exit")
    parser.add_argument("--no-preview", action="store_true",
                        help="run without the OpenCV preview window")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.calibrate:
        run_calibration(cfg)
        return 0

    preview = not args.no_preview
    while True:
        action = run_detector(cfg, preview)
        if action == _RECALIBRATE:
            run_calibration(cfg)
            continue   # restart detector; Homography reloads the new calib.json
        break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
