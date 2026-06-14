"""Plain RGB webcam source built on OpenCV VideoCapture."""

from __future__ import annotations

from typing import Optional

import cv2

from .base import CameraSource, Frame


class WebcamSource(CameraSource):
    def __init__(self, cfg):
        self._flip = bool(cfg.camera.flip_horizontal)
        index = int(cfg.camera.device_index)

        # CAP_DSHOW avoids the slow MSMF backend startup on Windows.
        self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            # Fall back to the default backend if DSHOW is unavailable.
            self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open webcam at device_index={index}. "
                f"Check the camera is connected and not in use by another app."
            )

        # MJPG + a high FPS request lets the webcam hit its real 30/60 fps ceiling
        # instead of the ~15-20 fps raw-YUY2 / auto-exposure default (measured: this
        # doubled capture from 16 -> 30 fps, which is the lens update rate).
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self._cap.set(cv2.CAP_PROP_FPS, 60)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(cfg.camera.request_width))
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(cfg.camera.request_height))
        # Keep latency low: a 1-frame buffer means we always read the newest frame.
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # The driver may negotiate a different resolution than requested - read back.
        self._w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._w, self._h)

    def read(self) -> Optional[Frame]:
        ok, bgr = self._cap.read()
        if not ok or bgr is None:
            return None
        if self._flip:
            # 1 = horizontal mirror. Baked in here so every downstream stage
            # (detection, calibration, live mapping) sees the same frame.
            bgr = cv2.flip(bgr, 1)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return Frame(rgb=rgb)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
