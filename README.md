# Kenobi ⚡
### Acoustic Desk Surface Interaction Suite for Windows

**Kenobi** turns the empty desk space to the left and right of your laptop into an interactive acoustic touch surface. By analyzing micro-vibrations and acoustic transients captured by the laptop's stereo microphones, Kenobi detects physical taps on your desk, localizes whether they occurred on the left or right, and triggers customizable actions.

---

## ✨ Features
- **Acoustic Desk Sensing**: No specialized hardware, webcams, or wearable sensors required. Uses your laptop's built-in stereo microphones.
- **Left & Right Spatial Localization**: Accurately differentiates left desk taps from right desk taps using energy ratio and arrival transients.
- **Smart Anti-False Trigger Guard**:
  - **Typing Guard**: Global low-level keyboard hook suppresses detection while typing.
  - **Spectral Signature Filter**: Distinguishes deep desk thumps (60–800 Hz) from crisp mechanical key clicks (>2000 Hz).
- **Single & Double Tap Gestures**:
  - `Left Single Tap`
  - `Right Single Tap`
  - `Left Double Tap`
  - `Right Double Tap`
- **Configurable Profiles**:
  - **Media Control**: Play/Pause, Next Track, Previous Track, Volume Up/Down, Mute.
  - **Productivity & Browsing**: Browser Back, Browser Forward, Tab Navigation.
  - **Mouse Companion**: Virtual Left Click, Right Click, Double Click.
  - **Custom**: User-mapped shortcuts and macros.
- **Floating On-Screen HUD**: Elegant, translucent, click-through overlay showing recognized gestures in real-time.
- **Modern Control Center GUI**: High-DPI dark theme with real-time stereo VU level meters, interactive desk visualization, calibration sliders, and Windows System Tray support.

---

## 🚀 Getting Started

### 1. Requirements
- Windows 10 / 11
- Python 3.10+
- Built-in stereo microphone (e.g., AMD Audio Device / Realtek Microphone Array)

### 2. Setup & Run
Activate the virtual environment and run `main.py`:
```powershell
# From the Kenobi root folder:
.\.venv\Scripts\activate
python main.py
```

---

## 🎛️ Calibration & Tips
1. **Select Microphone**: In the Kenobi Control Center under *Acoustic Calibration*, ensure your laptop's **Microphone Array** is selected (rather than a headset or virtual mic).
2. **Sensitivity Slider**: Adjust the slider until tapping your desk with fingertips or knuckles reliably triggers the pulse on the Left/Right zones.
3. **Stereo Balance**: If your laptop's microphones are offset towards one side of the screen, adjust the balance slider to center the baseline.
