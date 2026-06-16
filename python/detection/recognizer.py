"""MediaPipe Tasks HandLandmarker wrapper (LIVE_STREAM mode).

One HandLandmarker gives us, per hand and per frame:
  * 21 hand landmarks (image + 3D world position),
  * handedness.
There is NO gesture label: open vs fist is derived from the 21-point SKELETON
geometry (orientation/scale-invariant, see _curled_finger_count). That geometry
was already the PRIMARY open/fist signal under the old GestureRecognizer path;
dropping the classifier head only removes a small ensemble bonus and lightens
inference (HandLandmarker is GestureRecognizer minus the gesture head).

LIVE_STREAM is asynchronous: detect_async() returns immediately and the result
is delivered later to a callback on a MediaPipe worker thread. We stash the
latest result under a lock; the main loop reads it (latest-value-wins).
"""

from __future__ import annotations

import os
import threading
from typing import List, Optional

import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from .types import HandObservation

# Landmark indices we care about (MediaPipe Hands topology).
_WRIST = 0
_MIDDLE_MCP = 9
_PALM_POINTS = (0, 5, 9, 13, 17)  # wrist + the four finger MCPs -> stable centre

# Finger joints (MCP, PIP, DIP, TIP) in MediaPipe Hands topology - index..pinky.
_FINGER_JOINTS = (
    (5, 6, 7, 8),       # index
    (9, 10, 11, 12),    # middle
    (13, 14, 15, 16),   # ring
    (17, 18, 19, 20),   # pinky
)
# A finger is "curled" when its tip->MCP straight line is much shorter than the
# summed joint path (i.e. the finger folds back). This ratio is invariant to hand
# ORIENTATION and SCALE, so a fist is recognized sideways / upside-down / angled.
# It is now the SOLE open/fist signal (no MediaPipe 'Closed_Fist' label exists on
# HandLandmarker); tune _FIST_CURL_RATIO if facing-hand fists read late.
_FIST_CURL_RATIO = 0.55   # straight/path below this = curled finger
_FIST_MIN_CURLED = 3      # >= this many curled fingers (of 4) = fist


def _dist3(a, b) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def _curled_finger_count(landmarks) -> int:
    """Count curled fingers from a 21-point hand (world or normalized landmarks)."""
    curled = 0
    for mcp, pip, dip, tip in _FINGER_JOINTS:
        path = (_dist3(landmarks[mcp], landmarks[pip])
                + _dist3(landmarks[pip], landmarks[dip])
                + _dist3(landmarks[dip], landmarks[tip]))
        if path <= 1e-9:
            continue
        if _dist3(landmarks[mcp], landmarks[tip]) / path < _FIST_CURL_RATIO:
            curled += 1
    return curled


class HandRecognizer:
    def __init__(self, cfg):
        model_path = cfg.detection.model_path
        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"Hand model not found: {model_path!r}. "
                f"Run  python download_model.py  to fetch hand_landmarker.task."
            )

        self._lock = threading.Lock()
        self._latest: Optional[mp_vision.HandLandmarkerResult] = None
        self._result_id = 0  # bumped on each callback; lets the loop skip duplicate frames
        self._frame_wh: Optional[tuple[int, int]] = None

        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=mp_vision.RunningMode.LIVE_STREAM,
            num_hands=int(cfg.detection.num_hands),
            min_hand_detection_confidence=float(cfg.detection.min_hand_detection_confidence),
            min_hand_presence_confidence=float(cfg.detection.min_hand_presence_confidence),
            min_tracking_confidence=float(cfg.detection.min_tracking_confidence),
            result_callback=self._on_result,  # REQUIRED for LIVE_STREAM
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)

    # --- MediaPipe worker thread: just stash the newest result -------------
    def _on_result(self, result, output_image, timestamp_ms):  # noqa: ANN001
        with self._lock:
            self._latest = result
            self._result_id += 1

    @property
    def result_id(self) -> int:
        """Monotonic counter of completed inferences. The main loop runs the
        pipeline only when this changes, so One Euro + the selector/FSM frame
        counters see the TRUE ~20-30 Hz inference rate, not duplicate 60 Hz ticks."""
        with self._lock:
            return self._result_id

    # --- Main thread ------------------------------------------------------
    def submit(self, rgb_frame: np.ndarray, timestamp_ms: int) -> None:
        """Feed a frame. timestamp_ms MUST be strictly increasing."""
        h, w = rgb_frame.shape[:2]
        self._frame_wh = (w, h)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        self._landmarker.detect_async(mp_image, timestamp_ms)

    def get_observations(self) -> List[HandObservation]:
        """Convert the latest stashed result into HandObservation objects."""
        with self._lock:
            result = self._latest
        if result is None or not result.hand_landmarks or self._frame_wh is None:
            return []

        w, h = self._frame_wh
        observations: List[HandObservation] = []

        for i, landmarks in enumerate(result.hand_landmarks):
            # Pixel landmarks (for overlay + homography source).
            lm_px = [(int(p.x * w), int(p.y * h)) for p in landmarks]

            # Palm centre = mean of wrist + 4 MCPs, both normalized and pixel.
            cx01 = sum(landmarks[j].x for j in _PALM_POINTS) / len(_PALM_POINTS)
            cy01 = sum(landmarks[j].y for j in _PALM_POINTS) / len(_PALM_POINTS)
            centroid_px = (cx01 * w, cy01 * h)

            # Size proxy: wrist -> middle-MCP distance in normalized coords.
            dx = landmarks[_MIDDLE_MCP].x - landmarks[_WRIST].x
            dy = landmarks[_MIDDLE_MCP].y - landmarks[_WRIST].y
            span01 = (dx * dx + dy * dy) ** 0.5

            # Orientation-invariant fist detection from the hand SKELETON.
            # Prefer 3D world landmarks (metric, orientation-aware); fall back to
            # the normalized image landmarks if world landmarks are unavailable.
            # HandLandmarker has no gesture label, so this geometry IS the signal.
            skel = landmarks
            if (i < len(result.hand_world_landmarks)
                    and result.hand_world_landmarks[i]):
                skel = result.hand_world_landmarks[i]
            curled = _curled_finger_count(skel)
            is_fist = curled >= _FIST_MIN_CURLED
            gesture = "Closed_Fist" if is_fist else "Open_Palm"
            gscore = curled / 4.0

            handedness = "Unknown"
            det_score = 0.0
            if i < len(result.handedness) and result.handedness[i]:
                handedness = result.handedness[i][0].category_name
                det_score = result.handedness[i][0].score

            observations.append(HandObservation(
                centroid01=(cx01, cy01),
                centroid_px=centroid_px,
                span01=span01,
                gesture=gesture,
                gesture_score=gscore,
                handedness=handedness,
                detection_score=det_score,
                landmarks_px=lm_px,
            ))

        return observations

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
