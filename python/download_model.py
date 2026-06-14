"""Download the MediaPipe Gesture Recognizer model (gesture_recognizer.task).

Run once before first use:   python download_model.py
Saves to models/gesture_recognizer.task (the path in config.json).
"""

from __future__ import annotations

import os
import sys
import urllib.request

URL = ("https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
       "gesture_recognizer/float16/latest/gesture_recognizer.task")
DEST = os.path.join("models", "gesture_recognizer.task")


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
