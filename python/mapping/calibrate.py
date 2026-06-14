"""Interactive 4-corner calibration.

Run:  python main.py --calibrate

The projector shows the game full-screen. The operator points their index
finger at each projected corner in turn (TOP-LEFT, TOP-RIGHT, BOTTOM-RIGHT,
BOTTOM-LEFT) and presses SPACE to capture. After 4 captures the homography is
built and saved to calib.json; it is reloaded automatically on every later run,
so you only recalibrate if the camera or projector is physically moved.

Capture uses the INDEX-FINGER TIP (landmark 8) of the LARGEST visible hand
(the operator standing closest), so bystanders do not corrupt calibration.
"""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import cv2

from camera import create_camera
from detection import HandRecognizer
from detection.types import HandObservation
from mapping.homography import Homography, CORNER_ORDER

_INDEX_TIP = 8


def _largest_hand(hands: List[HandObservation]) -> Optional[HandObservation]:
    return max(hands, key=lambda h: h.span01) if hands else None


def run_calibration(cfg) -> bool:
    """Returns True if a new calibration was saved, False if cancelled."""
    homography = Homography(cfg)
    win = "Calibration - point at each corner, SPACE to capture, ESC to cancel"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    captured: List[Tuple[float, float]] = []
    step = 0
    ts = 0

    cam = create_camera(cfg)
    recognizer = HandRecognizer(cfg)
    try:
        while True:
            frame = cam.read()
            if frame is None:
                continue
            bgr = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)
            h, w = bgr.shape[:2]

            ts += 33  # monotonic-ish ms; just must strictly increase
            recognizer.submit(frame.rgb, ts)
            hands = recognizer.get_observations()
            hand = _largest_hand(hands)

            tip_px: Optional[Tuple[int, int]] = None
            if hand is not None and len(hand.landmarks_px) > _INDEX_TIP:
                tip_px = hand.landmarks_px[_INDEX_TIP]
                cv2.circle(bgr, tip_px, 12, (0, 255, 0), 2)
                cv2.circle(bgr, tip_px, 2, (0, 255, 0), 3)

            # On-screen guidance.
            target = CORNER_ORDER[step]
            cv2.putText(bgr, f"[{step + 1}/4] Point INDEX FINGER at the {target} "
                             f"projected corner, then press SPACE",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(bgr, "ESC = cancel    R = restart",
                        (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            for (cx, cy) in captured:
                cv2.drawMarker(bgr, (int(cx), int(cy)), (0, 0, 255),
                               cv2.MARKER_CROSS, 18, 2)

            cv2.imshow(win, bgr)
            key = cv2.waitKey(1) & 0xFF

            if key == 27:        # ESC
                print("[calibrate] cancelled.")
                return False
            if key in (ord('r'), ord('R')):
                captured.clear()
                step = 0
                continue
            if key == 32:        # SPACE
                if tip_px is None:
                    print("[calibrate] no hand detected - cannot capture this corner.")
                    continue
                captured.append((float(tip_px[0]), float(tip_px[1])))
                print(f"[calibrate] captured {target} at {tip_px}")
                step += 1
                if step >= 4:
                    homography.save(captured, homography.dst_corners().tolist(),
                                    cam.resolution)
                    print("[calibrate] DONE.")
                    return True
    finally:
        cam.close()
        recognizer.close()
        cv2.destroyWindow(win)
