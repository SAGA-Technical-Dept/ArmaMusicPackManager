"""config.cpp 生成器：按 Arma 3 规范渲染 CfgPatches / CfgMusicClasses / CfgMusic。

与参考范例 demo_files/douzi_SAGA_music/config.cpp 的约定保持一致：
- 制表符缩进，类 + 花括号结构
- sound[] 用反斜杠路径，前缀为 project.sound_prefix
- duration 保留 6 位小数
- 曲目类名：{class_prefix}_{album_prefix}_Track_{NN:02d}
  （专辑前缀为 "CN_Mil_Song" 时使用范例的特殊格式 {class_prefix}_{album_prefix}_{N}）
- name 自动加 NN- 编号前缀（范例格式），除非显示名已带编号
"""

from __future__ import annotations

import re

from ..models import Album, Project, Track
from ..utils.path_utils import to_backslash

_NUM_PREFIX_RE = re.compile(r"^\d+-")

_TAB = "\t"
_CN_MIL_PREFIX = "CN_Mil_Song"


def generate_config(project: Project) -> str:
    """生成完整 config.cpp 文本。"""
    parts = [
        _cfg_patches(project),
        _cfg_music_classes(project),
        _cfg_music(project),
    ]
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------- CfgPatches

def _cfg_patches(p: Project) -> str:
    lines = [
        "class CfgPatches",
        "{",
        f"{_TAB}class {p.mod_name}",
        f"{_TAB}{{",
        f"{_TAB}{_TAB}author = \"{p.author}\";",
        f"{_TAB}{_TAB}name = \"{p.display_name}\";",
        f"{_TAB}{_TAB}requiredAddons[] = {{{_join(p.required_addons)}}};",
        f"{_TAB}{_TAB}requiredVersion = {p.required_version};",
        f"{_TAB}{_TAB}units[] = {{}};",
        f"{_TAB}{_TAB}weapons[] = {{}};",
        f"{_TAB}}};",
        "};",
    ]
    return "\n".join(lines)


def _join(items: list[str]) -> str:
    return ", ".join(f'"{i}"' for i in items)


# ---------------------------------------------------------------- CfgMusicClasses

def _cfg_music_classes(p: Project) -> str:
    lines = ["class CfgMusicClasses", "{"]
    for album in p.albums.values():
        lines.append(f"{_TAB}class {album.cfg_class}")
        lines.append(f"{_TAB}{{")
        lines.append(f'{_TAB}{_TAB}displayname = "{album.display_name_zh}";')
        lines.append(f"{_TAB}}};")
    if p.unassigned_tracks():
        lines.append(f"{_TAB}class {p.generic_music_class}")
        lines.append(f"{_TAB}{{")
        lines.append(f'{_TAB}{_TAB}displayname = "{p.generic_music_display}";')
        lines.append(f"{_TAB}}};")
    lines.append("};")
    return "\n".join(lines)


# ---------------------------------------------------------------- CfgMusic

def _cfg_music(p: Project) -> str:
    blocks: list[str] = []

    # 专辑曲目（按专辑顺序，专辑内按 track_ids 顺序）
    for album in p.albums.values():
        for i, tid in enumerate(album.track_ids, start=1):
            track = p.tracks.get(tid)
            if track is None:
                continue
            blocks.append(_music_entry(p, track, album, i))

    # 未分配曲目（通用，编号续排）
    for i, track in enumerate(p.unassigned_tracks(), start=1):
        blocks.append(_music_entry(p, track, None, i))

    if not blocks:
        return "class CfgMusic\n{\n};"

    body = "\n\n".join(blocks)
    return f"class CfgMusic\n{{\n{body}\n}};"


def _music_entry(p: Project, track: Track, album: Album | None, index: int) -> str:
    """生成单个曲目条目。"""
    class_name = track_class_name(p, album, index)
    base = track.display_name_zh or track.display_name_en
    display = base if _NUM_PREFIX_RE.match(base) else f"{index:02d}-{base}"
    folder = album.name if album else "music"
    sound = to_backslash(f"{p.sound_prefix}{folder}\\{track.ogg_filename}")
    music_class = album.cfg_class if album else p.generic_music_class
    duration = f"{track.duration:.6f}"

    track.class_name = class_name
    track.config_name = display
    track.sound_path = sound
    track.music_class = music_class

    return (
        f"{_TAB}class {class_name}\n"
        f"{_TAB}{{\n"
        f'{_TAB}{_TAB}name = "{display}";\n'
        f'{_TAB}{_TAB}sound[] = {{"{sound}", 1.0, 1.0}};\n'
        f"{_TAB}{_TAB}duration = {duration};\n"
        f'{_TAB}{_TAB}musicClass = "{music_class}";\n'
        f"{_TAB}}};"
    )


def track_class_name(p: Project, album: Album | None, index: int) -> str:
    """生成 CfgMusic 类名。

    专辑模式：{class_prefix}_{album_prefix}_Track_{NN:02d}
    通用模式：{class_prefix}_Generic_Track_{NN:02d}
    CN 军歌（范例特殊）：{class_prefix}_{album_prefix}_{N}（无 0 填充、无 Track）
    """
    if album is None:
        return f"{p.class_prefix}_Generic_Track_{index:02d}"
    prefix = album.class_prefix
    if prefix == _CN_MIL_PREFIX:
        return f"{p.class_prefix}_{prefix}_{index}"
    return f"{p.class_prefix}_{prefix}_Track_{index:02d}"
