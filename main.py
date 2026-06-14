"""Shiftab — Claude Code 用ソフトキーボード（Windows）。

常時最前面・非アクティブ化のフローティングバーを表示する。
ボタンを押すと、フォーカスを保持したまま操作対象（ターミナル等）へキーが送られる。
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from mainbar import MainBar


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Shiftab")
    # 最後のウィンドウを閉じたら終了
    app.setQuitOnLastWindowClosed(True)

    bar = MainBar()
    bar.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
