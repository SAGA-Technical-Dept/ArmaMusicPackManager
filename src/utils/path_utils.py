"""路径与文件名处理工具。"""

import os
import re

_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_UNDERSCORES = re.compile(r"_+")


def to_backslash(path: str) -> str:
    """将路径统一为反斜杠形式（Arma 3 config 中 sound[] 路径的写法）。"""
    return path.replace("/", "\\")


def to_forward_slash(path: str) -> str:
    """将路径统一为正斜杠形式。"""
    return path.replace("\\", "/")


def sanitize_filename(name: str) -> str:
    """生成 Arma 3 安全文件名：替换非法字符、压缩连续下划线、去除首尾空白。

    注意：保留撇号（'），因为参考范例中存在含撇号的文件名且 Arma 3 可正常处理。
    """
    name = name.strip()
    name = _ILLEGAL_CHARS.sub("_", name)
    name = _UNDERSCORES.sub("_", name)
    name = name.strip("_")
    return name or "untitled"


def stem_without_ext(path: str) -> str:
    """返回不含扩展名的文件名。"""
    return os.path.splitext(os.path.basename(path))[0]


def relative_path(source_path: str, base_dir: str) -> str:
    """返回 source_path 相对于 base_dir 的路径（正斜杠）。"""
    return os.path.relpath(source_path, base_dir).replace("\\", "/")
