
import time
from collections import deque

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_PATH = "hand_landmarker.task"
PALM_IDX = 9          
TRAIL_LEN = 15        

options = vision.HandLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.6,
    min_tracking_confidence=0.5,
)
landmarker = vision.HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)
trail = deque(maxlen=TRAIL_LEN)
t0 = time.monotonic()

while True:
    ok, frame = cap.read()
    if not ok:
        print("Couldn't read from camera")
        break

    frame = cv2.flip(frame, 1)                 # mirror so right = right
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    ts_ms = int((time.monotonic() - t0) * 1000)  # must strictly increase
    result = landmarker.detect_for_video(mp_image, ts_ms)

    if result.hand_landmarks:
        lms = result.hand_landmarks[0]           # normalised 0..1 coords
        for lm in lms:
            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 255, 0), -1)

        palm = lms[PALM_IDX]
        px, py = int(palm.x * w), int(palm.y * h)
        trail.append((px, py))
        cv2.putText(frame, f"palm: ({palm.x:.2f}, {palm.y:.2f})", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    else:
        trail.clear()

    for i in range(1, len(trail)):
        cv2.line(frame, trail[i - 1], trail[i], (0, 200, 255), 3)

    cv2.imshow("Hand tracking (q to quit)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
landmarker.close()