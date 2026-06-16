"""Download the MediaPipe Hand Landmarker model (hand_landmarker.task).

Run once before first use:   python download_model.py
Saves to models/hand_landmarker.task (the path in config.json).
"""

from __future__ import annotations

import os
import sys
import urllib.request

URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
       "hand_landmarker/float16/latest/hand_landmarker.task")
DEST = os.path.join("models", "hand_landmarker.task")


def main() -> int:
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    if os.path.isfile(DEST) and os.path.getsize(DEST) > 0:
        print(f"Already present: {DEST} ({os.path.getsize(DEST)} bytes)")
        return 0
    print(f"Downloading {URL}\n      -> {DEST}")
    try:
        urllib.request.urlretrieve(URL, DEST)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: download failed: {exc}")
        print("If you are offline, download the URL above in a browser and place "
              "the file at the destination path manually.")
        return 1
    print(f"Done: {os.path.getsize(DEST)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
