"""全局常量定义。"""

# 支持的音频导入格式（白名单）
SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".aac", ".m4a", ".ogg", ".wma"}

# 目标格式（Arma 3 硬性要求）
TARGET_CONTAINER = "ogg"
TARGET_CODEC = "libvorbis"
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHANNELS = 2

# 可选目标比特率（kbps）
BITRATE_OPTIONS = [96, 112, 128, 160, 192, 256, 320]
DEFAULT_BITRATE = 128  # kbps

# Arma 3 命名约束
DEFAULT_SOUND_PREFIX = "douzi\\douzi_SAGA_music\\"
DEFAULT_CLASS_PREFIX = "douzi"
DEFAULT_REQUIRED_ADDONS = ["A3_Data_F"]
DEFAULT_REQUIRED_VERSION = "0.1"

# 项目文件扩展名
PROJECT_EXT = ".amp.json"

# 专辑内部名 → 类名前缀（用于生成 CfgMusic 类名）
# 用户自定义专辑时，从专辑内部名自动派生前缀
DEFAULT_ALBUM_PREFIX_MAP = {
    "Battlefield4": "BF4",
    "MedalOfHonor2010": "MOH2010",
    "MedalOfHonorWarfighter": "MOHWF",
    "ChinaMilSongBundle1": "CN_Mil_Song",
    "music": "Generic",
}
