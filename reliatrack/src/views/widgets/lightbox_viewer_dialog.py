"""图片/文档内置轻量画廊预览器 (Lightbox Viewer Dialog)。"""
from __future__ import annotations

import os
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPixmap, QTransform, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QApplication,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY


class LightboxViewerDialog(QDialog):
    """毛玻璃高阶图片/文档浮动预览画廊。"""

    def __init__(self, file_path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._file_path = file_path
        self._scale = 1.0
        self._rotation = 0
        self._pixmap: QPixmap | None = None
        self._setup_ui()
        self._load_media()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(750, 550)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        self._container = QFrame()
        self._container.setObjectName("lightbox-container")
        self._container.setStyleSheet(
            f"QFrame#lightbox-container {{"
            f"  background: {_theme.BASE};"
            f"  border: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 12px;"
            f"}}"
        )
        add_shadow(self._container)

        clay = QVBoxLayout(self._container)
        clay.setContentsMargins(16, 12, 16, 12)
        clay.setSpacing(10)

        # 头部标题栏 + 工具箱
        header = QHBoxLayout()
        header.setSpacing(8)

        fname = os.path.basename(self._file_path)
        self._title_lbl = QLabel(f"🖼️ {fname}")
        self._title_lbl.setStyleSheet(f"color: {_theme.TEXT}; font-size: 14px; font-weight: bold;")
        header.addWidget(self._title_lbl)

        header.addStretch()

        # 放大/缩小/旋转/复制按钮
        btn_in = QPushButton("🔍 放大", self)
        btn_out = QPushButton("🔍 缩小", self)
        btn_rot = QPushButton("🔄 旋转", self)
        btn_copy = QPushButton("📋 复制图片", self)
        btn_close = QPushButton("✖ 关闭", self)

        for b in (btn_in, btn_out, btn_rot, btn_copy, btn_close):
            b.setProperty("class", "btn-secondary")
            b.setStyleSheet(
                f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; "
                f"border-radius: 6px; padding: 4px 10px; font-size: 12px;"
            )
            header.addWidget(b)

        btn_in.clicked.connect(self._zoom_in)
        btn_out.clicked.connect(self._zoom_out)
        btn_rot.clicked.connect(self._rotate)
        btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_close.clicked.connect(self.accept)

        clay.addLayout(header)

        # 主内容区域
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background: transparent; border: none;")

        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setStyleSheet("background: transparent;")
        self._scroll.setWidget(self._img_label)

        clay.addWidget(self._scroll, 1)

        root.addWidget(self._container)

    def _load_media(self) -> None:
        if not os.path.exists(self._file_path):
            self._img_label.setText(f"❌ 文件不存在: {self._file_path}")
            self._img_label.setStyleSheet(f"color: {_theme.DANGER}; font-size: 14px;")
            return

        ext = os.path.splitext(self._file_path)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".svg", ".gif"):
            pix = QPixmap(self._file_path)
            if not pix.isNull():
                self._pixmap = pix
                self._update_transform()
            else:
                self._img_label.setText("⚠️ 无法解析该图片")
        else:
            # 文本或其它文档轻量预览
            try:
                with open(self._file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(4000)
                self._img_label.setText(content)
                self._img_label.setWordWrap(True)
                self._img_label.setStyleSheet(f"color: {_theme.TEXT}; font-size: 12px; font-family: monospace;")
            except Exception as e:
                self._img_label.setText(f"📄 附件文档: {os.path.basename(self._file_path)}\n({e})")

    def _update_transform(self) -> None:
        if not self._pixmap:
            return
        transform = QTransform()
        transform.rotate(self._rotation)
        transformed = self._pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        sw = int(transformed.width() * self._scale)
        sh = int(transformed.height() * self._scale)
        scaled = transformed.scaled(
            max(sw, 50), max(sh, 50),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._img_label.setPixmap(scaled)

    def _zoom_in(self) -> None:
        self._scale = min(self._scale * 1.25, 4.0)
        self._update_transform()

    def _zoom_out(self) -> None:
        self._scale = max(self._scale / 1.25, 0.25)
        self._update_transform()

    def _rotate(self) -> None:
        self._rotation = (self._rotation + 90) % 360
        self._update_transform()

    def _copy_to_clipboard(self) -> None:
        if self._pixmap and not self._pixmap.isNull():
            QApplication.clipboard().setPixmap(self._pixmap)
            self._title_lbl.setText(f"✅ 已复制图片到剪贴板！")

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)

    def show_centered(self) -> None:
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, max(y, 80))
        self.exec()
