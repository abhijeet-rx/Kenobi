import sounddevice as sd

print("--- Realtek Input Devices ---")
for idx, dev in enumerate(sd.query_devices()):
    if 'realtek' in dev['name'].lower() and dev['max_input_channels'] > 0:
        api = sd.query_hostapis(dev['hostapi'])['name']
        print(f"[{idx:2d}] {dev['name']} | API: {api} | Channels: {dev['max_input_channels']} | SR: {dev['default_samplerate']}")
