import json
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, Any

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kenobi_config.json")

DEFAULT_PROFILES = {
    "Media": {
        "LEFT_SINGLE": {"type": "media", "action": "prev_track", "label": "Previous Track"},
        "RIGHT_SINGLE": {"type": "media", "action": "next_track", "label": "Next Track"},
        "LEFT_DOUBLE": {"type": "media", "action": "volume_down", "label": "Volume Down"},
        "RIGHT_DOUBLE": {"type": "media", "action": "volume_up", "label": "Volume Up"},
    },
    "Productivity": {
        "LEFT_SINGLE": {"type": "hotkey", "action": ["alt", "left"], "label": "Browser Back"},
        "RIGHT_SINGLE": {"type": "hotkey", "action": ["alt", "right"], "label": "Browser Forward"},
        "LEFT_DOUBLE": {"type": "hotkey", "action": ["ctrl", "shift", "tab"], "label": "Previous Tab"},
        "RIGHT_DOUBLE": {"type": "hotkey", "action": ["ctrl", "tab"], "label": "Next Tab"},
    },
    "Mouse Companion": {
        "LEFT_SINGLE": {"type": "mouse", "action": "left_click", "label": "Left Click"},
        "RIGHT_SINGLE": {"type": "mouse", "action": "right_click", "label": "Right Click"},
        "LEFT_DOUBLE": {"type": "mouse", "action": "double_click", "label": "Double Click"},
        "RIGHT_DOUBLE": {"type": "mouse", "action": "middle_click", "label": "Middle Click"},
    },
    "Custom": {
        "LEFT_SINGLE": {"type": "media", "action": "play_pause", "label": "Play / Pause"},
        "RIGHT_SINGLE": {"type": "media", "action": "mute", "label": "Mute / Unmute"},
        "LEFT_DOUBLE": {"type": "hotkey", "action": ["win", "d"], "label": "Show Desktop"},
        "RIGHT_DOUBLE": {"type": "hotkey", "action": ["alt", "tab"], "label": "Switch App"},
    }
}

@dataclass
class AppConfig:
    enabled: bool = True
    sensitivity: float = 0.015         # Lower means more sensitive (trigger threshold)
    stereo_balance: float = 0.0        # -1.0 (favor left) to 1.0 (favor right)
    min_side_ratio: float = 1.08       # Minimum amplitude ratio to distinguish Left vs Right
    typing_guard_enabled: bool = True  # Ignore taps while typing on keyboard
    typing_cooldown_ms: int = 350      # Milliseconds to silence taps after any keystroke
    double_tap_window_ms: int = 380    # Max time between taps for a double-tap
    hud_enabled: bool = True           # Show floating HUD
    hud_duration_ms: int = 1200        # How long HUD stays visible
    audio_feedback: bool = True        # Play subtle click sound on tap
    audio_device_index: int = -1       # -1 for system default
    active_profile: str = "Media"
    profiles: Dict[str, Any] = field(default_factory=lambda: DEFAULT_PROFILES.copy())

    def save(self, filepath: str = CONFIG_FILE_PATH):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    @classmethod
    def load(cls, filepath: str = CONFIG_FILE_PATH) -> "AppConfig":
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**data)
            except Exception as e:
                print(f"[Config] Error loading config ({e}), using defaults.")
        config = cls()
        config.save(filepath)
        return config
