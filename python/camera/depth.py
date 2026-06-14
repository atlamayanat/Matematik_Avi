"""Depth (RGB-D) camera source - STUB for the future hardware upgrade.

When the tent crowd makes the RGB size-heuristic unreliable, swap config
``camera.source`` to ``"depth"`` and implement this class. With depth, background
rejection becomes a single Z-band mask (keep only 0.8-1.8 m); the entire waiting
crowd is cut off before hand detection runs, which largely obsoletes the
active-player size heuristic. The OSC schema and ALL Unity code stay unchanged.

Recommended 2026 hardware:
  * Orbbec Femto Bolt  - the Microsoft-blessed Azure Kinect DK successor (ToF).
                         Azure Kinect itself is discontinued; do not spec it.
  * Intel/RealSense D4xx (D435/D455) - active stereo, better outdoors.

Implementation sketch:
  1. Open the device via its SDK (pyorbbecsdk / pyrealsense2).
  2. Per frame: read aligned colour + depth, convert colour to mirrored RGB
     (same flip as WebcamSource), build a float32 depth map in metres.
  3. Optionally zero out RGB pixels whose depth is outside [z_min_m, z_max_m]
     BEFORE returning, so MediaPipe only ever sees the interaction volume.
  4. Return Frame(rgb=..., depth=...).
"""

from __future__ import annotations

from typing import Optional

from .base import CameraSource, Frame


class DepthSource(CameraSource):
    def __init__(self, cfg):
        self._cfg = cfg
        raise NotImplementedError(
            "DepthSource is a stub for the future depth-camera upgrade. "
            "Implement it against your Orbbec/RealSense SDK, then set "
            "config.camera.source = 'depth'. See the module docstring for the recipe."
        )

    @property
    def resolution(self) -> tuple[int, int]:  # pragma: no cover - stub
        raise NotImplementedError

    def read(self) -> Optional[Frame]:  # pragma: no cover - stub
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - stub
        pass
