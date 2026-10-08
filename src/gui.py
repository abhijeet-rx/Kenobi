import sys
import os
import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QBrush, QPen, QLinearGradient
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QSlider, QCheckBox, QFrame, 
    QGroupBox, QGridLayout, QSystemTrayIcon, QMenu, QMessageBox
)

from .config import AppConfig, DEFAULT_PROFILES
from .audio_engine import AudioEngine
from .gesture_engine import GestureEngine
from .anti_noise import TypingGuard
from .action_dispatcher import ActionDispatcher
from .hud_overlay import HUDOverlay


class DeskZoneWidget(QFrame):
    """Visual desk zone widget that pulses when a tap is detected."""
    def __init__(self, title: str, subtitle: str, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self.title_text = title
        self.subtitle_text = subtitle
        self.active_opacity = 0.0
        self.last_action_text = "Idle"
        
        self.setMinimumHeight(140)
        self.setStyleSheet("""
            DeskZoneWidget {
                background-color: #1e293b;
                border: 2px solid #334155;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(self.title_label)

        self.icon_label = QLabel("◀" if side == "LEFT" else "▶", self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("color: #38bdf8; font-size: 28px; font-weight: bold;")
        layout.addWidget(self.icon_label)

        self.status_label = QLabel(self.last_action_text, self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Pulse decay timer
        self.decay_timer = QTimer(self)
        self.decay_timer.setInterval(30)
        self.decay_timer.timeout.connect(self._decay)

    def trigger_pulse(self, gesture_type: str, action_name: str):
        self.last_action_text = action_name
        self.status_label.setText(action_name)
        self.active_opacity = 1.0

        if "DOUBLE" in gesture_type:
            self.setStyleSheet("""
                DeskZoneWidget {
                    background-color: #3b1d54;
                    border: 2px solid #c084fc;
                    border-radius: 12px;
                }
            """)
            self.status_label.setStyleSheet("color: #c084fc; font-weight: bold; font-size: 13px;")
        else:
            self.setStyleSheet("""
                DeskZoneWidget {
                    background-color: #0f3d4c;
                    border: 2px solid #38bdf8;
                    border-radius: 12px;
                }
            """)
            self.status_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")

        self.decay_timer.start()

    def _decay(self):
        self.active_opacity -= 0.05
        if self.active_opacity <= 0.0:
            self.active_opacity = 0.0
            self.decay_timer.stop()
            self.setStyleSheet("""
                DeskZoneWidget {
                    background-color: #1e293b;
                    border: 2px solid #334155;
                    border-radius: 12px;
                }
            """)
            self.status_label.setStyleSheet("color: #64748b; font-size: 12px;")


class LevelMeterWidget(QWidget):
    """Dual-channel stereo VU level meter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_level = 0.0
        self.right_level = 0.0
        self.setMinimumHeight(24)

    def set_levels(self, left: float, right: float):
        # Smoothing & scaling
        self.left_level = max(0.0, min(1.0, left * 8.0))
        self.right_level = max(0.0, min(1.0, right * 8.0))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_h = (h - 6) // 2

        # Background track
        painter.setBrush(QBrush(QColor("#0f172a")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, bar_h, 3, 3)
        painter.drawRoundedRect(0, bar_h + 4, w, bar_h, 3, 3)

        # Left bar gradient
        l_grad = QLinearGradient(0, 0, w, 0)
        l_grad.setColorAt(0.0, QColor("#38bdf8"))
        l_grad.setColorAt(0.7, QColor("#818cf8"))
        l_grad.setColorAt(1.0, QColor("#f43f5e"))
        painter.setBrush(QBrush(l_grad))
        painter.drawRoundedRect(0, 0, int(w * self.left_level), bar_h, 3, 3)

        # Right bar gradient
        r_grad = QLinearGradient(0, 0, w, 0)
        r_grad.setColorAt(0.0, QColor("#38bdf8"))
        r_grad.setColorAt(0.7, QColor("#818cf8"))
        r_grad.setColorAt(1.0, QColor("#f43f5e"))
        painter.setBrush(QBrush(r_grad))
        painter.drawRoundedRect(0, bar_h + 4, int(w * self.right_level), bar_h, 3, 3)


class MainWindow(QMainWindow):
    # Signals for cross-thread audio & gesture events
    levels_signal = pyqtSignal(float, float)
    gesture_signal = pyqtSignal(str, float)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

        self.setWindowTitle("Kenobi — Acoustic Desk Surface Control")
        self.setMinimumSize(780, 680)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0f19;
            }
            QLabel {
                color: #e2e8f0;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox {
                color: #94a3b8;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #1e293b;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            QComboBox {
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #f1f5f9;
                selection-background-color: #38bdf8;
                selection-color: #0f172a;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #38bdf8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #f8fafc;
                border: 1px solid #38bdf8;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QCheckBox {
                color: #cbd5e1;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #475569;
                background: #1e293b;
            }
            QCheckBox::indicator:checked {
                background: #38bdf8;
                border: 1px solid #38bdf8;
            }
        """)

        # Initialize core components
        self.typing_guard = TypingGuard(
            cooldown_ms=self.config.typing_cooldown_ms,
            enabled=self.config.typing_guard_enabled
        )
        self.action_dispatcher = ActionDispatcher(audio_feedback=self.config.audio_feedback)
        self.hud_overlay = HUDOverlay()

        self.gesture_engine = GestureEngine(
            double_tap_window_ms=self.config.double_tap_window_ms,
            on_gesture_callback=self._on_gesture_detected
        )

        self.audio_engine = AudioEngine(
            sensitivity=self.config.sensitivity,
            stereo_balance=self.config.stereo_balance,
            min_side_ratio=self.config.min_side_ratio,
            device_index=self.config.audio_device_index,
            typing_guard=self.typing_guard,
            on_tap_callback=self._on_raw_tap,
            on_levels_callback=self._on_levels_update
        )

        # Connect signals
        self.levels_signal.connect(self._handle_levels_update)
        self.gesture_signal.connect(self._handle_gesture_event)

        # Build UI layout
        self._build_ui()

        # Initialize System Tray
        self._setup_tray()

        # Auto-start audio if enabled
        if self.config.enabled:
            self._start_engine()

    def _build_ui(self):
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(16)

        # 1. Header Bar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_lbl = QLabel("KENOBI", self)
        title_lbl.setStyleSheet("color: #38bdf8; font-size: 26px; font-weight: 800; letter-spacing: 2px;")
        sub_lbl = QLabel("Acoustic Desk Surface Interaction Suite", self)
        sub_lbl.setStyleSheet("color: #64748b; font-size: 13px; font-weight: 500;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)

        header.addStretch()

        # Power Toggle Button
        self.toggle_btn = QPushButton("Active" if self.config.enabled else "Paused", self)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(self.config.enabled)
        self._update_toggle_btn_style()
        self.toggle_btn.clicked.connect(self._toggle_power)
        header.addWidget(self.toggle_btn)

        root_layout.addLayout(header)

        # 2. Interactive Desk Surface Visualization
        desk_frame = QFrame(self)
        desk_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 14px;
            }
        """)
        desk_layout = QHBoxLayout(desk_frame)
        desk_layout.setContentsMargins(18, 18, 18, 18)
        desk_layout.setSpacing(16)

        # Left Zone
        self.left_zone = DeskZoneWidget("LEFT DESK ZONE", "Single & Double Tap", "LEFT", self)
        desk_layout.addWidget(self.left_zone, 3)

        # Center Laptop Graphic
        center_box = QVBoxLayout()
        center_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        laptop_icon = QLabel("💻", self)
        laptop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        laptop_icon.setStyleSheet("font-size: 42px;")
        laptop_lbl = QLabel("LAPTOP", self)
        laptop_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        laptop_lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        
        center_box.addWidget(laptop_icon)
        center_box.addWidget(laptop_lbl)

        # VU meter in center
        self.level_meter = LevelMeterWidget(self)
        center_box.addWidget(self.level_meter)

        desk_layout.addLayout(center_box, 2)

        # Right Zone
        self.right_zone = DeskZoneWidget("RIGHT DESK ZONE", "Single & Double Tap", "RIGHT", self)
        desk_layout.addWidget(self.right_zone, 3)

        root_layout.addWidget(desk_frame)

        # 3. Profile & Actions Configuration
        profile_group = QGroupBox("Active Interaction Profile", self)
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.setContentsMargins(16, 16, 16, 16)
        profile_layout.setSpacing(12)

        p_row = QHBoxLayout()
        p_lbl = QLabel("Profile Preset:", self)
        p_lbl.setStyleSheet("color: #cbd5e1; font-weight: 600;")
        p_row.addWidget(p_lbl)

        self.profile_combo = QComboBox(self)
        for p_name in self.config.profiles.keys():
            self.profile_combo.addItem(p_name)
        self.profile_combo.setCurrentText(self.config.active_profile)
        self.profile_combo.currentTextChanged.connect(self._change_profile)
        p_row.addWidget(self.profile_combo, 1)

        profile_layout.addLayout(p_row)

        # Grid of current bindings
        self.bindings_grid = QGridLayout()
        self.binding_labels = {}
        bindings = [
            ("LEFT_SINGLE", "Left Single Tap", 0, 0),
            ("RIGHT_SINGLE", "Right Single Tap", 0, 1),
            ("LEFT_DOUBLE", "Left Double Tap", 1, 0),
            ("RIGHT_DOUBLE", "Right Double Tap", 1, 1),
        ]
        for key, name, row, col in bindings:
            card = QFrame(self)
            card.setStyleSheet("""
                QFrame {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 4px;
                }
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(10, 6, 10, 6)
            t_lbl = QLabel(name, card)
            t_lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
            v_lbl = QLabel("", card)
            v_lbl.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: bold;")
            c_lay.addWidget(t_lbl)
            c_lay.addWidget(v_lbl)
            self.binding_labels[key] = v_lbl
            self.bindings_grid.addWidget(card, row, col)

        profile_layout.addLayout(self.bindings_grid)
        self._refresh_binding_labels()

        root_layout.addWidget(profile_group)

        # 4. Calibration & Acoustic Tuning
        tune_group = QGroupBox("Acoustic Calibration & Noise Rejection", self)
        tune_layout = QGridLayout(tune_group)
        tune_layout.setContentsMargins(16, 16, 16, 16)
        tune_layout.setHorizontalSpacing(18)
        tune_layout.setVerticalSpacing(12)

        # Audio Input Device
        tune_layout.addWidget(QLabel("Input Microphone:"), 0, 0)
        self.device_combo = QComboBox(self)
        self._populate_audio_devices()
        self.device_combo.currentIndexChanged.connect(self._change_device)
        tune_layout.addWidget(self.device_combo, 0, 1)

        # Sensitivity Slider
        tune_layout.addWidget(QLabel("Tap Sensitivity:"), 1, 0)
        sens_row = QHBoxLayout()
        self.sens_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.sens_slider.setRange(1, 100)
        # Inverted mapping: high slider = more sensitive (lower threshold)
        cur_val = int((1.0 - (self.config.sensitivity / 0.15)) * 100)
        self.sens_slider.setValue(max(5, min(95, cur_val)))
        self.sens_slider.valueChanged.connect(self._update_sensitivity)
        sens_row.addWidget(self.sens_slider)
        tune_layout.addLayout(sens_row, 1, 1)

        # Stereo Balance Slider
        tune_layout.addWidget(QLabel("Stereo Balance (L / R Bias):"), 2, 0)
        bal_row = QHBoxLayout()
        self.bal_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.bal_slider.setRange(-50, 50)
        self.bal_slider.setValue(int(self.config.stereo_balance * 50))
        self.bal_slider.valueChanged.connect(self._update_balance)
        bal_row.addWidget(self.bal_slider)
        tune_layout.addLayout(bal_row, 2, 1)

        # Toggles Row
        toggles_row = QHBoxLayout()
        self.typing_guard_chk = QCheckBox("Typing Guard (suppress while typing)", self)
        self.typing_guard_chk.setChecked(self.config.typing_guard_enabled)
        self.typing_guard_chk.toggled.connect(self._toggle_typing_guard)
        toggles_row.addWidget(self.typing_guard_chk)

        self.hud_chk = QCheckBox("On-Screen Floating HUD", self)
        self.hud_chk.setChecked(self.config.hud_enabled)
        self.hud_chk.toggled.connect(self._toggle_hud)
        toggles_row.addWidget(self.hud_chk)

        self.audio_feedback_chk = QCheckBox("Click Sound Feedback", self)
        self.audio_feedback_chk.setChecked(self.config.audio_feedback)
        self.audio_feedback_chk.toggled.connect(self._toggle_audio_feedback)
        toggles_row.addWidget(self.audio_feedback_chk)

        tune_layout.addLayout(toggles_row, 3, 0, 1, 2)

        root_layout.addWidget(tune_group)

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Basic icon fallback
        self.tray_icon.setIcon(self.windowIcon())
        tray_menu = QMenu()

        toggle_action = tray_menu.addAction("Toggle Kenobi")
        toggle_action.triggered.connect(self._toggle_power)

        profile_menu = tray_menu.addMenu("Switch Profile")
        for p in self.config.profiles.keys():
            act = profile_menu.addAction(p)
            act.triggered.connect(lambda ch, name=p: self._change_profile(name))

        tray_menu.addSeparator()
        show_action = tray_menu.addAction("Open Control Center")
        show_action.triggered.connect(self.showNormal)

        quit_action = tray_menu.addAction("Quit Kenobi")
        quit_action.triggered.connect(self._quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def _populate_audio_devices(self):
        devices = AudioEngine.get_input_devices()
        self.device_combo.clear()
        self.device_combo.addItem("Default Microphone", -1)

        preferred_idx = -1
        for dev in devices:
            label = f"{dev['name']} ({dev['channels']} ch)"
            self.device_combo.addItem(label, dev['index'])

            # Smart detection: prioritize 'Microphone Array' if default isn't explicitly set
            if self.config.audio_device_index == -1:
                if "microphone array" in dev['name'].lower() and preferred_idx == -1:
                    preferred_idx = dev['index']

        if self.config.audio_device_index != -1:
            # Set to saved index
            idx = self.device_combo.findData(self.config.audio_device_index)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
        elif preferred_idx != -1:
            idx = self.device_combo.findData(preferred_idx)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
                self.config.audio_device_index = preferred_idx

    def _change_device(self, combo_idx: int):
        device_index = self.device_combo.itemData(combo_idx)
        if device_index is not None and device_index != self.config.audio_device_index:
            self.config.audio_device_index = device_index
            self.config.save()
            # Restart audio engine with new device
            if self.audio_engine.is_running:
                self.audio_engine.stop()
                self.audio_engine.device_index = device_index if device_index >= 0 else None
                self.audio_engine.start()

    def _change_profile(self, profile_name: str):
        if profile_name in self.config.profiles:
            self.config.active_profile = profile_name
            self.profile_combo.setCurrentText(profile_name)
            self._refresh_binding_labels()
            self.config.save()

    def _refresh_binding_labels(self):
        profile = self.config.profiles.get(self.config.active_profile, {})
        for key, lbl in self.binding_labels.items():
            spec = profile.get(key, {})
            lbl.setText(spec.get("label", "None"))

    def _update_sensitivity(self, val: int):
        # Invert: higher val = lower threshold (more sensitive)
        sens = (1.0 - (val / 100.0)) * 0.15
        sens = max(0.008, min(0.15, sens))
        self.config.sensitivity = sens
        self.audio_engine.update_settings(self.config.sensitivity, self.config.stereo_balance, self.config.min_side_ratio)
        self.config.save()

    def _update_balance(self, val: int):
        bal = val / 50.0  # -1.0 to 1.0
        self.config.stereo_balance = bal
        self.audio_engine.update_settings(self.config.sensitivity, self.config.stereo_balance, self.config.min_side_ratio)
        self.config.save()

    def _toggle_typing_guard(self, checked: bool):
        self.config.typing_guard_enabled = checked
        self.typing_guard.set_enabled(checked)
        self.config.save()

    def _toggle_hud(self, checked: bool):
        self.config.hud_enabled = checked
        self.config.save()

    def _toggle_audio_feedback(self, checked: bool):
        self.config.audio_feedback = checked
        self.action_dispatcher.audio_feedback = checked
        self.config.save()

    def _toggle_power(self):
        self.config.enabled = not self.config.enabled
        self.toggle_btn.setChecked(self.config.enabled)
        self.toggle_btn.setText("Active" if self.config.enabled else "Paused")
        self._update_toggle_btn_style()
        self.config.save()

        if self.config.enabled:
            self._start_engine()
        else:
            self._stop_engine()

    def _update_toggle_btn_style(self):
        if self.config.enabled:
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                    border-radius: 8px;
                    padding: 8px 18px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """)
        else:
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    font-size: 13px;
                    font-weight: bold;
                    border-radius: 8px;
                    padding: 8px 18px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #475569;
                }
            """)

    def _start_engine(self):
        self.audio_engine.start()

    def _stop_engine(self):
        self.audio_engine.stop()
        self.gesture_engine.reset()

    def _on_levels_update(self, left: float, right: float):
        self.levels_signal.emit(left, right)

    def _on_raw_tap(self, side: str, energy: float):
        if not self.config.enabled:
            return
        self.gesture_engine.register_tap(side, energy)

    def _on_gesture_detected(self, gesture_name: str, energy: float):
        self.gesture_signal.emit(gesture_name, energy)

    @pyqtSlot(float, float)
    def _handle_levels_update(self, left: float, right: float):
        self.level_meter.set_levels(left, right)

    @pyqtSlot(str, float)
    def _handle_gesture_event(self, gesture_name: str, energy: float):
        if not self.config.enabled:
            return

        profile = self.config.profiles.get(self.config.active_profile, {})
        action_spec = profile.get(gesture_name)

        if not action_spec:
            return

        action_label = action_spec.get("label", "Action")

        # 1. Trigger Pulse Animation on Desk Visualizer
        if "LEFT" in gesture_name:
            self.left_zone.trigger_pulse(gesture_name, action_label)
        elif "RIGHT" in gesture_name:
            self.right_zone.trigger_pulse(gesture_name, action_label)

        # 2. Show On-Screen Floating HUD
        if self.config.hud_enabled:
            self.hud_overlay.show_gesture(gesture_name, action_label, self.config.hud_duration_ms)

        # 3. Dispatch System Action (Media, Mouse, Shortcut)
        self.action_dispatcher.trigger(action_spec)

    def closeEvent(self, event):
        # Minimize to tray instead of exiting
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "Kenobi",
                "Kenobi is listening on your desk surface in the background.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            event.ignore()
        else:
            self._quit_app()

    def _quit_app(self):
        self._stop_engine()
        self.typing_guard.stop()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        sys.exit(0)
