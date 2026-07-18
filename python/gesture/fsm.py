"""Gesture debounce finite-state machine.

Raw per-frame labels flicker near the open/fist boundary - especially at 2-3 m
where the landmarks are noisy. The old rule ("N CONSECUTIVE frames") reset the
whole count on a single glitch frame, so a far or loosely-closed fist often
never committed. Now a SLIDING-WINDOW MAJORITY VOTE decides:

  * FIST commits when >= fist_votes of the last `window` raw labels are fist,
  * back to SEARCHING when >= open_votes of the window are open.

A lone noisy frame merely dilutes the vote instead of restarting it. The vote
asymmetry is deliberate and INVERTS the old bias (the old FSM made entering
fist the stickiest transition, which is why far/loose fists never fired):
entering FIST needs fewer votes so the catch stays responsive, while leaving
needs more so a held fist survives brief landmark glitches. A 1-2 frame
accidental fist still cannot fire on its own.

NOTE: fist_votes + open_votes MUST exceed window, otherwise both commit
conditions can hold at once and the state oscillates every frame (enforced
in __init__).

Committed states (these are the strings sent to the game):
  "searching" - open palm / no clear gesture -> the player is hunting the mouse.
  "fist"      - closed fist -> drop the net.
"""

from __future__ import annotations

from collections import deque

SEARCHING = "searching"
FIST = "fist"


def _raw_to_target(raw_gesture: str) -> str:
    """Collapse the canonical MediaPipe gesture labels into our two states."""
    return FIST if raw_gesture == "Closed_Fist" else SEARCHING


class GestureFSM:
    def __init__(self, cfg):
        g = cfg.gesture_fsm
        self.window = int(g.get("window", 7))
        self.fist_votes = int(g.get("fist_votes", 4))
        self.open_votes = int(g.get("open_votes", 5))
        if self.fist_votes + self.open_votes <= self.window:
            raise ValueError(
                "gesture_fsm: fist_votes + open_votes must be GREATER than "
                f"window (got {self.fist_votes}+{self.open_votes} <= {self.window}); "
                "otherwise fist and open can commit on the same frame and the "
                "state oscillates.")
        self._recent: deque[str] = deque(maxlen=self.window)
        self._committed = SEARCHING

    @property
    def state(self) -> str:
        return self._committed

    @property
    def fist_ratio(self) -> float:
        """Fraction of the current window voting FIST (0..1). The cursor
        extrapolation uses this to DAMP prediction as a real fist builds up, so
        it does not overshoot at the moment of selection - while a single stray
        fist frame (ratio ~1/window) barely damps and the sweep stays live."""
        if not self._recent:
            return 0.0
        return sum(1 for s in self._recent if s == FIST) / len(self._recent)

    def reset(self) -> None:
        """Reset to SEARCHING (call when the active player changes)."""
        self._recent.clear()
        self._committed = SEARCHING

    def update(self, raw_gesture: str) -> str:
        """Feed one raw label, return the committed state."""
        self._recent.append(_raw_to_target(raw_gesture))
        fist_n = sum(1 for s in self._recent if s == FIST)
        open_n = len(self._recent) - fist_n

        if self._committed != FIST and fist_n >= self.fist_votes:
            self._committed = FIST
        elif self._committed == FIST and open_n >= self.open_votes:
            self._committed = SEARCHING
        return self._committed
