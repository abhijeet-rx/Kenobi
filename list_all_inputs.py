import sounddevice as sd

print(f"Default input: {sd.default.device[0]}")
for idx, dev in enumerate(sd.query_devices()):
    if dev['max_input_channels'] > 0:
        host = sd.query_hostapis(dev['hostapi'])['name']
        print(f"[{idx:2d}] {dev['name']:<45} | {host:<20} | in_ch={dev['max_input_channels']}")
