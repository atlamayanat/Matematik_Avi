"""Camera source abstraction.

The rest of the pipeline only depends on the ``CameraSource`` interface, so a
depth camera (Orbbec Femto Bolt / Intel RealSense) can be swapped in later
without touching detection, the game logic, or Unity.
"""

from .base import CameraSource, Frame
from .webcam import WebcamSource


def create_camera(cfg) -> CameraSource:
    """Factory: build the camera source named in config.camera.source."""
    source = cfg.camera.source.lower()
    if source == "webcam":
        return WebcamSource(cfg)
    if source == "depth":
        # Imported lazily so the webcam path never requires depth SDKs.
        from .depth import DepthSource
        return DepthSource(cfg)
    raise ValueError(f"Unknown camera source: {cfg.camera.source!r} (use 'webcam' or 'depth')")


__all__ = ["CameraSource", "Frame", "WebcamSource", "create_camera"]
