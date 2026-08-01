"""音频元数据读取：mutagen 提取 duration/采样率/声道/编码。"""

from __future__ import annotations

import logging

from mutagen import File as MutagenFile

from ..models import Track

logger = logging.getLogger(__name__)


def fill_metadata(track: Track) -> Track:
    """用 mutagen 读取源文件的音频属性并填充到 Track。"""
    try:
        audio = MutagenFile(track.source_path)
        if audio is None or audio.info is None:
            track.source_codec = _guess_codec(track.source_path)
            return track
        info = audio.info
        track.duration = float(getattr(info, "length", 0.0))
        track.sample_rate = int(getattr(info, "sample_rate", 0) or 0)
        track.channels = int(getattr(info, "channels", 0) or 0)
        track.source_bitrate = int(getattr(info, "bitrate", 0) or 0)
        track.source_codec = getattr(info, "codec_name", None) or (
            getattr(audio, "mime", [""])[0].split("/")[-1] if getattr(audio, "mime", None) else ""
        )
        if not track.source_codec:
            track.source_codec = _guess_codec(track.source_path)
    except Exception as exc:  # noqa: BLE001 - 损坏文件等均需兜底
        logger.warning("读取元数据失败 %s: %s", track.source_path, exc)
    return track


def _guess_codec(path: str) -> str:
    import os
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return {"mp3": "mp3", "wav": "pcm_s16le", "flac": "flac", "ogg": "vorbis"}.get(ext, ext)
