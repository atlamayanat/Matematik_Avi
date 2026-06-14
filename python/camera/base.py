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
