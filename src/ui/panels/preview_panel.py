"""音频预览面板：播放选中曲目的源文件。"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    QT_MULTIMEDIA = True
except ImportError:  # 缺少多媒体后端时降级为只读显示
    QT_MULTIMEDIA = False


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = None
        self._audio_output = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.label = QLabel("未选择曲目")
        self.label.setStyleSheet("color: #888; font-size: 11px;")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        if not QT_MULTIMEDIA:
            layout.addWidget(QLabel("（音频预览不可用：缺少 QtMultimedia 后端）"))
            return

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        # 控制按钮行
        btn_row = QHBoxLayout()
        self.btn_play = QPushButton("▶")
        self.btn_pause = QPushButton("⏸")
        self.btn_stop = QPushButton("⏹")
        self.btn_play.setFixedWidth(36)
        self.btn_pause.setFixedWidth(36)
        self.btn_stop.setFixedWidth(36)
        self.btn_play.clicked.connect(self._player.play)
        self.btn_pause.clicked.connect(self._player.pause)
        self.btn_stop.clicked.connect(self._player.stop)
        btn_row.addWidget(self.btn_play)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_stop)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # 进度 + 音量
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self._seek)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.valueChanged.connect(lambda v: self._audio_output.setVolume(v / 100))
        layout.addWidget(self.slider)
        layout.addWidget(self.volume)

        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.mediaStatusChanged.connect(self._on_status)

    # ---- 外部接口 ----

    def play_file(self, path: str) -> None:
        if self._player is None or not os.path.isfile(path):
            return
        self.label.setText(os.path.basename(path))
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()

    # ---- 内部 ----

    def _seek(self, value: int) -> None:
        if self._player is not None and self._player.duration() > 0:
            self._player.setPosition(int(value / 1000 * self._player.duration()))

    def _on_position(self, pos: int) -> None:
        if self._player.duration() > 0:
            self.slider.blockSignals(True)
            self.slider.setValue(int(pos / self._player.duration() * 1000))
            self.slider.blockSignals(False)

    def _on_duration(self, _duration: int) -> None:
        pass

    def _on_status(self, status) -> None:
        # 播放结束自动复位滑块
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.slider.blockSignals(True)
            self.slider.setValue(0)
            self.slider.blockSignals(False)
