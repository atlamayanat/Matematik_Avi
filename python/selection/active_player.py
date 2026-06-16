"""Active-player selection: always track the NEAREST hand, at ANY distance.

A single RGB camera sees the player's hand and possibly bystanders. Policy:
  1. NO distance floor - whenever MediaPipe detects a hand, one is selected. A
     lone hand stays tracked however far it is; only MediaPipe's own detection
     confidence limits range (there is no minimum-size / "too far" rejection).
  2. NEAREST wins - among several hands, pick the largest apparent size
     (wrist->middle-MCP span is the only distance proxy from one RGB camera), so
     the front-most player drives the cursor.
  3. STABLE lock - keep identity by nearest-centroid association; release only
     after the hand is gone for K frames (NOT for shrinking/going far); a clearly
     nearer challenger (steal_ratio x for several frames) can take over, so the
     cursor doesn't flip-flop between two people standing at similar distance.

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


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class ActivePlayerSelector:
    def __init__(self, cfg):
        ap = cfg.active_player
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
        # NO lower size bound -> a lone/far hand stays selectable (MediaPipe's own
        # detection confidence is the only range limit now). Keep the upper bound
        # (hand shoved onto the lens) and the ROI gate (edge bystanders).
        return [h for h in hands
                if h.span01 < self.max_size and self._in_roi(h)]

    # --- main update ------------------------------------------------------
    def update(self, hands: List[HandObservation]) -> SelectionResult:
        cands = self._candidates(hands)

        if self._locked is None:
            return self._try_acquire(cands)
        return self._track_locked(cands)

    def _try_acquire(self, cands: List[HandObservation]) -> SelectionResult:
        if not cands:
            return SelectionResult(None, False, False)
        # Front-most = largest apparent hand; any detected hand qualifies.
        self._locked = max(cands, key=lambda h: h.span01)
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

        if match is None:
            # Hand gone (out of frame / not detected): hold the last hand, then
            # release after K frames. We do NOT release for being far/small.
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
