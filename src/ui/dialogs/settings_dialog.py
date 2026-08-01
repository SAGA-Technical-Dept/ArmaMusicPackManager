"""新建项目对话框：配置模组身份。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout,
)

from ...models import Project
from ...utils.constants import DEFAULT_CLASS_PREFIX, DEFAULT_SOUND_PREFIX
from ...utils.validators import is_valid_cfg_class


class NewProjectDialog(QDialog):
    """从模板项目复制身份字段，让用户修改后生成新项目。"""

    def __init__(self, template: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建项目")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.ed_mod_name = QLineEdit(template.mod_name)
        self.ed_display_name = QLineEdit(template.display_name)
        self.ed_author = QLineEdit(template.author)
        self.ed_sound_prefix = QLineEdit(template.sound_prefix or DEFAULT_SOUND_PREFIX)
        self.ed_class_prefix = QLineEdit(template.class_prefix or DEFAULT_CLASS_PREFIX)

        form.addRow("模组类名（根目录名）:", self.ed_mod_name)
        form.addRow("模组显示名:", self.ed_display_name)
        form.addRow("作者:", self.ed_author)
        form.addRow("sound[] 路径前缀:", self.ed_sound_prefix)
        form.addRow("类名前缀:", self.ed_class_prefix)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not is_valid_cfg_class(self.ed_mod_name.text()):
            self.ed_mod_name.setFocus()
            self.ed_mod_name.selectAll()
            self.ed_mod_name.setToolTip("必须是合法 config 类名（字母/下划线开头）")
            return
        self.accept()

    def result_project(self) -> Project:
        return Project(
            mod_name=self.ed_mod_name.text().strip(),
            display_name=self.ed_display_name.text().strip(),
            author=self.ed_author.text().strip(),
            sound_prefix=self.ed_sound_prefix.text().strip() or DEFAULT_SOUND_PREFIX,
            class_prefix=self.ed_class_prefix.text().strip() or DEFAULT_CLASS_PREFIX,
        )
