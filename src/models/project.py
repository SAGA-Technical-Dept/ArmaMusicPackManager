"""项目（模组）数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .album import Album
from .track import Track


@dataclass
class Project:
    """一个完整的 Arma 3 音乐模组项目。"""

    # 模组身份（→ CfgPatches）
    mod_name: str = ""                  # 模组类名 + 根目录名（如 "douzi_SAGA_music"）
    author: str = ""
    display_name: str = ""              # 显示名（name 字段）
    required_addons: list[str] = field(default_factory=lambda: ["A3_Data_F"])
    required_version: str = "0.1"

    # 路径与命名
    sound_prefix: str = ""              # sound[] 路径前缀（如 "douzi\\douzi_SAGA_music\\"）
    class_prefix: str = ""              # CfgMusic 类名前缀（如 "douzi"）

    # 通用曲目（未分配专辑）的 CfgMusicClasses 归属
    generic_music_class: str = "SAGA_Generic_Music"   # 类名（与范例一致）
    generic_music_display: str = "新增曲目"           # displayname

    # 内容
    albums: dict[str, Album] = field(default_factory=dict)  # album_id → Album
    tracks: dict[str, Track] = field(default_factory=dict)  # track_id → Track

    # 元数据
    project_file: str = ""              # .amp.json 保存路径
    _dirty: bool = field(default=False, repr=False)  # 未保存更改标记（不序列化）

    # ---- 脏状态 ----

    def mark_dirty(self) -> None:
        self._dirty = True

    def mark_clean(self) -> None:
        self._dirty = False

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    # ---- 便捷方法 ----

    def album_of(self, track: Track) -> Album | None:
        if track.album_id is None:
            return None
        return self.albums.get(track.album_id)

    def tracks_of(self, album: Album) -> list[Track]:
        return [self.tracks[tid] for tid in album.track_ids if tid in self.tracks]

    def unassigned_tracks(self) -> list[Track]:
        """未分配专辑的曲目（通用曲目）。"""
        return [t for t in self.tracks.values() if t.album_id is None]

    def to_dict(self) -> dict:
        return {
            "mod_name": self.mod_name,
            "author": self.author,
            "display_name": self.display_name,
            "required_addons": self.required_addons,
            "required_version": self.required_version,
            "sound_prefix": self.sound_prefix,
            "class_prefix": self.class_prefix,
            "generic_music_class": self.generic_music_class,
            "generic_music_display": self.generic_music_display,
            "albums": [a.to_dict() for a in self.albums.values()],
            "tracks": [t.to_dict() for t in self.tracks.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        p = cls()
        for k in ("mod_name", "author", "display_name", "required_addons",
                  "required_version", "sound_prefix", "class_prefix",
                  "generic_music_class", "generic_music_display", "project_file"):
            if k in d:
                setattr(p, k, d[k])
        for a in d.get("albums", []):
            album = Album.from_dict(a)
            p.albums[album.album_id] = album
        for t in d.get("tracks", []):
            track = Track.from_dict(t)
            p.tracks[track.track_id] = track
        return p
