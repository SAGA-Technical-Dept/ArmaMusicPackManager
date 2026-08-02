"""专辑侧边栏：专辑列表 + 右键 CRUD + 曲目过滤 + 拖放入专辑。"""

from __future__ import annotations

import json
import uuid

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from ...models import Album, Project
from ..dialogs.album_edit import AlbumEditDialog
from ..widgets.track_table import MIME_TRACK_IDS

# 列表项 type 值
TYPE_ALL = "all"          # 全部曲目
TYPE_UNASSIGNED = "none"  # 未分配
TYPE_ALBUM = "album"      # 具体专辑

# 拖放悬停时目标项的高亮色（比选中蓝 #094771 亮，区分"放置目标"状态）
_DRAG_HIGHLIGHT = QColor("#1a6fb0")


class AlbumPanel(QWidget):
    """显示全部/未分配/各专辑；选中后发出 album_selected(album_id|None)。"""

    album_selected = Signal(object)   # album_id (str) 或 None（全部）
    assign_requested = Signal(list, str)     # 拖放：track_ids → album_id
    unassign_requested = Signal(list)        # 拖放：track_ids → 未分配

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Project | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("+ 新建专辑")
        self.btn_new.clicked.connect(self.new_album)
        btn_row.addWidget(self.btn_new)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.list = QListWidget()
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.currentItemChanged.connect(self._on_select)
        self.list.setAcceptDrops(True)
        self.list.viewport().setAcceptDrops(True)
        layout.addWidget(self.list, stretch=1)

    # ---- 拖放（接收曲目表格拖来的 track_ids） ----

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_TRACK_IDS):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if not event.mimeData().hasFormat(MIME_TRACK_IDS):
            event.ignore()
            return
        # itemAt 需要 viewport 坐标：把事件坐标从本面板映射到列表视口
        pos = self.list.viewport().mapFrom(self, event.position().toPoint())
        item = self.list.itemAt(pos)
        self._set_highlight(item)
        if item is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_highlight(None)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        if not mime.hasFormat(MIME_TRACK_IDS):
            return
        self._set_highlight(None)
        try:
            track_ids = json.loads(bytes(mime.data(MIME_TRACK_IDS)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        pos = self.list.viewport().mapFrom(self, event.position().toPoint())
        item = self.list.itemAt(pos)
        kind, album_id = item.data(Qt.ItemDataRole.UserRole) if item else (None, None)
        if kind == TYPE_ALBUM and album_id:
            self.assign_requested.emit(track_ids, album_id)
            event.acceptProposedAction()
        elif kind == TYPE_UNASSIGNED:
            self.unassign_requested.emit(track_ids)
            event.acceptProposedAction()

    def _set_highlight(self, target: QListWidgetItem | None) -> None:
        """高亮拖放目标项；传入 None 清除所有高亮。"""
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is target:
                item.setBackground(QBrush(_DRAG_HIGHLIGHT))
            else:
                item.setBackground(QBrush())

    # ---- 数据绑定 ----

    def set_project(self, project: Project) -> None:
        self._project = project
        self.rebuild()

    def rebuild(self) -> None:
        self.list.clear()
        if self._project is None:
            return
        item_all = QListWidgetItem(f"全部曲目 ({len(self._project.tracks)})")
        item_all.setData(Qt.ItemDataRole.UserRole, (TYPE_ALL, None))
        self.list.addItem(item_all)

        unassigned = len(self._project.unassigned_tracks())
        item_none = QListWidgetItem(f"未分配 ({unassigned})")
        item_none.setData(Qt.ItemDataRole.UserRole, (TYPE_UNASSIGNED, None))
        self.list.addItem(item_none)

        for album in self._project.albums.values():
            n = len(album.track_ids)
            item = QListWidgetItem(f"{album.display_name_zh or album.name} ({n})")
            item.setData(Qt.ItemDataRole.UserRole, (TYPE_ALBUM, album.album_id))
            self.list.addItem(item)

        self.list.setCurrentRow(0)

    # ---- 选择 ----

    def _on_select(self, current: QListWidgetItem | None, _previous=None) -> None:
        if current is None:
            return
        kind, album_id = current.data(Qt.ItemDataRole.UserRole)
        if kind == TYPE_ALL:
            self.album_selected.emit(None)      # None = 全部
        elif kind == TYPE_ALBUM:
            self.album_selected.emit(album_id)
        elif kind == TYPE_UNASSIGNED:
            self.album_selected.emit("__unassigned__")

    # ---- CRUD ----

    def _context_menu(self, pos) -> None:
        if self._project is None:
            return
        item = self.list.itemAt(pos)
        menu = QMenu(self)
        act_new = menu.addAction("新建专辑...")
        act_edit = act_delete = None
        if item is not None:
            kind, album_id = item.data(Qt.ItemDataRole.UserRole)
            if kind == TYPE_ALBUM:
                act_edit = menu.addAction("编辑专辑...")
                act_delete = menu.addAction("删除专辑")
        action = menu.exec(self.list.mapToGlobal(pos))
        if action is act_new:
            self.new_album()
        elif action is act_edit:
            self._edit_album(album_id)
        elif action is act_delete:
            self._delete_album(album_id)

    def new_album(self) -> None:
        if self._project is None:
            return
        album = Album(album_id=uuid.uuid4().hex)
        dialog = AlbumEditDialog(album, is_new=True, parent=self)
        if dialog.exec():
            result = dialog.result_album()
            if result.name in {a.name for a in self._project.albums.values()}:
                QMessageBox.warning(self, "名称冲突", f"专辑内部名 '{result.name}' 已存在")
                return
            self._project.albums[result.album_id] = result
            self.rebuild()
            self._select_album(result.album_id)

    def _edit_album(self, album_id: str) -> None:
        album = self._project.albums.get(album_id)
        if album is None:
            return
        dialog = AlbumEditDialog(album, parent=self)
        if dialog.exec():
            self.rebuild()
            self._select_album(album_id)

    def _delete_album(self, album_id: str) -> None:
        album = self._project.albums.get(album_id)
        if album is None:
            return
        n = len(album.track_ids)
        if n and QMessageBox.question(
                self, "删除专辑",
                f"专辑 '{album.display_name_zh or album.name}' 含 {n} 首曲目。\n"
                "删除后这些曲目将变为未分配。继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        for tid in album.track_ids:
            track = self._project.tracks.get(tid)
            if track is not None:
                track.album_id = None
        self._project.albums.pop(album_id, None)
        self.rebuild()
        self.list.setCurrentRow(0)  # 回到"全部曲目"

    def _select_album(self, album_id: str) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            kind, aid = item.data(Qt.ItemDataRole.UserRole)
            if kind == TYPE_ALBUM and aid == album_id:
                self.list.setCurrentItem(item)
                break
