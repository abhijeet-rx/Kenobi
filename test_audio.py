"""
Interactive CLI acoustic diagnostic and calibration tool for Kenobi.
"""

import time
import sys
import os
import sounddevice as sd
import numpy as np

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.audio_engine import AudioEngine

def find_best_device():
    """Finds the device with actual live signal."""
    candidates = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev['max_input_channels'] > 0:
            candidates.append(idx)

    best_idx = None
    best_peak = -1.0

    print("Quick-scanning candidate microphones for live audio signal...")
    for idx in [29, 19, 10, 2, 3, 20, 0]:
        if idx not in candidates:
            continue
        dev = sd.query_devices(idx)
        name_lower = dev['name'].lower()
        if "virtual" in name_lower or "stereo mix" in name_lower or "speaker" in name_lower:
            continue
        ch = min(2, dev.get('max_input_channels', 1))
        sr = int(dev.get('default_samplerate', 44100))
        try:
            rec = sd.rec(int(sr * 0.15), samplerate=sr, channels=ch, device=idx, blocking=True)
            peak = float(np.max(np.abs(rec)))
            if peak > best_peak:
                best_peak = peak
                best_idx = idx
        except Exception:
            continue

    if best_idx is not None and best_peak > 0.0005:
        dev_name = sd.query_devices(best_idx)['name']
        print(f"--> Auto-detected active microphone: [{best_idx}] {dev_name} (Peak: {best_peak:.4f})\n")
        return best_idx

    # Fallback to device 29 if present, else default
    return 29 if 29 in candidates else 0

def main():
    print("=" * 65)
    print(" Kenobi Acoustic Diagnostic & Calibration Tool (v2)")
    print("=" * 65)

    devices = AudioEngine.get_input_devices()
    print("\nAvailable Input Devices:")
    for d in devices:
        print(f" [{d['index']:2d}] {d['name']} ({d['channels']} ch)")

    # Select device: from command line arg or auto-detect
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        selected_index = int(sys.argv[1])
        dev_name = sd.query_devices(selected_index)['name']
        print(f"\n--> Using user-specified device: [{selected_index}] {dev_name}\n")
    else:
        selected_index = find_best_device()

    # Query device sample rate
    dev_info = sd.query_devices(selected_index)
    native_sr = int(dev_info.get('default_samplerate', 44100))

    def on_tap(side, energy):
        if side == "LEFT":
            arrow = "◀◀◀ [LEFT DESK TAP]"
        elif side == "RIGHT":
            arrow = "[RIGHT DESK TAP] ▶▶▶"
        else:
            arrow = "--- [CENTER TAP] ---"
        print(f"\n\n{'*'*50}\n>>> {arrow}  |  Peak: {energy:.4f}  |  Impact Registered!\n{'*'*50}\n")

    def on_levels(l, r):
        # Convert to dBFS (-60 dB to 0 dB) for human-perceivable responsive metering
        l_db = 20 * np.log10(max(l, 1e-6))
        r_db = 20 * np.log10(max(r, 1e-6))

        l_bars = max(0, min(24, int((l_db + 60) * 0.4)))
        r_bars = max(0, min(24, int((r_db + 60) * 0.4)))

        l_str = "#" * l_bars
        r_str = "#" * r_bars

        # Print live VU meter with numerical peak
        sys.stdout.write(f"\rL: [{l_str:<24}] ({l:.4f})  |  R: [{r_str:<24}] ({r:.4f}) ")
        sys.stdout.flush()

    # Create audio engine with sensitive threshold adapted for laptop desk physics
    engine = AudioEngine(
        sample_rate=native_sr,
        sensitivity=0.012,       # Lower threshold so gentle desk taps register easily!
        stereo_balance=0.0,
        min_side_ratio=1.10,     # 10% lateral difference distinguishes Left vs Right
        device_index=selected_index,
        on_tap_callback=on_tap,
        on_levels_callback=on_levels
    )

    print(f"Monitoring device [{selected_index}] at {native_sr} Hz...")
    print("Tap your desk with your fingertips or knuckle on the LEFT or RIGHT side.")
    print("Press Ctrl+C to stop.\n")

    engine.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
    finally:
        engine.stop()

if __name__ == "__main__":
    main()
