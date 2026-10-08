import sys
import os
import time
import math
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QPainter, QBrush, QPen, 
    QLinearGradient, QRadialGradient, QPainterPath
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QSlider, QCheckBox, QFrame, 
    QGroupBox, QGridLayout, QSystemTrayIcon, QMenu, QMessageBox,
    QScrollArea
)

from .config import AppConfig, DEFAULT_PROFILES
from .audio_engine import AudioEngine
from .gesture_engine import GestureEngine
from .anti_noise import TypingGuard
from .action_dispatcher import ActionDispatcher
from .hud_overlay import HUDOverlay


# ==========================================
# DESIGN SYSTEM CONSTANTS (Stitch FIDELITY)
# ==========================================
COLOR_BASE_ABYSS = "#090d16"
COLOR_SURFACE_MID = "#0b1120"
COLOR_SURFACE_ELEVATED = "#0f172a"
COLOR_SURFACE_INTERACTIVE = "#1e293b"
COLOR_BORDER_SUBTLE = "#1e293b"
COLOR_BORDER_STROKE = "#334155"

COLOR_CYAN = "#38bdf8"       # Primary Single Tap / Active
COLOR_VIOLET = "#c084fc"     # Secondary Double Tap
COLOR_EMERALD = "#10b981"    # DSP Live / Normal
COLOR_ROSE = "#f43f5e"       # Peak Warning / Fault
COLOR_AMBER = "#f59e0b"      # Gating / Suppression

COLOR_TEXT_PRIMARY = "#f1f5f9"
COLOR_TEXT_SECONDARY = "#94a3b8"
COLOR_TEXT_MUTED = "#64748b"

AVAILABLE_ACTIONS = [
    {"label": "Previous Track", "type": "media", "action": "prev_track", "icon": "⏮"},
    {"label": "Next Track", "type": "media", "action": "next_track", "icon": "⏭"},
    {"label": "Play / Pause", "type": "media", "action": "play_pause", "icon": "⏯"},
    {"label": "Volume Down", "type": "media", "action": "volume_down", "icon": "🔉"},
    {"label": "Volume Up", "type": "media", "action": "volume_up", "icon": "🔊"},
    {"label": "Mute / Unmute", "type": "media", "action": "mute", "icon": "🔇"},
    {"label": "Browser Back", "type": "hotkey", "action": ["alt", "left"], "icon": "◀"},
    {"label": "Browser Forward", "type": "hotkey", "action": ["alt", "right"], "icon": "▶"},
    {"label": "Previous Tab", "type": "hotkey", "action": ["ctrl", "shift", "tab"], "icon": "⇤"},
    {"label": "Next Tab", "type": "hotkey", "action": ["ctrl", "tab"], "icon": "⇥"},
    {"label": "Show Desktop", "type": "hotkey", "action": ["win", "d"], "icon": "🖥"},
    {"label": "Switch App", "type": "hotkey", "action": ["alt", "tab"], "icon": "🔀"},
    {"label": "Left Click", "type": "mouse", "action": "left_click", "icon": "🖱"},
    {"label": "Right Click", "type": "mouse", "action": "right_click", "icon": "🖱"},
    {"label": "Double Click", "type": "mouse", "action": "double_click", "icon": "🖱"},
    {"label": "Middle Click", "type": "mouse", "action": "middle_click", "icon": "🖱"},
]


