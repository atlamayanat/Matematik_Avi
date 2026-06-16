"""Config loader.

Loads ``config.json`` into a nested attribute-accessible object so the rest of
the code can write ``cfg.active_player.max_size`` instead of dict indexing.
All tunable parameters live in the JSON file; nothing is hardcoded elsewhere.
"""

from __future__ import annotations

import json
import os
from typing import Any


class _NS:
    """Recursive read-only namespace wrapping a dict (attribute + item access)."""

    def __init__(self, data: dict):
        self._data = data
        for key, value in data.items():
            setattr(self, key, _NS(value) if isinstance(value, dict) else value)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> dict:
        return self._data

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"_NS({self._data!r})"


def load_config(path: str = "config.json") -> _NS:
    """Load and lightly validate the config file, returning a namespace."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Config file not found: {path!r}. Run the detector from the 'python/' "
            f"folder, or pass --config <path>."
        )
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    # Minimal sanity checks so a typo surfaces immediately, not 200 lines later.
    for section in ("osc", "camera", "detection", "active_player",
                    "gesture_fsm", "smoothing", "calibration"):
        if section not in data:
            raise KeyError(f"config.json is missing the '{section}' section")

    return _NS(data)
