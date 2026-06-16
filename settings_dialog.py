"""設定画面。

定型文・コマンドの追加／編集／削除と、外観（不透明度・ボタンサイズ・列数）を編集する。
OK で result_config() に反映後の設定 dict を返す。
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import keysender

# 「＋追加」メニューに出す候補: (表示名, トークン列)
KEY_CATALOG = [
    ("⇧Tab", ["shift", "tab"]),
    ("⏎ Enter", ["enter"]),
    ("Esc", ["esc"]),
    ("Tab", ["tab"]),
    ("←", ["left"]),
    ("↑", ["up"]),
    ("↓", ["down"]),
    ("→", ["right"]),
    ("⌃C", ["ctrl", "c"]),
    ("⌃V", ["ctrl", "v"]),
    ("Home", ["home"]),
    ("End", ["end"]),
    ("PgUp", ["pageup"]),
    ("PgDn", ["pagedown"]),
    ("Delete", ["delete"]),
    ("⌫", ["backspace"]),
]

# カスタムキー作成ダイアログ用
_MODIFIERS = [("Ctrl", "ctrl"), ("Shift", "shift"), ("Alt", "alt"), ("Win", "win")]
_BASE_KEYS = [
    ("(なし)", None),
    ("Enter", "enter"), ("Esc", "esc"), ("Tab", "tab"),
    ("Backspace", "backspace"), ("Delete", "delete"),
    ("←", "left"), ("↑", "up"), ("↓", "down"), ("→", "right"),
    ("Home", "home"), ("End", "end"), ("PgUp", "pageup"), ("PgDn", "pagedown"),
] + [(c.upper(), c) for c in "abcdefghijklmnopqrstuvwxyz"] \
  + [(str(d), str(d)) for d in range(10)]


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cfg = copy.deepcopy(cfg)
        self.setWindowTitle("Shiftab 設定")
        self.setMinimumWidth(520)
        # 親(MainBar)は非アクティブ化なので、ダイアログは通常通り操作できるよう独立表示
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)

        root = QVBoxLayout(self)
        root.addWidget(self._build_phrases_group())
        root.addWidget(self._build_commands_group())
        root.addWidget(self._build_appearance_group())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------- phrases
    def _build_phrases_group(self) -> QGroupBox:
        box = QGroupBox("定型文（押すと「文字列＋Enter」を送信）")
        layout = QVBoxLayout(box)

        self.phrase_table = QTableWidget(0, 2)
        self.phrase_table.setHorizontalHeaderLabels(["表示名", "送信する文字列"])
        self._setup_table(self.phrase_table)
        for item in self._cfg.get("phrases", []):
            self._add_phrase_row(item.get("label", ""), item.get("text", ""))
        layout.addWidget(self.phrase_table)
        layout.addLayout(
            self._row_buttons(
                lambda: self._add_phrase_row("", ""),
                self.phrase_table,
            )
        )
        return box

    def _add_phrase_row(self, label: str, text: str) -> None:
        r = self.phrase_table.rowCount()
        self.phrase_table.insertRow(r)
        self.phrase_table.setItem(r, 0, QTableWidgetItem(label))
        self.phrase_table.setItem(r, 1, QTableWidgetItem(text))

    # ------------------------------------------------------------ commands
    def _build_commands_group(self) -> QGroupBox:
        box = QGroupBox("コマンド")
        layout = QVBoxLayout(box)

        hint = QLabel(
            "・「単独実行」ON … コマンド＋Enter（例: /model でピッカーを開く）\n"
            "・「単独実行」OFF … コマンド＋半角スペースのみ（Enterなし）。続けて定型文ボタンで補完"
        )
        hint.setStyleSheet("color:#888; font-size:11px;")
        layout.addWidget(hint)

        self.command_table = QTableWidget(0, 3)
        self.command_table.setHorizontalHeaderLabels(["表示名", "コマンド", "単独実行(Enter)"])
        self._setup_table(self.command_table)
        for item in self._cfg.get("commands", []):
            self._add_command_row(
                item.get("label", ""),
                item.get("command", ""),
                bool(item.get("auto_enter", True)),
            )
        layout.addWidget(self.command_table)
        layout.addLayout(
            self._row_buttons(
                lambda: self._add_command_row("", "", True),
                self.command_table,
            )
        )
        return box

    def _add_command_row(self, label: str, command: str, auto_enter: bool) -> None:
        r = self.command_table.rowCount()
        self.command_table.insertRow(r)
        self.command_table.setItem(r, 0, QTableWidgetItem(label))
        self.command_table.setItem(r, 1, QTableWidgetItem(command))
        chk = QCheckBox()
        chk.setChecked(auto_enter)
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setAlignment(Qt.AlignCenter)
        wl.addWidget(chk)
        self.command_table.setCellWidget(r, 2, wrap)

    # ---------------------------------------------------------- appearance
    def _build_appearance_group(self) -> QGroupBox:
        box = QGroupBox("外観")
        layout = QHBoxLayout(box)
        win = self._cfg.get("window", {})

        layout.addWidget(QLabel("不透明度"))
        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.3, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setValue(float(win.get("opacity", 0.95)))
        layout.addWidget(self.opacity_spin)

        layout.addWidget(QLabel("ボタンサイズ"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(32, 120)
        self.size_spin.setValue(int(win.get("button_size", 56)))
        layout.addWidget(self.size_spin)

        layout.addWidget(QLabel("列数"))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 12)
        self.cols_spin.setValue(int(win.get("columns", 6)))
        layout.addWidget(self.cols_spin)
        layout.addStretch(1)
        return box

    # --------------------------------------------------------------- utils
    def _setup_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMaximumHeight(160)

    def _row_buttons(self, add_fn, table: QTableWidget) -> QHBoxLayout:
        bar = QHBoxLayout()
        add = QPushButton("＋ 追加")
        add.clicked.connect(add_fn)
        remove = QPushButton("－ 削除")
        remove.clicked.connect(lambda: self._remove_selected(table))
        bar.addWidget(add)
        bar.addWidget(remove)
        bar.addStretch(1)
        return bar

    def _remove_selected(self, table: QTableWidget) -> None:
        rows = sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True)
        for r in rows:
            table.removeRow(r)

    # -------------------------------------------------------------- result
    def _cell_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        return item.text().strip() if item is not None else ""

    def result_config(self) -> dict:
        """ダイアログの内容を反映した設定 dict を返す。"""
        phrases = []
        for r in range(self.phrase_table.rowCount()):
            text = self._cell_text(self.phrase_table, r, 1)
            if not text:
                continue
            label = self._cell_text(self.phrase_table, r, 0) or text
            phrases.append({"label": label, "text": text})

        commands = []
        for r in range(self.command_table.rowCount()):
            command = self._cell_text(self.command_table, r, 1)
            if not command:
                continue
            label = self._cell_text(self.command_table, r, 0) or command
            wrap = self.command_table.cellWidget(r, 2)
            chk = wrap.findChild(QCheckBox) if wrap is not None else None
            auto_enter = chk.isChecked() if chk is not None else True
            commands.append(
                {"label": label, "command": command, "auto_enter": auto_enter}
            )

        self._cfg["phrases"] = phrases
        self._cfg["commands"] = commands
        self._cfg.setdefault("window", {})
        self._cfg["window"]["opacity"] = round(self.opacity_spin.value(), 2)
        self._cfg["window"]["button_size"] = self.size_spin.value()
        self._cfg["window"]["columns"] = self.cols_spin.value()
        return self._cfg
