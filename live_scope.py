import sounddevice as sd
import numpy as np
import sys
import time

def run_live_scope(device_idx=None, duration=10):
    dev = sd.query_devices(device_idx, 'input')
    sr = int(dev.get('default_samplerate', 44100))
    ch = min(2, dev.get('max_input_channels', 1))
    print(f"Testing device [{device_idx}]: {dev['name']}")
    print(f"Channels: {ch}, Sample Rate: {sr}")
    print("Speak or tap now... (showing live numerical levels and dB)")

    def callback(indata, frames, time_info, status):
        if ch >= 2:
            l = float(np.sqrt(np.mean(indata[:, 0]**2)))
            r = float(np.sqrt(np.mean(indata[:, 1]**2)))
        else:
            l = float(np.sqrt(np.mean(indata[:, 0]**2)))
            r = l
        peak = float(np.max(np.abs(indata)))
        
        # Convert to dBFS
        l_db = 20 * np.log10(l + 1e-6)
        r_db = 20 * np.log10(r + 1e-6)
        
        # Scale to 0-30 chars: -60 dB to 0 dB
        l_bars = max(0, min(30, int((l_db + 60) / 2)))
        r_bars = max(0, min(30, int((r_db + 60) / 2)))
        
        bar_l = "#" * l_bars
        bar_r = "#" * r_bars
        
        sys.stdout.write(f"\rL: [{bar_l:<30}] ({l*1000:6.1f}) | R: [{bar_r:<30}] ({r*1000:6.1f}) | Peak: {peak*1000:6.1f}  ")
        sys.stdout.flush()

    with sd.InputStream(device=device_idx, channels=ch, samplerate=sr, blocksize=1024, callback=callback):
        time.sleep(duration)
    print("\nDone.")

if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_live_scope(idx, duration=5)
