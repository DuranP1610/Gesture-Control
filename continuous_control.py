"""
Continuous "pinch and drag" control.

Pinch thumb + index to grab. While pinched, moving your hand drags a slider:
  up/down    -> brightness
  left/right -> volume
The axis locks after the first bit of movement so you don't change both at
once. Release the pinch to let go (like lifting a mouse to reposition it).
"""
import math

WRIST, THUMB_TIP, INDEX_TIP, MIDDLE_MCP = 0, 4, 8, 9


class PinchSlider:
    def __init__(self, pinch_on=0.35, pinch_off=0.5, lock_dist=0.03,
                 gain=120, smoothing=0.5, accel = 1.5):
        self.pinch_on = pinch_on      # pinch ratio below this -> grab
        self.pinch_off = pinch_off    # pinch ratio above this -> release
        self.lock_dist = lock_dist    # movement (0..1) needed to pick an axis
        self.gain = gain              # % change per full frame width/height moved
        self.smoothing = smoothing    # 0 = no smoothing, closer to 1 = smoother
        self.accel = accel
        self.reset()

    def reset(self):
        self.pinching = False
        self.axis = None              # None until locked, then "x" or "y"
        self.anchor = None            # where the pinch started
        self.prev = None              # last smoothed position
        self.pos = None

    @staticmethod
    def _dist(a, b, w, h):
        # measure in pixels so the frame's aspect ratio doesn't distort it
        return math.hypot((a.x - b.x) * w, (a.y - b.y) * h)

    def pinch_ratio(self, lms, w, h):
        """Thumb-index gap divided by hand size, so it works near or far from the camera."""
        hand_size = self._dist(lms[WRIST], lms[MIDDLE_MCP], w, h)
        return self._dist(lms[THUMB_TIP], lms[INDEX_TIP], w, h) / max(hand_size, 1e-6)

    def update(self, lms, w, h):
        """Feed one frame of landmarks. Returns ('volume'|'brightness', delta%) or None."""
        ratio = self.pinch_ratio(lms, w, h)
        p = lms[MIDDLE_MCP]

        # Two thresholds (hysteresis) so a borderline pinch doesn't flicker on/off
        if not self.pinching:
            if ratio < self.pinch_on:
                self.pinching = True
                self.anchor = self.prev = self.pos = (p.x, p.y)
            return None
        if ratio > self.pinch_off:
            self.reset()
            return None

        # Smooth the position to kill landmark jitter
        a = self.smoothing
        self.pos = (a * self.pos[0] + (1 - a) * p.x,
                    a * self.pos[1] + (1 - a) * p.y)
        x, y = self.pos

        if self.axis is None:
            dx, dy = x - self.anchor[0], y - self.anchor[1]
            if max(abs(dx), abs(dy)) < self.lock_dist:
                return None
            self.axis = "x" if abs(dx) > abs(dy) else "y"
            self.prev = self.anchor   # count the movement made while locking

        px, py = self.prev
        self.prev = (x, y)
        d = (x - px) if self.axis == "x" else -(y - py)   # up = positive
        speed = abs(d)                                     # movement this frame (0..1)
        accel = 1 + self.accel * speed / 0.02              # ~1x when slow, more when fast
        target = "volume" if self.axis == "x" else "brightness"
        return target, d * self.gain * accel