"""Arma 3 音乐包管理器 — 应用入口。"""

import sys

from PySide6.QtWidgets import QApplication

from .app import create_main_window


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
