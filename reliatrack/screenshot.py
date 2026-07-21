#!/usr/bin/env python3
"""Offscreen 截图 — 启动 ReliaTrack 并截取主窗口。"""

import os, sys, warnings
warnings.filterwarnings("ignore")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from src.controllers import AppController
from main import MainWindow

app = QApplication(sys.argv)
ctrl = AppController("")
ctrl.initialize()
window = MainWindow(ctrl)
window.resize(1280, 800)
window.show()

def snap():
    pix = window.grab()
    path = os.path.expanduser("~/Desktop/reliatrack_screenshot.png")
    pix.save(path)
    print(f"OK: {pix.width()}x{pix.height()} -> {path}")
    app.quit()

QTimer.singleShot(2000, snap)
app.exec()
