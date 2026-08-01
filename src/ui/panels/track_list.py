"""曲目列表面板：搜索/筛选 + 专辑过滤 + 右键菜单。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QMenu, QVBoxLayout, QWidget

from ...models import Project
from ..widgets.track_table import AlbumDelegate, TrackTableModel, TrackTableView

UNASSIGNED_KEY = "__unassigned__"


class TrackListPanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._project: Project | None = None
        self._album_filter: str | None = None  # None=全部, UNASSIGNED_KEY=未分配, 或 album_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        search_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("筛选曲目...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_box)
        layout.addLayout(search_row)

        self.model = TrackTableModel(Project(), self)
        self.table = TrackTableView(self)
        self.table.setModel(self.model)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(self._on_double_click)
        # 专辑列内联编辑：变更回调交给主窗口（与右键菜单/拖放共用入口）
        self.table.set_album_delegate(AlbumDelegate(
            self._project_getter,
            self._main.assign_tracks_to_album,
            self._main.unassign_tracks,
            self.table,
        ))
        layout.addWidget(self.table, stretch=1)

    def _project_getter(self) -> Project:
        return self._main.project

    def _on_double_click(self, index) -> None:
        track = self.model.track_at(index.row())
        if track is not None:
            self._main.preview_track(track)

    # ---- 数据绑定 ----

    def set_project(self, project: Project) -> None:
        self._project = project
        self._apply_filter()

    def set_album_filter(self, album_id: str | None) -> None:
        self._album_filter = album_id
        self._apply_filter()

    def _apply_filter(self) -> None:
        if self._project is None:
            return
        query = self.search_box.text().strip().lower()
        tracks = list(self._project.tracks.values())

        if self._album_filter is not None:
            if self._album_filter == UNASSIGNED_KEY:
                tracks = [t for t in tracks if t.album_id is None]
            else:
                tracks = [t for t in tracks if t.album_id == self._album_filter]

        if query:
            tracks = [t for t in tracks
                      if query in t.ogg_filename.lower()
                      or query in t.display_name_en.lower()
                      or query in t.display_name_zh.lower()
                      or query in t.source_path.lower()
                      or query in t.source_codec.lower()]
        self.model.set_tracks(tracks)

    # ---- 右键菜单 ----

    def _context_menu(self, pos) -> None:
        if self._project is None:
            return
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()})
        tracks = self.model.tracks_of_rows(rows)
        if not tracks:
            return

        menu = QMenu(self)
        sub_assign = menu.addMenu("移入专辑")
        for album in self._project.albums.values():
            act = sub_assign.addAction(album.display_name_zh or album.name)
            act.triggered.connect(
                lambda _=False, aid=album.album_id:
                self._main.assign_tracks_to_album([t.track_id for t in tracks], aid))
        act_unassign = menu.addAction("移出专辑")
        act_unassign.triggered.connect(
            lambda: self._main.unassign_tracks([t.track_id for t in tracks]))
        menu.addSeparator()
        act_remove = menu.addAction("移除曲目")
        act_remove.triggered.connect(
            lambda: self._main.remove_tracks([t.track_id for t in tracks]))
        menu.exec(self.table.mapToGlobal(pos))

    # ---- 移除（供主窗口调用） ----

    def remove_selected_tracks(self) -> list:
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()})
        tracks = self.model.tracks_of_rows(rows)
        self._main.remove_tracks([t.track_id for t in tracks])
        return tracks
