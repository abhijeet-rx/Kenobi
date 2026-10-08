import sys
import os
import ctypes

# Ensure current directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.config import AppConfig
from src.gui import MainWindow

def main():
    # Enable High DPI scaling on Windows
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Kenobi")
    app.setOrganizationName("Kenobi")
    
    # Don't exit when main window is closed (minimize to tray support)
    app.setQuitOnLastWindowClosed(False)

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
