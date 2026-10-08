import ctypes
import time
import winsound
import threading
from typing import Dict, Any, List

# Windows Virtual-Key Codes
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

# Mouse Event Flags
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

KEY_MAPPINGS = {
    "alt": 0x12,
    "ctrl": 0x11,
    "shift": 0x10,
    "win": 0x5B,
    "tab": 0x09,
    "enter": 0x0D,
    "escape": 0x1B,
    "space": 0x20,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "d": 0x44,
    "w": 0x57,
    "t": 0x54,
}

class ActionDispatcher:
    """Dispatches simulated media keys, mouse events, and shortcuts on Windows."""

    def __init__(self, audio_feedback: bool = True):
        self.audio_feedback = audio_feedback
        self.user32 = ctypes.windll.user32

    def trigger(self, action_spec: Dict[str, Any]):
        """Dispatches an action based on its specification dictionary."""
        if not action_spec:
            return

        action_type = action_spec.get("type")
        action = action_spec.get("action")

        if self.audio_feedback:
            threading.Thread(target=self._play_click, daemon=True).start()

        if action_type == "media":
            self._trigger_media(action)
        elif action_type == "mouse":
            self._trigger_mouse(action)
        elif action_type == "hotkey":
            self._trigger_hotkey(action)

    def _play_click(self):
        try:
            # Play a short, crisp, high-pitched subtle tick (1800Hz for 25ms)
            winsound.Beep(1800, 25)
        except Exception:
            pass

    def _trigger_media(self, action: str):
        vk_map = {
            "volume_up": VK_VOLUME_UP,
            "volume_down": VK_VOLUME_DOWN,
            "mute": VK_VOLUME_MUTE,
            "play_pause": VK_MEDIA_PLAY_PAUSE,
            "next_track": VK_MEDIA_NEXT_TRACK,
            "prev_track": VK_MEDIA_PREV_TRACK,
        }
        vk = vk_map.get(action)
        if vk:
            self._send_key(vk)

    def _trigger_mouse(self, action: str):
        if action == "left_click":
            self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif action == "right_click":
            self.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            self.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        elif action == "middle_click":
            self.user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            self.user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
        elif action == "double_click":
            self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.05)
            self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def _trigger_hotkey(self, keys: List[str]):
        if isinstance(keys, str):
            keys = [keys]

        vks = []
        for k in keys:
            k_lower = k.lower()
            if k_lower in KEY_MAPPINGS:
                vks.append(KEY_MAPPINGS[k_lower])
            elif len(k) == 1:
                vks.append(ord(k.upper()))

        # Press in order
        for vk in vks:
            self.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.03)
        # Release in reverse order
        for vk in reversed(vks):
            self.user32.keybd_event(vk, 0, 2, 0)

    def _send_key(self, vk: int):
        self.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        self.user32.keybd_event(vk, 0, 2, 0)
