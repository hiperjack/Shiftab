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
        root.addWidget(self._build_keys_group())
        root.addWidget(self._build_phrases_group())
        root.addWidget(self._build_commands_group())
        root.addWidget(self._build_appearance_group())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ---------------------------------------------------------- 操作キー
    def _build_keys_group(self) -> QGroupBox:
        box = QGroupBox("操作キー（1回押すとそのキー／組み合わせを送信）")
        layout = QVBoxLayout(box)

        self.keys_table = QTableWidget(0, 2)
        self.keys_table.setHorizontalHeaderLabels(["表示名", "キー"])
        self._setup_table(self.keys_table)
        for item in self._cfg.get("keys", []):
            self._add_key_row(item.get("label", ""), item.get("keys", []))
        layout.addWidget(self.keys_table)
        layout.addLayout(self._key_row_buttons())
        return box

    def _add_key_row(self, label: str, tokens: list) -> None:
        tokens = list(tokens)
        r = self.keys_table.rowCount()
        self.keys_table.insertRow(r)
        self.keys_table.setItem(r, 0, QTableWidgetItem(label or keysender.keys_to_label(tokens)))
        key_item = QTableWidgetItem(keysender.keys_to_label(tokens))
        key_item.setData(Qt.UserRole, tokens)
        key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)  # キー列は直接編集不可
        self.keys_table.setItem(r, 1, key_item)

    def _key_row_buttons(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        add = QPushButton("＋ 追加")
        menu = QMenu(add)
        for label, tokens in KEY_CATALOG:
            act = menu.addAction(label)
            act.triggered.connect(
                lambda _checked=False, l=label, t=list(tokens): self._add_key_row(l, t)
            )
        menu.addSeparator()
        custom = menu.addAction("カスタム…")
        custom.triggered.connect(self._add_custom_key)
        add.setMenu(menu)

        remove = QPushButton("－ 削除")
        remove.clicked.connect(lambda: self._remove_selected(self.keys_table))
        up = QPushButton("▲")
        up.clicked.connect(lambda: self._move_row(self.keys_table, -1))
        down = QPushButton("▼")
        down.clicked.connect(lambda: self._move_row(self.keys_table, 1))
        for w in (add, remove, up, down):
            bar.addWidget(w)
        bar.addStretch(1)
        return bar

    def _add_custom_key(self) -> None:
        dlg = CustomKeyDialog(self)
        if dlg.exec():
            tokens = dlg.tokens()
            if tokens:
                self._add_key_row(keysender.keys_to_label(tokens), tokens)

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
        up = QPushButton("▲")
        up.clicked.connect(lambda: self._move_row(table, -1))
        down = QPushButton("▼")
        down.clicked.connect(lambda: self._move_row(table, 1))
        for w in (add, remove, up, down):
            bar.addWidget(w)
        bar.addStretch(1)
        return bar

    def _remove_selected(self, table: QTableWidget) -> None:
        rows = sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True)
        for r in rows:
            table.removeRow(r)

    def _move_row(self, table: QTableWidget, delta: int) -> None:
        rows = sorted({idx.row() for idx in table.selectedIndexes()})
        if len(rows) != 1:
            return
        r = rows[0]
        target = r + delta
        if target < 0 or target >= table.rowCount():
            return
        self._swap_rows(table, r, target)
        table.selectRow(target)

    def _swap_rows(self, table: QTableWidget, a: int, b: int) -> None:
        """2行の内容を入れ替える。

        各列は同種（全行プレーンな item か、全行セル widget か）であることを前提とする。
        現状の3テーブルはこの前提を満たす（コマンド表の3列目のみ常にチェックボックス）。
        """
        for col in range(table.columnCount()):
            wa = table.cellWidget(a, col)
            wb = table.cellWidget(b, col)
            if wa is not None or wb is not None:
                ca = self._checkbox_state(table, a, col)
                cb = self._checkbox_state(table, b, col)
                self._set_checkbox_state(table, a, col, cb)
                self._set_checkbox_state(table, b, col, ca)
            else:
                ia = table.takeItem(a, col)
                ib = table.takeItem(b, col)
                table.setItem(a, col, ib)
                table.setItem(b, col, ia)

    def _checkbox_state(self, table: QTableWidget, row: int, col: int):
        wrap = table.cellWidget(row, col)
        if wrap is None:
            return None
        chk = wrap.findChild(QCheckBox)
        return chk.isChecked() if chk is not None else None

    def _set_checkbox_state(self, table: QTableWidget, row: int, col: int, state) -> None:
        if state is None:
            return
        wrap = table.cellWidget(row, col)
        if wrap is None:
            return
        chk = wrap.findChild(QCheckBox)
        if chk is not None:
            chk.setChecked(bool(state))

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

        keys = []
        for r in range(self.keys_table.rowCount()):
            key_item = self.keys_table.item(r, 1)
            tokens = key_item.data(Qt.UserRole) if key_item is not None else None
            if not tokens:
                continue
            label = self._cell_text(self.keys_table, r, 0) or keysender.keys_to_label(tokens)
            keys.append({"label": label, "keys": list(tokens)})
        self._cfg["keys"] = keys

        self._cfg["phrases"] = phrases
        self._cfg["commands"] = commands
        self._cfg.setdefault("window", {})
        self._cfg["window"]["opacity"] = round(self.opacity_spin.value(), 2)
        self._cfg["window"]["button_size"] = self.size_spin.value()
        self._cfg["window"]["columns"] = self.cols_spin.value()
        return self._cfg


class CustomKeyDialog(QDialog):
    """修飾キー（Ctrl/Shift/Alt/Win）＋ベースキーから組み合わせを作る。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("カスタムキー")
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        root = QVBoxLayout(self)

        root.addWidget(QLabel("修飾キー"))
        mod_row = QHBoxLayout()
        self._mod_checks = []
        for label, token in _MODIFIERS:
            chk = QCheckBox(label)
            self._mod_checks.append((chk, token))
            mod_row.addWidget(chk)
        mod_row.addStretch(1)
        root.addLayout(mod_row)

        base_row = QHBoxLayout()
        base_row.addWidget(QLabel("キー"))
        self._base = QComboBox()
        for label, token in _BASE_KEYS:
            self._base.addItem(label, token)
        base_row.addWidget(self._base)
        base_row.addStretch(1)
        root.addLayout(base_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def tokens(self) -> list:
        result = [token for chk, token in self._mod_checks if chk.isChecked()]
        base = self._base.currentData()
        if base is not None:
            result.append(base)
        return result