# ==========================================
# 1. INTERACTIVE DESK ZONE WIDGET
# ==========================================
class DeskZoneWidget(QFrame):
    """
    Tactile acoustic surface zone card with animated radar/ripple wave pulses
    and active gesture assignment telemetry.
    """
    def __init__(self, title: str, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self.title_text = title
        self.pulse_phase = 0.0
        self.is_active = False
        self.pulse_color = QColor(COLOR_CYAN)
        self.last_action = "Idle"
        self.single_label_text = "Prev Track"
        self.double_label_text = "Volume Down"

        self.setMinimumHeight(210)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.decay_timer = QTimer(self)
        self.decay_timer.setInterval(25)
        self.decay_timer.timeout.connect(self._on_decay)

    def set_bindings(self, single_label: str, double_label: str):
        self.single_label_text = single_label
        self.double_label_text = double_label
        self.update()

    def trigger_pulse(self, gesture_type: str, action_name: str):
        self.last_action = action_name
        self.is_active = True
        self.pulse_phase = 1.0
        if "DOUBLE" in gesture_type:
            self.pulse_color = QColor(COLOR_VIOLET)
        else:
            self.pulse_color = QColor(COLOR_CYAN)
        self.decay_timer.start()
        self.update()

    def _on_decay(self):
        self.pulse_phase -= 0.04
        if self.pulse_phase <= 0.0:
            self.pulse_phase = 0.0
            self.is_active = False
            self.decay_timer.stop()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 1. Background Card with Sub-surface glow
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 12, 12)

        # Base Surface
        painter.fillPath(path, QColor(COLOR_SURFACE_MID))

        # Pulse Glow overlay
        if self.pulse_phase > 0.0:
            glow_grad = QRadialGradient(
                w * 0.5, h * 0.45, max(w, h) * 0.7
            )
            col = QColor(self.pulse_color)
            col.setAlphaF(0.28 * self.pulse_phase)
            glow_grad.setColorAt(0.0, col)
            glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillPath(path, glow_grad)

        # 2. Border Stroke
        border_col = QColor(COLOR_BORDER_STROKE)
        if self.pulse_phase > 0.0:
            b_alpha = int(120 + 135 * self.pulse_phase)
            border_col = QColor(self.pulse_color)
            border_col.setAlpha(b_alpha)
        pen = QPen(border_col, 1.5)
        painter.strokePath(path, pen)

        # 3. Concentric Acoustic Waves Graphic
        cx = w * (0.35 if self.side == "LEFT" else 0.65)
        cy = h * 0.46
        ring_count = 4
        base_radius = 24.0

        for i in range(ring_count):
            r = base_radius + i * 18.0 + (1.0 - self.pulse_phase) * 6.0
            ring_pen = QPen()
            if self.pulse_phase > 0.0:
                alpha = int(max(0, 180 * self.pulse_phase - (i * 35)))
                col = QColor(self.pulse_color)
                col.setAlpha(alpha)
                ring_pen.setColor(col)
                ring_pen.setWidthF(1.8)
            else:
                ring_pen.setColor(QColor(51, 65, 85, 90 - i * 18))
                ring_pen.setWidthF(1.0)
                ring_pen.setStyle(Qt.PenStyle.DashLine if i % 2 == 1 else Qt.PenStyle.SolidLine)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r * 0.65)

        # Center Acoustic Spark Icon
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.setPen(self.pulse_color if self.pulse_phase > 0.0 else QColor(COLOR_TEXT_MUTED))
        arrow = "◀" if self.side == "LEFT" else "▶"
        painter.drawText(QRectF(cx - 16, cy - 14, 32, 28), Qt.AlignmentFlag.AlignCenter, arrow)

        # 4. Header Bar
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor(COLOR_TEXT_SECONDARY))
        painter.drawText(QRectF(16, 14, w - 32, 20), Qt.AlignmentFlag.AlignLeft, self.title_text)

        # Status Badge Pill (ARMED / ACTIVE)
        badge_rect = QRectF(w - 76, 12, 60, 20)
        badge_path = QPainterPath()
        badge_path.addRoundedRect(badge_rect, 10, 10)
        
        if self.pulse_phase > 0.0:
            painter.fillPath(badge_path, QColor(self.pulse_color.red(), self.pulse_color.green(), self.pulse_color.blue(), 40))
            painter.setPen(self.pulse_color)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "HIT!")
        else:
            painter.fillPath(badge_path, QColor(16, 185, 129, 28))
            painter.setPen(QColor(COLOR_EMERALD))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "● ARMED")

        # 5. Bottom Binding Telemetry
        tag_y = h - 62
        # Single Tap Pill
        s_rect = QRectF(14, tag_y, (w - 34) / 2, 22)
        s_path = QPainterPath()
        s_path.addRoundedRect(s_rect, 4, 4)
        painter.fillPath(s_path, QColor(15, 23, 42, 180))
        painter.setPen(QPen(QColor(56, 189, 248, 70), 1))
        painter.strokePath(s_path, painter.pen())
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(COLOR_CYAN))
        painter.drawText(s_rect, Qt.AlignmentFlag.AlignCenter, f"1× {self.single_label_text}")

        # Double Tap Pill
        d_rect = QRectF(14 + (w - 34) / 2 + 6, tag_y, (w - 34) / 2, 22)
        d_path = QPainterPath()
        d_path.addRoundedRect(d_rect, 4, 4)
        painter.fillPath(d_path, QColor(15, 23, 42, 180))
        painter.setPen(QPen(QColor(192, 132, 252, 70), 1))
        painter.strokePath(d_path, painter.pen())
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(COLOR_VIOLET))
        painter.drawText(d_rect, Qt.AlignmentFlag.AlignCenter, f"2× {self.double_label_text}")

        # Last Action Telemetry readout
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(COLOR_TEXT_MUTED))
        act_text = f"Telemetry: {self.last_action}"
        painter.drawText(QRectF(14, h - 30, w - 28, 18), Qt.AlignmentFlag.AlignLeft, act_text)


