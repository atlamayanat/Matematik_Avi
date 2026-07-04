"""Intel RealSense (D4xx) RGB-D camera source via pyrealsense2.

Delivers the SAME mirrored RGB frames as WebcamSource plus a color-aligned
float32 depth map in metres, so the selector can tell the extended playing
hand (nearest to camera) from the idle hand at the body plane (~0.5-0.7 m
farther) - the one distinction a single RGB image fundamentally cannot make.

Capture runs in a BACKGROUND daemon thread (latest-value-wins). This is the
key to the non-negotiable 60 fps feel: a USB bandwidth hiccup or a slow
frameset NEVER blocks the main loop, because read() returns the most recent
frame instantly instead of waiting on the device. While the camera stalls the
main loop keeps emitting its 60 Hz cursor/WS heartbeat, so the game does not
freeze. A truly dead device (pipeline restart keeps failing) is surfaced by
raising from read() - the operator sees a real fault instead of a silent hang.

Notes specific to the kiosk D435f:
  * The color sensor caps at 30 fps at 1280x720; 960x540 and below run 60 fps.
    We try 60 fps first and fall back to 30 so any configured mode still opens.
  * auto_exposure_priority is DISABLED: with it on, dim exhibition lighting
    silently halves the frame rate to keep exposure, which reads as game lag.
  * Depth is streamed at 848x480 (native fast mode) and aligned to color by
    the SDK, so depth[y, x] corresponds to rgb[y, x] 1:1.
  * Both color AND depth are mirrored together when flip_horizontal is set -
    the whole pipeline (detection, calibration, mapping) sees ONE coordinate
    frame, exactly like WebcamSource.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import cv2
import numpy as np

from .base import CameraSource, Frame

_DEPTH_W, _DEPTH_H = 848, 480   # native D4xx fast depth mode


class DepthSource(CameraSource):
    def __init__(self, cfg):
        import pyrealsense2 as rs   # lazy: webcam path must not require the SDK

        self._rs = rs
        self._flip = bool(cfg.camera.flip_horizontal)
        w = int(cfg.camera.request_width)
        h = int(cfg.camera.request_height)

        self._pipe = rs.pipeline()
        profile = None
        last_exc: Optional[Exception] = None
        for fps in (60, 30):
            try:
                rs_cfg = rs.config()
                rs_cfg.enable_stream(rs.stream.color, w, h, rs.format.bgr8, fps)
                rs_cfg.enable_stream(rs.stream.depth, _DEPTH_W, _DEPTH_H,
                                     rs.format.z16, fps)
                profile = self._pipe.start(rs_cfg)
                self._rs_cfg = rs_cfg   # kept for a mid-run pipeline restart
                break
            except RuntimeError as exc:   # unsupported mode combination
                last_exc = exc
        if profile is None:
            raise RuntimeError(
                f"RealSense could not start color {w}x{h} @60/30fps + depth "
                f"{_DEPTH_W}x{_DEPTH_H}: {last_exc}"
            )

        dev = profile.get_device()
        name = dev.get_info(rs.camera_info.name)
        self._depth_scale = float(dev.first_depth_sensor().get_depth_scale())

        # Constant frame rate > pretty exposure: with auto-exposure PRIORITY on,
        # the RGB sensor drops fps in dim light and the game visibly stutters.
        try:
            color_sensor = None
            for s in dev.query_sensors():
                if s.get_info(rs.camera_info.name) == "RGB Camera":
                    color_sensor = s
                    break
            if color_sensor is not None and color_sensor.supports(
                    rs.option.auto_exposure_priority):
                color_sensor.set_option(rs.option.auto_exposure_priority, 0)
        except Exception:   # noqa: BLE001 - cosmetic option; never block startup
            pass

        self._align = rs.align(rs.stream.color)
        self._w, self._h = w, h

        # --- background capture thread (latest-value-wins) -----------------
        self._lock = threading.Lock()
        self._latest: Optional[Frame] = None
        self._error: Optional[Exception] = None      # fatal device fault, raised by read()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._capture_loop, name="realsense-capture", daemon=True)
        self._thread.start()
        print(f"[camera] RealSense '{name}' acildi: renk {w}x{h} + "
              f"hizali derinlik {_DEPTH_W}x{_DEPTH_H} (arka plan yakalama thread'i)")

        # Give the thread a beat to produce the first frame so the game does not
        # open on a 'no camera' flicker. Non-fatal: if none arrives the main
        # loop's None-path just retries (and a real fault sets self._error).
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            with self._lock:
                if self._latest is not None or self._error is not None:
                    break
            time.sleep(0.02)

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._w, self._h)

    # --- capture thread ---------------------------------------------------
    def _capture_loop(self) -> None:
        """Continuously pull frames OFF the main thread; keep only the newest.
        All the per-frame cost (align, flip, colour convert, metric scaling)
        happens here, so the main loop's read() is a cheap latest-value fetch."""
        timeouts = 0
        while not self._stop.is_set():
            try:
                frames = self._pipe.wait_for_frames(timeout_ms=1000)
                timeouts = 0
            except RuntimeError:
                timeouts += 1
                if timeouts % 5 == 0:   # ~5 s without frames -> try to recover
                    print(f"[camera] RealSense {timeouts} sn'dir kare vermiyor; "
                          "pipeline yeniden baslatiliyor...")
                    try:
                        self._pipe.stop()
                    except RuntimeError:
                        pass
                    try:
                        self._pipe.start(self._rs_cfg)
                        print("[camera] RealSense yeniden baglandi.")
                        timeouts = 0
                    except RuntimeError as exc:
                        # Device truly gone: record it; read() raises so the
                        # operator sees a real error instead of a hung game.
                        with self._lock:
                            self._error = RuntimeError(
                                "RealSense kurtarilamadi (kablo/USB portunu "
                                f"kontrol et): {exc}")
                        return
                continue

            frames = self._align.process(frames)
            color = frames.get_color_frame()
            depth = frames.get_depth_frame()
            if not color or not depth:
                continue

            bgr = np.asanyarray(color.get_data())
            z16 = np.asanyarray(depth.get_data())
            if self._flip:
                bgr = cv2.flip(bgr, 1)
                z16 = cv2.flip(z16, 1)   # mirrored TOGETHER: depth[y,x] <-> rgb[y,x]
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            depth_m = z16.astype(np.float32) * self._depth_scale   # metres; 0 = invalid
            with self._lock:
                self._latest = Frame(rgb=rgb, depth=depth_m)

    # --- main thread ------------------------------------------------------
    def read(self) -> Optional[Frame]:
        """Non-blocking: return the newest captured frame (never waits on the
        device). Returns None until the first frame arrives; raises only on a
        confirmed unrecoverable device fault (so it is not swallowed silently)."""
        with self._lock:
            if self._error is not None:
                raise self._error
            return self._latest

    def close(self) -> None:
        self._stop.set()
        t = getattr(self, "_thread", None)
        if t is not None:
            t.join(timeout=2.0)
        if self._pipe is not None:
            try:
                self._pipe.stop()
            except RuntimeError:
                pass   # already stopped
            self._pipe = None
