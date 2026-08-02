"""转码面板：曲目转码状态表 + 后台线程转码。"""

from __future__ import annotations

import os

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...models import Project, Track
from ...services.transcoder import TranscodeParams, TranscodeError, transcode
from ...utils.path_utils import app_root

STATE_PENDING = "待转码"
STATE_RUNNING = "转码中..."
STATE_DONE = "完成"
STATE_ERROR = "失败"
STATE_SKIP = "复制(合规)"


class TranscodeWorker(QThread):
    """后台顺序转码任务。jobs: [(track, output_path, params)]"""

    progress = Signal(str, float)                 # track_id, ratio
    finished_one = Signal(str, bool, str)         # track_id, ok, error
    all_done = Signal(int, int)                   # ok_count, total

    def __init__(self, jobs: list[tuple[Track, str, TranscodeParams]], parent=None):
        super().__init__(parent)
        self._jobs = jobs

    def run(self) -> None:
        ok = 0
        for track, output_path, params in self._jobs:
            try:
                transcode(track, output_path, params,
                          progress_cb=lambda r, tid=track.track_id: self.progress.emit(tid, r))
                ok += 1
                self.finished_one.emit(track.track_id, True, "")
            except Exception as exc:  # noqa: BLE001
                self.finished_one.emit(track.track_id, False, str(exc))
        self.all_done.emit(ok, len(self._jobs))


class TranscodePanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._project: Project | None = None
        self._worker: TranscodeWorker | None = None
        self._row_of: dict[str, int] = {}   # track_id → 行号

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # 输出目录
        dir_row = QHBoxLayout()
        self.ed_output = QLineEdit()
        self.ed_output.setPlaceholderText("输出目录（默认: output/<模组名>/）")
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self._pick_dir)
        dir_row.addWidget(self.ed_output, stretch=1)
        dir_row.addWidget(self.btn_browse)
        layout.addLayout(dir_row)

        # 状态表
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["曲目", "专辑", "比特率", "状态", "进度"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.table, stretch=1)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.btn_all = QPushButton("全部转码")
        self.btn_selected = QPushButton("转码选中")
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_all.clicked.connect(lambda: self._start(None))
        self.btn_selected.clicked.connect(self._start_selected)
        self.btn_stop.clicked.connect(self._stop)
        btn_row.addWidget(self.btn_all)
        btn_row.addWidget(self.btn_selected)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_stop)
        layout.addLayout(btn_row)

    # ---- 数据绑定 ----

    def set_project(self, project: Project) -> None:
        self._project = project
        self._rebuild()

    def _rebuild(self) -> None:
        if self._project is None:
            return
        if self._worker is not None and self._worker.isRunning():
            return  # 转码进行中不重建
        self._row_of.clear()
        tracks = list(self._project.tracks.values())
        self.table.setRowCount(len(tracks))
        for row, t in enumerate(tracks):
            self._row_of[t.track_id] = row
            album = self._project.album_of(t)
            album_name = album.display_name_zh or album.name if album else "通用"
            bitrate = t.target_bitrate or (album.target_bitrate if album else 128)
            self.table.setItem(row, 0, QTableWidgetItem(t.ogg_filename))
            self.table.setItem(row, 1, QTableWidgetItem(album_name))
            self.table.setItem(row, 2, QTableWidgetItem(f"{bitrate} kbps"))
            self.table.setItem(row, 3, QTableWidgetItem(self._status_text(t)))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(100 if t.transcode_status == "done" else 0)
            self.table.setCellWidget(row, 4, bar)

    @staticmethod
    def _status_text(t: Track) -> str:
        if t.transcode_status == "done":
            return STATE_DONE
        if t.transcode_status == "error":
            return t.transcode_error or STATE_ERROR
        return STATE_PENDING

    # ---- 转码执行 ----

    def _pick_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.ed_output.setText(folder)

    def _output_dir(self) -> str:
        if self.ed_output.text().strip():
            return self.ed_output.text().strip()
        return os.path.join(app_root(), "output", self._project.mod_name or "music_pack")

    def _album_folder(self, t: Track) -> str:
        album = self._project.album_of(t)
        return album.name if album else "music"

    def _start(self, track_ids: list[str] | None) -> None:
        if self._project is None or self._worker is not None and self._worker.isRunning():
            return
        if track_ids is None:
            tracks = list(self._project.tracks.values())
        else:
            tracks = [self._project.tracks[i] for i in track_ids if i in self._project.tracks]
        if not tracks:
            return
        output_dir = self._output_dir()
        jobs = []
        for t in tracks:
            album = self._project.album_of(t)
            bitrate = t.target_bitrate or (album.target_bitrate if album else 128)
            out = os.path.join(output_dir, self._album_folder(t), t.ogg_filename)
            jobs.append((t, out, TranscodeParams(bitrate_kbps=bitrate)))

        self._worker = TranscodeWorker(jobs, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_one.connect(self._on_finished_one)
        self._worker.all_done.connect(self._on_all_done)
        for t, _out, _p in jobs:
            row = self._row_of.get(t.track_id)
            if row is not None:
                self.table.item(row, 3).setText(STATE_RUNNING)
        self.btn_all.setEnabled(False)
        self.btn_selected.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._worker.start()

    def _start_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        tracks = list(self._project.tracks.values())
        self._start([tracks[r].track_id for r in rows if r < len(tracks)])

    def _stop(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
            self._on_all_done(0, 0)

    def _on_progress(self, track_id: str, ratio: float) -> None:
        row = self._row_of.get(track_id)
        if row is not None:
            bar = self.table.cellWidget(row, 4)
            if isinstance(bar, QProgressBar):
                bar.setValue(int(ratio * 100))

    def _on_finished_one(self, track_id: str, ok: bool, error: str) -> None:
        row = self._row_of.get(track_id)
        if row is None:
            return
        t = self._project.tracks.get(track_id)
        if t is not None:
            t.transcode_status = "done" if ok else "error"
            t.transcode_error = error
            if ok:
                t.transcode_status = "done"
            self._project.mark_dirty()
            self._main._update_title()
        self.table.item(row, 3).setText(STATE_DONE if ok else (error or STATE_ERROR))
        bar = self.table.cellWidget(row, 4)
        if isinstance(bar, QProgressBar):
            bar.setValue(100 if ok else 0)

    def _on_all_done(self, ok: int, total: int) -> None:
        self.btn_all.setEnabled(True)
        self.btn_selected.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if total:
            msg = f"转码完成：成功 {ok} / {total}"
            if ok < total:
                QMessageBox.warning(self, "转码完成", msg + "\n失败项请查看状态列。")
            else:
                self._main.statusBar().showMessage(msg, 3000)