# ==========================================
# 2. LAPTOP & STEREO VU LEVEL METER WIDGET
# ==========================================
class LaptopCenterWidget(QWidget):
    """
    Sleek top-down laptop schematic with stereo microphone apertures
    and high-precision real-time stereo VU dBFS meters.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_level = 0.0
        self.right_level = 0.0
        self.left_peak = 0.0
        self.right_peak = 0.0
        self.threshold = 0.25  # Relative normalized trigger threshold
        self.setMinimumHeight(210)
        self.setMinimumWidth(260)

        # Peak decay timer
        self.decay_timer = QTimer(self)
        self.decay_timer.setInterval(40)
        self.decay_timer.timeout.connect(self._decay_peaks)
        self.decay_timer.start()

    def set_levels(self, left: float, right: float):
        l_db = 20 * math.log10(max(left, 1e-6))
        r_db = 20 * math.log10(max(right, 1e-6))
        # Map -60 dB -> 0.0, 0 dB -> 1.0
        norm_l = max(0.0, min(1.0, (l_db + 60.0) / 60.0))
        norm_r = max(0.0, min(1.0, (r_db + 60.0) / 60.0))

        self.left_level = norm_l
        self.right_level = norm_r

        if norm_l > self.left_peak:
            self.left_peak = norm_l
        if norm_r > self.right_peak:
            self.right_peak = norm_r

        self.update()

    def set_threshold(self, normalized_thresh: float):
        self.threshold = max(0.05, min(0.95, normalized_thresh))
        self.update()

    def _decay_peaks(self):
        self.left_peak = max(self.left_level, self.left_peak - 0.015)
        self.right_peak = max(self.right_level, self.right_peak - 0.015)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 1. Enclosure Panel
        outer = QRectF(0, 0, w, h)
        out_path = QPainterPath()
        out_path.addRoundedRect(outer, 12, 12)
        painter.fillPath(out_path, QColor(COLOR_SURFACE_MID))
        painter.setPen(QPen(QColor(COLOR_BORDER_STROKE), 1))
        painter.strokePath(out_path, painter.pen())

        # 2. Top-down Laptop Chassis Schematic
        lp_w = min(200.0, w - 48.0)
        lp_h = 76.0
        lp_x = (w - lp_w) / 2
        lp_y = 18.0

        # Laptop Base Chassis
        base_path = QPainterPath()
        base_path.addRoundedRect(QRectF(lp_x, lp_y, lp_w, lp_h), 8, 8)
        painter.fillPath(base_path, QColor(COLOR_SURFACE_INTERACTIVE))
        painter.setPen(QPen(QColor(71, 85, 105, 160), 1.2))
        painter.strokePath(base_path, painter.pen())

        # Display Hinge
        hinge_w = lp_w * 0.55
        hinge_x = lp_x + (lp_w - hinge_w) / 2
        painter.fillRect(QRectF(hinge_x, lp_y + 2, hinge_w, 4), QColor(15, 23, 42))

        # Stylized Keyboard Matrix Lines
        kb_w = lp_w - 24.0
        kb_h = 34.0
        kb_x = lp_x + 12.0
        kb_y = lp_y + 12.0
        painter.fillRect(QRectF(kb_x, kb_y, kb_w, kb_h), QColor(15, 23, 42, 180))
        painter.setPen(QPen(QColor(51, 65, 85, 120), 1))
        for line_y in [kb_y + 8, kb_y + 16, kb_y + 24]:
            painter.drawLine(QPointF(kb_x + 4, line_y), QPointF(kb_x + kb_w - 4, line_y))

        # Trackpad
        tp_w = 40.0
        tp_h = 16.0
        tp_x = lp_x + (lp_w - tp_w) / 2
        tp_y = kb_y + kb_h + 5.0
        painter.fillRect(QRectF(tp_x, tp_y, tp_w, tp_h), QColor(30, 41, 59))
        painter.setPen(QPen(QColor(71, 85, 105, 100), 1))
        painter.drawRect(QRectF(tp_x, tp_y, tp_w, tp_h))

        # Stereo Microphone Apertures (L & R with active glowing dots)
        mic_l_x = lp_x + 8.0
        mic_r_x = lp_x + lp_w - 14.0
        mic_y = lp_y + 5.0

        # Mic L
        painter.setBrush(QColor(COLOR_CYAN if self.left_level > 0.1 else COLOR_TEXT_MUTED))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(mic_l_x, mic_y, 6, 6))

        # Mic R
        painter.setBrush(QColor(COLOR_CYAN if self.right_level > 0.1 else COLOR_TEXT_MUTED))
        painter.drawEllipse(QRectF(mic_r_x, mic_y, 6, 6))

        painter.setFont(QFont("JetBrains Mono", 7, QFont.Weight.Bold))
        painter.setPen(QColor(COLOR_CYAN))
        painter.drawText(QRectF(lp_x + 2, lp_y + 14, 24, 12), Qt.AlignmentFlag.AlignCenter, "MIC L")
        painter.drawText(QRectF(lp_x + lp_w - 26, lp_y + 14, 24, 12), Qt.AlignmentFlag.AlignCenter, "MIC R")

        # 3. Stereo VU Level Meters Title
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(COLOR_TEXT_SECONDARY))
        painter.drawText(QRectF(16, lp_y + lp_h + 10, w - 32, 16), Qt.AlignmentFlag.AlignCenter, "STEREO VU ACOUSTIC SPECTRUM")

        # 4. VU Meters Trough
        meter_w = w - 40.0
        meter_h = 10.0
        m_x = 20.0
        m_y_left = lp_y + lp_h + 30.0
        m_y_right = m_y_left + 16.0

        # Background Troughs
        painter.setBrush(QColor(15, 23, 42))
        painter.setPen(QPen(QColor(30, 41, 59), 1))
        painter.drawRoundedRect(QRectF(m_x, m_y_left, meter_w, meter_h), 3, 3)
        painter.drawRoundedRect(QRectF(m_x, m_y_right, meter_w, meter_h), 3, 3)

        # Gradient bar painter
        def draw_bar(y_pos: float, norm_level: float, peak_level: float):
            if norm_level <= 0.001:
                return
            grad = QLinearGradient(m_x, y_pos, m_x + meter_w, y_pos)
            grad.setColorAt(0.0, QColor(COLOR_EMERALD))
            grad.setColorAt(0.70, QColor(COLOR_CYAN))
            grad.setColorAt(0.88, QColor(COLOR_AMBER))
            grad.setColorAt(1.0, QColor(COLOR_ROSE))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            fill_w = max(2.0, meter_w * norm_level)
            painter.drawRoundedRect(QRectF(m_x, y_pos, fill_w, meter_h), 3, 3)

            # Peak Hold Marker Line
            if peak_level > 0.05:
                peak_x = m_x + meter_w * min(1.0, peak_level)
                painter.setPen(QPen(QColor(COLOR_TEXT_PRIMARY), 1.5))
                painter.drawLine(QPointF(peak_x, y_pos - 1), QPointF(peak_x, y_pos + meter_h + 1))

        draw_bar(m_y_left, self.left_level, self.left_peak)
        draw_bar(m_y_right, self.right_level, self.right_peak)

        # Threshold Indicator Line Overlay
        thresh_x = m_x + meter_w * self.threshold
        painter.setPen(QPen(QColor(COLOR_AMBER), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(thresh_x, m_y_left - 3), QPointF(thresh_x, m_y_right + meter_h + 3))

        # 5. dBFS Scale Ticks
        painter.setFont(QFont("JetBrains Mono", 7))
        painter.setPen(QColor(COLOR_TEXT_MUTED))
        scale_ticks = [("-60", 0.0), ("-30", 0.5), ("-12", 0.8), ("0dB", 1.0)]
        for lbl, pos in scale_ticks:
            x_pos = m_x + meter_w * pos - 8
            painter.drawText(QRectF(x_pos, m_y_right + 14, 28, 12), Qt.AlignmentFlag.AlignCenter, lbl)

        # Threshold badge
        painter.setPen(QColor(COLOR_AMBER))
        painter.drawText(QRectF(thresh_x - 30, m_y_left - 15, 60, 12), Qt.AlignmentFlag.AlignCenter, "TRIGGER")


# ==========================================
# 3. TACTILE MACRO TILE WIDGET (PAD)
# ==========================================
class MacroTileWidget(QFrame):
    """
    Machined macro button tile representing a desk gesture with action pill,
    accent luminescence, and quick action remapping.
    """
    binding_changed = pyqtSignal(str, dict)

    def __init__(self, gesture_key: str, gesture_title: str, is_double: bool = False, parent=None):
        super().__init__(parent)
        self.gesture_key = gesture_key
        self.gesture_title = gesture_title
        self.is_double = is_double
        self.accent_color = COLOR_VIOLET if is_double else COLOR_CYAN
        self.current_action: Dict[str, Any] = {}
        self.flash_alpha = 0.0

        self.setMinimumHeight(100)
        self.setStyleSheet(f"""
            MacroTileWidget {{
                background-color: {COLOR_SURFACE_INTERACTIVE};
                border: 1px solid {COLOR_BORDER_STROKE};
                border-radius: 8px;
            }}
            MacroTileWidget:hover {{
                border: 1px solid {self.accent_color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Top Row: Sub-badge & Accent Bar
        top_row = QHBoxLayout()
        self.title_lbl = QLabel(gesture_title.upper(), self)
        self.title_lbl.setStyleSheet(f"""
            color: {self.accent_color};
            font-family: 'Segoe UI', sans-serif;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1px;
        """)
        top_row.addWidget(self.title_lbl)

        top_row.addStretch()

        self.type_pill = QLabel("2× DOUBLE" if is_double else "1× SINGLE", self)
        self.type_pill.setStyleSheet(f"""
            color: {COLOR_TEXT_PRIMARY};
            background-color: {'rgba(192, 132, 252, 0.2)' if is_double else 'rgba(56, 189, 248, 0.2)'};
            border: 1px solid {'rgba(192, 132, 252, 0.4)' if is_double else 'rgba(56, 189, 248, 0.4)'};
            border-radius: 4px;
            font-family: 'JetBrains Mono', sans-serif;
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
        """)
        top_row.addWidget(self.type_pill)
        layout.addLayout(top_row)

        # Action Selector Dropdown
        self.action_combo = QComboBox(self)
        self.action_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_BASE_ABYSS};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_STROKE};
                border-radius: 6px;
                padding: 6px 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 600;
            }}
            QComboBox:hover {{
                border: 1px solid {self.accent_color};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLOR_SURFACE_MID};
                color: {COLOR_TEXT_PRIMARY};
                selection-background-color: {self.accent_color};
                selection-color: {COLOR_BASE_ABYSS};
            }}
        """)
        for item in AVAILABLE_ACTIONS:
            self.action_combo.addItem(f"{item['icon']}  {item['label']}", item)
        self.action_combo.currentIndexChanged.connect(self._on_combo_change)
        layout.addWidget(self.action_combo)

        # Flash animation timer
        self.flash_timer = QTimer(self)
        self.flash_timer.setInterval(30)
        self.flash_timer.timeout.connect(self._decay_flash)

    def set_action_spec(self, spec: Dict[str, Any]):
        self.current_action = spec
        label = spec.get("label", "")
        # Find in combo
        idx = -1
        for i in range(self.action_combo.count()):
            item_data = self.action_combo.itemData(i)
            if item_data and item_data.get("label") == label:
                idx = i
                break
        if idx >= 0:
            self.action_combo.blockSignals(True)
            self.action_combo.setCurrentIndex(idx)
            self.action_combo.blockSignals(False)

    def trigger_flash(self):
        self.flash_alpha = 1.0
        self.flash_timer.start()
        self.setStyleSheet(f"""
            MacroTileWidget {{
                background-color: {'rgba(192, 132, 252, 0.25)' if self.is_double else 'rgba(56, 189, 248, 0.25)'};
                border: 2px solid {self.accent_color};
                border-radius: 8px;
            }}
        """)

    def _decay_flash(self):
        self.flash_alpha -= 0.08
        if self.flash_alpha <= 0.0:
            self.flash_alpha = 0.0
            self.flash_timer.stop()
            self.setStyleSheet(f"""
                MacroTileWidget {{
                    background-color: {COLOR_SURFACE_INTERACTIVE};
                    border: 1px solid {COLOR_BORDER_STROKE};
                    border-radius: 8px;
                }}
                MacroTileWidget:hover {{
                    border: 1px solid {self.accent_color};
                }}
            """)

    def _on_combo_change(self, idx: int):
        data = self.action_combo.itemData(idx)
        if data:
            self.current_action = data
            self.binding_changed.emit(self.gesture_key, data)


# ==========================================
# 4. MAIN WINDOW CONTROL CENTER
# ==========================================
class MainWindow(QMainWindow):
    levels_signal = pyqtSignal(float, float)
    gesture_signal = pyqtSignal(str, float)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

        self.setWindowTitle("Kenobi — Acoustic Desk Surface Control Center")
        self.setMinimumSize(1000, 780)
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BASE_ABYSS};
            }}
            QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                font-family: 'Segoe UI', 'Geist', sans-serif;
            }}
            QGroupBox {{
                color: {COLOR_TEXT_SECONDARY};
                font-family: 'Segoe UI', sans-serif;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 16px;
                background-color: {COLOR_SURFACE_MID};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                color: {COLOR_CYAN};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {COLOR_SURFACE_INTERACTIVE};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLOR_CYAN};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 1px solid {COLOR_CYAN};
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }}
            QCheckBox {{
                color: {COLOR_TEXT_PRIMARY};
                font-size: 13px;
                spacing: 8px;
                font-weight: 500;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {COLOR_BORDER_STROKE};
                background: {COLOR_SURFACE_INTERACTIVE};
            }}
            QCheckBox::indicator:checked {{
                background: {COLOR_CYAN};
                border: 1px solid {COLOR_CYAN};
            }}
        """)

        # Core Engines
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

        # Cross-thread Qt Signal connections
        self.levels_signal.connect(self._handle_levels_update)
        self.gesture_signal.connect(self._handle_gesture_event)

        # Build UI layout
        self._build_ui()

        # System Tray
        self._setup_tray()

        # Telemetry & Typing Guard Monitor Timer (100ms)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.setInterval(100)
        self.telemetry_timer.timeout.connect(self._update_telemetry)
        self.telemetry_timer.start()

        # Auto-start engine
        if self.config.enabled:
            self._start_engine()

    def _build_ui(self):
        # Use a ScrollArea so the window adapts seamlessly to smaller screens
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.setCentralWidget(scroll)

        main_widget = QWidget(scroll)
        scroll.setWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(28, 22, 28, 24)
        root_layout.setSpacing(18)

        # ==========================================
        # 1. HEADER BAR & TELEMETRY STRIP
        # ==========================================
        header = QHBoxLayout()
        header.setSpacing(16)

        # Brand Title Box
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_row = QHBoxLayout()
        icon_lbl = QLabel("(((⚡)))", self)
        icon_lbl.setStyleSheet(f"color: {COLOR_CYAN}; font-size: 20px; font-weight: bold;")
        title_row.addWidget(icon_lbl)

        brand_lbl = QLabel("KENOBI", self)
        brand_lbl.setStyleSheet(f"color: {COLOR_CYAN}; font-size: 24px; font-weight: 900; letter-spacing: 2px;")
        title_row.addWidget(brand_lbl)
        title_row.addStretch()
        title_box.addLayout(title_row)

        sub_lbl = QLabel("Acoustic Desk Surface Interaction Suite • Precision DSP Bridge", self)
        sub_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px; font-weight: 500;")
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)

        header.addStretch()

        # Audio Stream Telemetry Pill
        self.stream_pill = QLabel("● 48.0 kHz | 2 CH | WASAPI", self)
        self.stream_pill.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_EMERALD};
                background-color: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 6px;
                padding: 6px 12px;
                font-family: 'JetBrains Mono', sans-serif;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        header.addWidget(self.stream_pill)

        # Typing Guard Status Pill
        self.typing_pill = QLabel("● GUARD ARMED", self)
        self.typing_pill.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_EMERALD};
                background-color: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 6px;
                padding: 6px 12px;
                font-family: 'JetBrains Mono', sans-serif;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        header.addWidget(self.typing_pill)

        # Master Power Toggle Latch
        self.power_btn = QPushButton("● SENSING ACTIVE" if self.config.enabled else "○ PAUSED", self)
        self.power_btn.setCheckable(True)
        self.power_btn.setChecked(self.config.enabled)
        self._update_power_button_style()
        self.power_btn.clicked.connect(self._toggle_power)
        header.addWidget(self.power_btn)

        root_layout.addLayout(header)

        # ==========================================
        # 2. HERO STAGE — INTERACTIVE DESK SURFACE
        # ==========================================
        desk_stage_box = QFrame(self)
        desk_stage_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_SURFACE_MID};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 14px;
            }}
        """)
        desk_layout = QHBoxLayout(desk_stage_box)
        desk_layout.setContentsMargins(16, 16, 16, 16)
        desk_layout.setSpacing(16)

        # Left Desk Zone Card
        self.left_zone = DeskZoneWidget("LEFT DESK ZONE", "LEFT", self)
        desk_layout.addWidget(self.left_zone, 3)

        # Center Laptop Schematic & VU Meter
        self.laptop_widget = LaptopCenterWidget(self)
        desk_layout.addWidget(self.laptop_widget, 4)

        # Right Desk Zone Card
        self.right_zone = DeskZoneWidget("RIGHT DESK ZONE", "RIGHT", self)
        desk_layout.addWidget(self.right_zone, 3)

        root_layout.addWidget(desk_stage_box)

        # ==========================================
        # 3. GESTURE ACTION MATRIX & PROFILES
        # ==========================================
        matrix_group = QGroupBox("Gesture Action Matrix & Macro Controller", self)
        matrix_layout = QVBoxLayout(matrix_group)
        matrix_layout.setContentsMargins(18, 16, 18, 18)
        matrix_layout.setSpacing(14)

        # Profile Switcher Pill Tabs
        p_row = QHBoxLayout()
        p_lbl = QLabel("Profile Preset:", self)
        p_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-weight: 700; font-size: 12px;")
        p_row.addWidget(p_lbl)

        self.profile_buttons: Dict[str, QPushButton] = {}
        profiles = list(self.config.profiles.keys())
        for pname in profiles:
            p_btn = QPushButton(pname, self)
            p_btn.setCheckable(True)
            p_btn.setChecked(pname == self.config.active_profile)
            p_btn.clicked.connect(lambda ch, name=pname: self._change_profile(name))
            p_row.addWidget(p_btn)
            self.profile_buttons[pname] = p_btn
        self._update_profile_buttons_style()

        p_row.addStretch()
        matrix_layout.addLayout(p_row)

        # 2x2 Grid of Tactile Macro Pads
        pads_grid = QGridLayout()
        pads_grid.setHorizontalSpacing(14)
        pads_grid.setVerticalSpacing(14)

        self.macro_pads: Dict[str, MacroTileWidget] = {}
        gestures = [
            ("LEFT_SINGLE", "Left Desk • Single Tap", False, 0, 0),
            ("RIGHT_SINGLE", "Right Desk • Single Tap", False, 0, 1),
            ("LEFT_DOUBLE", "Left Desk • Double Tap", True, 1, 0),
            ("RIGHT_DOUBLE", "Right Desk • Double Tap", True, 1, 1),
        ]

        for key, title, is_dbl, r, c in gestures:
            pad = MacroTileWidget(key, title, is_double=is_dbl, parent=self)
            pad.binding_changed.connect(self._on_pad_binding_changed)
            pads_grid.addWidget(pad, r, c)
            self.macro_pads[key] = pad

        matrix_layout.addLayout(pads_grid)
        root_layout.addWidget(matrix_group)

        # ==========================================
        # 4. ACOUSTIC CALIBRATION & HARDWARE STRIP
        # ==========================================
        calib_group = QGroupBox("Acoustic Calibration & Hardware Rejection Strip", self)
        calib_layout = QGridLayout(calib_group)
        calib_layout.setContentsMargins(18, 16, 18, 16)
        calib_layout.setHorizontalSpacing(24)
        calib_layout.setVerticalSpacing(14)

        # Audio Input Device Dropdown
        calib_layout.addWidget(QLabel("Stereo Mic Array:"), 0, 0)
        self.device_combo = QComboBox(self)
        self.device_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_BASE_ABYSS};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_STROKE};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border: 1px solid {COLOR_CYAN};
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLOR_SURFACE_MID};
                color: {COLOR_TEXT_PRIMARY};
                selection-background-color: {COLOR_CYAN};
                selection-color: {COLOR_BASE_ABYSS};
            }}
        """)
        self._populate_audio_devices()
        self.device_combo.currentIndexChanged.connect(self._change_device)
        calib_layout.addWidget(self.device_combo, 0, 1)

        # Tap Sensitivity Slider with numeric badge
        calib_layout.addWidget(QLabel("Tap Sensitivity:"), 1, 0)
        sens_row = QHBoxLayout()
        self.sens_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.sens_slider.setRange(1, 100)
        cur_val = int((1.0 - (self.config.sensitivity / 0.15)) * 100)
        self.sens_slider.setValue(max(5, min(95, cur_val)))
        self.sens_slider.valueChanged.connect(self._update_sensitivity)
        sens_row.addWidget(self.sens_slider, 1)

        self.sens_val_lbl = QLabel(f"{self.config.sensitivity:.3f}", self)
        self.sens_val_lbl.setStyleSheet(f"color: {COLOR_CYAN}; font-family: 'JetBrains Mono'; font-weight: bold; min-width: 45px;")
        sens_row.addWidget(self.sens_val_lbl)
        calib_layout.addLayout(sens_row, 1, 1)

        # Stereo Balance Slider with Center Detent
        calib_layout.addWidget(QLabel("Stereo Bias (L / R Balance):"), 2, 0)
        bal_row = QHBoxLayout()
        self.bal_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.bal_slider.setRange(-50, 50)
        self.bal_slider.setValue(int(self.config.stereo_balance * 50))
        self.bal_slider.valueChanged.connect(self._update_balance)
        bal_row.addWidget(self.bal_slider, 1)

        self.bal_val_lbl = QLabel(f"{self.config.stereo_balance:+.2f}", self)
        self.bal_val_lbl.setStyleSheet(f"color: {COLOR_CYAN}; font-family: 'JetBrains Mono'; font-weight: bold; min-width: 45px;")
        bal_row.addWidget(self.bal_val_lbl)
        calib_layout.addLayout(bal_row, 2, 1)

        # Feature Toggles Row
        toggles_row = QHBoxLayout()
        toggles_row.setSpacing(24)

        self.typing_guard_chk = QCheckBox("Typing Guard (Suppress taps while typing)", self)
        self.typing_guard_chk.setChecked(self.config.typing_guard_enabled)
        self.typing_guard_chk.toggled.connect(self._toggle_typing_guard)
        toggles_row.addWidget(self.typing_guard_chk)

        self.hud_chk = QCheckBox("On-Screen Floating HUD", self)
        self.hud_chk.setChecked(self.config.hud_enabled)
        self.hud_chk.toggled.connect(self._toggle_hud)
        toggles_row.addWidget(self.hud_chk)

        self.audio_feedback_chk = QCheckBox("Acoustic Click Sound", self)
        self.audio_feedback_chk.setChecked(self.config.audio_feedback)
        self.audio_feedback_chk.toggled.connect(self._toggle_audio_feedback)
        toggles_row.addWidget(self.audio_feedback_chk)

        toggles_row.addStretch()
        calib_layout.addLayout(toggles_row, 3, 0, 1, 2)

        root_layout.addWidget(calib_group)

        # Synchronize UI states
        self._refresh_all_bindings()
        self._update_sensitivity_threshold_view()

    # ==========================================
    # LOGIC & DISPATCH HANDLERS
    # ==========================================
    def _update_power_button_style(self):
        if self.config.enabled:
            self.power_btn.setText("● SENSING ACTIVE")
            self.power_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #0284c7;
                    color: white;
                    font-size: 13px;
                    font-weight: 800;
                    letter-spacing: 0.5px;
                    border-radius: 8px;
                    padding: 8px 18px;
                    border: 1px solid {COLOR_CYAN};
                }}
                QPushButton:hover {{
                    background-color: #0369a1;
                }}
            """)
        else:
            self.power_btn.setText("○ PAUSED")
            self.power_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_SURFACE_INTERACTIVE};
                    color: {COLOR_TEXT_MUTED};
                    font-size: 13px;
                    font-weight: 700;
                    border-radius: 8px;
                    padding: 8px 18px;
                    border: 1px solid {COLOR_BORDER_STROKE};
                }}
                QPushButton:hover {{
                    background-color: #334155;
                }}
            """)

    def _toggle_power(self):
        self.config.enabled = not self.config.enabled
        self.power_btn.setChecked(self.config.enabled)
        self._update_power_button_style()
        self.config.save()

        if self.config.enabled:
            self._start_engine()
        else:
            self._stop_engine()

    def _start_engine(self):
        self.audio_engine.start()

    def _stop_engine(self):
        self.audio_engine.stop()
        self.gesture_engine.reset()

    def _change_profile(self, profile_name: str):
        if profile_name in self.config.profiles:
            self.config.active_profile = profile_name
            self._update_profile_buttons_style()
            self._refresh_all_bindings()
            self.config.save()

    def _update_profile_buttons_style(self):
        for name, btn in self.profile_buttons.items():
            is_active = (name == self.config.active_profile)
            btn.setChecked(is_active)
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: rgba(56, 189, 248, 0.16);
                        color: {COLOR_CYAN};
                        border: 1px solid {COLOR_CYAN};
                        border-radius: 6px;
                        padding: 6px 14px;
                        font-weight: 700;
                        font-size: 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLOR_SURFACE_MID};
                        color: {COLOR_TEXT_SECONDARY};
                        border: 1px solid {COLOR_BORDER_STROKE};
                        border-radius: 6px;
                        padding: 6px 14px;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLOR_SURFACE_INTERACTIVE};
                        color: {COLOR_TEXT_PRIMARY};
                    }}
                """)

    def _refresh_all_bindings(self):
        profile = self.config.profiles.get(self.config.active_profile, {})

        # 1. Update Macro Pads
        for key, pad in self.macro_pads.items():
            spec = profile.get(key, {})
            pad.set_action_spec(spec)

        # 2. Update Desk Zones
        l_single = profile.get("LEFT_SINGLE", {}).get("label", "None")
        l_double = profile.get("LEFT_DOUBLE", {}).get("label", "None")
        self.left_zone.set_bindings(l_single, l_double)

        r_single = profile.get("RIGHT_SINGLE", {}).get("label", "None")
        r_double = profile.get("RIGHT_DOUBLE", {}).get("label", "None")
        self.right_zone.set_bindings(r_single, r_double)

    def _on_pad_binding_changed(self, gesture_key: str, action_data: dict):
        if self.config.active_profile in self.config.profiles:
            self.config.profiles[self.config.active_profile][gesture_key] = action_data
            self.config.save()
            self._refresh_all_bindings()

    def _update_sensitivity(self, val: int):
        sens = 0.05 - (val / 100.0) * (0.05 - 0.003)
        self.config.sensitivity = sens
        self.sens_val_lbl.setText(f"{sens:.3f}")
        self.audio_engine.update_settings(self.config.sensitivity, self.config.stereo_balance, self.config.min_side_ratio)
        self._update_sensitivity_threshold_view()
        self.config.save()

    def _update_sensitivity_threshold_view(self):
        # Map sensitivity (0.003 - 0.05) to normalized threshold on meter (0.1 - 0.85)
        norm = 0.15 + (self.config.sensitivity / 0.05) * 0.65
        self.laptop_widget.set_threshold(norm)

    def _update_balance(self, val: int):
        bal = val / 50.0
        self.config.stereo_balance = bal
        self.bal_val_lbl.setText(f"{bal:+.2f}")
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

    def _populate_audio_devices(self):
        devices = AudioEngine.get_input_devices()
        self.device_combo.clear()
        self.device_combo.addItem("Auto-Detect Active Microphone", -1)

        best_detected = AudioEngine.auto_detect_active_device()

        for dev in devices:
            label = f"[{dev['index']:2d}] {dev['name']} ({dev['api']}, {dev['channels']} ch)"
            self.device_combo.addItem(label, dev['index'])

        if self.config.audio_device_index != -1:
            idx = self.device_combo.findData(self.config.audio_device_index)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
        elif best_detected != -1:
            idx = self.device_combo.findData(best_detected)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
                self.config.audio_device_index = best_detected

    def _change_device(self, combo_idx: int):
        device_index = self.device_combo.itemData(combo_idx)
        if device_index is not None and device_index != self.config.audio_device_index:
            self.config.audio_device_index = device_index
            self.config.save()
            if self.audio_engine.is_running:
                self.audio_engine.stop()
                self.audio_engine.device_index = device_index if device_index >= 0 else None
                self.audio_engine.start()

    def _update_telemetry(self):
        # Update typing guard live status pill
        if not self.config.typing_guard_enabled:
            self.typing_pill.setText("○ GUARD OFF")
            self.typing_pill.setStyleSheet(f"""
                QLabel {{
                    color: {COLOR_TEXT_MUTED};
                    background-color: rgba(100, 116, 139, 0.12);
                    border: 1px solid rgba(100, 116, 139, 0.3);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-family: 'JetBrains Mono', sans-serif;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
        elif self.typing_guard.is_typing():
            self.typing_pill.setText("⌨ TYPING SUPPRESSED")
            self.typing_pill.setStyleSheet(f"""
                QLabel {{
                    color: {COLOR_AMBER};
                    background-color: rgba(245, 158, 11, 0.16);
                    border: 1px solid rgba(245, 158, 11, 0.45);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-family: 'JetBrains Mono', sans-serif;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
        else:
            self.typing_pill.setText("● GUARD ARMED")
            self.typing_pill.setStyleSheet(f"""
                QLabel {{
                    color: {COLOR_EMERALD};
                    background-color: rgba(16, 185, 129, 0.12);
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-family: 'JetBrains Mono', sans-serif;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)

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
        self.laptop_widget.set_levels(left, right)

    @pyqtSlot(str, float)
    def _handle_gesture_event(self, gesture_name: str, energy: float):
        if not self.config.enabled:
            return

        profile = self.config.profiles.get(self.config.active_profile, {})
        action_spec = profile.get(gesture_name)
        if not action_spec:
            return

        action_label = action_spec.get("label", "Action")

        # 1. Trigger Pulse on Desk Visualizer
        if "LEFT" in gesture_name:
            self.left_zone.trigger_pulse(gesture_name, action_label)
        elif "RIGHT" in gesture_name:
            self.right_zone.trigger_pulse(gesture_name, action_label)

        # 2. Flash Macro Pad
        if gesture_name in self.macro_pads:
            self.macro_pads[gesture_name].trigger_flash()

        # 3. Show On-Screen Floating HUD
        if self.config.hud_enabled:
            self.hud_overlay.show_gesture(gesture_name, action_label, self.config.hud_duration_ms)

        # 4. Dispatch System Action
        self.action_dispatcher.trigger(action_spec)

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
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

    def closeEvent(self, event):
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
