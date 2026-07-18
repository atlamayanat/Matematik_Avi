"""Camera-pixel -> projector-normalized mapping via a single planar homography.

The player's hand moves in a roughly fixed plane (they stand at a fixed
distance), so the camera->screen relationship is exactly a 2D projective
transform (3x3 homography). We build it once from an N-point calibration and
apply it per frame. The homography also absorbs any camera mirroring and the
camera/projector resolution & aspect-ratio difference, so NO extra scaling.

Calibration uses >=4 point correspondences:
  * exactly 4  -> cv2.getPerspectiveTransform (exact, no slack),
  * 5 or more   -> cv2.findHomography. Method is config-driven:
       "lsq"    -> plain least-squares over all points (previous behaviour),
       "ransac" -> RANSAC, so a single jittery capture is rejected as an
                   outlier instead of skewing the whole fit.

Optional RGB undistortion (calibration.undistort_rgb): the ONE nonlinearity a
homography cannot model is the camera's radial lens distortion. When factory
colour intrinsics are available (RealSense) we undistort the source pixels
BEFORE fitting AND on every live map_point, using the SAME intrinsics. The
undistort flag + intrinsics are SAVED into calib.json, so map_point always
follows what the calibration was built with (never the live config) - the two
can never silently disagree. On a plain webcam (no intrinsics) undistort is a
no-op and calibration/mapping both stay in raw pixels, still consistent.

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
        cal = cfg.calibration
        self.file = cal.file
        self.proj_w = int(cal.proj_w)
        self.proj_h = int(cal.proj_h)
        # Fit + undistort options (drive the NEXT calibration).
        self._fit_method = str(cal.get("fit_method", "lsq")).lower()
        self._ransac_frac = float(cal.get("ransac_reproj_frac", 0.02))
        self._undistort_cfg = bool(cal.get("undistort_rgb", False))
        # Default MUST match calibrate.run_calibration's default (1.5) so a missing
        # config key does not bake a gain into calib.json that differs from the one
        # that actually shaped the capture (would corrupt the drift-warning baseline).
        self._cursor_gain = float(cal.get("cursor_gain", 1.5))

        self._H: Optional[np.ndarray] = None
        self._flip: Optional[bool] = None           # flip the calib was built with
        self._cam_res: Optional[List[int]] = None    # camera resolution at calib time
        self._reproj_err: Optional[float] = None      # normalized RMS reprojection error
        self._residuals: Optional[List[float]] = None  # per-point normalized residual
        self._warned = False

        # Intrinsics for undistort. _K_cam/_dist_cam come from the live camera (used
        # for the NEXT calibration); _K/_dist/_undistort describe the CURRENT H
        # (loaded from calib.json) and are what map_point applies.
        self._K_cam: Optional[np.ndarray] = None
        self._dist_cam: Optional[np.ndarray] = None
        self._K: Optional[np.ndarray] = None
        self._dist: Optional[np.ndarray] = None
        self._undistort = False
        self._saved_gain: Optional[float] = None      # cursor_gain baked into calib.json
        self.load()

    @property
    def is_calibrated(self) -> bool:
        return self._H is not None

    @property
    def reproj_err(self) -> Optional[float]:
        """Normalized RMS reprojection error of the current fit (None if unknown)."""
        return self._reproj_err

    @property
    def residuals(self) -> Optional[List[float]]:
        """Per-point normalized reprojection residuals from the last fit."""
        return self._residuals

    def set_intrinsics(self, K, dist) -> None:
        """Register the live camera's factory colour intrinsics so the NEXT
        calibration can undistort. No-op-safe: pass None to clear."""
        self._K_cam = np.asarray(K, dtype=np.float64) if K is not None else None
        self._dist_cam = np.asarray(dist, dtype=np.float64) if dist is not None else None

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
            self._saved_gain = d.get("cursor_gain", None)
            # Undistort baked into THIS calibration (so map_point matches the fit).
            self._undistort = bool(d.get("undistort", False))
            if self._undistort and d.get("K") is not None and d.get("dist") is not None:
                self._K = np.array(d["K"], dtype=np.float64)
                self._dist = np.array(d["dist"], dtype=np.float64)
            else:
                self._undistort = False
                self._K = self._dist = None
            return True
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            print(f"[homography] WARNING: could not read {self.file!r}: {exc}")
            self._H = None
            return False

    # --- undistort helper -------------------------------------------------
    def _undistort_pts(self, pts: np.ndarray) -> np.ndarray:
        """Undistort pixel points with the CURRENT calibration's intrinsics
        (identity when undistort is off / no intrinsics). Keeps pixel units by
        reprojecting through K (P=K)."""
        if not self._undistort or self._K is None or self._dist is None:
            return pts
        src = np.asarray(pts, np.float32).reshape(-1, 1, 2)
        out = cv2.undistortPoints(src, self._K, self._dist, P=self._K)
        return out.reshape(-1, 2)

    def fit(self, src_px: Sequence, dst_px: Sequence,
            method: Optional[str] = None) -> float:
        """Build H in-memory from N (>=4) src/dst pairs. Returns the normalized
        RMS reprojection error. Does NOT write to disk (used for live preview /
        verification before the operator accepts)."""
        src = np.float32(src_px)
        dst = np.float32(dst_px)
        if len(src) < 4 or len(src) != len(dst):
            raise ValueError(f"need >=4 matched point pairs, got {len(src)}/{len(dst)}")

        # Decide undistort for THIS fit: only if configured AND camera intrinsics
        # are available. Record what we used so map_point + save stay consistent.
        self._undistort = bool(self._undistort_cfg and self._K_cam is not None
                               and self._dist_cam is not None)
        self._K = self._K_cam if self._undistort else None
        self._dist = self._dist_cam if self._undistort else None
        src_u = self._undistort_pts(src)

        method_name = (method or self._fit_method or "lsq").lower()
        if len(src) == 4:
            H = cv2.getPerspectiveTransform(np.float32(src_u), dst)
        elif method_name == "ransac":
            thr = max(1.0, self._ransac_frac * float(self.proj_w))
            H, _ = cv2.findHomography(np.float32(src_u), dst, cv2.RANSAC, thr)
            if H is None:   # RANSAC could not agree -> fall back to plain LSQ
                H, _ = cv2.findHomography(np.float32(src_u), dst, 0)
        else:
            H, _ = cv2.findHomography(np.float32(src_u), dst, 0)  # plain least-squares
        if H is None:
            raise ValueError("findHomography failed (degenerate/collinear points?)")
        self._H = H.astype(np.float32)
        self._reproj_err = self._reproj_error(np.float32(src_u), dst)
        return self._reproj_err

    def save(self, src_px: Sequence, dst_px: Sequence, cam_res,
             flip: Optional[bool] = None) -> float:
        """Build H from src (camera px) / dst (projector px) pairs and persist.
        Returns the normalized RMS reprojection error."""
        err = self.fit(src_px, dst_px)
        self._flip = bool(flip) if flip is not None else None
        self._cam_res = list(cam_res) if cam_res else None
        self._saved_gain = float(self._cursor_gain)
        payload = {
            "version": 3,
            "H": self._H.tolist(),
            "src": np.float32(src_px).tolist(),
            "dst": np.float32(dst_px).tolist(),
            "points": int(len(src_px)),
            "proj_w": self.proj_w,
            "proj_h": self.proj_h,
            "cam_res": self._cam_res,
            "flip_horizontal": self._flip,
            "reproj_err_norm": err,
            # cursor_gain shapes the captured src points; recording it lets the
            # next run WARN if config changed it without a recalibration.
            "cursor_gain": self._saved_gain,
            # undistort intrinsics baked in, so map_point matches the fit exactly.
            "undistort": bool(self._undistort),
            "K": self._K.tolist() if (self._undistort and self._K is not None) else None,
            "dist": self._dist.tolist() if (self._undistort and self._dist is not None) else None,
        }
        with open(self.file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"[homography] saved calibration -> {self.file}  "
              f"(points={len(src_px)}, err={err * 100:.2f}% of screen, "
              f"method={self._fit_method}, undistort={self._undistort})")
        return err

    def clear(self) -> None:
        """Drop the in-memory fit (used when the operator chooses to recalibrate)."""
        self._H = None
        self._reproj_err = None
        self._residuals = None

    def _reproj_error(self, src: np.ndarray, dst: np.ndarray) -> Optional[float]:
        """Normalized RMS error: map src through H, compare to dst, scale to
        [0,1]. Also stashes the per-point residuals for the operator report."""
        if self._H is None:
            return None
        pts = np.asarray(src, np.float32).reshape(-1, 1, 2)
        mapped = cv2.perspectiveTransform(pts, self._H).reshape(-1, 2)
        diff = (mapped - np.asarray(dst, np.float32)) / np.array(
            [self.proj_w, self.proj_h], np.float32)
        per_point = np.sqrt(np.sum(diff * diff, axis=1))
        self._residuals = [float(v) for v in per_point]
        return float(np.sqrt(np.mean(per_point * per_point)))

    def dst_corners(self) -> np.ndarray:
        """Destination rectangle in projector pixels, in CORNER_ORDER."""
        w, h = self.proj_w, self.proj_h
        return np.float32([[0, 0], [w, 0], [w, h], [0, h]])

    # --- environment validation ------------------------------------------
    def warn_if_environment_changed(self, cam_res, flip,
                                    cursor_gain: Optional[float] = None) -> None:
        """Reconcile the saved calibration with the current camera environment.

        A SAME-ASPECT resolution change is a linear per-axis rescale of the
        source pixels, so it is composed into H losslessly (same-aspect webcam
        modes share the same field of view) instead of silently misprojecting
        the cursor. A DIFFERENT-aspect change (e.g. driver fell back to 4:3)
        crops the FOV and is NOT a pure rescale, and a FLIP change cannot be
        absorbed either -> warn loudly so the operator recalibrates instead of
        chasing a 'drifting cursor' ghost. A cursor_gain change since the
        calibration was captured ALSO silently moves where the corners land
        (gain shapes the captured reach) -> warn the same way."""
        if self._H is None:
            return
        if (self._cam_res
                and [int(v) for v in self._cam_res] != [int(v) for v in cam_res]
                and int(cam_res[0]) > 0 and int(cam_res[1]) > 0):
            ow, oh = (float(v) for v in self._cam_res)
            nw, nh = float(cam_res[0]), float(cam_res[1])
            if abs(ow / oh - nw / nh) < 0.01 and self._undistort:
                # Undistort intrinsics (K/dist) are pinned to the OLD resolution;
                # composing scale into H would leave map_point undistorting new-res
                # pixels with old-res K (wrong). No lossless shortcut here -> warn.
                print(f"[homography] UYARI: kamera cozunurlugu {self._cam_res} -> "
                      f"{list(cam_res)} degisti VE undistort acik (intrinsics eski "
                      "cozunurluge bagli) -> otomatik olcekleme guvenli degil, "
                      "yeniden kalibre et (oyunda C tusu).")
            elif abs(ow / oh - nw / nh) < 0.01:
                scale = np.array([[ow / nw, 0.0, 0.0],
                                  [0.0, oh / nh, 0.0],
                                  [0.0, 0.0, 1.0]], dtype=np.float32)
                self._H = (self._H @ scale).astype(np.float32)
                print(f"[homography] kalibrasyon {self._cam_res} cozunurlugunde "
                      f"kaydedilmisti; H, {list(cam_res)} icin otomatik olceklendi "
                      f"(ayni en-boy orani, kayipsiz). Kesin dogruluk icin firsat "
                      f"oldugunda yeniden kalibre et (oyunda C tusu).")
                self._cam_res = [int(cam_res[0]), int(cam_res[1])]
            else:
                print(f"[homography] UYARI: kamera cozunurlugu {self._cam_res} -> "
                      f"{list(cam_res)} EN-BOY ORANI degiserek degisti (FOV kirpilir, "
                      "otomatik olcekleme guvenli degil) -> yeniden kalibre et "
                      "(oyunda C tusu).")
        if self._flip is not None and bool(self._flip) != bool(flip):
            print(f"[homography] UYARI: flip_horizontal {self._flip} -> {bool(flip)} "
                  "degisti -> dogruluk icin yeniden kalibre et (oyunda C tusu).")
        # cursor_gain drift: the saved calib baked in a specific gain; if config
        # changed it, the corner tokens can silently become unreachable.
        cg = self._cursor_gain if cursor_gain is None else float(cursor_gain)
        if (self._saved_gain is not None
                and abs(float(self._saved_gain) - float(cg)) > 1e-6):
            print(f"[homography] UYARI: cursor_gain {self._saved_gain} -> {cg} "
                  "degisti; kalibrasyon eski gain ile yapilmisti -> KOSE TOKEN'LARI "
                  "erisilemez olabilir. Yeniden kalibre et (oyunda C tusu).")

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

        # Undistort FIRST, with the same intrinsics the fit used (no-op when the
        # calibration was built without undistort), then apply H.
        if self._undistort:
            p = self._undistort_pts(np.array([[px, py]], dtype=np.float32))
            px, py = float(p[0][0]), float(p[0][1])
        pt = np.array([[[px, py]]], dtype=np.float32)        # shape (1,1,2) - required
        out = cv2.perspectiveTransform(pt, self._H)[0][0]
        nx = float(out[0]) / self.proj_w
        ny = float(out[1]) / self.proj_h
        # Clamp so an out-of-bounds hand never sends wild values downstream.
        return (min(1.0, max(0.0, nx)), min(1.0, max(0.0, ny)))
