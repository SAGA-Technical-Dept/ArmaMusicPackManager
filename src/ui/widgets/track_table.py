"""曲目表格：QTableView + 自定义数据模型。"""

from __future__ import annotations

import json

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QTableView

from ...models import Album, Project, Track

MIME_TRACK_IDS = "application/x-track-ids"


class TrackTableModel(QAbstractTableModel):
    """以 project.tracks 为数据源的表格模型。

    显示列：序号 / 文件名 / 中文名 / 时长 / 格式 / 采样率 / 专辑 / 转码状态
    """

    COLUMNS = ["#", "文件名", "中文名", "时长", "格式", "采样率", "专辑", "状态"]

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project
        self._tracks: list[Track] = []

    # ---- 视图管理 ----

    def set_tracks(self, tracks: list[Track]) -> None:
        """设置当前显示的曲目列表（排序/过滤后）。"""
        self.beginResetModel()
        self._tracks = list(tracks)
        self.endResetModel()

    def track_at(self, row: int) -> Track | None:
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def tracks_of_rows(self, rows: list[int]) -> list[Track]:
        return [self._tracks[r] for r in rows if 0 <= r < len(self._tracks)]

    # ---- QAbstractTableModel 接口 ----

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._tracks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        track = self._tracks[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(track, col)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(track, col)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def _display_value(self, t: Track, col: int) -> str:
        if col == 0:
            return str(t.track_index or "")
        if col == 1:
            return t.ogg_filename
        if col == 2:
            return t.display_name_zh
        if col == 3:
            m, s = divmod(round(t.duration), 60)
            return f"{m}:{s:02d}" if t.duration else ""
        if col == 4:
            return t.source_codec
        if col == 5:
            return str(t.sample_rate) if t.sample_rate else ""
        if col == 6:
            return self._album_name(t)
        if col == 7:
            return t.transcode_status
        return ""

    def _album_name(self, t: Track) -> str:
        album = self._project.album_of(t)
        return album.display_name_zh if album else "通用"

    def _tooltip(self, t: Track, col: int) -> str:
        if col == 1:
            return t.source_path
        if col == 7 and t.transcode_error:
            return t.transcode_error
        return self._display_value(t, col)

    # ---- 拖拽支持（曲目 → 专辑面板） ----

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if index.isValid():
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        return flags

    def mimeTypes(self) -> list[str]:
        return [MIME_TRACK_IDS]

    def mimeData(self, indexes) -> object:
        """以 JSON 数组携带选中曲目的 track_id 列表。"""
        from PySide6.QtCore import QMimeData
        ids = []
        for idx in indexes:
            if idx.isValid() and idx.column() == 0:
                t = self._tracks[idx.row()]
                if t is not None:
                    ids.append(t.track_id)
        if not ids:
            return None
        mime = QMimeData()
        mime.setData(MIME_TRACK_IDS, json.dumps(ids).encode("utf-8"))
        return mime


class TrackTableView(QTableView):
    """曲目表格视图：单选/多选 + 列自适应。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)  # 由外部排序，避免 model 索引错乱
        self.setDragEnabled(True)
        self.setDragDropMode(QTableView.DragDropMode.DragOnly)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
