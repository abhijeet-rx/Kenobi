import sounddevice as sd
import numpy as np

print("--- Testing Input Devices for Active Audio Signal ---")
devices = sd.query_devices()
candidates = [0, 1, 2, 3, 8, 9, 10, 11, 19, 20, 22, 29, 39]

for idx in candidates:
    if idx >= len(devices):
        continue
    dev = devices[idx]
    ch = min(2, dev.get('max_input_channels', 0))
    if ch == 0:
        continue
    sr = int(dev.get('default_samplerate', 44100))
    hostapi_name = sd.query_hostapis(dev['hostapi'])['name']
    try:
        data = sd.rec(int(sr * 0.3), samplerate=sr, channels=ch, device=idx, blocking=True)
        max_val = float(np.max(np.abs(data)))
        rms_val = float(np.sqrt(np.mean(data**2)))
        print(f"[{idx:2d}] {dev['name'][:35]:<35} | {hostapi_name:<18} | sr={sr} | Peak={max_val:.5f} | RMS={rms_val:.5f}")
    except Exception as e:
        print(f"[{idx:2d}] {dev['name'][:35]:<35} | {hostapi_name:<18} | ERROR: {e}")
