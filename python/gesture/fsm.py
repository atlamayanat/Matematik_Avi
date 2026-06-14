"""Gesture debounce finite-state machine.

Raw per-frame labels flicker near the open/fist boundary. This commits a new
state only after it has been stable for N frames, with an asymmetric threshold:
entering FIST (the catch action) is made stickier than returning to SEARCHING,
so a brief accidental fist does not fire, and a momentary landmark glitch does
not drop a held fist.

Committed states (these are the strings sent to Unity):
  "searching" - open palm / no clear gesture -> the player is hunting the mouse.
  "fist"      - closed fist -> drop the net.
"""

from __future__ import annotations

SEARCHING = "searching"
FIST = "fist"


def _raw_to_target(raw_gesture: str) -> str:
    """Collapse the 8 canonical MediaPipe gestures into our two states."""
    return FIST if raw_gesture == "Closed_Fist" else SEARCHING


class GestureFSM:
    def __init__(self, cfg):
        self.enter_frames = int(cfg.gesture_fsm.stable_frames_enter)
        self.fist_frames = int(cfg.gesture_fsm.stable_frames_fist)
        self._committed = SEARCHING
        self._pending = SEARCHING
        self._count = 0

    @property
    def state(self) -> str:
        return self._committed

    def reset(self) -> None:
        """Reset to SEARCHING (call when the active player changes)."""
        self._committed = SEARCHING
        self._pending = SEARCHING
        self._count = 0

    def update(self, raw_gesture: str) -> str:
        """Feed one raw label, return the committed state."""
        target = _raw_to_target(raw_gesture)

        if target == self._committed:
            # Already there; cancel any pending change.
            self._pending = target
            self._count = 0
            return self._committed

        # A change is being proposed.
        if target == self._pending:
            self._count += 1
        else:
            self._pending = target
            self._count = 1

        needed = self.fist_frames if target == FIST else self.enter_frames
        if self._count >= needed:
            self._committed = target
            self._count = 0

        return self._committed
