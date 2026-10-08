import sounddevice as sd
import numpy as np
import time

for dev_id, name, sr in [(20, "AMD Array (WASAPI)", 48000), 
                         (19, "Realtek Headset (WASAPI)", 48000), 
                         (29, "Realtek Mic (WDM-KS)", 44100),
                         (3, "AMD Array (MME)", 44100),
                         (2, "Realtek Headset (MME)", 44100)]:
    try:
        peaks = []
        def cb(indata, frames, time_info, status):
            peaks.append(float(np.max(np.abs(indata))))
        
        s = sd.InputStream(device=dev_id, channels=2, samplerate=sr, blocksize=1024, callback=cb)
        s.start()
        time.sleep(0.5)
        s.stop()
        s.close()
        max_p = max(peaks) if peaks else 0.0
        print(f"[{dev_id:2d}] {name:<25}: OK - Max Peak: {max_p:.6f}")
    except Exception as e:
        print(f"[{dev_id:2d}] {name:<25}: Failed - {e}")
