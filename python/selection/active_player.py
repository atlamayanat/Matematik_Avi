"""Active-player selection: track the NEAREST hand, now DEPTH-FIRST.

A single RGB camera cannot reliably tell the extended playing hand from the
idle hand resting at the body: apparent size is pose-dependent (a palm-down
reach toward the camera foreshortens), so size-only selection either jumps to
the idle hand (loose gates) or freezes on fast sweeps (tight gates). With an
RGB-D camera (RealSense) every hand carries z_m - metres from the camera - and
the ambiguity disappears:

  1. ACQUIRE   - lock the hand nearest IN DEPTH (min z). The extended playing
                 hand is definitionally nearest in this kiosk. Falls back to
                 largest apparent size when depth is unavailable.
  2. IDENTITY  - nearest-centroid association within a GENEROUS positional
                 gate (fast sweeps re-match instantly -> no freeze/stutter),
                 plus a DEPTH gate: a candidate more than assoc_max_dz farther/
                 nearer than the locked hand is a DIFFERENT hand (the idle hand
                 sits ~0.5-0.7 m behind the playing hand) and can never
                 silently inherit the lock.
  3. STEAL     - only a hand clearly NEARER in depth (by steal_z_margin, for
                 steal_frames) may take over: that is the player extending
                 their OTHER hand (intentional hand switch). The idle hand is
                 farther and structurally cannot steal. Span-ratio steal is
                 kept only as the no-depth fallback.
  4. RELEASE   - unchanged: hold through dropouts, release after K frames.

Remaining gates are NOT about distance: ROI rejects hands at the frame edges,
and max_size rejects a hand shoved onto the lens.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from detection.types import HandObservation


@dataclass
class SelectionResult:
    locked: Optional[HandObservation]   # the chosen hand this frame, or None
    just_acquired: bool                 # lock started this frame OR switched player
    just_released: bool                 # lock ended this frame
    coasted: bool = False               # locked hand is STALE (re-served through a
                                        # detection dropout, not seen this frame) ->
                                        # its gesture must NOT feed the FSM (ghost fist)


def _dist(a, b, y_scale: float = 1.0) -> float:
    """Distance in FRAME-WIDTH units: y (normalized by height) is rescaled by
    h/w so vertical moves are not inflated 16/9x versus horizontal ones."""
    return math.hypot(a[0] - b[0], (a[1] - b[1]) * y_scale)


def _z_or_none(obs: Optional[HandObservation]) -> Optional[float]:
    return None if obs is None else obs.z_m


class ActivePlayerSelector:
    def __init__(self, cfg, cam_res=None):
        ap = cfg.active_player
        self.max_size = float(ap.max_size)
        self.roi = (float(ap.roi_x_min), float(ap.roi_x_max),
                    float(ap.roi_y_min), float(ap.roi_y_max))
        self.steal_ratio = float(ap.steal_ratio)
        self.steal_frames = int(ap.steal_frames)
        self.lost_frames_to_release = int(ap.lost_frames_to_release)
        self.assoc_max_jump = float(ap.assoc_max_jump)
        # Depth gates (metres). Used only when BOTH hands carry a valid z_m.
        self.assoc_max_dz = float(ap.get("assoc_max_dz", 0.4))
        self.steal_z_margin = float(ap.get("steal_z_margin", 0.25))
        # Prefer the NEGOTIATED camera resolution (the driver may ignore the
        # request); fall back to the requested one when no camera is around.
        w, h = cam_res if cam_res else (cfg.camera.request_width,
                                        cfg.camera.request_height)
        self._y_scale = float(h) / float(w)

        self._locked: Optional[HandObservation] = None
        self._locked_z: Optional[float] = None   # last KNOWN depth of the lock
        self._lost = 0
        self._steal = 0

    # --- gates ------------------------------------------------------------
    def _in_roi(self, obs: HandObservation) -> bool:
        x, y = obs.centroid01
        xmin, xmax, ymin, ymax = self.roi
        return xmin <= x <= xmax and ymin <= y <= ymax

    def _candidates(self, hands: List[HandObservation]) -> List[HandObservation]:
        # NO lower size bound -> a lone/far hand stays selectable (MediaPipe's own
        # detection confidence is the only range limit now). Keep the upper bound
        # (hand shoved onto the lens) and the ROI gate (edge bystanders).
        return [h for h in hands
                if h.span01 < self.max_size and self._in_roi(h)]


    @staticmethod
    def _nearest(cands: List[HandObservation]) -> HandObservation:
        """Nearest hand: min depth when known; largest apparent size otherwise.
        Used to pick the STEAL challenger; acquire uses _acquire_pick (which is
        ambiguity-aware) instead, so a momentary depth hole cannot lock the far
        idle hand."""
        with_z = [h for h in cands if h.z_m is not None]
        if with_z:
            return min(with_z, key=lambda h: h.z_m)
        return max(cands, key=lambda h: h.span01)

    @staticmethod
    def _acquire_pick(cands: List[HandObservation]) -> Optional[HandObservation]:
        """Which hand to LOCK on a fresh acquire. Nearest in depth wins, but if a
        depth-UNKNOWN hand is at least as large (apparent size) as the depth-known
        nearest, it might actually be nearer - its depth patch just dropped this
        frame - so locking now risks grabbing the far idle hand (+ a spurious net
        drop). Return None in that ambiguous case to WAIT one frame for depth to
        return; acquire latency is invisible (there is no cursor yet). With no
        depth at all, fall back to largest apparent size."""
        with_z = [h for h in cands if h.z_m is not None]
        if not with_z:
            return max(cands, key=lambda h: h.span01)
        z_near = min(with_z, key=lambda h: h.z_m)
        for h in cands:
            if h.z_m is None and h.span01 >= z_near.span01:
                return None   # ambiguous: a large depth-unknown hand could be nearer
        return z_near

    # --- main update ------------------------------------------------------
    def update(self, hands: List[HandObservation]) -> SelectionResult:
        cands = self._candidates(hands)

        if self._locked is None:
            return self._try_acquire(cands)
        return self._track_locked(cands)

    def _try_acquire(self, cands: List[HandObservation]) -> SelectionResult:
        if not cands:
            return SelectionResult(None, False, False)
        pick = self._acquire_pick(cands)
        if pick is None:
            # Ambiguous depth this frame (a large hand lost its depth patch);
            # do not risk locking the far idle hand - wait for depth to return.
            return SelectionResult(None, False, False)
        self._locked = pick
        self._locked_z = pick.z_m
        self._lost = 0
        self._steal = 0
        return SelectionResult(self._locked, True, False)

    def _track_locked(self, cands: List[HandObservation]) -> SelectionResult:
        ref = self._locked.centroid01
        # Associate to the same physical hand, two-tier:
        #   * depth-CONFIRMED candidates (|dz| <= assoc_max_dz) get the GENEROUS
        #     positional gate - a fast sweep between inferences re-matches
        #     instantly, no hold/freeze stutter;
        #   * depth-CONTRADICTED candidates (idle hand ~0.5-0.7 m behind) are
        #     excluded outright - they can never silently inherit the lock;
        #   * depth-UNKNOWN candidates (speckle hole / no depth camera) only
        #     pass a TIGHT gate, so missing evidence is not a free pass.
        # A depth-confirmed match is always preferred over a depth-unknown one.
        match = None
        best = None
        match_confirmed = False
        for h in cands:
            dz_known = self._locked_z is not None and h.z_m is not None
            if dz_known and abs(h.z_m - self._locked_z) > self.assoc_max_dz:
                continue   # depth POSITIVELY says: different hand
            limit = self.assoc_max_jump if dz_known \
                else self.assoc_max_jump * 0.45
            d = _dist(h.centroid01, ref, self._y_scale)
            if d > limit:
                continue
            if (dz_known and not match_confirmed) or \
                    (dz_known == match_confirmed and (best is None or d < best)):
                best = d
                match = h
                match_confirmed = dz_known

        if match is None:
            # Hand gone (out of frame / not detected): hold the last hand, then
            # release after K frames. We do NOT release for being far/small.
            self._lost += 1
            if self._lost >= self.lost_frames_to_release:
                self._locked = None
                self._locked_z = None
                self._lost = 0
                self._steal = 0
                return SelectionResult(None, False, True)
            # Keep reporting the last known hand while we wait it out, but flag
            # it COASTED: this HandObservation is stale (not seen this frame), so
            # the main loop must not feed its gesture to the FSM or a briefly
            # curled hand yanked out of frame could commit a ghost fist.
            return SelectionResult(self._locked, False, False, coasted=True)

        # Still tracking.
        self._locked = match
        if match.z_m is not None:
            self._locked_z = match.z_m   # keep last KNOWN depth through gaps
        self._lost = 0

        # Challenger steal: another hand CLEARLY NEARER in depth for several
        # frames = the player extended their other hand (intentional switch).
        # The idle body hand is FARTHER and structurally cannot steal. Without
        # depth, fall back to the apparent-size ratio rule.
        challenger = None
        others = [h for h in cands if h is not match]
        if others:
            challenger = self._nearest(others)
        stealing = False
        if challenger is not None:
            if challenger.z_m is not None and self._locked_z is not None:
                stealing = challenger.z_m < self._locked_z - self.steal_z_margin
            elif self._locked_z is None:
                # No depth on the lock at all (webcam mode / persistent hole):
                # the apparent-size ratio is the only cue we have.
                stealing = challenger.span01 > self.steal_ratio * match.span01
            # else: we KNOW the locked hand's depth but the challenger's is
            # momentarily unknown -> do NOT steal on apparent size. A palm-forward
            # idle hand out-spans the foreshortened playing hand, and a size-based
            # steal here is exactly the idle-hand false switch depth was added to
            # kill. Wait until the challenger carries depth and is provably nearer.
        if stealing:
            self._steal += 1
            if self._steal >= self.steal_frames:
                self._locked = challenger
                self._locked_z = challenger.z_m
                self._steal = 0
                # Player change -> treat as a fresh acquire (resets smoother/FSM).
                return SelectionResult(self._locked, True, False)
        else:
            self._steal = 0

        return SelectionResult(self._locked, False, False)
