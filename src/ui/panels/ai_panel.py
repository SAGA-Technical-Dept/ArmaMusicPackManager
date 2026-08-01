"""AI 翻译面板：API 配置 + 批量翻译 + 结果预览应用。"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...models import Project
from ...services.ai_translator import (
    DEFAULT_BASE_URL, DEFAULT_MODEL, TranslationError, translate_names,
)
from ...utils.path_utils import sanitize_filename

STATE_UNT = "待翻译"
STATE_OK = "已翻译"
STATE_ERR = "失败"


class TranslateWorker(QThread):
    """后台翻译任务：names → {原: 译}。"""

    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, names: list[str], base_url: str, api_key: str, model: str, parent=None):
        super().__init__(parent)
        self._names = names
        self._base_url = base_url
        self._api_key = api_key
        self._model = model

    def run(self) -> None:
        try:
            result = translate_names(self._names, self._base_url, self._api_key, self._model)
            self.finished_ok.emit(result)
        except TranslationError as exc:
            self.failed.emit(str(exc))


class AITranslatePanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._project: Project | None = None
        self._worker: TranslateWorker | None = None
        self._row_of: dict[str, int] = {}   # track_id → 行号
        self._settings = QSettings("ArmaMusicPackManager", "ai_translate")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # API 配置
        cfg_row = QHBoxLayout()
        self.ed_base = QLineEdit(self._settings.value("base_url", DEFAULT_BASE_URL, str))
        self.ed_base.setPlaceholderText("API Base URL")
        self.ed_key = QLineEdit(self._settings.value("api_key", "", str))
        self.ed_key.setPlaceholderText("API Key")
        self.ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_model = QLineEdit(self._settings.value("model", DEFAULT_MODEL, str))
        self.ed_model.setPlaceholderText("模型名")
        cfg_row.addWidget(self.ed_base, stretch=3)
        cfg_row.addWidget(self.ed_key, stretch=3)
        cfg_row.addWidget(self.ed_model, stretch=2)
        layout.addLayout(cfg_row)

        # 曲目翻译表（英文文件名列可编辑）
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["曲目", "中文名", "英文翻译(文件名,可编辑)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.table, stretch=1)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.btn_translate_all = QPushButton("翻译全部")
        self.btn_translate_sel = QPushButton("翻译选中")
        self.btn_apply = QPushButton("应用翻译")
        self.btn_translate_all.clicked.connect(lambda: self._start(None))
        self.btn_translate_sel.clicked.connect(self._start_selected)
        self.btn_apply.clicked.connect(self._apply)
        btn_row.addWidget(self.btn_translate_all)
        btn_row.addWidget(self.btn_translate_sel)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_apply)
        layout.addLayout(btn_row)

    # ---- 数据绑定 ----

    def set_project(self, project: Project) -> None:
        self._project = project
        self._rebuild()

    def _rebuild(self) -> None:
        if self._project is None or self._worker is not None and self._worker.isRunning():
            return
        self._row_of.clear()
        tracks = list(self._project.tracks.values())
        self.table.setRowCount(len(tracks))
        for row, t in enumerate(tracks):
            self._row_of[t.track_id] = row
            self.table.setItem(row, 0, QTableWidgetItem(t.ogg_filename))
            # 中文名列：无中文名时回退英文名
            self.table.setItem(row, 1, QTableWidgetItem(t.display_name_zh or t.display_name_en))
            en = QTableWidgetItem(t.display_name_en)
            en.setFlags(en.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, en)

    # ---- 翻译执行 ----

    def _start(self, track_ids: list[str] | None) -> None:
        if self._project is None or self._worker is not None and self._worker.isRunning():
            return
        if track_ids is None:
            tracks = list(self._project.tracks.values())
        else:
            tracks = [self._project.tracks[i] for i in track_ids if i in self._project.tracks]
        if not tracks:
            return
        # 翻译源：中文名（无则回退英文名）
        names = [t.display_name_zh or t.display_name_en or t.ogg_filename for t in tracks]
        self._save_config()
        self._worker = TranslateWorker(
            names, self.ed_base.text().strip(), self.ed_key.text().strip(),
            self.ed_model.text().strip() or DEFAULT_MODEL, self)
        self._worker.finished_ok.connect(self._on_result)
        self._worker.failed.connect(self._on_error)
        for t in tracks:
            row = self._row_of.get(t.track_id)
            if row is not None:
                pass  # 状态由结果回调更新
        self.btn_translate_all.setEnabled(False)
        self.btn_translate_sel.setEnabled(False)
        self._worker.start()

    def _start_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        tracks = list(self._project.tracks.values())
        self._start([tracks[r].track_id for r in rows if r < len(tracks)])

    def _save_config(self) -> None:
        self._settings.setValue("base_url", self.ed_base.text().strip())
        self._settings.setValue("api_key", self.ed_key.text().strip())
        self._settings.setValue("model", self.ed_model.text().strip())

    def _on_result(self, result: dict[str, str]) -> None:
        self.btn_translate_all.setEnabled(True)
        self.btn_translate_sel.setEnabled(True)
        tracks = list(self._project.tracks.values())
        applied = 0
        for t in tracks:
            src = t.display_name_zh or t.display_name_en or t.ogg_filename
            en = result.get(src)
            if en:
                en = sanitize_filename(en, replace_spaces=True)  # 兜底：空格→下划线
                row = self._row_of.get(t.track_id)
                if row is not None:
                    self.table.item(row, 2).setText(en)
                applied += 1
        self._main.statusBar().showMessage(
            f"翻译完成：{applied}/{len(result)} 首获得翻译，可手动修改后应用", 4000)

    def _on_error(self, message: str) -> None:
        self.btn_translate_all.setEnabled(True)
        self.btn_translate_sel.setEnabled(True)
        QMessageBox.warning(self, "翻译失败", message)

    # ---- 应用翻译 ----

    def _apply(self) -> None:
        if self._project is None:
            return
        tracks = list(self._project.tracks.values())
        count = 0
        transcoded = 0
        for row, t in enumerate(tracks):
            en = self.table.item(row, 2).text().strip()
            if not en:
                continue
            en = sanitize_filename(en, replace_spaces=True)  # 空格/非法字符 → 下划线
            if not en:
                continue
            t.display_name_en = en
            t.ogg_filename = f"{en}.ogg"
            if t.transcode_status == "done":
                transcoded += 1
            count += 1
        if count:
            self._project.mark_dirty()
            self._main._update_title()
        self._main.refresh_all()
        msg = f"已应用 {count} 首曲目的英文文件名"
        if transcoded:
            msg += f"\n其中 {transcoded} 首已转码：输出目录中的 .ogg 文件名不会自动重命名，请重新转码以匹配新文件名"
            QMessageBox.information(self, "应用翻译", msg)
        else:
            self._main.statusBar().showMessage(msg, 3000)
