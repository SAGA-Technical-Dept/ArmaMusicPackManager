"""导入对话框：拖放 + 文件/文件夹选择，确认后创建 Track。"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ...services import audio_importer
from ...services.audio_reader import fill_metadata
from ...utils.constants import SUPPORTED_AUDIO_EXTS
from ...utils.path_utils import stem_without_ext


class DropZone(QLabel):
    """接受文件拖放的区域。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "QLabel { border: 2px dashed #5a5a5a; border-radius: 6px;"
            " color: #888; font-size: 13px; }"
            "QLabel[dragOver=true] { border-color: #4daafc; color: #4daafc; }"
        )
        self.setText("拖放音频文件/文件夹到此处\n(.wav .mp3 .flac .aac .m4a .ogg .wma)")
        self._paths: list[str] = []

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragOver", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):
        self.setProperty("dragOver", False)
        urls = event.mimeData().urls()
        dropped = [u.toLocalFile() for u in urls if u.isLocalFile()]
        self._paths.extend(audio_importer.scan_paths(dropped))
        self._emit_changed()

    def add_paths(self, paths: list[str]) -> None:
        self._paths.extend(audio_importer.scan_paths(paths))
        self._emit_changed()

    def _emit_changed(self):
        """通知父对话框路径集合已变化（通过 QListWidget 更新）。"""
        parent = self.parent()
        if parent is not None and hasattr(parent, "refresh_file_list"):
            parent.refresh_file_list()

    def paths(self) -> list[str]:
        return list(dict.fromkeys(self._paths))  # 去重保序


class ImportDialog(QDialog):
    """导入流程：文件收集 → 预览 → 确认导入。"""

    def __init__(self, existing_paths: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("导入音频")
        self.resize(560, 420)
        self._existing = {os.path.normcase(p) for p in existing_paths}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.drop_zone = DropZone(self)
        layout.addWidget(self.drop_zone)

        btn_row = QHBoxLayout()
        self.btn_files = QPushButton("选择文件...")
        self.btn_folder = QPushButton("选择文件夹...")
        self.btn_files.clicked.connect(self._pick_files)
        self.btn_folder.clicked.connect(self._pick_folder)
        btn_row.addWidget(self.btn_files)
        btn_row.addWidget(self.btn_folder)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        layout.addWidget(QLabel("待导入文件（双击条目可从列表移除）："))
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self._remove_item)
        layout.addWidget(self.file_list, stretch=1)

        self.hint = QLabel("")
        self.hint.setStyleSheet("color: #c77;")
        layout.addWidget(self.hint)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.btn_cancel = QPushButton("取消")
        self.btn_import = QPushButton("导入")
        self.btn_import.setDefault(True)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_import.clicked.connect(self._do_import)
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_import)
        layout.addLayout(action_row)

    # ---- 文件收集 ----

    def _pick_files(self) -> None:
        pattern = "音频文件 (*" + " *".join(sorted(SUPPORTED_AUDIO_EXTS)) + ");;所有文件 (*)"
        files, _ = QFileDialog.getOpenFileNames(self, "选择音频文件", "", pattern)
        if files:
            self.drop_zone.add_paths(files)

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.drop_zone.add_paths([folder])

    def refresh_file_list(self) -> None:
        self.file_list.clear()
        for p in self.drop_zone.paths():
            QListWidgetItem(p, self.file_list)

    def _remove_item(self, item: QListWidgetItem) -> None:
        path = item.text()
        self.drop_zone._paths.remove(path)
        self.refresh_file_list()

    # ---- 导入 ----

    def _do_import(self) -> None:
        paths = self.drop_zone.paths()
        if not paths:
            self.hint.setText("没有可导入的文件")
            return
        existing = set(self._existing)
        tracks = audio_importer.create_tracks(paths, existing)
        if not tracks:
            self.hint.setText("所选文件均已导入过")
            return
        # 同步读取元数据（小型列表可接受；大量文件后续可后台化）
        for t in tracks:
            fill_metadata(t)
        self._imported = tracks
        self.accept()

    def imported_tracks(self) -> list:
        return getattr(self, "_imported", [])
