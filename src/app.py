"""应用组装：创建主窗口。"""

from .ui.main_window import MainWindow


def create_main_window() -> MainWindow:
    return MainWindow()
