"""
Interactive CLI acoustic diagnostic and calibration tool for Kenobi.
Run this script to inspect live stereo microphone levels and verify tap localization.
"""

import time
import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.audio_engine import AudioEngine

def main():
    print("=" * 60)
    print(" Kenobi Acoustic Diagnostic & Calibration Tool")
    print("=" * 60)

    devices = AudioEngine.get_input_devices()
    print("\nAvailable Input Devices:")
    for d in devices:
        print(f" [{d['index']}] {d['name']} ({d['channels']} channels)")

    selected_index = None
    # Auto-detect 'Microphone Array'
    for d in devices:
        if "microphone array" in d['name'].lower():
            selected_index = d['index']
            print(f"\n--> Auto-selected built-in array: [{d['index']}] {d['name']}")
            break

    def on_tap(side, energy):
        arrow = "◀◀◀ LEFT" if side == "LEFT" else "RIGHT ▶▶▶"
        print(f"\n>>> [TAP DETECTED] {arrow} | Peak Amplitude: {energy:.4f}\n")

    def on_levels(l, r):
        l_bar = "#" * int(min(30, l * 300))
        r_bar = "#" * int(min(30, r * 300))
        sys.stdout.write(f"\rL: [{l_bar:<30}] | R: [{r_bar:<30}]")
        sys.stdout.flush()

    engine = AudioEngine(
        sensitivity=0.06,
        stereo_balance=0.0,
        min_side_ratio=1.15,
        device_index=selected_index,
        on_tap_callback=on_tap,
        on_levels_callback=on_levels
    )

    print("\nStarting acoustic monitor... Tap the desk to the LEFT or RIGHT of your laptop.")
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
