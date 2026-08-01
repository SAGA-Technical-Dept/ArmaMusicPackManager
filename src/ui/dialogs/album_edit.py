"""专辑编辑对话框：新建/编辑专辑。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout,
)

from ...models import Album
from ...utils.constants import BITRATE_OPTIONS, DEFAULT_ALBUM_PREFIX_MAP
from ...utils.validators import is_valid_cfg_class


class AlbumEditDialog(QDialog):
    def __init__(self, album: Album | None = None, is_new: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建专辑" if is_new else "编辑专辑")
        self.setMinimumWidth(400)
        self._album = album

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.ed_name = QLineEdit(album.name if album else "")
        self.ed_display = QLineEdit(album.display_name_zh if album else "")
        self.ed_cfg_class = QLineEdit(album.cfg_class if album else "")
        self.ed_prefix = QLineEdit(album.class_prefix if album else "")
        self.cb_bitrate = QComboBox()
        self.cb_bitrate.addItems([str(b) for b in BITRATE_OPTIONS])
        current = (album.target_bitrate if album else 128)
        if current in BITRATE_OPTIONS:
            self.cb_bitrate.setCurrentText(str(current))
        else:
            self.cb_bitrate.addItem(str(current))

        form.addRow("内部名（子目录名）:", self.ed_name)
        form.addRow("显示名（displayname）:", self.ed_display)
        form.addRow("CfgMusicClasses 类名:", self.ed_cfg_class)
        form.addRow("曲目类名前缀:", self.ed_prefix)
        form.addRow("目标比特率 (kbps):", self.cb_bitrate)
        layout.addLayout(form)

        hint = QFormLayout()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.ed_name.text().strip():
            self.ed_name.setFocus()
            return
        if not self.ed_cfg_class.text().strip() or not is_valid_cfg_class(self.ed_cfg_class.text().strip()):
            self.ed_cfg_class.setFocus()
            self.ed_cfg_class.selectAll()
            return
        self.accept()

    def result_album(self) -> Album:
        """返回编辑后的 Album（编辑模式返回原对象，新建模式返回新对象）。"""
        bitrate = int(self.cb_bitrate.currentText())
        if self._album is not None:
            album = self._album
        else:
            album = Album(album_id="")
        album.name = self.ed_name.text().strip()
        album.display_name_zh = self.ed_display.text().strip()
        album.cfg_class = self.ed_cfg_class.text().strip()
        album.class_prefix = self.ed_prefix.text().strip() or self._auto_prefix(album.name)
        album.target_bitrate = bitrate
        return album

    @staticmethod
    def _auto_prefix(name: str) -> str:
        """从专辑内部名推导类名前缀（参考范例的映射）。"""
        if name in DEFAULT_ALBUM_PREFIX_MAP:
            return DEFAULT_ALBUM_PREFIX_MAP[name]
        return name.replace("_", "")[:8] or "Album"
