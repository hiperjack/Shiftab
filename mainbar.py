"""フローティングバー本体（非アクティブ化・常時最前面）。

クリックしてもフォーカスを奪わないよう、ウィンドウ生成後に拡張スタイル
WS_EX_NOACTIVATE を付与する。これにより操作対象（ターミナル）のフォーカスが
残り、SendInput がそこへ届く。
"""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config as config_mod
import keysender
from settings_dialog import SettingsDialog

# 拡張ウィンドウスタイル定数
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOPMOST = 0x00000008

# SetWindowPos フラグ（スタイル変更をタスクバーに反映させる frame-changed 通知用）
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SW_HIDE = 0
SW_SHOWNA = 8  # アクティブ化せずに表示


def _apply_no_activate(hwnd: int) -> None:
    """HWND に WS_EX_NOACTIVATE を付与してフォーカスを奪わないようにしつつ、
    WS_EX_APPWINDOW を付けてタスクバーに（アプリ独自アイコンで）表示させる。"""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    get_long = user32.GetWindowLongPtrW
    set_long = user32.SetWindowLongPtrW
    get_long.restype = ctypes.c_longlong
    set_long.restype = ctypes.c_longlong
    ex = get_long(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
    # 非アクティブ化＋常時最前面＋タスクバー表示。ツールウィンドウ化は外す。
    ex |= WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_APPWINDOW
    ex &= ~WS_EX_TOOLWINDOW
    set_long(ctypes.c_void_p(hwnd), GWL_EXSTYLE, ex)
    # frame-changed を通知し、タスクバーボタンを再評価させる。
    user32.SetWindowPos(
        ctypes.c_void_p(hwnd), None, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )
    # WS_EX_APPWINDOW をタスクバーに確実に反映させるため、非アクティブのまま
    # 隠して再表示する（ShowWindow はネイティブ呼び出しで Qt の showEvent を
    # 再帰させない）。
    user32.ShowWindow(ctypes.c_void_p(hwnd), SW_HIDE)
    user32.ShowWindow(ctypes.c_void_p(hwnd), SW_SHOWNA)


class MainBar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = config_mod.load_config()
        self._drag_offset: QPoint | None = None

        self.setWindowTitle("Shiftab")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            # Qt.Tool は付けない（タスクバーに表示するため）。
            # タスクバー非表示化は _apply_no_activate 側で WS_EX_TOOLWINDOW を
            # 外し WS_EX_APPWINDOW を付けて制御する。
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # Qt.Tool ウィンドウは既定で WA_QuitOnClose=False となり、✕ で閉じても
        # プロセスが残ってしまう。明示的に True にして、最後の窓を閉じたら
        # プロセスごと終了するようにする。
        self.setAttribute(Qt.WA_QuitOnClose, True)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(6, 6, 6, 6)
        self._root.setSpacing(6)

        self._build_ui()
        self._apply_window_settings()

    # ------------------------------------------------------------------ UI
    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _build_ui(self) -> None:
        self._clear_layout(self._root)

        size = int(self.cfg["window"].get("button_size", 56))
        cols = max(1, int(self.cfg["window"].get("columns", 6)))

        # --- ヘッダ（ドラッグ取っ手 + 設定 + 閉じる） ---
        header = QHBoxLayout()
        handle = QLabel("⠿ Shiftab")
        handle.setStyleSheet("color:#888; font-weight:bold;")
        header.addWidget(handle)
        header.addStretch(1)

        gear = QPushButton("⚙")
        gear.setFixedSize(28, 24)
        gear.setToolTip("設定")
        gear.clicked.connect(self._open_settings)
        header.addWidget(gear)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 24)
        close_btn.setToolTip("閉じる")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        self._root.addLayout(header)

        # --- 操作キー（設定 cfg["keys"] から動的生成、列数で折り返し） ---
        keys = self.cfg.get("keys", [])
        if keys:
            grid = QGridLayout()
            grid.setSpacing(4)
            for i, item in enumerate(keys):
                tokens = item.get("keys", [])
                if not tokens:
                    continue
                label = item.get("label") or keysender.keys_to_label(tokens)
                b = self._make_button(label, size, height=size)
                b.setToolTip(keysender.keys_to_label(tokens))
                b.clicked.connect(
                    lambda _checked=False, ks=list(tokens): keysender.send_keys(ks)
                )
                grid.addWidget(b, i // cols, i % cols)
            self._root.addLayout(grid)

        # --- 定型文ボタン ---
        if self.cfg["phrases"]:
            self._root.addWidget(self._section_label("定型文（文字列＋Enter）"))
            grid = QGridLayout()
            grid.setSpacing(4)
            for i, item in enumerate(self.cfg["phrases"]):
                text = item.get("text", "")
                label = item.get("label") or text
                b = self._make_button(label, size * 2, height=size)
                b.setToolTip(text)
                b.clicked.connect(lambda _checked=False, t=text: self._send_phrase(t))
                grid.addWidget(b, i // cols, i % cols)
            self._root.addLayout(grid)

        # --- コマンドボタン ---
        if self.cfg["commands"]:
            self._root.addWidget(self._section_label("コマンド"))
            grid = QGridLayout()
            grid.setSpacing(4)
            for i, item in enumerate(self.cfg["commands"]):
                cmd = item.get("command", "")
                label = item.get("label") or cmd
                auto = bool(item.get("auto_enter", True))
                b = self._make_button(label, size * 2, height=size)
                tip = f"{cmd} + Enter" if auto else f"{cmd} （Enterなし／文章ボタンで補完）"
                b.setToolTip(tip)
                b.clicked.connect(
                    lambda _checked=False, c=cmd, a=auto: self._send_command(c, a)
                )
                grid.addWidget(b, i // cols, i % cols)
            self._root.addLayout(grid)

        self.adjustSize()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#aaa; font-size:10px;")
        return lbl

    def _make_button(self, text: str, width: int, height: int) -> QPushButton:
        b = QPushButton(text)
        b.setMinimumSize(width, height)
        b.setFocusPolicy(Qt.NoFocus)  # ボタン自身にフォーカスを残さない
        return b

    # ------------------------------------------------------------- handlers
    def _send_phrase(self, text: str) -> None:
        # 送信中だけ送信先の IME をオフにする（重複入力・Enter 不達の回避）。
        with keysender.ime_disabled():
            keysender.send_text(text)
            keysender.send_enter()

    def _send_command(self, command: str, auto_enter: bool) -> None:
        # 送信中だけ送信先の IME をオフにする（重複入力・Enter 不達の回避）。
        with keysender.ime_disabled():
            if auto_enter:
                keysender.send_text(command)
                keysender.send_enter()
            else:
                # 引数待ち: コマンド + 半角スペースのみ。Enter は押さない。
                keysender.send_text(command + " ")

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            self.cfg = dlg.result_config()
            config_mod.save_config(self.cfg)
            self._build_ui()
            self._apply_window_settings()

    # ------------------------------------------------------- window helpers
    def _apply_window_settings(self) -> None:
        win = self.cfg.get("window", {})
        self.setWindowOpacity(float(win.get("opacity", 0.95)))
        x, y = win.get("x"), win.get("y")
        if isinstance(x, int) and isinstance(y, int):
            x, y = self._ensure_on_screen(x, y)
            self.move(x, y)

    def _ensure_on_screen(self, x: int, y: int) -> tuple[int, int]:
        """保存座標がいずれの画面にも乗っていなければ可視範囲へ補正する。

        モニタ構成が2画面→1画面に変わると、旧位置がオフスクリーンになり
        ウィンドウが見えなくなるため、左上点が現在の画面範囲外なら
        プライマリ画面内へクランプする。
        """
        # ウィンドウサイズ確定前でも安全なよう sizeHint で見積もる
        size = self.size()
        w = size.width() or self.sizeHint().width()
        h = size.height() or self.sizeHint().height()
        for screen in QGuiApplication.screens():
            geo = screen.availableGeometry()
            # 左上付近が画面内にあれば可視とみなす
            if geo.contains(QPoint(x + 10, y + 10)):
                return x, y

        # どの画面にも乗っていない → プライマリ画面内にクランプ
        primary = QGuiApplication.primaryScreen()
        geo = primary.availableGeometry() if primary else QRect(0, 0, 1920, 1080)
        max_x = max(geo.left(), geo.right() - w)
        max_y = max(geo.top(), geo.bottom() - h)
        new_x = min(max(x, geo.left()), max_x)
        new_y = min(max(y, geo.top()), max_y)
        return new_x, new_y

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # ウィンドウ生成後に非アクティブ化スタイルを付与
        if sys.platform == "win32":
            _apply_no_activate(int(self.winId()))

    def _save_position(self) -> None:
        self.cfg.setdefault("window", {})
        self.cfg["window"]["x"] = self.x()
        self.cfg["window"]["y"] = self.y()
        config_mod.save_config(self.cfg)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_position()
        super().closeEvent(event)

    # ------------------------------------------------------------- dragging
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self._drag_offset = None
            self._save_position()
            event.accept()
