"""专辑数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class Album:
    """一个专辑：对应 CfgMusicClasses 条目 + 模组中的一个子目录。"""

    album_id: str
    name: str = ""                  # 内部标识名，也用作子目录名（如 "Battlefield4"）
    display_name_zh: str = ""       # displayname（如 "专辑-战地风云4"）
    cfg_class: str = ""             # CfgMusicClasses 类名（如 "SAGA_Battlefield4_OST_Music"）
    class_prefix: str = ""          # 用于生成 CfgMusic 类名的前缀（如 "BF4"）
    target_bitrate: int = 128       # 该专辑统一比特率（kbps）
    track_ids: list[str] = None     # 曲目 UUID 列表（有序）

    def __post_init__(self):
        if self.track_ids is None:
            self.track_ids = []

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Album":
        known = {f: d[f] for f in cls.__dataclass_fields__ if f in d}
        return cls(**known)
