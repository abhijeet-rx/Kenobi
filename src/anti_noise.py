import time
import threading
from typing import Optional

class TypingGuard:
    """
    Monitors global keyboard strokes to inhibit desk tap detection
    during and immediately after active typing.
    """
    def __init__(self, cooldown_ms: int = 350, enabled: bool = True):
        self.cooldown_ms = cooldown_ms
        self.enabled = enabled
        self._last_key_time: float = 0.0
        self._listener = None
        self._lock = threading.Lock()
        self._start_listener()

    def _start_listener(self):
        try:
            from pynput import keyboard

            def on_press(key):
                with self._lock:
                    self._last_key_time = time.time()

            self._listener = keyboard.Listener(on_press=on_press)
            self._listener.daemon = True
            self._listener.start()
            print("[TypingGuard] Global keyboard hook active.")
        except Exception as e:
            print(f"[TypingGuard] Warning: could not initialize keyboard hook: {e}")
            self._listener = None

    def is_typing(self) -> bool:
        """Returns True if a key was pressed within the cooldown window."""
        if not self.enabled:
            return False
        with self._lock:
            elapsed = (time.time() - self._last_key_time) * 1000.0
            return elapsed < self.cooldown_ms

    def set_cooldown(self, cooldown_ms: int):
        with self._lock:
            self.cooldown_ms = cooldown_ms

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
