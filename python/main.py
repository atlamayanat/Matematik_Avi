"""Gesture Exhibit - detection entry point.

Pipeline per frame:
    camera -> HandLandmarker -> active-player selection -> gesture FSM
           -> homography map -> One Euro smoothing -> OSC /hand -> Unity

Usage (run from this 'python/' folder):
    python download_model.py        # once, fetch the model
    python main.py                  # run the detector
    python main.py --calibrate      # 4-corner projector calibration
    python main.py --no-preview     # headless (no OpenCV window)
    python main.py --config foo.json

Hotkeys in the preview window:  ESC = quit,  C = recalibrate.
"""

from __future__ import annotations

import argparse
import os
import time

import cv2

from collections import deque

from config import load_config
from camera import create_camera, sample_depth
from detection import HandRecognizer
from selection import ActivePlayerSelector
from gesture import GestureFSM, FIST
from smoothing import CursorSmoother
from mapping import Homography
from mapping.calibrate import run_calibration
from net import create_sender

_QUIT = "quit"
_RECALIBRATE = "recalibrate"

# MediaPipe Hands 21-point skeleton topology (drawn in the preview overlay).
_HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),            # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),            # index
    (5, 9), (9, 10), (10, 11), (11, 12),       # middle
    (9, 13), (13, 14), (14, 15), (15, 16),     # ring
    (13, 17), (17, 18), (18, 19), (19, 20),    # pinky
    (0, 17),                                   # palm base
)


def _draw_skeleton(bgr, landmarks_px, color):
    """Draw the 21-point hand skeleton: connection lines + joint dots."""
    n = len(landmarks_px)
    for a, b in _HAND_CONNECTIONS:
        if a < n and b < n:
            cv2.line(bgr, landmarks_px[a], landmarks_px[b], color, 2, cv2.LINE_AA)
    for p in landmarks_px:
        cv2.circle(bgr, p, 3, color, -1, cv2.LINE_AA)


class MonotonicMs:
    """Strictly increasing millisecond clock for detect_async timestamps."""
    def __init__(self):
        self._last = -1

    def now(self) -> int:
        ts = int(time.monotonic() * 1000)
        if ts <= self._last:
            ts = self._last + 1
        self._last = ts
        return ts


def _approaching(depth, near_z: float, frac_thresh: float) -> bool:
    """True when a large fraction of the CENTRAL ROI is nearer than near_z - i.e.
    a body has stepped into the play zone. ~0 cost (one numpy mask on a slice);
    used only to wake the attract screen, and only computed when no player is
    locked. The 0.2 m floor rejects a lens smudge / a hand shoved onto the lens."""
    try:
        h, w = depth.shape[:2]
        roi = depth[int(0.30 * h):int(0.70 * h), int(0.30 * w):int(0.70 * w)]
        total = roi.size
        if total == 0:
            return False
        near = int(((roi > 0.2) & (roi < near_z)).sum())
        return (float(near) / float(total)) >= frac_thresh
    except Exception:   # noqa: BLE001 - never let the attract probe break the loop
        return False


def _fist_damp(mode: str, fsm, committed: str) -> float:
    """Extrapolation damping in [0,1]. 'damped' scales DOWN as the fist vote
    builds (a single stray fist frame barely damps; a real held fist freezes the
    cursor). 'freeze' hard-freezes on the committed FIST. Anything else = none."""
    if mode in ("damped", "damp"):
        return max(0.0, 1.0 - fsm.fist_ratio)
    if mode in ("freeze", "true", "1", "on", "yes"):
        return 0.0 if committed == FIST else 1.0
    return 1.0


def _extrapolate(anchor, vel, anchor_t, now, lead_s, horizon_s, gain, damp):
    """Constant-velocity dead reckoning of the locked cursor, capped at
    horizon_s and clamped to [0,1] so an out-of-range hand never flings the
    cursor off-screen. anchor = last smoothed pos, vel = last smoothed speed."""
    ahead = (now - anchor_t) + lead_s
    if ahead < 0.0:
        ahead = 0.0
    if ahead > horizon_s:
        ahead = horizon_s
    k = ahead * gain * damp
    x = anchor[0] + vel[0] * k
    y = anchor[1] + vel[1] * k
    x = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
    y = 0.0 if y < 0.0 else 1.0 if y > 1.0 else y
    return (x, y)


