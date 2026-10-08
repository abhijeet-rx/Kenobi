import sounddevice as sd
import numpy as np

for idx in [2, 10, 19, 29]:
    dev = sd.query_devices(idx)
    api = sd.query_hostapis(dev['hostapi'])['name']
    sr = int(dev.get('default_samplerate', 44100))
    ch = min(2, dev.get('max_input_channels', 1))
    try:
        rec = sd.rec(int(sr * 1.0), samplerate=sr, channels=ch, device=idx, blocking=True)
        peak = float(np.max(np.abs(rec)))
        rms = float(np.sqrt(np.mean(rec**2)))
        left_rms = float(np.sqrt(np.mean(rec[:, 0]**2)))
        right_rms = float(np.sqrt(np.mean(rec[:, 1]**2))) if ch >= 2 else left_rms
        print(f"Device [{idx:2d}] ({api}) {dev['name']}: Peak={peak:.5f}, L_RMS={left_rms:.5f}, R_RMS={right_rms:.5f}")
    except Exception as e:
        print(f"Device [{idx:2d}] Error: {e}")
