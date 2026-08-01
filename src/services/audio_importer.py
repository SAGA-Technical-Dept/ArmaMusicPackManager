"""音频导入服务：文件扫描、格式白名单过滤、去重。"""

from __future__ import annotations

import os
import re
import uuid

from ..models import Track
from ..utils.constants import SUPPORTED_AUDIO_EXTS
from ..utils.path_utils import sanitize_filename, stem_without_ext


def scan_paths(paths: list[str]) -> list[str]:
    """将用户提供的文件/文件夹列表展开为支持的音频文件路径列表。

    - 文件：按扩展名白名单过滤
    - 文件夹：递归扫描
    """
    files: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                for name in names:
                    if os.path.splitext(name)[1].lower() in SUPPORTED_AUDIO_EXTS:
                        files.append(os.path.join(root, name))
        elif os.path.isfile(p) and os.path.splitext(p)[1].lower() in SUPPORTED_AUDIO_EXTS:
            files.append(p)
    return sorted(set(files))


def create_tracks(paths: list[str], existing: set[str]) -> list[Track]:
    """为扫描到的文件创建 Track 对象（跳过已存在的 source_path）。

    existing 是原始路径集合（相对/绝对均可），内部统一用
    normcase(abspath()) 规范化后比较，保证去重可靠。
    """
    seen = {os.path.normcase(os.path.abspath(p)) for p in existing}
    tracks: list[Track] = []
    for path in scan_paths(paths):
        norm = os.path.normcase(os.path.abspath(path))
        if norm in seen:
            continue
        stem = stem_without_ext(path)
        tracks.append(Track(
            track_id=uuid.uuid4().hex,
            source_path=path,
            ogg_filename=f"{sanitize_filename(stem)}.ogg",
            display_name_en=friendly_name(stem),
        ))
        seen.add(norm)
    return tracks


def friendly_name(stem: str) -> str:
    """从文件名生成友好显示名：下划线转空格、压缩多余空白。

    参考范例的 name 字段形式，如 "Battlefield 4 Stutter Theme"。
    连字符保留（范例中 "Hunter-Killer"、"H-Hour" 均保留原连字符）。
    """
    name = stem.replace("_", " ").strip()
    name = re.sub(r"\s+", " ", name)
    return name