def _draw_overlay(bgr, cfg, observations, sel, committed, present,
                  mapped, fps, calibrated):
    h, w = bgr.shape[:2]
    ap = cfg.active_player

    # ROI rectangle (interaction zone).
    cv2.rectangle(bgr,
                  (int(ap.roi_x_min * w), int(ap.roi_y_min * h)),
                  (int(ap.roi_x_max * w), int(ap.roi_y_max * h)),
                  (80, 80, 80), 1)

    locked = sel.locked
    for obs in observations:
        xs = [p[0] for p in obs.landmarks_px]
        ys = [p[1] for p in obs.landmarks_px]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        is_locked = locked is not None and obs is locked
        color = (0, 255, 0) if is_locked else (130, 130, 130)
        # Hand skeleton: fist -> magenta, open -> the lock colour above.
        skel_color = (255, 0, 255) if obs.gesture == "Closed_Fist" else color
        _draw_skeleton(bgr, obs.landmarks_px, skel_color)
        cv2.rectangle(bgr, (x1, y1), (x2, y2), color, 2 if is_locked else 1)
        z_txt = f" z{obs.z_m:.2f}m" if obs.z_m is not None else ""
        label = f"{obs.gesture} {obs.gesture_score:.2f} sz{obs.span01:.2f}{z_txt}"
        cv2.putText(bgr, label, (x1, max(y1 - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        if is_locked:
            cx, cy = int(obs.centroid_px[0]), int(obs.centroid_px[1])
            cv2.circle(bgr, (cx, cy), 6, (0, 255, 0), -1)

    # Status bar.
    state_color = (0, 0, 255) if committed == FIST else (0, 200, 255)
    lines = [
        f"FPS {fps:4.1f}   hands {len(observations)}   "
        f"{'CALIBRATED' if calibrated else 'NOT CALIBRATED (raw coords)'}",
        f"present={int(present)}  state={committed}  "
        f"mapped=({mapped[0]:.3f},{mapped[1]:.3f})",
        "ESC quit   C recalibrate",
    ]
    for i, line in enumerate(lines):
        cv2.putText(bgr, line, (12, 24 + 22 * i),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    state_color if i == 1 else (255, 255, 255), 2)


def _dbg_log(path, observations, sel, selector) -> None:
    """TEMP selector diagnostics (enabled by env MA_DEBUG=<logpath>): log both
    hands' apparent size + depth and the lock decision, so a wrong-hand jump can
    be traced to the real z values / steal counter. No-op unless MA_DEBUG is set."""
    hs = " ".join(
        f"h{i}(sz{o.span01:.3f} "
        f"z{('%.3f' % o.z_m) if o.z_m is not None else 'None'} {o.gesture[0]})"
        for i, o in enumerate(observations))
    lz = ('%.3f' % selector._locked_z) if selector._locked_z is not None else 'None'
    ln = ('%.3f' % sel.locked.z_m) if (sel.locked is not None
                                       and sel.locked.z_m is not None) else 'None'
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{time.monotonic():9.2f} n={len(observations)} {hs} | "
                f"baseZ={lz} lockedNowZ={ln} steal={selector._steal} "
                f"acq={int(sel.just_acquired)} coast={int(sel.coasted)}\n")


def run_detector(cfg, preview: bool) -> str:
    # Resource-safe setup: init to None and CREATE inside the try, so a constructor
    # that throws partway (model missing, WS port busy, camera fault) still hits the
    # finally and releases the RealSense pipeline+thread instead of leaking it. A
    # leaked capture thread holds the device, so the supervisor's next restart would
    # fail with 'device busy' in a permanent loop.
    cam = recognizer = sender = None
    try:
        cam = create_camera(cfg)
        recognizer = HandRecognizer(cfg)
        homography = Homography(cfg)
        # Saved calibration is tied to the camera resolution + mirroring it was built
        # with; if either changed, the px coords no longer line up -> warn loudly.
        homography.warn_if_environment_changed(cam.resolution, cfg.camera.flip_horizontal)
        selector = ActivePlayerSelector(cfg, cam_res=cam.resolution)
        fsm = GestureFSM(cfg)
        smoother = CursorSmoother(cfg.smoothing.min_cutoff, cfg.smoothing.beta,
                                  cfg.smoothing.d_cutoff)
        # 60 Hz predictive extrapolation (dead reckoning) config.
        _sm = cfg.smoothing
        predict_enabled = bool(_sm.get("predict_enabled", False))
        predict_lead_s = float(_sm.get("predict_lead_ms", 0)) / 1000.0
        predict_horizon_s = float(_sm.get("predict_horizon_cap_ms", 50)) / 1000.0
        predict_gain = float(_sm.get("predict_gain", 1.0))
        predict_freeze = str(_sm.get("predict_freeze_on_fist", "damped")).lower()
        # Depth-blob attract trigger config.
        _ap = cfg.active_player
        attract_near_z = float(_ap.get("attract_near_z_m", 0.0) or 0.0)
        attract_frac = float(_ap.get("attract_pixel_frac", 0.0) or 0.0)
        _net_cfg = cfg.get("net", None)
        send_approaching = bool(getattr(_net_cfg, "send_approaching", False)) \
            if _net_cfg is not None else False
        sender = create_sender(cfg)   # OSC | WebSocket | her ikisi (config.json net.transport)
        clock = MonotonicMs()
        _dbg_path = os.environ.get("MA_DEBUG")  # set to a logpath to trace selection

        frame_budget = 1.0 / float(cfg.osc.send_rate_hz)
        win = cfg.preview.window_name
        if preview:
            cv2.namedWindow(win, cv2.WINDOW_NORMAL)

        last_xy = (0.5, 0.5)
        # Extrapolation state: anchor = last smoothed pos, its wall time, and the
        # last smoothed velocity. Reset on every lock change so the cursor never
        # flings using the previous player's motion.
        pred_anchor = (0.5, 0.5)
        pred_anchor_t = time.monotonic()
        pred_vel = (0.0, 0.0)
        committed = "searching"
        mapped = (0.5, 0.5)
        present = False
        observations = []
        sel = None
        last_rid = -1
        fps = 0.0
        fps_t = time.monotonic()
        # SEPARATE inference-rate clock. The selector's steal/lost counters tick
        # once per NEW inference (~20-30 Hz), NOT once per loop (~60 Hz), so the
        # second-based thresholds must be converted with the INFERENCE rate, not
        # the loop/heartbeat `fps` above (else lost_seconds=1.0 would take ~2.4 s).
        inf_fps = 0.0
        inf_fps_t = time.monotonic()
        # Dakikalik saglik istatistigi -> stdout -> logs\detector_*.out.log.
        # tools/rapor.py bu [stats] satirlarini okuyup "kamera sorun cikardi mi"
        # bolumunu doldurur. ASCII kalir (Windows log kodlamasindan bagimsiz).
        st = {"t0": time.monotonic(), "results": 0, "hands": 0, "locked": 0, "cam_fail": 0}

        def _stats_tick(now_mono: float) -> None:
            if now_mono - st["t0"] < 60.0:
                return
            res = st["results"]
            hands_pct = 100.0 * st["hands"] / res if res else 0.0
            locked_pct = 100.0 * st["locked"] / res if res else 0.0
            try:
                # Istatistik yazimi dedektoru ASLA oldurmemeli: stdout log dosyasina
                # yonlendirilmis; disk dolarsa (ENOSPC) print OSError firlatir ve bu
                # periyodik nokta dedektoru dakikada bir cokerten bir dongu yaratirdi.
                print(f"[stats] fps={fps:.1f} results={res} hands_pct={hands_pct:.0f} "
                      f"locked_pct={locked_pct:.0f} cam_fail={st['cam_fail']} "
                      f"win_s={now_mono - st['t0']:.0f}", flush=True)
            except OSError:
                pass
            st.update(t0=now_mono, results=0, hands=0, locked=0, cam_fail=0)
        # Recent depth maps keyed by the submit timestamp, so landmarks are paired
        # with the depth of the SAME frame (inference lags capture by 1-2 frames;
        # sampling the current frame at an old centroid reads background depth
        # during fast sweeps and would break the selector's depth gate). Sized to
        # absorb an inference HITCH (GC/thermal) too, so the timestamp match rarely
        # misses; on a miss we mark depth UNKNOWN rather than trust the wrong frame.
        depth_ring = deque(maxlen=32)   # ~0.5 s at 60 fps

        _net = cfg.get("net", None)
        _transport = str(getattr(_net, "transport", "osc") if _net is not None else "osc").lower()
        print(f"[detector] running. transport={_transport}  OSC -> {cfg.osc.host}:{cfg.osc.port}  "
              f"calibrated={homography.is_calibrated}")
        while True:
            loop_start = time.monotonic()

            frame = cam.read()
            if frame is None:
                # Transient grab failure; keep the cursor parked, don't busy-spin.
                st["cam_fail"] += 1
                _stats_tick(time.monotonic())   # kamera uzun sure kesikken de istatistik aksin
                sender.send_absent(*last_xy)
                if preview and (cv2.waitKey(1) & 0xFF) == 27:
                    return _QUIT
                time.sleep(0.01)
                continue

            ts = clock.now()
            recognizer.submit(frame.rgb, ts)
            if frame.depth is not None:
                depth_ring.append((ts, frame.depth))

            # Run the pipeline only on a NEW inference result. The loop spins at
            # ~60 Hz but MediaPipe completes only ~20-30 Hz; feeding One Euro (and
            # ticking the selector/FSM frame counters) with duplicate frames is what
            # defeated the smoothing and made the lens step. We still emit an OSC
            # packet every loop (~60 Hz heartbeat) below so Unity never starves.
            rid = recognizer.result_id
            if rid != last_rid:
                last_rid = rid
                st["results"] += 1
                # Inference-rate EMA (this branch runs once per new inference).
                # Feeds the selector's second->frame conversion with the TRUE
                # tick rate, so it stays correct when thermal throttle drops the
                # inference rate below the ~60 Hz loop rate.
                _now_inf = time.monotonic()
                _inf_dt = _now_inf - inf_fps_t
                inf_fps_t = _now_inf
                if _inf_dt > 1e-3:
                    _inf_inst = 1.0 / _inf_dt
                    inf_fps = 0.9 * inf_fps + 0.1 * _inf_inst if inf_fps else _inf_inst
                observations = recognizer.get_observations()
                if observations:
                    st["hands"] += 1
                # Attach depth (metres) at each palm centre, from the depth map
                # of the SAME frame the landmarks were computed on (ring lookup
                # by timestamp), so the selector can separate the playing hand
                # from the idle body hand by ACTUAL distance. No-op on webcams.
                if depth_ring:
                    rts = recognizer.result_timestamp_ms
                    dmap = next((d for t, d in depth_ring if t == rts), None)
                    # On a ring MISS (matching frame evicted after a long hitch)
                    # leave z_m = None (unknown) rather than sample the CURRENT
                    # frame's depth at these STALE centroids - during a sweep that
                    # reads background metres and would feed the selector a
                    # confidently-wrong depth. Unknown -> the tight positional gate.
                    if dmap is not None:
                        for obs in observations:
                            obs.z_m = sample_depth(dmap,
                                                   obs.centroid_px[0],
                                                   obs.centroid_px[1])
                sel = selector.update(observations, fps=inf_fps)
                if _dbg_path and len(observations) >= 2:
                    _dbg_log(_dbg_path, observations, sel, selector)

                if sel.just_acquired:
                    smoother.reset()
                    fsm.reset()
                    pred_vel = (0.0, 0.0)   # don't fling on the new player's first frame
                if sel.just_released:
                    fsm.reset()
                    smoother.reset()
                    pred_vel = (0.0, 0.0)

                if sel.locked is not None:
                    st["locked"] += 1
                    # On a COASTED frame the locked hand was NOT seen this frame
                    # (its observation is stale). Do not feed its gesture to the
                    # FSM - re-serving a stale 'Closed_Fist' would let a hand that
                    # briefly curled while leaving the frame accrue votes and drop
                    # a ghost net. Hold the last committed state; position still
                    # coasts (stable) through the same centroid below.
                    if not sel.coasted:
                        committed = fsm.update(sel.locked.gesture)
                    raw = homography.map_point(
                        sel.locked.centroid_px[0], sel.locked.centroid_px[1],
                        sel.locked.centroid01)
                    t = time.monotonic()
                    mapped = smoother(t, raw[0], raw[1])
                    last_xy = mapped
                    # Refresh the extrapolation anchor + velocity from this fresh
                    # smoothed sample; heartbeat frames dead-reckon from here.
                    pred_anchor = mapped
                    pred_anchor_t = t
                    pred_vel = smoother.velocity()
                    present = True
                else:
                    committed = "searching"
                    present = False

            # Approaching flag (attract): fraction of the central ROI nearer than
            # attract_near_z. Computed ONLY when no player is locked, so it is
            # truly ~0 cost during play; wakes the web attract loop.
            approaching = False
            if send_approaching and not present and frame.depth is not None \
                    and attract_near_z > 0.0 and attract_frac > 0.0:
                approaching = _approaching(frame.depth, attract_near_z, attract_frac)

            # ~60 Hz heartbeat. With prediction on, the heartbeat EXTRAPOLATES the
            # locked cursor along its last smoothed velocity so it moves at 60 Hz
            # instead of stepping at the ~20-30 Hz inference rate; damped as a
            # fist builds so it does not overshoot at the moment of selection.
            if present:
                if predict_enabled:
                    damp = _fist_damp(predict_freeze, fsm, committed)
                    sx, sy = _extrapolate(pred_anchor, pred_vel, pred_anchor_t,
                                          time.monotonic(), predict_lead_s,
                                          predict_horizon_s, predict_gain, damp)
                else:
                    sx, sy = mapped
                sender.send_hand(sx, sy, True, committed, approaching)
            else:
                sender.send_absent(last_xy[0], last_xy[1], approaching)

            # FPS (EMA). Floor the interval at half the frame budget so a rare
            # near-zero dt (loop body overran the budget, next loop ran fast)
            # cannot spike inst to ~1e6 and poison the EMA into a garbage reading
            # (the loop is rate-capped, so a real value above ~2x send_rate is
            # impossible anyway).
            now = time.monotonic()
            inst = 1.0 / max(now - fps_t, frame_budget * 0.5)
            fps = 0.9 * fps + 0.1 * inst if fps else inst
            fps_t = now
            _stats_tick(now)

            if preview:
                bgr = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)
                _draw_overlay(bgr, cfg, observations, sel, committed, present,
                              mapped, fps, homography.is_calibrated)
                cv2.imshow(win, bgr)
                key = cv2.waitKey(1) & 0xFF
                if key == 27:               # ESC
                    return _QUIT
                if key in (ord('c'), ord('C')):
                    return _RECALIBRATE

            # Rate cap: never flood Unity faster than its render rate.
            sleep = frame_budget - (time.monotonic() - loop_start)
            if sleep > 0:
                time.sleep(sleep)
    finally:
        # None-guarded: setup may have thrown before a given resource existed.
        if cam is not None:
            cam.close()
        if recognizer is not None:
            recognizer.close()
        if sender is not None:
            _close = getattr(sender, "close", None)
            if callable(_close):
                _close()   # WS sunucusunu kapat / portu serbest bırak (recalibrate yeniden-başlatması için)
        if preview:
            cv2.destroyAllWindows()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gesture Exhibit detector")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--calibrate", action="store_true",
                        help="run 4-corner projector calibration and exit")
    parser.add_argument("--no-preview", action="store_true",
                        help="run without the OpenCV preview window")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.calibrate:
        run_calibration(cfg)
        return 0

    preview = not args.no_preview
    # Unattended-kiosk supervision: a crash in the detector (camera fault, driver
    # re-enumeration, an unexpected exception) must NOT be terminal. Catch it,
    # log it, and restart with a capped exponential backoff so a persistent fault
    # (camera unplugged) retries calmly instead of hot-looping. A clean run resets
    # the backoff. ESC (_QUIT) exits deliberately; Ctrl+C exits deliberately.
    backoff = 1.0
    while True:
        try:
            action = run_detector(cfg, preview)
        except KeyboardInterrupt:
            print("[detector] KeyboardInterrupt -> cikiliyor.")
            return 0
        except Exception as exc:   # noqa: BLE001 - top-level kiosk supervisor
            import traceback
            print(f"[detector] BEKLENMEDIK HATA; {backoff:.0f} sn sonra yeniden "
                  f"baslatiliyor: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)
            continue
        backoff = 1.0   # clean return -> reset backoff
        if action == _RECALIBRATE:
            run_calibration(cfg)
            continue   # restart detector; Homography reloads the new calib.json
        break          # _QUIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
