from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtGui import QFont, QColor

class HUDOverlay(QWidget):
    """
    Subtle floating on-screen translucent overlay (HUD)
    showing recognized desk taps and triggered actions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Main Layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(20, 12, 20, 12)
        self.layout.setSpacing(14)

        # Icon Label
        self.icon_label = QLabel("⚡", self)
        self.icon_label.setStyleSheet("color: #38bdf8; font-size: 20px; font-weight: bold;")
        self.layout.addWidget(self.icon_label)

        # Text Label
        self.text_label = QLabel("Kenobi Active", self)
        self.text_label.setStyleSheet("color: #f1f5f9; font-size: 14px; font-weight: 600;")
        self.layout.addWidget(self.text_label)

        # Container styling
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 23, 42, 0.88);
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 20px;
            }
        """)

        # Opacity effect for animations
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        # Animation
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(220)

        # Auto-dismiss timer
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._fade_out)

    def show_gesture(self, gesture_name: str, action_label: str, duration_ms: int = 1200):
        # Choose icon & directional styling
        icons = {
            "LEFT_SINGLE": "◀  Left Tap",
            "RIGHT_SINGLE": "Right Tap  ▶",
            "LEFT_DOUBLE": "◀◀ Left Double-Tap",
            "RIGHT_DOUBLE": "Right Double-Tap ▶▶",
        }
        icon_display = icons.get(gesture_name, "⚡ Desk Tap")
        
        self.icon_label.setText(icon_display)
        self.text_label.setText(action_label)
        self.adjustSize()

        # Position at bottom-center of the primary screen
        screen = self.screen()
        if screen:
            screen_geo = screen.geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = screen_geo.height() - self.height() - 90  # 90px above bottom
            self.move(x, y)

        self.show()
        
        # Fade in
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()

        # Reset hide timer
        self.hide_timer.start(duration_ms)

    def _fade_out(self):
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.finished.connect(self._on_fade_finished)
        self.anim.start()

    def _on_fade_finished(self):
        if self.opacity_effect.opacity() == 0.0:
            self.hide()
            try:
                self.anim.finished.disconnect(self._on_fade_finished)
            except Exception:
                pass
