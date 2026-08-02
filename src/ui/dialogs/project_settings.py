"""项目设置对话框：编辑模组身份与命名属性。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout,
)

from ...models import Project
from ...utils.constants import DEFAULT_CLASS_PREFIX, DEFAULT_SOUND_PREFIX
from ...utils.validators import is_valid_cfg_class


class ProjectSettingsDialog(QDialog):
    """编辑当前项目的身份/命名字段（直接修改传入的 Project 对象）。"""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("项目设置")
        self.setMinimumWidth(420)
        self._project = project

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.ed_mod_name = QLineEdit(project.mod_name)
        self.ed_display_name = QLineEdit(project.display_name)
        self.ed_author = QLineEdit(project.author)
        self.ed_required_version = QLineEdit(project.required_version)
        self.ed_required_addons = QLineEdit(", ".join(project.required_addons))
        self.ed_sound_prefix = QLineEdit(project.sound_prefix or DEFAULT_SOUND_PREFIX)
        self.ed_class_prefix = QLineEdit(project.class_prefix or DEFAULT_CLASS_PREFIX)
        self.ed_generic_class = QLineEdit(project.generic_music_class)
        self.ed_generic_display = QLineEdit(project.generic_music_display)

        form.addRow("模组类名（根目录名）:", self.ed_mod_name)
        form.addRow("模组显示名:", self.ed_display_name)
        form.addRow("作者:", self.ed_author)
        form.addRow("requiredVersion:", self.ed_required_version)
        form.addRow("requiredAddons（逗号分隔）:", self.ed_required_addons)
        form.addRow("sound[] 路径前缀:", self.ed_sound_prefix)
        form.addRow("类名前缀:", self.ed_class_prefix)
        form.addRow("通用曲目类名:", self.ed_generic_class)
        form.addRow("通用曲目显示名:", self.ed_generic_display)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not is_valid_cfg_class(self.ed_mod_name.text().strip()):
            self.ed_mod_name.setFocus()
            self.ed_mod_name.selectAll()
            return
        if not is_valid_cfg_class(self.ed_generic_class.text().strip()):
            self.ed_generic_class.setFocus()
            self.ed_generic_class.selectAll()
            return
        if not self.ed_sound_prefix.text().strip():
            self.ed_sound_prefix.setFocus()
            return
        self.apply()
        self.accept()

    def apply(self) -> None:
        """将对话框字段写回项目对象（调用方负责 mark_dirty / 刷新）。"""
        p = self._project
        p.mod_name = self.ed_mod_name.text().strip()
        p.display_name = self.ed_display_name.text().strip()
        p.author = self.ed_author.text().strip()
        p.required_version = self.ed_required_version.text().strip()
        p.required_addons = [s.strip() for s in self.ed_required_addons.text().split(",") if s.strip()]
        p.sound_prefix = self.ed_sound_prefix.text().strip() or DEFAULT_SOUND_PREFIX
        p.class_prefix = self.ed_class_prefix.text().strip() or DEFAULT_CLASS_PREFIX
        p.generic_music_class = self.ed_generic_class.text().strip()
        p.generic_music_display = self.ed_generic_display.text().strip()
