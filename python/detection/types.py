"""Plain data types passed between detection and the rest of the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class HandObservation:
    """One detected hand for a single frame.

    centroid01:    palm centre in NORMALIZED [0,1] image coords (for ROI/selection).
    centroid_px:   palm centre in CAMERA PIXELS (homography source point).
    span01:        wrist(0) -> middle-MCP(9) distance in normalized coords; a
                   pose-stable proxy for apparent hand size = distance from camera.
    gesture:       raw canonical label, e.g. 'Open_Palm' / 'Closed_Fist' / 'None'.
    gesture_score: confidence [0,1] of that label.
    handedness:    'Left' / 'Right' (as reported by MediaPipe).
    detection_score: hand detection/presence confidence [0,1].
    landmarks_px:  all 21 landmarks in camera pixels (for the preview overlay).
    """
    centroid01: Tuple[float, float]
    centroid_px: Tuple[float, float]
    span01: float
    gesture: str
    gesture_score: float
    handedness: str
    detection_score: float
    landmarks_px: List[Tuple[int, int]]
