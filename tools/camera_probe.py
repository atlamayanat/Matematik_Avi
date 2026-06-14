"""Find the fastest webcam config. The detector is capped by camera FPS, so we
want the highest stable capture rate. Tries backends / resolutions / fps caps /
manual exposure / MJPG pixel format (often unlocks 60fps vs raw YUY2).
"""
import time
import cv2

MJPG = cv2.VideoWriter_fourcc(*"MJPG")
CONFIGS = [
    # name, backend, w, h, fps, exposure, fourcc
    ("DSHOW 640x480 MJPG fps60",     cv2.CAP_DSHOW, 640, 480, 60, None, MJPG),
    ("DSHOW 640x480 MJPG manExp -6", cv2.CAP_DSHOW, 640, 480, 60, -6,   MJPG),
    ("DSHOW 1280x720 MJPG fps60",    cv2.CAP_DSHOW, 1280, 720, 60, None, MJPG),
    ("MSMF 640x480 MJPG fps60",      cv2.CAP_MSMF,  640, 480, 60, None, MJPG),
    ("DSHOW 640x480 manExp -6",      cv2.CAP_DSHOW, 640, 480, 60, -6,   None),
    ("MSMF 640x480 fps60",           cv2.CAP_MSMF,  640, 480, 60, None, None),
]


def probe(name, backend, w, h, fps, exposure, fourcc):
    cap = cv2.VideoCapture(0, backend)
    if not cap.isOpened():
        print(f"{name}: could not open")
        return
    if fourcc is not None:
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if exposure is not None:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   # 0.25 = manual on most Win drivers
        cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
    for _ in range(12):
        cap.read()                                   # warmup / let settings apply
    t0 = time.time()
    n = 0
    for _ in range(100):
        ok, _f = cap.read()
        if ok:
            n += 1
    dt = time.time() - t0
    aw = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    ah = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    rep = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    print(f"{name}: {n/dt:5.1f} fps  (res {int(aw)}x{int(ah)}, driver-reported {rep:.0f})")


if __name__ == "__main__":
    for c in CONFIGS:
        try:
            probe(*c)
        except Exception as e:  # noqa: BLE001
            print(f"{c[0]}: ERROR {e}")
        time.sleep(0.3)
