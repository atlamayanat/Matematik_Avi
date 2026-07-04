"""Camera source abstraction.

The rest of the pipeline only depends on the ``CameraSource`` interface, so a
depth camera (Orbbec Femto Bolt / Intel RealSense) can be swapped in later
without touching detection, the game logic, or Unity.
"""

from .base import CameraSource, Frame, sample_depth
from .webcam import WebcamSource


def create_camera(cfg) -> CameraSource:
    """Factory: build the camera source named in config.camera.source."""
    source = cfg.camera.source.lower()
    if source == "webcam":
        return WebcamSource(cfg)
    if source in ("depth", "realsense"):
        # Probe the SDK import HERE (pyrealsense2 is imported lazily deep inside
        # DepthSource.__init__, so a try/except around `from .depth import ...`
        # alone would NOT catch a missing SDK). ONLY the missing-SDK case falls
        # back to webcam; a DEVICE fault (unplugged, USB2 port, second instance
        # holding the camera) is raised by DepthSource(cfg) below and PROPAGATES,
        # so the operator sees the real fault instead of a silently worse game.
        try:
            import pyrealsense2  # noqa: F401 - availability probe
            from .depth import DepthSource
        except ImportError as exc:
            print(f"[camera] UYARI: pyrealsense2 kurulu degil ({exc}); duz "
                  "webcam moduna dusuluyor (DERINLIKSIZ secim - el atlama "
                  "korumasi zayif). Kurulum: pip install pyrealsense2")
            return WebcamSource(cfg)
        return DepthSource(cfg)
    raise ValueError(f"Unknown camera source: {cfg.camera.source!r} "
                     "(use 'webcam' or 'depth')")


__all__ = ["CameraSource", "Frame", "WebcamSource", "create_camera", "sample_depth"]
