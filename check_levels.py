import sounddevice as sd
import numpy as np

def test_device(idx):
    try:
        dev = sd.query_devices(idx)
        sr = int(dev.get('default_samplerate', 44100))
        ch = min(2, dev.get('max_input_channels', 1))
        # record 1 second
        data = sd.rec(int(sr * 1.0), samplerate=sr, channels=ch, device=idx, blocking=True)
        peak = np.max(np.abs(data))
        rms = np.sqrt(np.mean(data**2))
        return f"[{idx}] {dev['name']}: Peak={peak:.6f}, RMS={rms:.6f}"
    except Exception as e:
        return f"[{idx}] Error: {e}"

print("Checking primary microphones:")
for i in [0, 1, 2, 3, 10, 11, 19, 20, 22, 29]:
    print(test_device(i))
