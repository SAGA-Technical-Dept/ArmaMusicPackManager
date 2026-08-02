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
    from PySide6.QtMultimedia import (QAudioFormat, QAudioOutput, QAudioSink,
                                      QMediaPlayer, QtAudio)
    QT_MULTIMEDIA = True
except ImportError:  # 缺少多媒体后端时仍可用 ffmpeg 播放
    QT_MULTIMEDIA = False

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _fmt_sec(sec: float) -> str:
    """秒数 → m:ss。"""
    s = max(0, int(sec))
    return f"{s // 60}:{s % 60:02d}"


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
        self._seek_offset = 0.0      # ffmpeg 模式 seek 的起始偏移（秒），显示位置 = offset + 已播秒数
        self._pcm_buffer = bytearray()  # 待写入 sink 的 PCM 数据（防止 short write 丢数据）
        self._playback_gen = 0       # 播放世代计数器：每次停止/重启递增，旧异步回调据此失效
        self._ffmpeg_used = False    # 当前曲目已降级 ffmpeg 播放（▶ 点击时跳过 QMediaPlayer 路径）
        self._pending_seek = 0.0     # 防抖待执行的 ffmpeg seek 位置（秒）
        self._seek_timer = QTimer(self)
        self._seek_timer.setSingleShot(True)
        self._seek_timer.setInterval(50)   # 拖动防抖：50ms 为安全下限（Windows 鼠标采样
        # 8-16ms/次，快速拖动时定时器被持续重置可合并；低于 50ms 会在拖动中途
        # 触发重启，造成静音间隙；单击延迟 ≈ 50ms + ffmpeg 重启耗时）
        self._seek_timer.timeout.connect(self._do_ffmpeg_seek)

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

        # 进度 + 时间标签 + 音量
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        # sliderMoved：拖动实时定位；valueChanged：单击/释放等一切用户操作
        # （程序 setValue 被 blockSignals 阻断不会触发）。ffmpeg 模式每次 seek
        # 需重启进程，由 _seek_timer 防抖合并为一次
        self.slider.sliderMoved.connect(self._seek)
        self.slider.valueChanged.connect(self._seek)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("color: #888; font-size: 11px;")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.valueChanged.connect(self._set_volume)
        layout.addWidget(self.slider)
        layout.addWidget(self.time_label)
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
        self._ffmpeg_used = False
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
        self.time_label.setText("0:00 / 0:00")
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
            return
        if self._player is not None and not self._ffmpeg_used:
            # QMediaPlayer 模式
            from PySide6.QtMultimedia import QMediaPlayer
            # 上次解码失败或无媒体时，重新加载当前曲目
            if (self._player.source().isEmpty()
                    or self._player.mediaStatus() in (QMediaPlayer.MediaStatus.InvalidMedia,
                                                      QMediaPlayer.MediaStatus.NoMedia)):
                if self._current_path:
                    self.play_file(self._current_path)
                return
            self._player.play()
            return
        # ffmpeg 模式播放已结束（sink 已清理）：从头重播当前曲目
        if self._current_path:
            self.play_file(self._current_path)

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
        if self._audio_sink is not None:
            # ffmpeg 模式：防抖重启（拖动时 valueChanged 连续触发，只取最终位置）。
            # 单击也走这里——valueChanged 单击即发射，150ms 内完成跳转
            if self._ffmpeg_duration <= 0:
                return
            pos = value / 1000 * self._ffmpeg_duration
            if pos >= self._ffmpeg_duration - 1:
                return  # seek 到末尾没有意义
            self._pending_seek = pos
            self._seek_timer.start()  # 重置计时器：停止操作 150ms 后真正重启
            return
        # QMediaPlayer 模式：即时定位（setPosition 无开销，拖动/单击都实时响应）
        if self._player is not None and self._player.duration() > 0:
            self._player.setPosition(int(value / 1000 * self._player.duration()))

    def _do_ffmpeg_seek(self) -> None:
        """防抖定时器到期：重启 ffmpeg 从目标位置解码（-ss 输入定位）。"""
        if self._current_path and self._audio_sink is not None:
            self._play_ffmpeg(self._current_path, seek_from=self._pending_seek)

    def _on_state(self, state) -> None:
        """播放/暂停/停止状态 → 按钮可用性联动（仅 QMediaPlayer 模式）。

        ffmpeg 模式下 QMediaPlayer 的异步状态信号（error 后的 StoppedState）会
        在 _play_ffmpeg 启动之后才到达，错误覆盖按钮状态，必须忽略。
        """
        if self._audio_sink is not None:
            return
        from PySide6.QtMultimedia import QMediaPlayer
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        paused = state == QMediaPlayer.PlaybackState.PausedState
        self.btn_play.setEnabled(not playing)
        self.btn_pause.setEnabled(playing or paused)

    def _on_position(self, pos: int) -> None:
        duration = self._player.duration()
        if duration > 0:
            self.slider.blockSignals(True)
            self.slider.setValue(int(pos / duration * 1000))
            self.slider.blockSignals(False)
            self.time_label.setText(f"{_fmt_sec(pos / 1000)} / {_fmt_sec(duration / 1000)}")

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
            self._ffmpeg_used = True
            self._play_ffmpeg(self._current_path)
        else:
            self._show_error(f"无法解码或加载音频文件: {error_string}")

    # ---- ffmpeg 降级后端 ----

    def _play_ffmpeg(self, path: str, seek_from: float | None = None) -> None:
        self._stop_ffmpeg()
        if seek_from is not None:
            self._seek_offset = seek_from
        if not shutil.which("ffmpeg"):
            self._show_error("无法播放：未找到 ffmpeg（请安装并加入 PATH）")
            self._reset_controls()
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(44100)
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        # 先启动进程再创建 sink：sink.start() 会立即发出初始 Idle 状态，
        # 此时 _ffmpeg_proc 必须已赋值，_on_sink_state 才不会误清理
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        # lambda 捕获 proc 对象 + 世代号双重身份校验：跨线程 queued 连接下
        # sender() 为 None 不能用于判断来源，而旧进程被 kill 后其信号仍可能晚到
        gen = self._playback_gen
        proc.readyReadStandardOutput.connect(lambda: self._pump_audio(proc, gen))
        proc.readyReadStandardError.connect(lambda: self._read_duration(proc, gen))
        proc.finished.connect(lambda code, status: self._on_ffmpeg_finished(proc, gen, code, status))
        self._ffmpeg_proc = proc
        args = ["-hide_banner", "-i", path,
                "-f", "s16le", "-ac", "2", "-ar", "44100", "-"]
        if seek_from is not None:
            # -ss 放在 -i 前 = 输入定位（seek 到 pos 秒处开始解码，输出到管道）
            args = ["-hide_banner", "-ss", f"{seek_from:.2f}", "-i", path,
                    "-f", "s16le", "-ac", "2", "-ar", "44100", "-"]
        proc.start("ffmpeg", args)

        sink = QAudioSink(fmt, self)
        sink.setBufferSize(44100 * 2 * 2 * 2)  # 2 秒内部缓冲（配合回压写入）
        sink.setVolume(self.volume.value() / 100)
        # 注意：PySide6 6.8 中 sink.stateChanged 信号无法连接到 Python 回调
        # （信号元类型为 QAudio::State 但实际发出 QtAudio::State，转换失败抛 TypeError），
        # 播完检测改为 _ffmpeg_tick 轮询 sink.state() 实现
        self._audio_sink = sink
        self._sink_io = sink.start()
        self._sink_io.bytesWritten.connect(self._drain_buffer)
        self._pcm_buffer.clear()
        self._ffmpeg_timer.start()
        # 显式设置按钮状态：QMediaPlayer 的异步信号（error → StoppedState）会
        # 在 _play_ffmpeg 启动之后到达，若不覆盖则按钮被错误复位为"可播放"
        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(True)

    def _stop_ffmpeg(self) -> None:
        self._playback_gen += 1  # 世代递增：旧进程/旧 sink 的所有异步回调立即失效
        if self._ffmpeg_proc is not None:
            proc = self._ffmpeg_proc
            # blockSignals 阻止一切信号发射：kill 后 finished/readyRead* 等信号仍会
            # 排队到达，若不屏蔽会触发旧回调（PySide6 无参 disconnect() 不可用，
            # 且 blockSignals 已足以阻断）
            proc.blockSignals(True)
            proc.kill()
            self._ffmpeg_proc = None
        self._pcm_buffer.clear()
        if self._audio_sink is not None:
            # reset() 清空内部与硬件缓冲并重置设备，比 stop() 更彻底：
            # stop() 在 Windows 上已提交给 WASAPI 的缓冲仍会继续播完（切换曲目重叠）
            self._audio_sink.reset()
        self._audio_sink = None
        self._sink_io = None
        self._seek_offset = 0.0
        self._ffmpeg_duration = 0.0
        if self._ffmpeg_timer is not None:
            self._ffmpeg_timer.stop()
        self._seek_timer.stop()  # 取消挂起的 seek：避免在下一次播放启动后误触发

    def _pump_audio(self, proc, gen: int) -> None:
        if gen != self._playback_gen or proc is not self._ffmpeg_proc:
            return  # 旧进程（被 kill）的残留信号，忽略
        data = bytes(proc.readAllStandardOutput())
        if data:
            self._pcm_buffer.extend(data)
            self._drain_buffer()

    def _drain_buffer(self, _written: int = 0) -> None:
        """将缓冲中的 PCM 写入 sink（受 bytesFree 限制，不会阻塞 UI 线程）。

        由 _pump_audio（新数据到达）和 _sink_io.bytesWritten（设备消费后）驱动，
        保证每次写入量不超过空闲空间，不会发生 short write 丢数据。
        """
        if self._sink_io is None or self._audio_sink is None or not self._pcm_buffer:
            return
        free = self._audio_sink.bytesFree()
        if free <= 0:
            return
        chunk = self._pcm_buffer[:free]
        written = self._sink_io.write(chunk)
        if written > 0:
            del self._pcm_buffer[:written]

    def _read_duration(self, proc, gen: int) -> None:
        if gen != self._playback_gen or proc is not self._ffmpeg_proc:
            return
        if self._ffmpeg_duration:
            return
        text = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
        m = _DURATION_RE.search(text)
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            self._ffmpeg_duration = h * 3600 + mi * 60 + s

    def _ffmpeg_tick(self) -> None:
        if self._audio_sink is None:
            return
        if self._ffmpeg_proc is None and self._audio_sink.state() == QtAudio.State.IdleState:
            # ffmpeg 已退出且缓冲播完（Idle）→ 清理。stateChanged 信号在 PySide6 6.8
            # 下无法连接（枚举类型转换失败），只能轮询检测播完
            self._finish_ffmpeg_cleanup()
            return
        if self._ffmpeg_duration > 0:
            us = self._audio_sink.processedUSecs()
            # seek 后进程从 _seek_offset 处开始解码，显示位置 = 偏移 + 已播秒数
            pos = self._seek_offset + us / 1e6
            self.slider.blockSignals(True)
            self.slider.setValue(min(1000, int(pos / self._ffmpeg_duration * 1000)))
            self.slider.blockSignals(False)
            self.time_label.setText(f"{_fmt_sec(pos)} / {_fmt_sec(self._ffmpeg_duration)}")

    def _on_ffmpeg_finished(self, proc, gen: int, _code: int, _status) -> None:
        if gen != self._playback_gen or proc is not self._ffmpeg_proc:
            return  # 旧进程（被 kill）的结束回调，避免污染新播放状态
        # ffmpeg 已退出：把缓冲中剩余 PCM 全部排进 sink，等播完（Idle）再清理
        self._ffmpeg_proc = None
        self._drain_buffer()
        if self._pcm_buffer or self._audio_sink is None:
            return  # 缓冲未排空时继续等 bytesWritten / stateChanged
        if self._audio_sink.state() != QtAudio.State.IdleState:
            return  # sink 仍在播放排队数据，等 stateChanged(Idle) 统一清理
        self._finish_ffmpeg_cleanup()

    def _finish_ffmpeg_cleanup(self) -> None:
        """播放全部结束：停止 sink、复位 UI。"""
        self._pcm_buffer.clear()
        if self._audio_sink is not None:
            self._audio_sink.stop()
            self._audio_sink = None
        self._sink_io = None
        self._seek_offset = 0.0
        self._ffmpeg_duration = 0.0
        if self._ffmpeg_timer is not None:
            self._ffmpeg_timer.stop()
        self._seek_timer.stop()  # 取消挂起的 seek：避免在下一次播放启动后误触发
        self.slider.blockSignals(True)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.time_label.setText("0:00 / 0:00")
        self._reset_controls()
