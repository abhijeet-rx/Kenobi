import time
import math
import numpy as np
import sounddevice as sd
from scipy.signal import butter, lfilter
from typing import Callable, Optional, Tuple, List, Dict

class AudioEngine:
    """
    Real-time stereo acoustic detection engine.
    Listens to microphone input, detects desk tap transients,
    filters out mechanical key clicks, and localizes Left vs Right desk taps.
    """

    def __init__(self,
                 sample_rate: int = 44100,
                 block_size: int = 1024,
                 sensitivity: float = 0.06,
                 stereo_balance: float = 0.0,
                 min_side_ratio: float = 1.15,
                 device_index: Optional[int] = None,
                 typing_guard = None,
                 on_tap_callback: Optional[Callable[[str, float], None]] = None,
                 on_levels_callback: Optional[Callable[[float, float], None]] = None):

        self.sample_rate = sample_rate
        self.block_size = block_size
        self.sensitivity = sensitivity
        self.stereo_balance = stereo_balance
        self.min_side_ratio = min_side_ratio
        self.device_index = device_index if device_index is not None and device_index >= 0 else None
        self.typing_guard = typing_guard

        self.on_tap_callback = on_tap_callback
        self.on_levels_callback = on_levels_callback

        self.is_running = False
        self.stream: Optional[sd.InputStream] = None

        # Noise floor tracking
        self.noise_floor = 0.005
        self.last_tap_time = 0.0
        self.cooldown_ms = 120.0  # Hardware refractory period after a tap

        # Bandpass filter design for desk thump (60Hz to 800Hz)
        self.b_low, self.a_low = butter(2, [60.0 / (sample_rate / 2), 800.0 / (sample_rate / 2)], btype='band')
        # Highpass filter for key clicks (> 2000Hz)
        self.b_high, self.a_high = butter(2, 2000.0 / (sample_rate / 2), btype='high')

    def update_settings(self, sensitivity: float, stereo_balance: float, min_side_ratio: float):
        self.sensitivity = max(0.005, min(1.0, sensitivity))
        self.stereo_balance = max(-1.0, min(1.0, stereo_balance))
        self.min_side_ratio = max(1.01, min_side_ratio)

    @staticmethod
    def get_input_devices() -> List[Dict[str, any]]:
        """Returns list of available stereo/input audio devices."""
        devices = []
        try:
            device_list = sd.query_devices()
            for idx, dev in enumerate(device_list):
                if dev.get('max_input_channels', 0) > 0:
                    devices.append({
                        'index': idx,
                        'name': dev.get('name', f"Device {idx}"),
                        'channels': dev.get('max_input_channels', 1),
                        'default_samplerate': dev.get('default_samplerate', 44100)
                    })
        except Exception as e:
            print(f"[AudioEngine] Error querying devices: {e}")
        return devices

    def start(self):
        if self.is_running:
            return

        try:
            # Query default device or specific device
            dev_info = sd.query_devices(self.device_index, 'input')
            channels = min(2, dev_info['max_input_channels'])
            if channels < 2:
                print(f"[AudioEngine] Warning: Device has only {channels} channel(s). Stereo localization needs 2 channels.")

            self.stream = sd.InputStream(
                device=self.device_index,
                channels=channels,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self._audio_callback
            )
            self.stream.start()
            self.is_running = True
            print(f"[AudioEngine] Audio stream started on device {self.device_index or 'default'} ({channels} ch, {self.sample_rate} Hz).")
        except Exception as e:
            print(f"[AudioEngine] Failed to start audio stream: {e}")
            self.is_running = False

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        print("[AudioEngine] Audio stream stopped.")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            pass # Overflow/underflow flags if any

        num_channels = indata.shape[1]
        if num_channels < 2:
            # Single channel fallback (treat as mono)
            left_data = indata[:, 0]
            right_data = indata[:, 0]
        else:
            left_data = indata[:, 0]
            right_data = indata[:, 1]

        # Calculate peak & RMS
        left_rms = float(np.sqrt(np.mean(left_data**2)))
        right_rms = float(np.sqrt(np.mean(right_data**2)))
        max_peak = float(np.max(np.abs(indata)))

        # Send live levels to GUI
        if self.on_levels_callback:
            try:
                self.on_levels_callback(left_rms, right_rms)
            except Exception:
                pass

        # Update ambient noise floor tracker
        current_ambient = (left_rms + right_rms) / 2.0
        if current_ambient < self.noise_floor * 1.5:
            self.noise_floor = 0.98 * self.noise_floor + 0.02 * current_ambient

        # Check if peak exceeds sensitivity threshold
        trigger_threshold = max(self.sensitivity, self.noise_floor * 3.0)
        if max_peak < trigger_threshold:
            return

        # Check refractory cooldown
        now = time.time()
        if (now - self.last_tap_time) * 1000.0 < self.cooldown_ms:
            return

        # Check Typing Guard: ignore if user is actively typing
        if self.typing_guard and self.typing_guard.is_typing():
            return

        # Spectral Fingerprint Analysis
        # Desk thump vs mechanical key click
        try:
            mono_data = (left_data + right_data) / 2.0
            low_energy = float(np.sum(lfilter(self.b_low, self.a_low, mono_data)**2))
            high_energy = float(np.sum(lfilter(self.b_high, self.a_high, mono_data)**2))

            # Mechanical key clicks have sharp high frequency transients
            if high_energy > 0 and low_energy > 0:
                high_to_low_ratio = high_energy / (low_energy + 1e-9)
                if high_to_low_ratio > 2.5:
                    # Likely a key click or sharp plastic snap on laptop
                    return
        except Exception:
            pass

        # Stereo Localization
        # Apply balance factor: balance in [-1.0, 1.0]
        # balance < 0 favors Left; balance > 0 favors Right
        bal_l = 1.0 - (self.stereo_balance * 0.5)
        bal_r = 1.0 + (self.stereo_balance * 0.5)

        adj_left_rms = left_rms * bal_l
        adj_right_rms = right_rms * bal_r

        # Determine side
        side = None
        if adj_left_rms > adj_right_rms * self.min_side_ratio:
            side = "LEFT"
        elif adj_right_rms > adj_left_rms * self.min_side_ratio:
            side = "RIGHT"
        else:
            # Impact in the middle (e.g. keyboard tap, palm rest tap) -> ignore to prevent false center triggers
            return

        self.last_tap_time = now

        # Emit tap event
        if self.on_tap_callback:
            try:
                self.on_tap_callback(side, max_peak)
            except Exception as e:
                print(f"[AudioEngine] Tap callback error: {e}")
