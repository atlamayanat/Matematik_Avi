"""Plain data types passed between detection and the rest of the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class HandObservation:
    """One detected hand for a single frame.

    centroid01:    palm centre in NORMALIZED [0,1] image coords (for ROI/selection).
    centroid_px:   palm centre in CAMERA PIXELS (homography source point).
    span01:        apparent hand size in normalized coords = max of the two palm
                   axes (wrist(0)->middle-MCP(9) length, index-MCP(5)->pinky-MCP(17)
                   width). Perspective can foreshorten one axis but not both, so
                   this stays a usable distance proxy even for a hand extended
                   toward the camera.
    gesture:       raw canonical label, e.g. 'Open_Palm' / 'Closed_Fist' / 'None'.
    gesture_score: confidence [0,1] of that label.
    handedness:    'Left' / 'Right' (as reported by MediaPipe).
    detection_score: hand detection/presence confidence [0,1].
    landmarks_px:  all 21 landmarks in camera pixels (for the preview overlay).
    z_m:           depth at the palm centre in METRES (median of a small patch
                   from the color-aligned depth map), or None when no depth
                   camera / no valid reading. Filled in by the main loop.
    """
    centroid01: Tuple[float, float]
    centroid_px: Tuple[float, float]
    span01: float
    gesture: str
    gesture_score: float
    handedness: str
    detection_score: float
    landmarks_px: List[Tuple[int, int]]
    z_m: Optional[float] = None
