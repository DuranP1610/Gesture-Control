"""
Real Windows volume and brightness control.
Both take and return percentages (0-100).
"""
import threading
from ctypes import POINTER, cast

import screen_brightness_control as sbc
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


class Volume:
    """Master volume of the default speakers. Same scale as the Windows volume slider."""

    def __init__(self):
        speakers = AudioUtilities.GetSpeakers()
        if hasattr(speakers, "EndpointVolume"):        # newer pycaw
            self._ep = speakers.EndpointVolume
        else:                                          # older pycaw
            iface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._ep = cast(iface, POINTER(IAudioEndpointVolume))
        self._last = None

    def get(self):
        self._last = None
        return self._ep.GetMasterVolumeLevelScalar() * 100

    def set(self, pct):
        pct = round(pct)
        if pct == self._last:          # skip pointless calls
            return
        self._last = pct
        self._ep.SetMasterVolumeLevelScalar(pct / 100, None)


class Brightness:
    """
    Screen brightness. Setting it is slow (~50-150 ms per call), so a background
    thread applies the latest requested value. The camera loop never waits on it.
    """

    def __init__(self, display=0):
        self.display = display
        self.available = True
        try:
            self._applied = sbc.get_brightness(display=display)[0]
        except Exception as e:
            print(f"Brightness control unavailable: {e}")
            self.available = False
            self._applied = 50
        self._target = None
        self._cv = threading.Condition()
        if self.available:
            threading.Thread(target=self._worker, daemon=True).start()

    def get(self):
        if not self.available:
            return self._applied
        try:
            return sbc.get_brightness(display=self.display)[0]
        except Exception:
            return self._applied

    def set(self, pct):
        if not self.available:
            return
        with self._cv:
            self._target = round(pct)
            self._cv.notify()

    def _worker(self):
        while True:
            with self._cv:
                while self._target is None or self._target == self._applied:
                    self._cv.wait()
                target = self._target
            try:
                sbc.set_brightness(target, display=self.display)
                self._applied = target
            except Exception as e:
                print(f"Brightness control stopped working: {e}")
                self.available = False
                return