"""Camera-pixel -> projector-normalized mapping via a single planar homography.

The player's hand moves in a roughly fixed plane (they stand at a fixed
distance), so the camera->screen relationship is exactly a 2D projective
transform (3x3 homography). We build it once from an N-point calibration and
apply it per frame. The homography also absorbs any camera mirroring and the
camera/projector resolution & aspect-ratio difference, so NO extra scaling.

Calibration uses >=4 point correspondences:
  * exactly 4  -> cv2.getPerspectiveTransform (exact, no slack),
  * 5 or more   -> cv2.findHomography least-squares (distributes capture noise
                   and webcam lens distortion across all points).

Data flow decision: the transform runs HERE (Python). The web game / Unity
receives already-mapped, normalized [0,1] coordinates and stays a pure renderer
(no recompile to recalibrate, no knowledge of camera resolution/mirroring).
"""

from __future__ import annotations

import json
import os
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

# Fixed 4-corner order kept for backward compatibility with old calib prompts.
CORNER_ORDER = ("TOP-LEFT", "TOP-RIGHT", "BOTTOM-RIGHT", "BOTTOM-LEFT")


class Homography:
    def __init__(self, cfg):
        self.file = cfg.calibration.file
        self.proj_w = int(cfg.calibration.proj_w)
        self.proj_h = int(cfg.calibration.proj_h)
        self._H: Optional[np.ndarray] = None
        self._flip: Optional[bool] = None          # flip the calib was built with
        self._cam_res: Optional[List[int]] = None   # camera resolution at calib time
        self._reproj_err: Optional[float] = None     # normalized RMS reprojection error
        self._warned = False
        self.load()

    @property
    def is_calibrated(self) -> bool:
        return self._H is not None

    @property
    def reproj_err(self) -> Optional[float]:
        """Normalized RMS reprojection error of the current fit (None if unknown)."""
        return self._reproj_err

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
            self._flip = d.get("flip_horizontal", None)
            self._cam_res = d.get("cam_res", None)
            self._reproj_err = d.get("reproj_err_norm", None)
            return True
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            print(f"[homography] WARNING: could not read {self.file!r}: {exc}")
            self._H = None
            return False

    def fit(self, src_px: Sequence, dst_px: Sequence) -> float:
        """Build H in-memory from N (>=4) src/dst pairs. Returns the normalized
        RMS reprojection error. Does NOT write to disk (used for live preview /
        verification before the operator accepts)."""
        src = np.float32(src_px)
        dst = np.float32(dst_px)
        if len(src) < 4 or len(src) != len(dst):
            raise ValueError(f"need >=4 matched point pairs, got {len(src)}/{len(dst)}")
        if len(src) == 4:
            H = cv2.getPerspectiveTransform(src, dst)
        else:
            H, _ = cv2.findHomography(src, dst, 0)  # 0 = plain least-squares (all points)
            if H is None:
                raise ValueError("findHomography failed (degenerate/collinear points?)")
        self._H = H.astype(np.float32)
        self._reproj_err = self._reproj_error(src, dst)
        return self._reproj_err

    def save(self, src_px: Sequence, dst_px: Sequence, cam_res,
             flip: Optional[bool] = None) -> float:
        """Build H from src (camera px) / dst (projector px) pairs and persist.
        Returns the normalized RMS reprojection error."""
        err = self.fit(src_px, dst_px)
        self._flip = bool(flip) if flip is not None else None
        self._cam_res = list(cam_res) if cam_res else None
        payload = {
            "version": 2,
            "H": self._H.tolist(),
            "src": np.float32(src_px).tolist(),
            "dst": np.float32(dst_px).tolist(),
            "points": int(len(src_px)),
            "proj_w": self.proj_w,
            "proj_h": self.proj_h,
            "cam_res": self._cam_res,
            "flip_horizontal": self._flip,
            "reproj_err_norm": err,
        }
        with open(self.file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"[homography] saved calibration -> {self.file}  "
              f"(points={len(src_px)}, err={err * 100:.2f}% of screen)")
        return err

    def clear(self) -> None:
        """Drop the in-memory fit (used when the operator chooses to recalibrate)."""
        self._H = None
        self._reproj_err = None

    def _reproj_error(self, src: np.ndarray, dst: np.ndarray) -> Optional[float]:
        """Normalized RMS error: map src through H, compare to dst, scale to [0,1]."""
        if self._H is None:
            return None
        pts = np.asarray(src, np.float32).reshape(-1, 1, 2)
        mapped = cv2.perspectiveTransform(pts, self._H).reshape(-1, 2)
        diff = (mapped - np.asarray(dst, np.float32)) / np.array(
            [self.proj_w, self.proj_h], np.float32)
        return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))

    def dst_corners(self) -> np.ndarray:
        """Destination rectangle in projector pixels, in CORNER_ORDER."""
        w, h = self.proj_w, self.proj_h
        return np.float32([[0, 0], [w, 0], [w, h], [0, h]])

    # --- environment validation ------------------------------------------
    def warn_if_environment_changed(self, cam_res, flip) -> None:
        """If the camera resolution or mirroring differs from what the saved
        calibration was built with, the pixel coordinates no longer line up and
        the mapping is silently wrong. Surface that loudly so the operator
        recalibrates instead of chasing a 'drifting cursor' ghost."""
        if self._H is None:
            return
        issues = []
        if self._cam_res and [int(v) for v in self._cam_res] != [int(v) for v in cam_res]:
            issues.append(f"kamera cozunurlugu {self._cam_res} -> {list(cam_res)}")
        if self._flip is not None and bool(self._flip) != bool(flip):
            issues.append(f"flip_horizontal {self._flip} -> {bool(flip)}")
        if issues:
            print("[homography] UYARI: " + "; ".join(issues)
                  + " degisti -> dogruluk icin yeniden kalibre et (oyunda C tusu).")

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
        # Clamp so an out-of-bounds hand never sends wild values downstream.
        return (min(1.0, max(0.0, nx)), min(1.0, max(0.0, ny)))
