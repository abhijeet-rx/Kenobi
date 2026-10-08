import time
import threading
from typing import Callable, Optional

class GestureEngine:
    """
    Classifies raw Left and Right tap events into:
    - LEFT_SINGLE
    - RIGHT_SINGLE
    - LEFT_DOUBLE
    - RIGHT_DOUBLE
    """

    def __init__(self, 
                 double_tap_window_ms: int = 380, 
                 min_debounce_ms: int = 80,
                 on_gesture_callback: Optional[Callable[[str, float], None]] = None):
        self.double_tap_window_ms = double_tap_window_ms
        self.min_debounce_ms = min_debounce_ms
        self.on_gesture_callback = on_gesture_callback

        self._pending_side: Optional[str] = None
        self._pending_energy: float = 0.0
        self._pending_timer: Optional[threading.Timer] = None
        self._last_tap_time: float = 0.0
        self._lock = threading.Lock()

    def set_double_tap_window(self, window_ms: int):
        with self._lock:
            self.double_tap_window_ms = window_ms

    def register_tap(self, side: str, energy: float):
        """Called whenever a physical tap is recognized on Left or Right."""
        now = time.time()
        with self._lock:
            time_since_last = (now - self._last_tap_time) * 1000.0
            if time_since_last < self.min_debounce_ms:
                # Ignore immediate acoustic echo / ringing
                return

            self._last_tap_time = now

            # Check if this tap completes a double tap on the same side
            if self._pending_side == side:
                # Cancel the single tap timer
                if self._pending_timer:
                    self._pending_timer.cancel()
                    self._pending_timer = None

                self._pending_side = None
                gesture = f"{side}_DOUBLE"
                self._dispatch(gesture, energy)
            else:
                # If there was a pending tap on a different side, fire it immediately as single tap
                if self._pending_timer:
                    self._pending_timer.cancel()
                    self._pending_timer = None
                    prev_gesture = f"{self._pending_side}_SINGLE"
                    self._dispatch(prev_gesture, self._pending_energy)

                # Set this tap as pending and start timer
                self._pending_side = side
                self._pending_energy = energy
                timer_delay = self.double_tap_window_ms / 1000.0
                self._pending_timer = threading.Timer(timer_delay, self._on_timer_expired, args=[side, energy])
                self._pending_timer.daemon = True
                self._pending_timer.start()

    def _on_timer_expired(self, side: str, energy: float):
        with self._lock:
            if self._pending_side == side:
                self._pending_side = None
                self._pending_timer = None
                self._dispatch(f"{side}_SINGLE", energy)

    def _dispatch(self, gesture: str, energy: float):
        if self.on_gesture_callback:
            try:
                self.on_gesture_callback(gesture, energy)
            except Exception as e:
                print(f"[GestureEngine] Error in callback: {e}")

    def reset(self):
        with self._lock:
            if self._pending_timer:
                self._pending_timer.cancel()
                self._pending_timer = None
            self._pending_side = None
