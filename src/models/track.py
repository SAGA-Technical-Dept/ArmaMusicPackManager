"""曲目数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Track:
    """一首曲目：从源文件导入到最终 config 输出的全程数据。"""

    track_id: str
    source_path: str
    ogg_filename: str = ""          # 目标 Ogg 文件名（如 "Battlefield_Theme.ogg"）
    display_name_en: str = ""       # 英文显示名（从文件名提取）
    display_name_zh: str = ""       # 中文显示名（AI 翻译或手动输入）

    # 音频属性（导入时通过 mutagen 读取）
    duration: float = 0.0           # 时长（秒）
    sample_rate: int = 0
    channels: int = 0
    source_codec: str = ""          # 源编码（mp3/flac/wav/ogg/...）
    source_bitrate: int = 0         # 源比特率（bps）

    # 专辑归属
    album_id: str | None = None     # 所属专辑 UUID，None = 未分配（通用曲目）
    track_index: int = 0            # 在专辑中的序号（1-based）

    # 转码
    target_bitrate: int = 128       # 目标比特率（kbps）
    transcode_status: str = "pending"  # pending/done/skipped/error
    transcode_error: str = ""

    # config.cpp 输出字段（由 config_generator 填充）
    class_name: str = ""            # CfgMusic 类名，如 "douzi_BF4_Track_01"
    config_name: str = ""           # name 字段值
    sound_path: str = ""            # sound[] 路径
    music_class: str = ""           # musicClass 引用

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        known = {f: d[f] for f in cls.__dataclass_fields__ if f in d}
        return cls(**known)
