"""CameraSource interface shared by the webcam and (future) depth implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Frame:
    """One captured frame.

    rgb:   HxWx3 uint8 RGB image, already mirrored according to config
           (flip is baked in at capture time so detection, calibration and live
           mapping all share ONE coordinate frame).
    depth: optional HxW float32 depth in metres (None for a plain webcam).
    """
    rgb: np.ndarray
    depth: Optional[np.ndarray] = None


def sample_depth(depth, cx: float, cy: float) -> Optional[float]:
    """Depth (metres) of the hand at a palm-centre pixel, from a color-aligned
    depth map. Uses the 25th percentile of valid pixels in an 11x11 patch: the
    hand is always NEARER than whatever background the patch straddles, so a
    low percentile stays on the hand even when a fast sweep drags the (slightly
    stale) centroid toward the palm's edge. Returns None when there is no depth
    map, the point is outside the frame, or the patch has no valid pixels."""
    if depth is None:
        return None
    h, w = depth.shape[:2]
    x, y = int(cx), int(cy)
    if not (0 <= x < w and 0 <= y < h):
        return None
    r = 5   # 11x11 patch; a hand at 2-3 m spans ~40-70 px, so this stays inside
    patch = depth[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1]
    valid = patch[patch > 0]
    if valid.size == 0:
        return None
    return float(np.percentile(valid, 25))


class CameraSource(ABC):
    """Abstract camera. Implementations must yield RGB (and optionally depth)."""

    @property
    @abstractmethod
    def resolution(self) -> tuple[int, int]:
        """(width, height) of the frames actually produced."""

    @abstractmethod
    def read(self) -> Optional[Frame]:
        """Grab the next frame, or None if the device failed / ended."""

    @abstractmethod
    def close(self) -> None:
        """Release the device."""

    # Context-manager sugar so callers can use `with create_camera(cfg) as cam:`
    def __enter__(self) -> "CameraSource":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
