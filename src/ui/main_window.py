"""主窗口：菜单/工具栏/分割面板/状态栏 + 拖放导入 + 项目生命周期。"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox, QSplitter, QStackedWidget,
    QToolBar, QVBoxLayout, QWidget,
)

from ..models import Project
from ..services import project_io
from ..utils.constants import DEFAULT_CLASS_PREFIX, DEFAULT_SOUND_PREFIX

from .dialogs.settings_dialog import NewProjectDialog
from .panels.ai_panel import AITranslatePanel
from .panels.album_panel import AlbumPanel
from .panels.config_panel import ConfigPanel
from .panels.import_panel import ImportDialog
from .panels.preview_panel import PreviewPanel
from .panels.track_list import TrackListPanel
from .panels.transcode_panel import TranscodePanel

PAGE_TRACKS = 0


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Arma 3 音乐包管理器")
        self.resize(1100, 700)
        self.setAcceptDrops(True)

        self.project = Project(
            mod_name="douzi_SAGA_music",
            display_name="=SAGA= 音乐包",
            author="",
            sound_prefix=DEFAULT_SOUND_PREFIX,
            class_prefix=DEFAULT_CLASS_PREFIX,
        )

        self._build_central()
        self._build_toolbar()
        self._build_menu()
        self.refresh_all()

    # ---------------------------------------------------------------- UI 构建

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # 左侧：专辑面板 + 预览面板
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        self.album_panel = AlbumPanel(left)
        self.album_panel.album_selected.connect(self.track_panel_filter)
        self.album_panel.assign_requested.connect(self.assign_tracks_to_album)
        self.album_panel.unassign_requested.connect(self.unassign_tracks)
        self.preview_panel = PreviewPanel(left)
        left_layout.addWidget(self.album_panel, stretch=3)
        left_layout.addWidget(self.preview_panel, stretch=1)
        left.setMinimumWidth(200)
        left.setMaximumWidth(340)
        splitter.addWidget(left)

        # 右侧：页面堆栈
        self.stack = QStackedWidget(splitter)
        self.track_panel = TrackListPanel(self)
        self.stack.addWidget(self.track_panel)          # 0: 曲目列表
        self.transcode_panel = TranscodePanel(self)
        self.stack.addWidget(self.transcode_panel)      # 1: 音频转码
        self.config_panel = ConfigPanel(self)
        self.stack.addWidget(self.config_panel)         # 2: config.cpp 预览
        self.ai_panel = AITranslatePanel(self)
        self.stack.addWidget(self.ai_panel)             # 3: AI 翻译

        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 880])

        self.setCentralWidget(splitter)
        self.statusBar().showMessage("就绪")

    def track_panel_filter(self, album_id: str | None) -> None:
        """专辑面板选择变化 → 曲目列表按专辑过滤。"""
        self.track_panel.set_album_filter(album_id)

    def preview_track(self, track) -> None:
        """双击曲目 → 预览播放源文件。"""
        self.preview_panel.play_file(track.source_path)

    def _placeholder_page(self, text: str) -> QWidget:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #666; font-size: 14px;")
        return label

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        act = QAction("导入", self)
        act.triggered.connect(self.import_files)
        toolbar.addAction(act)

        toolbar.addSeparator()

        act = QAction("转码", self)
        act.triggered.connect(lambda: self.stack.setCurrentIndex(1))
        toolbar.addAction(act)

        act = QAction("Config 预览", self)
        act.triggered.connect(lambda: self.stack.setCurrentIndex(2))
        toolbar.addAction(act)

        act = QAction("AI 翻译", self)
        act.triggered.connect(lambda: self.stack.setCurrentIndex(3))
        toolbar.addAction(act)

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        # 文件
        menu_file = menubar.addMenu("文件(&F)")
        self._add_action(menu_file, "新建项目(&N)", QKeySequence.StandardKey.New, self.new_project)
        self._add_action(menu_file, "打开项目(&O)...", QKeySequence.StandardKey.Open, self.open_project)
        self._add_action(menu_file, "保存项目(&S)", QKeySequence.StandardKey.Save, self.save_project)
        self._add_action(menu_file, "另存为(&A)...", QKeySequence.StandardKey.SaveAs, self.save_project_as)
        menu_file.addSeparator()
        self._add_action(menu_file, "退出(&X)", QKeySequence.StandardKey.Quit, self.close)

        # 编辑
        menu_edit = menubar.addMenu("编辑(&E)")
        self._add_action(menu_edit, "删除选中曲目", QKeySequence.StandardKey.Delete, self.remove_selected)

        # 工具
        menu_tools = menubar.addMenu("工具(&T)")
        self._add_action(menu_tools, "导入音频(&I)...", None, self.import_files)
        self._add_action(menu_tools, "项目设置(&P)...", None, self.project_settings)

        # 帮助
        menu_help = menubar.addMenu("帮助(&H)")
        self._add_action(menu_help, "关于(&A)", None, self.about)

    def _add_action(self, menu, text, shortcut, slot):
        act = QAction(text, self)
        if shortcut is not None:
            act.setShortcut(shortcut)
        act.triggered.connect(slot)
        menu.addAction(act)

    # ---------------------------------------------------------------- 项目生命周期

    def new_project(self) -> None:
        dialog = NewProjectDialog(self.project, self)
        if dialog.exec():
            self.project = dialog.result_project()
            self.refresh_all()

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", str(self._projects_dir()), "Arma 音乐包项目 (*.amp.json)")
        if not path:
            return
        try:
            self.project = project_io.load_project(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "打开失败", f"无法打开项目：\n{exc}")
            return
        self.refresh_all()

    def save_project(self) -> None:
        if self.project.project_file:
            project_io.save_project(self.project, self.project.project_file)
            self.statusBar().showMessage(f"已保存 {os.path.basename(self.project.project_file)}", 3000)
        else:
            self.save_project_as()

    def save_project_as(self) -> None:
        default_name = f"{self.project.mod_name or 'music_pack'}{project_io.PROJECT_EXT}"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存项目", str(self._projects_dir() / default_name),
            "Arma 音乐包项目 (*.amp.json)")
        if not path:
            return
        project_io.save_project(self.project, path)
        self.refresh_all()

    def _projects_dir(self) -> str:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(root, "projects")

    def project_settings(self) -> None:
        QMessageBox.information(self, "项目设置", "项目设置将在后续版本提供。")

    # ---------------------------------------------------------------- 导入

    def import_files(self, paths: list[str] | None = None) -> None:
        existing = {os.path.normcase(t.source_path) for t in self.project.tracks.values()}
        dialog = ImportDialog(existing, self)
        if paths:
            dialog.drop_zone.add_paths(paths)
            dialog.refresh_file_list()
        if dialog.exec():
            imported = dialog.imported_tracks()
            for t in imported:
                self.project.tracks[t.track_id] = t
            if imported:
                self.refresh_all()
                self.statusBar().showMessage(f"已导入 {len(imported)} 首曲目", 3000)

    # ---------------------------------------------------------------- 编辑

    def remove_selected(self) -> None:
        removed = self.track_panel.remove_selected_tracks()
        if removed:
            self.refresh_all()
            self.statusBar().showMessage(f"已移除 {len(removed)} 首曲目", 3000)

    def assign_tracks_to_album(self, track_ids: list[str], album_id: str) -> None:
        """将曲目划入专辑（右键菜单与拖放共用入口）。"""
        album = self.project.albums.get(album_id)
        if album is None:
            return
        for tid in track_ids:
            t = self.project.tracks.get(tid)
            if t is None:
                continue
            old = self.project.album_of(t)
            if old is not None and tid in old.track_ids:
                old.track_ids.remove(tid)
            if tid not in album.track_ids:
                album.track_ids.append(tid)
            t.album_id = album_id
        self.renumber_album_tracks(album)
        self.refresh_all()

    def unassign_tracks(self, track_ids: list[str]) -> None:
        for tid in track_ids:
            t = self.project.tracks.get(tid)
            if t is None:
                continue
            album = self.project.album_of(t)
            if album is not None and tid in album.track_ids:
                album.track_ids.remove(tid)
            t.album_id = None
        self.refresh_all()

    def remove_tracks(self, track_ids: list[str]) -> None:
        for tid in track_ids:
            t = self.project.tracks.get(tid)
            if t is None:
                continue
            album = self.project.album_of(t)
            if album is not None and tid in album.track_ids:
                album.track_ids.remove(tid)
            self.project.tracks.pop(tid, None)
        self.refresh_all()

    def renumber_album_tracks(self, album) -> None:
        """按专辑内顺序重新编号（track_index 1-based）。"""
        for i, tid in enumerate(album.track_ids, start=1):
            t = self.project.tracks.get(tid)
            if t is not None:
                t.track_index = i

    # ---------------------------------------------------------------- 拖放

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.import_files(paths)

    # ---------------------------------------------------------------- 刷新

    def refresh_all(self) -> None:
        self.track_panel.set_project(self.project)
        self.album_panel.set_project(self.project)
        self.transcode_panel.set_project(self.project)
        self.config_panel.set_project(self.project)
        self.ai_panel.set_project(self.project)
        self._update_status()

    def _update_status(self) -> None:
        n_tracks = len(self.project.tracks)
        n_albums = len(self.project.albums)
        name = self.project.mod_name or "未命名项目"
        self.statusBar().showMessage(f"项目: {name} | {n_tracks} 首曲目 | {n_albums} 个专辑")

    # ---------------------------------------------------------------- 关于

    def about(self) -> None:
        QMessageBox.about(
            self, "关于",
            "Arma 3 音乐包管理器\n\n"
            "将源音频整理为符合 Arma 3 规范的 Ogg 音乐包。\n"
            "参考范例: demo_files/douzi_SAGA_music/",
        )
