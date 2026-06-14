"""Camera-pixel -> projector-normalized mapping via a single planar homography.

The wall is a plane viewed at an angle, so the camera->projector relationship is
exactly a 2D projective transform (3x3 homography). We build it once from a
4-corner calibration and apply it per frame. The homography also absorbs any
camera/projector resolution & aspect-ratio difference, so NO extra scaling.

Data flow decision: the transform runs HERE (Python). Unity receives already
mapped, normalized [0,1] coordinates and stays a pure renderer (no recompile to
recalibrate, no knowledge of camera resolution/mirroring).
"""

from __future__ import annotations

import json
import os
from typing import Optional, Tuple

import cv2
import numpy as np

# Fixed corner order used everywhere (calibration prompts MUST match this).
CORNER_ORDER = ("TOP-LEFT", "TOP-RIGHT", "BOTTOM-RIGHT", "BOTTOM-LEFT")


class Homography:
    def __init__(self, cfg):
        self.file = cfg.calibration.file
        self.proj_w = int(cfg.calibration.proj_w)
        self.proj_h = int(cfg.calibration.proj_h)
        self._H: Optional[np.ndarray] = None
        self._warned = False
        self.load()

    @property
    def is_calibrated(self) -> bool:
        return self._H is not None

    # --- persistence ------------------------------------------------------
    def load(self) -> bool:
        if not os.path.isfile(self.file):
            return False
        try:
            with open(self.file, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            self._H = np.array(d["H"], dtype=np.float32)
            # Use the projector size the calibration was built for.
            self.proj_w = int(d.get("proj_w", self.proj_w))
            self.proj_h = int(d.get("proj_h", self.proj_h))
            return True
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            print(f"[homography] WARNING: could not read {self.file!r}: {exc}")
            self._H = None
            return False

    def save(self, src_px, dst_px, cam_res) -> None:
        """Build H from 4 src (camera px) / dst (projector px) pairs and persist."""
        src = np.float32(src_px)
        dst = np.float32(dst_px)
        self._H = cv2.getPerspectiveTransform(src, dst)
        payload = {
            "version": 1,
            "H": self._H.tolist(),
            "src": src.tolist(),
            "dst": dst.tolist(),
            "proj_w": self.proj_w,
            "proj_h": self.proj_h,
            "cam_res": list(cam_res) if cam_res else None,
            "corner_order": list(CORNER_ORDER),
        }
        with open(self.file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"[homography] saved calibration -> {self.file}")

    def dst_corners(self) -> np.ndarray:
        """Destination rectangle in projector pixels, in CORNER_ORDER."""
        w, h = self.proj_w, self.proj_h
        return np.float32([[0, 0], [w, 0], [w, h], [0, h]])

    # --- live mapping -----------------------------------------------------
    def map_point(self, px: float, py: float,
                  fallback01: Tuple[float, float]) -> Tuple[float, float]:
        """Map a camera-pixel point to normalized [0,1] projector coords.

        If not calibrated, returns ``fallback01`` (the raw normalized centroid),
        so the whole system still runs for bench testing before calibration.
        """
        if self._H is None:
            if not self._warned:
                print("[homography] NOT calibrated - passing raw normalized coords. "
                      "Run  python main.py --calibrate  to align with the projector.")
                self._warned = True
            return fallback01

        pt = np.array([[[px, py]]], dtype=np.float32)        # shape (1,1,2) - required
        out = cv2.perspectiveTransform(pt, self._H)[0][0]
        nx = float(out[0]) / self.proj_w
        ny = float(out[1]) / self.proj_h
        # Clamp so an out-of-bounds hand never sends wild values to Unity.
        return (min(1.0, max(0.0, nx)), min(1.0, max(0.0, ny)))
