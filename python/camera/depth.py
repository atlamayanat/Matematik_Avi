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

Depth quality knobs (config.camera.*) - added so the z-gate gets a FILLED,
denoised depth map instead of the raw stream:
  * visual_preset / laser_power / emitter_enabled / depth_gain are applied to
    the depth sensor ONCE at open. The preset is set FIRST because a preset
    change resets laser/gain to the preset defaults; we override afterwards.
  * A STATEFUL post-processing filter chain runs in the capture thread BEFORE
    align. The filters are created ONCE (temporal keeps history across frames -
    rebuilding them per frame would reset that history). Order matters and
    follows Intel's guidance: decimation -> depth->disparity -> spatial ->
    temporal -> disparity->depth -> hole-filling -> align(color). Each filter
    is fed the WHOLE frameset (`.process(frames).as_frameset()`), so align
    still finds a matching color frame; decimation shrinks depth but align
    resamples it back to color resolution, so depth[y,x] <-> rgb[y,x] stays 1:1.
  * RGB exposure/gain/white-balance can be LOCKED (rgb_lock.enabled) for a
    controlled tent; left OFF by default so an unattended kiosk keeps its
    auto-exposure safety net until the final on-site lighting is dialled in.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import cv2
import numpy as np

from .base import CameraSource, Frame

