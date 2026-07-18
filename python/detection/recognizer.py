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
_INDEX_MCP = 5
_MIDDLE_MCP = 9
_PINKY_MCP = 17
_PALM_POINTS = (0, 5, 9, 13, 17)  # wrist + the four finger MCPs -> stable centre

# Finger joints (MCP, PIP, DIP, TIP) in MediaPipe Hands topology - index..pinky.
_FINGER_JOINTS = (
    (5, 6, 7, 8),       # index
    (9, 10, 11, 12),    # middle
    (13, 14, 15, 16),   # ring
    (17, 18, 19, 20),   # pinky
)
# A finger is "curled" when its tip->MCP straight line is much shorter than the
# summed joint path (i.e. the finger folds back), OR when the tip has folded
# back toward the wrist past the PIP joint. Both tests are invariant to hand
# ORIENTATION and SCALE, so a fist is recognized sideways / upside-down / angled.
# This geometry is the SOLE open/fist signal (no MediaPipe 'Closed_Fist' label
# exists on HandLandmarker). Defaults are deliberately LOOSE so a child's
# half-closed fist counts; override via config detection.fist_curl_ratio /
# detection.fist_min_curled.
_DEF_FIST_CURL_RATIO = 0.7   # straight/path below this = curled finger
_DEF_FIST_MIN_CURLED = 3     # >= this many curled fingers (of 4) = fist


def _dist3(a, b) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def _curled_finger_count(landmarks, curl_ratio: float) -> int:
    """Count curled fingers from a 21-point hand (world or normalized landmarks)."""
    wrist = landmarks[_WRIST]
    curled = 0
    for mcp, pip, dip, tip in _FINGER_JOINTS:
        path = (_dist3(landmarks[mcp], landmarks[pip])
                + _dist3(landmarks[pip], landmarks[dip])
                + _dist3(landmarks[dip], landmarks[tip]))
        if path <= 1e-9:
            continue
        # Test 1: finger folds back on itself (loose fists included via ratio).
        if _dist3(landmarks[mcp], landmarks[tip]) / path < curl_ratio:
            curled += 1
            continue
        # Test 2: tip has folded back toward the wrist past its own PIP joint -
        # true for a deep fist even when landmark noise inflates the path ratio.
        if _dist3(wrist, landmarks[tip]) < _dist3(wrist, landmarks[pip]):
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
        self._latest_ts: Optional[int] = None   # timestamp of the frame _latest came from
        self._result_id = 0  # bumped on each callback; lets the loop skip duplicate frames
        self._frame_wh: Optional[tuple[int, int]] = None

        det = cfg.detection
        self._curl_ratio = float(det.get("fist_curl_ratio", _DEF_FIST_CURL_RATIO))
        self._min_curled = int(det.get("fist_min_curled", _DEF_FIST_MIN_CURLED))

        # Delegate: on Windows MediaPipe Tasks has NO GPU delegate, so CPU is the
        # only real choice; naming it explicitly documents intent.
        delegate_name = str(det.get("delegate", "cpu") or "cpu").lower()

        def _build(delegate):
            try:
                base_options = mp_python.BaseOptions(
                    model_asset_path=model_path, delegate=delegate)
            except Exception:   # noqa: BLE001 - very old Tasks builds lack `delegate`
                base_options = mp_python.BaseOptions(model_asset_path=model_path)
            options = mp_vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.LIVE_STREAM,
                num_hands=int(cfg.detection.num_hands),
                min_hand_detection_confidence=float(cfg.detection.min_hand_detection_confidence),
                min_hand_presence_confidence=float(cfg.detection.min_hand_presence_confidence),
                min_tracking_confidence=float(cfg.detection.min_tracking_confidence),
                result_callback=self._on_result,  # REQUIRED for LIVE_STREAM
            )
            return mp_vision.HandLandmarker.create_from_options(options)

        want_gpu = delegate_name == "gpu"
        delegate = mp_python.BaseOptions.Delegate.CPU
        if want_gpu:
            try:
                delegate = mp_python.BaseOptions.Delegate.GPU
            except Exception:   # noqa: BLE001 - enum missing on this build
                delegate = mp_python.BaseOptions.Delegate.CPU
        # The GPU-unavailable error surfaces at create_from_options (graph init),
        # NOT at BaseOptions construction - so the CPU fallback must wrap the
        # ACTUAL build, or a delegate="gpu" misconfig on Windows crash-loops.
        try:
            self._landmarker = _build(delegate)
        except Exception:   # noqa: BLE001
            if not want_gpu:
                raise   # a real CPU-build failure -> let the supervisor surface it
            print("[detection] GPU delegate kullanilamiyor -> CPU'ya dusuldu.")
            self._landmarker = _build(mp_python.BaseOptions.Delegate.CPU)

    # --- MediaPipe worker thread: just stash the newest result -------------
    def _on_result(self, result, output_image, timestamp_ms):  # noqa: ANN001
        with self._lock:
            self._latest = result
            self._latest_ts = timestamp_ms
            self._result_id += 1

    @property
    def result_id(self) -> int:
        """Monotonic counter of completed inferences. The main loop runs the
        pipeline only when this changes, so One Euro + the selector/FSM frame
        counters see the TRUE ~20-30 Hz inference rate, not duplicate 60 Hz ticks."""
        with self._lock:
            return self._result_id

    @property
    def result_timestamp_ms(self) -> Optional[int]:
        """Timestamp of the frame the latest result was computed FROM. Lets the
        main loop sample the depth map of the SAME frame as the landmarks -
        sampling the current frame at a 1-2 frame old centroid reads background
        depth during fast sweeps."""
        with self._lock:
            return self._latest_ts

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

            # Size proxy: the LARGER of the two palm axes (wrist->middle-MCP =
            # palm length, index-MCP->pinky-MCP = palm width), measured
            # ISOTROPICALLY in frame-width units (y is normalized by height, so
            # it must be rescaled by h/w or a vertical axis reads 16/9 too big
            # and the idle hanging hand out-measures the playing hand). The two
            # axes are ~orthogonal in the palm plane, so perspective can
            # foreshorten one but not both: a hand extended TOWARD the camera
            # (palm-down reach - the playing pose) collapses palm length but
            # keeps palm width visible. A single-axis proxy made the extended
            # hand measure "smaller" than an idle hand at the body and let the
            # idle hand steal the lock.
            aspect = h / w
            dx = landmarks[_MIDDLE_MCP].x - landmarks[_WRIST].x
            dy = (landmarks[_MIDDLE_MCP].y - landmarks[_WRIST].y) * aspect
            wx = landmarks[_PINKY_MCP].x - landmarks[_INDEX_MCP].x
            wy = (landmarks[_PINKY_MCP].y - landmarks[_INDEX_MCP].y) * aspect
            span01 = max((dx * dx + dy * dy) ** 0.5,
                         (wx * wx + wy * wy) ** 0.5)

            # Orientation-invariant fist detection from the hand SKELETON.
            # The 3D world landmarks (metric, orientation-aware) are
            # AUTHORITATIVE when present: the normalized image landmarks
            # collapse to projection noise exactly in the playing pose (open
            # hand reaching toward the camera) and would fire false fists.
            # Fall back to the image landmarks only if world data is missing.
            # HandLandmarker has no gesture label, so this geometry IS the signal.
            skel = landmarks
            if (i < len(result.hand_world_landmarks)
                    and result.hand_world_landmarks[i]):
                skel = result.hand_world_landmarks[i]
            curled = _curled_finger_count(skel, self._curl_ratio)
            is_fist = curled >= self._min_curled
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
