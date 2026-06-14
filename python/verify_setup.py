"""Smoke test: construct every pipeline component (no camera needed).

Validates that dependencies are installed, the MediaPipe Tasks GestureRecognizer
API names/params are correct, the model loads, and all modules wire together.

Run:  python verify_setup.py
"""

from __future__ import annotations

import time
import numpy as np

from config import load_config
from detection import HandRecognizer
from detection.types import HandObservation
from selection import ActivePlayerSelector
from gesture import GestureFSM, FIST, SEARCHING
from smoothing import CursorSmoother
from mapping import Homography
from net import OscSender


def main() -> int:
    cfg = load_config("config.json")
    print("config.json loaded OK")

    # 1. MediaPipe GestureRecognizer (LIVE_STREAM) + model file.
    rec = HandRecognizer(cfg)
    fake_rgb = np.zeros((cfg.camera.request_height, cfg.camera.request_width, 3),
                        dtype=np.uint8)
    rec.submit(fake_rgb, int(time.monotonic() * 1000))
    time.sleep(0.2)                      # let the async callback run
    _ = rec.get_observations()           # empty (black frame), but must not raise
    rec.close()
    print("MediaPipe GestureRecognizer constructed, fed a frame, closed OK")

    # 2. Selection + FSM logic with synthetic hands.
    sel = ActivePlayerSelector(cfg)
    fsm = GestureFSM(cfg)

    def fake_hand(x, y, span, gesture):
        return HandObservation(
            centroid01=(x, y), centroid_px=(x * 1280, y * 720), span01=span,
            gesture=gesture, gesture_score=0.9, handedness="Right",
            detection_score=0.9, landmarks_px=[(int(x * 1280), int(y * 720))] * 21)

    # A big central hand should get locked; a tiny edge hand should not steal.
    big = fake_hand(0.5, 0.5, 0.30, "Open_Palm")
    small = fake_hand(0.95, 0.5, 0.05, "Open_Palm")
    res = None
    for _ in range(5):
        res = sel.update([big, small])
    assert res.locked is big, "selector should lock the large central hand"
    print("ActivePlayerSelector locks the largest in-ROI hand OK")

    # FSM should require several stable fist frames before committing.
    state = SEARCHING
    for _ in range(cfg.gesture_fsm.stable_frames_fist + 1):
        state = fsm.update("Closed_Fist")
    assert state == FIST, "FSM should commit FIST after stable frames"
    state = fsm.update("Open_Palm")  # one frame back to open -> not yet committed
    assert state == FIST, "FSM should debounce a single open frame"
    print("GestureFSM debounce (enter/exit hysteresis) OK")

    # 3. Smoothing + homography + OSC construct & run.
    sm = CursorSmoother(cfg.smoothing.min_cutoff, cfg.smoothing.beta,
                        cfg.smoothing.d_cutoff)
    t = time.monotonic()
    sm(t, 0.5, 0.5); sm(t + 0.016, 0.6, 0.4)
    homo = Homography(cfg)
    nx, ny = homo.map_point(640, 360, (0.5, 0.5))
    assert 0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0
    print(f"CursorSmoother + Homography OK (calibrated={homo.is_calibrated})")

    osc = OscSender(cfg)
    osc.send_hand(0.5, 0.5, True, FIST)   # localhost UDP send; no receiver needed
    print(f"OscSender sent a /hand packet to {cfg.osc.host}:{cfg.osc.port} OK")

    print("\nALL CHECKS PASSED - the Python detector is ready. "
          "Run:  python main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
