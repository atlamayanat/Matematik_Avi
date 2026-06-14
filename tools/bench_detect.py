"""Measure where the latency/FPS budget goes, so we optimize the RIGHT thing.

Reports:
  1. Raw camera capture FPS at 640x480 (the hard ceiling for lens updates).
  2. MediaPipe GestureRecognizer inference FPS for num_hands = 1, 2, 3 (CPU).
  3. A GPU-delegate attempt (works on some platforms; usually CPU-only on Win).

Stop the live detector first (the webcam allows one consumer).
Run from the python/ folder with its venv.
"""
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

MODEL = "models/gesture_recognizer.task"
W, H = 640, 480
N = 90  # frames to time per config


def grab_frame():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    # ---- camera raw FPS ----
    for _ in range(10):
        cap.read()  # warmup
    t0 = time.time()
    got = 0
    for _ in range(120):
        ok, frame = cap.read()
        if ok:
            got += 1
    cam_fps = got / (time.time() - t0)
    print(f"[camera] raw capture: {cam_fps:.1f} fps  ({1000/cam_fps:.1f} ms/frame)")
    ok, frame = cap.read()
    cap.release()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return rgb, cam_fps


def bench(rgb, num_hands, delegate=None, label=""):
    base = mp_python.BaseOptions(model_asset_path=MODEL)
    if delegate is not None:
        base = mp_python.BaseOptions(model_asset_path=MODEL, delegate=delegate)
    opts = mp_vision.GestureRecognizerOptions(
        base_options=base,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=num_hands,
    )
    rec = mp_vision.GestureRecognizer.create_from_options(opts)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    # warmup
    for i in range(5):
        rec.recognize_for_video(mp_img, i)
    t0 = time.time()
    for i in range(N):
        rec.recognize_for_video(mp_img, 1000 + i)
    dt = time.time() - t0
    rec.close()
    fps = N / dt
    print(f"[gesture] {label} num_hands={num_hands}: {fps:.1f} fps  ({1000*dt/N:.1f} ms/frame)")
    return fps


def main():
    rgb, cam_fps = grab_frame()
    print("--- CPU (XNNPACK) ---")
    for nh in (3, 2, 1):
        bench(rgb, nh, label="CPU")
    print("--- GPU delegate attempt ---")
    try:
        bench(rgb, 2, delegate=mp_python.BaseOptions.Delegate.GPU, label="GPU")
    except Exception as e:  # noqa: BLE001
        print(f"[gesture] GPU delegate unavailable: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
