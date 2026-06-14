"""One Euro Filter - adaptive low-pass smoothing for the cursor.

Reference: Casiez, Roussel & Vogel, "1 Euro Filter: A Simple Speed-based
Low-pass Filter for Noisy Input in Interactive Systems" (CHI 2012).
https://gery.casiez.net/1euro/

Why this over a fixed EMA/lerp: the cutoff frequency adapts to hand speed
(fc = min_cutoff + beta * |speed|). At low speed it uses a low cutoff to kill
jitter (steady cursor while the user dwells/searches); at high speed it raises
the cutoff to cut lag (responsive fast moves). A fixed alpha cannot do both.

Implemented in-repo (no external dependency). beta here is tuned for NORMALIZED
[0,1] coordinates; if you ever filter pixel units, scale beta down by ~1/width.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple


def _smoothing_factor(t_e: float, cutoff: float) -> float:
    r = 2.0 * math.pi * cutoff * t_e
    return r / (r + 1.0)


def _exp_smooth(alpha: float, x: float, x_prev: float) -> float:
    return alpha * x + (1.0 - alpha) * x_prev


class OneEuroFilter:
    """Single-axis One Euro filter. Lazily initialises on the first sample."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0,
                 d_cutoff: float = 1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x_prev: Optional[float] = None
        self._dx_prev: float = 0.0
        self._t_prev: Optional[float] = None

    def reset(self) -> None:
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None

    def __call__(self, t: float, x: float) -> float:
        if self._x_prev is None or self._t_prev is None:
            self._x_prev = x
            self._t_prev = t
            self._dx_prev = 0.0
            return x

        t_e = t - self._t_prev
        if t_e <= 0.0:
            # Duplicate/again-in-same-instant timestamp; keep previous estimate.
            return self._x_prev

        # Derivative, smoothed by a fixed-cutoff low-pass.
        a_d = _smoothing_factor(t_e, self.d_cutoff)
        dx = (x - self._x_prev) / t_e
        dx_hat = _exp_smooth(a_d, dx, self._dx_prev)

        # Speed-adaptive cutoff for the value low-pass.
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = _smoothing_factor(t_e, cutoff)
        x_hat = _exp_smooth(a, x, self._x_prev)

        self._x_prev = x_hat
        self._dx_prev = dx_hat
        self._t_prev = t
        return x_hat


class CursorSmoother:
    """Smooths a 2D point with one OneEuroFilter per axis.

    Call ``reset()`` whenever the active player changes (lock acquired/released)
    so the cursor does not glide across the screen from the previous player's
    last position.
    """

    def __init__(self, min_cutoff: float, beta: float, d_cutoff: float):
        self._fx = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self._fy = OneEuroFilter(min_cutoff, beta, d_cutoff)

    def reset(self) -> None:
        self._fx.reset()
        self._fy.reset()

    def __call__(self, t: float, x: float, y: float) -> Tuple[float, float]:
        return self._fx(t, x), self._fy(t, y)
