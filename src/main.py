"""Arma 3 音乐包管理器 — 应用入口。"""

import os
import sys

# 兼容两种启动方式：
#   python src/main.py   （脚本模式：无父包，相对导入失败）
#   python -m src.main   （模块模式：相对导入正常）
# 脚本模式下把仓库根目录加入 sys.path，按 `src.` 包方式导入。
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.app import create_main_window
else:
    from .app import create_main_window

from PySide6.QtWidgets import QApplication


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ArmaMusicPackManager")
    app.setOrganizationName("ArmaMusicPackManager")

    # 加载样式表（存在时）
    from pathlib import Path
    qss = Path(__file__).resolve().parent.parent / "resources" / "style.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))

    window = create_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
