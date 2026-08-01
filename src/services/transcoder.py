"""音频转码服务：调用 ffmpeg 将源音频转为 Ogg Vorbis。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from ..models import Track
from ..utils.constants import DEFAULT_CHANNELS, DEFAULT_SAMPLE_RATE, TARGET_CODEC

FFMPEG = "ffmpeg"

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


@dataclass
class TranscodeParams:
    """一次转码的参数（比特率 kbps；采样率/声道固定为 Arma 3 要求）。"""
    bitrate_kbps: int = 128
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS


def needs_transcode(track: Track, params: TranscodeParams) -> bool:
    """源文件已是合规 Ogg Vorbis 且码率不高于目标时，可直接复制而非重编码。"""
    if track.source_codec.lower() not in ("vorbis", "libvorbis"):
        return True
    if track.sample_rate and track.sample_rate != params.sample_rate:
        return True
    if track.channels and track.channels != params.channels:
        return True
    if track.source_bitrate and track.source_bitrate > params.bitrate_kbps * 1000:
        return True
    return False


def transcode(
    track: Track,
    output_path: str,
    params: TranscodeParams,
    progress_cb=None,
    cancel_event=None,
) -> None:
    """将源音频转码为 Ogg Vorbis 写入 output_path。

    progress_cb(ratio: float) 0.0~1.0（可选）
    cancel_event: threading.Event，置位时终止（可选）
    合规源文件直接复制（copy 模式），否则调用 ffmpeg 重编码。
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not needs_transcode(track, params):
        shutil.copy2(track.source_path, output_path)
        if progress_cb:
            progress_cb(1.0)
        return

    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "info",
        "-i", track.source_path,
        "-c:a", TARGET_CODEC,
        "-b:a", f"{params.bitrate_kbps}k",
        "-ar", str(params.sample_rate),
        "-ac", str(params.channels),
        output_path,
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace")
    assert proc.stderr is not None

    duration = track.duration or 0.0
    for line in proc.stderr:
        if cancel_event is not None and cancel_event.is_set():
            proc.terminate()
            raise TranscodeError("已取消")
        if progress_cb is not None and duration > 0:
            m = _TIME_RE.search(line)
            if m:
                h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                elapsed = h * 3600 + mi * 60 + s
                progress_cb(min(1.0, elapsed / duration))

    proc.wait()
    if proc.returncode != 0:
        raise TranscodeError(f"ffmpeg 退出码 {proc.returncode}")
    if progress_cb is not None:
        progress_cb(1.0)


class TranscodeError(RuntimeError):
    pass
