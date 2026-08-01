"""Config 预览面板：生成/查看/导出 config.cpp。"""

from __future__ import annotations

import os

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from ...models import Project
from ...services.config_generator import generate_config


class ConfigPanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._project: Project | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setPlaceholderText("点击 [重新生成] 预览 config.cpp")
        layout.addWidget(self.editor, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_regenerate = QPushButton("重新生成")
        self.btn_copy = QPushButton("复制到剪贴板")
        self.btn_export = QPushButton("导出到 output/")
        self.btn_regenerate.clicked.connect(self.regenerate)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        self.btn_export.clicked.connect(self.export)
        btn_row.addWidget(self.btn_regenerate)
        btn_row.addWidget(self.btn_copy)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    # ---- 数据绑定 ----

    def set_project(self, project: Project) -> None:
        self._project = project
        if project and project.tracks:
            self.regenerate()

    # ---- 操作 ----

    def regenerate(self) -> None:
        if self._project is None:
            return
        self.editor.setPlainText(generate_config(self._project))

    def copy_to_clipboard(self) -> None:
        text = self.editor.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._main.statusBar().showMessage("config.cpp 已复制到剪贴板", 2000)

    def export(self) -> None:
        if self._project is None:
            return
        text = self.editor.toPlainText()
        if not text:
            self.regenerate()
            text = self.editor.toPlainText()
        mod_dir = os.path.join(self._output_root(), self._project.mod_name or "music_pack")
        os.makedirs(mod_dir, exist_ok=True)
        dest = os.path.join(mod_dir, "config.cpp")
        with open(dest, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        self._main.statusBar().showMessage(f"已导出 {dest}", 3000)

    def _output_root(self) -> str:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(root, "output")
