"""Arma 3 约束校验。"""

import re

_CFG_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_valid_cfg_class(name: str) -> bool:
    """config 类名必须匹配 Arma 3 标识符规则（字母/下划线开头，不含空格）。"""
    return bool(name) and bool(_CFG_CLASS_RE.match(name))


def validate_ogg_stream(codec: str, sample_rate: int, channels: int) -> list[str]:
    """校验 Ogg 文件是否符合 Arma 3 兼容要求，返回问题列表（空 = 合规）。"""
    problems = []
    if codec.lower() not in ("vorbis", "libvorbis"):
        problems.append(f"编码不是 Vorbis（当前 {codec}）")
    if sample_rate != 44100:
        problems.append(f"采样率不是 44100 Hz（当前 {sample_rate}）")
    if channels != 2:
        problems.append(f"声道数不是 2（当前 {channels}）")
    return problems
