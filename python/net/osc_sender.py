"""OSC sender: one atomic /hand message per frame.

Message schema (exactly 4 typed args -> within OscJack's limit):
    /hand  float nx   normalized X in [0,1] (mapped + smoothed, wall space)
           float ny   normalized Y in [0,1]
           int   present  1 = a player is locked this frame, 0 = none
           string gesture "searching" | "fist"  (committed FSM state)

One packet = one complete, consistent frame of hand data, so Unity never acts
on a half-updated frame. We use python-osc because it emits correct OSC 1.0
binary encoding (4-byte alignment, type-tag string) that OscJack expects; a
hand-rolled UDP payload would silently fail to parse.
"""

from __future__ import annotations

from pythonosc.udp_client import SimpleUDPClient

from gesture import SEARCHING


class OscSender:
    def __init__(self, cfg):
        self._client = SimpleUDPClient(cfg.osc.host, int(cfg.osc.port))
        self._address = "/hand"

    def send_hand(self, nx: float, ny: float, present: bool, gesture: str) -> None:
        self._client.send_message(
            self._address,
            [float(nx), float(ny), 1 if present else 0, str(gesture)],
        )

    def send_absent(self, last_nx: float, last_ny: float) -> None:
        """No active player: park the cursor, force the searching state."""
        self.send_hand(last_nx, last_ny, False, SEARCHING)
