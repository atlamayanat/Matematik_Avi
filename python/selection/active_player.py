"""Active-player selection with lock-on hysteresis.

A single RGB camera in a tent sees the player's hand AND the hands of people
waiting/watching behind. This picks exactly one hand to drive the cursor and
sticks to it, so the spotlight never teleports to a bystander.

Four mechanisms (all per-frame, cheap):
  1. SIZE gate - apparent hand size (wrist->middle-MCP span) is the only distance
     proxy from one RGB camera. Reject hands smaller than exit_size (too far) or
     larger than max_size (shoved onto the lens).
  2. ROI gate - reject hands near the frame edges where bystanders lean in.
  3. LOCK-ON + hysteresis - acquire only above enter_size; keep the lock until the
     hand is lost for K frames or shrinks below exit_size (enter > exit). Maintain
     identity frame-to-frame by nearest-centroid association within a max jump.
  4. CHALLENGER STEAL - another hand can take over only if it is clearly larger
     (steal_ratio x) for several consecutive frames, so a player must deliberately
     step closer to take control.
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


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class ActivePlayerSelector:
    def __init__(self, cfg):
        ap = cfg.active_player
        self.enter_size = float(ap.enter_size)
        self.exit_size = float(ap.exit_size)
        self.max_size = float(ap.max_size)
        self.roi = (float(ap.roi_x_min), float(ap.roi_x_max),
                    float(ap.roi_y_min), float(ap.roi_y_max))
        self.steal_ratio = float(ap.steal_ratio)
        self.steal_frames = int(ap.steal_frames)
        self.lost_frames_to_release = int(ap.lost_frames_to_release)
        self.assoc_max_jump = float(ap.assoc_max_jump)

        self._locked: Optional[HandObservation] = None
        self._lost = 0
        self._steal = 0

    # --- gates ------------------------------------------------------------
    def _in_roi(self, obs: HandObservation) -> bool:
        x, y = obs.centroid01
        xmin, xmax, ymin, ymax = self.roi
        return xmin <= x <= xmax and ymin <= y <= ymax

    def _candidates(self, hands: List[HandObservation]) -> List[HandObservation]:
        # Floor at exit_size (not enter_size) so a locked hand survives down to exit.
        return [h for h in hands
                if self.exit_size < h.span01 < self.max_size and self._in_roi(h)]

    # --- main update ------------------------------------------------------
    def update(self, hands: List[HandObservation]) -> SelectionResult:
        cands = self._candidates(hands)

        if self._locked is None:
            return self._try_acquire(cands)
        return self._track_locked(cands)

    def _try_acquire(self, cands: List[HandObservation]) -> SelectionResult:
        eligible = [h for h in cands if h.span01 >= self.enter_size]
        if not eligible:
            return SelectionResult(None, False, False)
        self._locked = max(eligible, key=lambda h: h.span01)
        self._lost = 0
        self._steal = 0
        return SelectionResult(self._locked, True, False)

    def _track_locked(self, cands: List[HandObservation]) -> SelectionResult:
        ref = self._locked.centroid01
        # Associate to the same physical hand: nearest centroid within max jump.
        match = None
        best = self.assoc_max_jump
        for h in cands:
            d = _dist(h.centroid01, ref)
            if d <= best:
                best = d
                match = h

        if match is None or match.span01 < self.exit_size:
            # Losing the hand: count frames before releasing (hysteresis).
            self._lost += 1
            if self._lost >= self.lost_frames_to_release:
                self._locked = None
                self._lost = 0
                self._steal = 0
                return SelectionResult(None, False, True)
            # Keep reporting the last known hand while we wait it out.
            return SelectionResult(self._locked, False, False)

        # Still tracking.
        self._locked = match
        self._lost = 0

        # Challenger steal: a clearly larger OTHER hand for several frames.
        challenger = None
        for h in cands:
            if h is match:
                continue
            if challenger is None or h.span01 > challenger.span01:
                challenger = h
        if challenger is not None and challenger.span01 > self.steal_ratio * match.span01:
            self._steal += 1
            if self._steal >= self.steal_frames:
                self._locked = challenger
                self._steal = 0
                # Player change -> treat as a fresh acquire (resets smoother/FSM).
                return SelectionResult(self._locked, True, False)
        else:
            self._steal = 0

        return SelectionResult(self._locked, False, False)
