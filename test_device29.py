import sounddevice as sd
import numpy as np
import time

def test_stream_29():
    print("Testing stream on device 29 (Microphone (Realtek HD Audio Mic input))...")
    received_frames = []
    def callback(indata, frames, time_info, status):
        peak = float(np.max(np.abs(indata)))
        received_frames.append(peak)

    stream = sd.InputStream(device=29, channels=2, samplerate=44100, blocksize=1024, callback=callback)
    stream.start()
    time.sleep(1.0)
    stream.stop()
    stream.close()
    print(f"Captured {len(received_frames)} blocks.")
    print(f"Max peak across blocks: {max(received_frames) if received_frames else 0.0}")

test_stream_29()
