"""Shiftab — Claude Code 用ソフトキーボード（Windows）。

常時最前面・非アクティブ化のフローティングバーを表示する。
ボタンを押すと、フォーカスを保持したまま操作対象（ターミナル等）へキーが送られる。
"""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from mainbar import MainBar

# 注: スタンドアロン exe では AppUserModelID をあえて宣言しない。
# 独自 AUMID を宣言すると、対応するショートカットが無い場合に
# タスクバーへのピン留めアイコンが解決できず既定アイコン化するため、
# Windows に exe 自身をアイデンティティとして扱わせる（埋め込みアイコンが使われる）。


def _resource_path(name: str) -> str:
    """同梱リソースの絶対パスを返す（PyInstaller onefile では _MEIPASS 配下）。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Shiftab")
    app.setWindowIcon(QIcon(_resource_path("icon.ico")))
    # 最後のウィンドウを閉じたら終了
    app.setQuitOnLastWindowClosed(True)

    bar = MainBar()
    bar.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
