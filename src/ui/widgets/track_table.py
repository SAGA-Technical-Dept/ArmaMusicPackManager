"""曲目表格：QTableView + 自定义数据模型 + 专辑内联编辑器。"""

from __future__ import annotations

import json
from collections.abc import Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox, QStyledItemDelegate, QTableView, QWidget,
)

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
        self._sort_column: int | None = None   # 用户选择的排序（过滤/刷新后重放）
        self._sort_order = Qt.SortOrder.AscendingOrder

    # ---- 视图管理 ----

    def set_tracks(self, tracks: list[Track]) -> None:
        """设置当前显示的曲目列表（过滤后），并重放用户排序。"""
        self.beginResetModel()
        self._tracks = list(tracks)
        self.endResetModel()
        if self._sort_column is not None:
            self.sort(self._sort_column, self._sort_order)

    def track_at(self, row: int) -> Track | None:
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def tracks_of_rows(self, rows: list[int]) -> list[Track]:
        return [self._tracks[r] for r in rows if 0 <= r < len(self._tracks)]

    # ---- 排序 ----

    def sort(self, column: int, order=Qt.SortOrder.AscendingOrder) -> None:
        """点击列头排序：数字列按数值，其余按显示文本（不区分大小写）。"""
        self._sort_column = column
        self._sort_order = order
        self.layoutAboutToBeChanged.emit()
        self._tracks.sort(
            key=lambda t: self._sort_key(t, column),
            reverse=(order == Qt.SortOrder.DescendingOrder),
        )
        self.layoutChanged.emit()

    def _sort_key(self, t: Track, col: int) -> tuple:
        # 元组排序：数字列 (数值, "") 排前面，字符串列 (0, 文本)
        if col == 0:
            return (t.track_index or 0, "")
        if col == 3:
            return (t.duration, "")
        if col == 5:
            return (t.sample_rate or 0, "")
        return (0, self._display_text(t, col).lower())

    def _display_text(self, t: Track, col: int) -> str:
        if col == 1:
            return t.ogg_filename
        if col == 2:
            return t.display_name_zh
        if col == 4:
            return t.source_codec
        if col == 6:
            album = self._project.album_of(t)
            return (album.display_name_zh or album.name) if album else "通用"
        if col == 7:
            return t.transcode_status
        return ""

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
        if role == Qt.ItemDataRole.UserRole and col == 6:
            return track.album_id  # 供专辑列内联编辑器定位当前选项
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
        return (album.display_name_zh or album.name) if album else "通用"

    # ---- 编辑支持（专辑列内联下拉） ----

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        return False  # 专辑变更通过 delegate 回调 main_window 处理，模型只读

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
            if index.column() == 6:  # 专辑列可内联编辑
                flags |= Qt.ItemFlag.ItemIsEditable
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


class AlbumDelegate(QStyledItemDelegate):
    """专辑列内联编辑器：下拉选择专辑或"通用（移出专辑）"。

    专辑变更通过回调交给 MainWindow（与右键菜单/拖放共用入口），
    保证 track_ids 列表和 track_index 编号的一致维护。
    """

    ALBUM_COLUMN = 6

    def __init__(self, project_getter: Callable[[], Project],
                 assign_cb: Callable[[list[str], str], None],
                 unassign_cb: Callable[[list[str]], None], parent=None):
        super().__init__(parent)
        self._project_getter = project_getter
        self._assign_cb = assign_cb
        self._unassign_cb = unassign_cb

    def createEditor(self, parent, option, index) -> QWidget:
        combo = QComboBox(parent)
        project = self._project_getter()
        combo.addItem("通用（移出专辑）", None)
        for album in project.albums.values():
            combo.addItem(album.display_name_zh or album.name, album.album_id)
        return combo

    def setEditorData(self, editor, index) -> None:
        combo: QComboBox = editor
        album_id = index.data(Qt.ItemDataRole.UserRole)
        idx = combo.findData(album_id)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor, model, index) -> None:
        combo: QComboBox = editor
        album_id = combo.currentData()
        track_id = model.track_at(index.row()).track_id if model.track_at(index.row()) else None
        if track_id is None:
            return
        if album_id is None:
            self._unassign_cb([track_id])
        else:
            self._assign_cb([track_id], album_id)

    def updateEditorGeometry(self, editor, option, index) -> None:
        editor.setGeometry(option.rect)


class TrackTableView(QTableView):
    """曲目表格视图：单选/多选 + 列自适应 + 专辑列内联编辑。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)  # 点击列头排序（模型内实现 sort()，索引安全）
        self.setDragEnabled(True)
        self.setDragDropMode(QTableView.DragDropMode.DragOnly)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)

    def set_album_delegate(self, delegate: AlbumDelegate) -> None:
        """为专辑列安装内联编辑器。"""
        self.setItemDelegateForColumn(AlbumDelegate.ALBUM_COLUMN, delegate)