_DEPTH_W, _DEPTH_H = 848, 480   # native D4xx fast depth mode
_SOFT_HANG_S = 15.0             # no REAL frame this long -> fatal (soft-hang recovery)


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

        # Depth sensor quality options + RGB exposure lock. Cosmetic: never block
        # startup, so each is wrapped and failures are logged but swallowed.
        self._apply_depth_options(dev, cfg)
        self._apply_rgb_options(dev, cfg)

        # Stateful post-processing filter chain (built once; see module docstring).
        self._filters = self._build_filters(cfg)

        # Factory colour intrinsics (for optional homography undistort). None on
        # any SDK hiccup so the mapping path just skips undistortion.
        self._intrinsics = self._read_intrinsics(profile, w, h)

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

    # --- one-time device configuration ------------------------------------
    def _apply_depth_options(self, dev, cfg) -> None:
        """visual_preset FIRST (it resets laser/gain), then emitter/laser/gain.
        The WHOLE body is guarded (enum lookups included) so an unsupported /
        renamed SDK symbol logs-and-skips instead of aborting camera startup."""
        rs = self._rs
        cam = cfg.camera
        try:
            ds = dev.first_depth_sensor()

            def _set(option, value, label):
                try:
                    if ds.supports(option):
                        ds.set_option(option, float(value))
                except Exception as exc:   # noqa: BLE001 - option unsupported/out of range
                    print(f"[camera] {label} ayarlanamadi ({value}): {exc}")

            preset_name = str(cam.get("depth_visual_preset", "") or "").lower()
            if preset_name:
                presets = {
                    "custom": rs.rs400_visual_preset.custom,
                    "default": rs.rs400_visual_preset.default,
                    "hand": rs.rs400_visual_preset.hand,
                    "high_accuracy": rs.rs400_visual_preset.high_accuracy,
                    "high_density": rs.rs400_visual_preset.high_density,
                    "medium_density": rs.rs400_visual_preset.medium_density,
                }
                if preset_name in presets:
                    _set(rs.option.visual_preset, int(presets[preset_name]),
                         f"visual_preset={preset_name}")
                else:
                    print(f"[camera] bilinmeyen depth_visual_preset {preset_name!r} "
                          "(high_density/high_accuracy/hand/default/medium_density)")

            emitter = cam.get("emitter_enabled", None)
            if emitter is not None:
                _set(rs.option.emitter_enabled, int(emitter), "emitter_enabled")
            laser = cam.get("laser_power", None)
            if laser is not None:
                _set(rs.option.laser_power, float(laser), "laser_power")
            gain = cam.get("depth_gain", None)
            if gain is not None:
                _set(rs.option.gain, float(gain), "depth_gain")
        except Exception as exc:   # noqa: BLE001 - cosmetic; never block startup
            print(f"[camera] derinlik sensoru ayarlari atlandi: {exc}")

    def _apply_rgb_options(self, dev, cfg) -> None:
        """Constant frame rate > pretty exposure: auto_exposure_priority=0 keeps
        fps stable in dim light. Optionally LOCK exposure/gain/WB (rgb_lock) for
        a controlled tent - OFF by default so the kiosk keeps auto-exposure."""
        rs = self._rs
        try:
            color_sensor = None
            for s in dev.query_sensors():
                if s.get_info(rs.camera_info.name) == "RGB Camera":
                    color_sensor = s
                    break
            if color_sensor is None:
                return
            if color_sensor.supports(rs.option.auto_exposure_priority):
                color_sensor.set_option(rs.option.auto_exposure_priority, 0)

            lock = cfg.camera.get("rgb_lock", None)
            if lock is None or not bool(lock.get("enabled", False)):
                return

            def _set(option, value, label):
                try:
                    if color_sensor.supports(option):
                        color_sensor.set_option(option, float(value))
                except Exception as exc:   # noqa: BLE001
                    print(f"[camera] RGB {label} ayarlanamadi ({value}): {exc}")

            # Turn OFF auto exposure / auto white balance, then pin the values.
            _set(rs.option.enable_auto_exposure, 0, "enable_auto_exposure")
            exp = lock.get("exposure", None)
            if exp is not None:
                _set(rs.option.exposure, exp, "exposure")
            g = lock.get("gain", None)
            if g is not None:
                _set(rs.option.gain, g, "gain")
            wb = lock.get("white_balance", None)
            if wb is not None:
                _set(rs.option.enable_auto_white_balance, 0, "enable_auto_white_balance")
                _set(rs.option.white_balance, wb, "white_balance")
            print("[camera] RGB pozlama/kazanc/WB KILITLENDI (rgb_lock.enabled=true).")
        except Exception as exc:   # noqa: BLE001 - cosmetic; never block startup
            print(f"[camera] RGB ayarlari atlandi: {exc}")

    def _build_filters(self, cfg) -> list:
        """Stateful RealSense post-processing chain, created ONCE. Empty list =
        no filtering (raw depth, previous behaviour)."""
        rs = self._rs
        cam = cfg.camera
        chain: list = []
        try:
            mag = int(cam.get("decimation_magnitude", 1) or 1)
            if mag > 1:
                dec = rs.decimation_filter()
                dec.set_option(rs.option.filter_magnitude, float(mag))
                chain.append(dec)

            sp = cam.get("spatial", None)
            tp = cam.get("temporal", None)
            sp_on = sp is not None and bool(sp.get("enabled", False))
            tp_on = tp is not None and bool(tp.get("enabled", False))
            use_disparity = bool(cam.get("disparity_transform", False)) and (sp_on or tp_on)

            if use_disparity:
                chain.append(rs.disparity_transform(True))   # depth -> disparity
            if sp_on:
                spatial = rs.spatial_filter()
                spatial.set_option(rs.option.filter_magnitude, float(sp.get("magnitude", 2)))
                spatial.set_option(rs.option.filter_smooth_alpha, float(sp.get("alpha", 0.5)))
                spatial.set_option(rs.option.filter_smooth_delta, float(sp.get("delta", 20)))
                spatial.set_option(rs.option.holes_fill, float(sp.get("holes_fill", 0)))
                chain.append(spatial)
            if tp_on:
                temporal = rs.temporal_filter()
                temporal.set_option(rs.option.filter_smooth_alpha, float(tp.get("alpha", 0.4)))
                temporal.set_option(rs.option.filter_smooth_delta, float(tp.get("delta", 20)))
                # temporal 'holes_fill' == persistency index (0-8).
                temporal.set_option(rs.option.holes_fill, float(tp.get("persistency", 3)))
                chain.append(temporal)
            if use_disparity:
                chain.append(rs.disparity_transform(False))  # disparity -> depth

            if bool(cam.get("hole_filling", False)):
                chain.append(rs.hole_filling_filter())
        except Exception as exc:   # noqa: BLE001 - any filter build failure -> run raw
            print(f"[camera] derinlik filtre zinciri kurulamadi, ham derinlikle "
                  f"devam: {exc}")
            return []
        if chain:
            print(f"[camera] derinlik filtre zinciri: {len(chain)} asama "
                  "(stateful, capture thread'inde).")
        return chain

    def _read_intrinsics(self, profile, w, h):
        """Factory colour intrinsics as (K 3x3, dist 5) for optional undistort.
        Mirrored to match flip_horizontal so it lines up with the flipped image.
        None on any failure -> mapping just skips undistortion."""
        rs = self._rs
        try:
            vp = profile.get_stream(rs.stream.color).as_video_stream_profile()
            it = vp.get_intrinsics()
            fx, fy, ppx, ppy = it.fx, it.fy, it.ppx, it.ppy
            coeffs = list(it.coeffs[:5]) + [0.0] * (5 - len(it.coeffs[:5]))
            if self._flip:
                # Image mirrored about x -> principal point mirrors, and the
                # x-tangential term (p2, index 3) flips sign.
                ppx = (float(it.width) - 1.0) - ppx
                coeffs[3] = -coeffs[3]
            K = np.array([[fx, 0.0, ppx],
                          [0.0, fy, ppy],
                          [0.0, 0.0, 1.0]], dtype=np.float64)
            dist = np.array(coeffs, dtype=np.float64)
            return (K, dist)
        except Exception as exc:   # noqa: BLE001
            print(f"[camera] renk intrinsics okunamadi (undistort kapali): {exc}")
            return None

    @property
    def intrinsics(self):
        """(K 3x3, dist 5) factory colour intrinsics, or None. Consumed by the
        homography undistort option; absent on webcams."""
        return self._intrinsics

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._w, self._h)

    # --- capture thread ---------------------------------------------------
    def _apply_filters(self, frames):
        """Run the stateful post-processing chain on the whole frameset. On any
        hiccup - or if a filter drops the colour frame so align would lose a
        stream - fall back to the UNFILTERED frameset (raw depth beats no frame)."""
        if not self._filters:
            return frames
        original = frames
        try:
            for f in self._filters:
                frames = f.process(frames).as_frameset()
            if not frames.get_color_frame():
                return original
        except Exception:   # noqa: BLE001
            return original
        return frames

    def _capture_loop(self) -> None:
        """Continuously pull frames OFF the main thread; keep only the newest.
        All the per-frame cost (filters, align, flip, colour convert, metric
        scaling) happens here, so the main loop's read() is a cheap fetch."""
        timeouts = 0
        last_ok = time.monotonic()   # wall time of the last REAL delivered frame
        while not self._stop.is_set():
            try:
                frames = self._pipe.wait_for_frames(timeout_ms=1000)
                timeouts = 0
            except RuntimeError:
                timeouts += 1
                # SOFT-HANG guard. The periodic restart below resets `timeouts`,
                # so a pipeline that keeps "starting OK" but delivers NO frames
                # (partial USB re-enumeration after a brownout) would otherwise
                # loop forever while read() serves a stale frame -> cursor looks
                # ALIVE but never responds, no error, no log. Track wall time
                # since the last REAL frame INDEPENDENTLY of the restart counter;
                # after _SOFT_HANG_S declare a fatal fault so read() raises and
                # the top-level supervisor restarts the whole detector clean.
                if time.monotonic() - last_ok > _SOFT_HANG_S:
                    with self._lock:
                        self._error = RuntimeError(
                            f"RealSense {_SOFT_HANG_S:.0f} sn'dir GERCEK kare "
                            "vermiyor (yumusak takilma) -> dedektor yeniden "
                            "baslatiliyor.")
                    return
                if timeouts % 5 == 0:   # ~5 s without frames -> try to recover
                    print(f"[camera] RealSense {timeouts} sn'dir kare vermiyor; "
                          "pipeline yeniden baslatiliyor...")
                    try:
                        self._pipe.stop()
                    except RuntimeError:
                        pass
                    try:
                        self._pipe.start(self._rs_cfg)
                        print("[camera] RealSense pipeline yeniden basladi "
                              "(kare akisi dogrulanacak).")
                        timeouts = 0   # NOTE: do NOT reset last_ok - only a real frame does
                    except RuntimeError as exc:
                        # Device truly gone: record it; read() raises so the
                        # supervisor restarts instead of hanging the game.
                        with self._lock:
                            self._error = RuntimeError(
                                "RealSense kurtarilamadi (kablo/USB portunu "
                                f"kontrol et): {exc}")
                        return
                continue

            # Post-process depth (stateful chain) BEFORE align, then align to
            # colour. Decimation shrinks depth; align resamples it back to
            # colour resolution, so depth[y,x] <-> rgb[y,x] stays 1:1.
            frames = self._apply_filters(frames)
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
            last_ok = time.monotonic()   # a genuine frame was delivered

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
