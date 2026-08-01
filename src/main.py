"""Arma 3 音乐包管理器 — 应用入口。"""

import os
import shutil
import sys

# 兼容两种启动方式：
#   python src/main.py   （脚本模式：无父包，相对导入失败）
#   python -m src.main   （模块模式：相对导入正常）
# 脚本模式下把仓库根目录加入 sys.path，按 `src.` 包方式导入。
# PyInstaller 打包后 (sys.frozen) 模块已内嵌，无需路径操作。
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.app import create_main_window
    from src.utils.path_utils import resource_path
else:
    from .app import create_main_window
    from .utils.path_utils import resource_path

from PySide6.QtWidgets import QApplication


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ArmaMusicPackManager")
    app.setOrganizationName("ArmaMusicPackManager")

    # 加载样式表（存在时）
    qss = resource_path("resources/style.qss")
    if os.path.isfile(qss):
        with open(qss, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # ffmpeg 启动检测（转码依赖系统 ffmpeg CLI，缺失时仅警告、不阻塞启动）
    if not shutil.which("ffmpeg"):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            None, "缺少依赖",
            "未在系统路径中找到 ffmpeg。\n\n"
            "音频转码功能依赖 ffmpeg 命令行工具。\n"
            "请安装 ffmpeg 并将其添加到 PATH 环境变量中。\n\n"
            "下载地址: https://ffmpeg.org/download.html\n\n"
            "其他功能（导入、管理、配置生成、AI 翻译）不受影响。",
        )

    window = create_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
