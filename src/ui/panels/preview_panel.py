"""音频预览面板：播放选中曲目的源文件。

双后端：优先 QMediaPlayer（Qt 多媒体后端）；Windows WMF 不支持
Ogg Vorbis / FLAC 等格式时，解码失败自动降级到 ffmpeg + QAudioSink 播放。
"""

from __future__ import annotations

import os
import re
import shutil

from PySide6.QtCore import QProcess, QTimer, Qt, QUrl
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioFormat, QAudioOutput, QAudioSink, QMediaPlayer
    QT_MULTIMEDIA = True
except ImportError:  # 缺少多媒体后端时仍可用 ffmpeg 播放
    QT_MULTIMEDIA = False

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = None
        self._audio_output = None
        self._pending_play = False   # setSource 异步加载完成后才 play()
        self._current_path: str | None = None
        # ffmpeg 降级后端状态
        self._ffmpeg_proc: QProcess | None = None
        self._audio_sink = None      # QAudioSink（pcm 播放）
        self._sink_io = None         # QAudioSink.start() 返回的写通道
        self._ffmpeg_duration = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.label = QLabel("未选择曲目")
        self.label.setStyleSheet("color: #888; font-size: 11px;")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        # 控制按钮行（QMediaPlayer 与 ffmpeg 降级共用）
        btn_row = QHBoxLayout()
        self.btn_play = QPushButton("▶")
        self.btn_pause = QPushButton("⏸")
        self.btn_stop = QPushButton("⏹")
        self.btn_play.setFixedWidth(36)
        self.btn_pause.setFixedWidth(36)
        self.btn_stop.setFixedWidth(36)
        self.btn_play.clicked.connect(self._on_play_clicked)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        self.btn_stop.clicked.connect(self.stop)
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
        self.volume.valueChanged.connect(self._set_volume)
        layout.addWidget(self.slider)
        layout.addWidget(self.volume)

        if QT_MULTIMEDIA:
            self._player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_output)
            self._player.playbackStateChanged.connect(self._on_state)
            self._player.positionChanged.connect(self._on_position)
            self._player.durationChanged.connect(self._on_duration)
            self._player.mediaStatusChanged.connect(self._on_status)
            self._player.errorOccurred.connect(self._on_error)

        self._ffmpeg_timer = QTimer(self)
        self._ffmpeg_timer.setInterval(200)
        self._ffmpeg_timer.timeout.connect(self._ffmpeg_tick)

    # ---- 外部接口 ----

    def play_file(self, path: str) -> None:
        if not os.path.isfile(path):
            self._show_error("源文件不存在或已被移动")
            return
        self._stop_ffmpeg()
        self._current_path = path
        self.label.setStyleSheet("color: #888; font-size: 11px;")
        self.label.setText(os.path.basename(path))
        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(True)
        if self._player is None:
            self._play_ffmpeg(path)
            return
        # Qt 6 的 setSource 是异步的：等 LoadedMedia 信号后再 play()
        self._pending_play = True
        self._player.setSource(QUrl.fromLocalFile(path))

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()
        self._stop_ffmpeg()
        self.slider.blockSignals(True)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._reset_controls()

    # ---- 内部 ----

    def _show_error(self, message: str) -> None:
        self.label.setStyleSheet("color: #c66; font-size: 11px;")
        self.label.setText(f"播放失败: {message}")

    def _reset_controls(self) -> None:
        self.btn_play.setEnabled(True)
        self.btn_pause.setEnabled(False)

    def _on_play_clicked(self) -> None:
        if self._audio_sink is not None:
            # ffmpeg 降级模式：暂停后恢复播放
            self._audio_sink.resume()
            self.btn_play.setEnabled(False)
            self.btn_pause.setEnabled(True)
        elif self._player is not None:
            from PySide6.QtMultimedia import QMediaPlayer
            # 上次解码失败或无媒体时，重新加载当前曲目
            if (self._player.source().isEmpty()
                    or self._player.mediaStatus() in (QMediaPlayer.MediaStatus.InvalidMedia,
                                                      QMediaPlayer.MediaStatus.NoMedia)):
                if self._current_path:
                    self.play_file(self._current_path)
                return
            self._player.play()

    def _on_pause_clicked(self) -> None:
        if self._audio_sink is not None:
            self._audio_sink.suspend()
            self.btn_play.setEnabled(True)
            self.btn_pause.setEnabled(False)
        elif self._player is not None:
            self._player.pause()

    def _set_volume(self, v: int) -> None:
        if self._audio_output is not None:
            self._audio_output.setVolume(v / 100)
        if self._audio_sink is not None:
            self._audio_sink.setVolume(v / 100)

    def _seek(self, value: int) -> None:
        # ffmpeg 降级模式不支持拖动定位
        if self._audio_sink is not None:
            return
        if self._player is not None and self._player.duration() > 0:
            self._player.setPosition(int(value / 1000 * self._player.duration()))

    def _on_state(self, state) -> None:
        """播放/暂停/停止状态 → 按钮可用性联动。"""
        from PySide6.QtMultimedia import QMediaPlayer
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        paused = state == QMediaPlayer.PlaybackState.PausedState
        self.btn_play.setEnabled(not playing)
        self.btn_pause.setEnabled(playing or paused)

    def _on_position(self, pos: int) -> None:
        if self._player.duration() > 0:
            self.slider.blockSignals(True)
            self.slider.setValue(int(pos / self._player.duration() * 1000))
            self.slider.blockSignals(False)

    def _on_duration(self, _duration: int) -> None:
        pass

    def _on_status(self, status) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._pending_play:
            # setSource 异步加载完成，此时才真正开始播放
            self._pending_play = False
            self._player.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            # 播放结束自动复位滑块（错误由 errorOccurred 信号处理）
            self.slider.blockSignals(True)
            self.slider.setValue(0)
            self.slider.blockSignals(False)

    def _on_error(self, error, error_string: str) -> None:
        """QMediaPlayer 解码失败（如 Windows WMF 不支持 Ogg/FLAC）→ 降级 ffmpeg。"""
        self._pending_play = False
        if self._audio_sink is not None:
            return  # 已在 ffmpeg 降级模式，忽略重复错误信号
        if self._current_path:
            self._play_ffmpeg(self._current_path)
        else:
            self._show_error(f"无法解码或加载音频文件: {error_string}")

    # ---- ffmpeg 降级后端 ----

    def _play_ffmpeg(self, path: str) -> None:
        self._stop_ffmpeg()
        if not shutil.which("ffmpeg"):
            self._show_error("无法播放：未找到 ffmpeg（请安装并加入 PATH）")
            self._reset_controls()
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(44100)
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        sink = QAudioSink(fmt, self)
        sink.setBufferSize(44100 * 2 * 2 * 4)  # 4 秒缓冲，避免 UI 线程写阻塞
        sink.setVolume(self.volume.value() / 100)
        self._audio_sink = sink
        self._sink_io = sink.start()

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        proc.readyReadStandardOutput.connect(self._pump_audio)
        proc.readyReadStandardError.connect(self._read_duration)
        proc.finished.connect(self._on_ffmpeg_finished)
        proc.start("ffmpeg", ["-hide_banner", "-i", path,
                              "-f", "s16le", "-ac", "2", "-ar", "44100", "-"])
        self._ffmpeg_proc = proc
        self._ffmpeg_timer.start()

    def _stop_ffmpeg(self) -> None:
        if self._ffmpeg_proc is not None:
            self._ffmpeg_proc.kill()
            self._ffmpeg_proc = None
        if self._audio_sink is not None:
            self._audio_sink.stop()
        self._audio_sink = None
        self._sink_io = None
        self._ffmpeg_duration = 0.0
        if self._ffmpeg_timer is not None:
            self._ffmpeg_timer.stop()

    def _pump_audio(self) -> None:
        if self.sender() is not self._ffmpeg_proc:
            return  # 旧进程（被 kill）的残留信号，忽略
        data = self._ffmpeg_proc.readAllStandardOutput()
        if self._sink_io is not None and not data.isEmpty():
            self._sink_io.write(data)

    def _read_duration(self) -> None:
        if self.sender() is not self._ffmpeg_proc:
            return
        if self._ffmpeg_duration:
            return
        text = bytes(self._ffmpeg_proc.readAllStandardError()).decode("utf-8", errors="replace")
        m = _DURATION_RE.search(text)
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            self._ffmpeg_duration = h * 3600 + mi * 60 + s

    def _ffmpeg_tick(self) -> None:
        if self._audio_sink is not None and self._ffmpeg_duration > 0:
            us = self._audio_sink.processedUSecs()
            self.slider.blockSignals(True)
            self.slider.setValue(min(1000, int(us / 1e6 / self._ffmpeg_duration * 1000)))
            self.slider.blockSignals(False)

    def _on_ffmpeg_finished(self, _code: int, _status) -> None:
        if self.sender() is not self._ffmpeg_proc:
            return  # 旧进程（被 kill）的结束回调，避免污染新播放状态
        # ffmpeg 自然结束（或主动 kill）→ 清理并复位 UI
        self._sink_io = None
        if self._audio_sink is not None:
            self._audio_sink.stop()
            self._audio_sink = None
        self._ffmpeg_duration = 0.0
        if self._ffmpeg_timer is not None:
            self._ffmpeg_timer.stop()
        self.slider.blockSignals(True)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._reset_controls()
