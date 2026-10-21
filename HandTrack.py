"""
Continuous gesture control of Windows volume and brightness.
Pinch thumb + index and drag: up/down = brightness, left/right = volume.
Press q to quit.
"""
import time
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from continuous_control import PinchSlider, THUMB_TIP, INDEX_TIP
from controls import Brightness, Volume

MODEL_PATH = str(Path(__file__).parent / "hand_landmarker.task")

options = vision.HandLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.6,
    min_tracking_confidence=0.5,
)
landmarker = vision.HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)
slider = PinchSlider(gain=250, smoothing=0.3, lock_dist=0.02)
devices = {"volume": Volume(), "brightness": Brightness()}
levels = {name: dev.get() for name, dev in devices.items()}   # start from real levels

t0 = time.monotonic()
last_ts = -1          # MediaPipe needs strictly increasing timestamps


def draw_bars(frame, levels, active):
    h, w = frame.shape[:2]
    # volume: horizontal bar along the bottom (matches left/right motion)
    x0, x1, y = 20, w - 80, h - 30
    cv2.rectangle(frame, (x0, y - 12), (x1, y + 12), (80, 80, 80), 2)
    fill = int(x0 + (x1 - x0) * levels["volume"] / 100)
    col = (0, 255, 255) if active == "volume" else (200, 200, 200)
    cv2.rectangle(frame, (x0, y - 12), (fill, y + 12), col, -1)
    cv2.putText(frame, f"Vol {levels['volume']:.0f}%", (x0, y - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

    # brightness: vertical bar on the right (matches up/down motion)
    x, y0, y1 = w - 40, 60, h - 60
    cv2.rectangle(frame, (x - 12, y0), (x + 12, y1), (80, 80, 80), 2)
    fill = int(y1 - (y1 - y0) * levels["brightness"] / 100)
    col = (0, 255, 255) if active == "brightness" else (200, 200, 200)
    cv2.rectangle(frame, (x - 12, fill), (x + 12, y1), col, -1)
    cv2.putText(frame, f"{levels['brightness']:.0f}%", (x - 30, y0 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)


while True:
    ok, frame = cap.read()
    if not ok:
        print("Couldn't read from camera")
        break

    frame = cv2.flip(frame, 1)                 # mirror so right = right
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    now = time.monotonic()
    ts_ms = max(int((now - t0) * 1000), last_ts + 1)   # never repeat a timestamp
    last_ts = ts_ms
    result = landmarker.detect_for_video(mp_image, ts_ms)

    active = None
    if result.hand_landmarks:
        lms = result.hand_landmarks[0]
        for lm in lms:
            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 255, 0), -1)

        was_pinching = slider.pinching
        out = slider.update(lms, w, h)

        # just grabbed: re-read real levels in case you changed them with the keyboard
        if slider.pinching and not was_pinching:
            levels = {name: dev.get() for name, dev in devices.items()}

        if out:
            target, delta = out
            levels[target] = min(100.0, max(0.0, levels[target] + delta))
            devices[target].set(levels[target])

        # pinch indicator: line between thumb and index, red when grabbed
        t, i = lms[THUMB_TIP], lms[INDEX_TIP]
        col = (0, 0, 255) if slider.pinching else (255, 255, 255)
        cv2.line(frame, (int(t.x * w), int(t.y * h)), (int(i.x * w), int(i.y * h)), col, 3)

        if slider.pinching:
            active = {"x": "volume", "y": "brightness"}.get(slider.axis)
            label = "GRAB: " + (active or "move to choose")
            cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
    else:
        slider.reset()

    draw_bars(frame, levels, active)
    cv2.imshow("Gesture control (q to quit)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
landmarker.close()