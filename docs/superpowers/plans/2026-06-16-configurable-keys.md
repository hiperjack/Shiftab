# 特殊キーの設定化＋全セクション並び替え Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 1列目の特殊キーを設定で自由に追加・並び替え・削除できるようにし、定型文・コマンドにも並び替えを追加する。

**Architecture:** 特殊キーを `config["keys"]`（表示名＋キートークン列）で表現する。`keysender` にトークン→VK 解決と汎用送出 `send_keys` を追加。`mainbar` は `cfg["keys"]` をグリッド描画。`settings_dialog` に操作キーグループ（候補メニュー＋カスタムビルダー）と3テーブル共通の並び替えを追加。

**Tech Stack:** Python 3.13 / PySide6 / ctypes(SendInput) / pytest

---

## File Structure

- `keysender.py`（変更）: VK 定数追加、`KEY_VK` マップ、`_resolve_token`、`send_keys`、`keys_to_label` を追加。送出ロジックの単一責務を維持。
- `config.py`（変更）: `DEFAULT_CONFIG["keys"]` 追加、`_merge_defaults` で `keys` を扱う、docstring 更新。
- `mainbar.py`（変更）: ハードコード特殊キー行を廃止し `cfg["keys"]` から動的生成（列数で折り返し）。
- `settings_dialog.py`（変更）: 「操作キー」グループ、候補メニュー、`CustomKeyDialog`、3テーブル共通の並び替え、`result_config` での `keys` 収集。
- `tests/test_keysender.py`（新規）: トークン解決・ラベル整形の単体テスト。
- `tests/test_config.py`（新規）: 既定値とマージの単体テスト。
- `tests/test_catalog.py`（新規）: 設定画面の候補プリセットが全て解決可能であることの整合テスト。
- `requirements-dev.txt`（新規）: `pytest`。

---

### Task 1: keysender — トークン解決と汎用送出

**Files:**
- Modify: `keysender.py`（VK 定数群の直後 `keysender.py:29` 付近、および末尾に関数追加）
- Create: `tests/test_keysender.py`
- Create: `requirements-dev.txt`

- [ ] **Step 1: dev 依存とテストディレクトリを用意**

Create `requirements-dev.txt`:

```
pytest>=8
```

- [ ] **Step 2: 失敗するテストを書く**

Create `tests/test_keysender.py`:

```python
import pytest

import keysender


def test_resolve_named_token():
    assert keysender._resolve_token("enter") == keysender.VK_RETURN
    assert keysender._resolve_token("ctrl") == keysender.VK_CONTROL
    assert keysender._resolve_token("left") == keysender.VK_LEFT


def test_resolve_single_char_token():
    # 1文字英数字は ord(大文字) で VK を導出
    assert keysender._resolve_token("c") == 0x43
    assert keysender._resolve_token("v") == 0x56
    assert keysender._resolve_token("7") == 0x37


def test_resolve_is_case_insensitive():
    assert keysender._resolve_token("Ctrl") == keysender.VK_CONTROL
    assert keysender._resolve_token("ENTER") == keysender.VK_RETURN


def test_resolve_unknown_raises():
    with pytest.raises(ValueError):
        keysender._resolve_token("nope")


def test_keys_to_label():
    assert keysender.keys_to_label(["ctrl", "c"]) == "Ctrl+C"
    assert keysender.keys_to_label(["shift", "tab"]) == "Shift+Tab"
    assert keysender.keys_to_label(["left"]) == "←"
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `python -m pytest tests/test_keysender.py -v`
Expected: FAIL（`_resolve_token` / `keys_to_label` が未定義、`VK_*` の一部が未定義）

- [ ] **Step 4: 最小実装を追加**

`keysender.py` の既存 VK 定数群（`keysender.py:20-29`）に不足分を追加する。`VK_DOWN = 0x28` の直後に挿入:

```python
VK_ESCAPE = 0x1B
VK_DELETE = 0x2E
VK_HOME = 0x24
VK_END = 0x23
VK_PRIOR = 0x21  # PageUp
VK_NEXT = 0x22   # PageDown
VK_MENU = 0x12   # Alt
VK_LWIN = 0x5B   # Windows キー
VK_V = 0x56
```

同ファイルの `ARROW_VK` 定義（`keysender.py:32-37`）の直後に名前→VK マップと表示マップを追加:

```python
# トークン名 → 仮想キーコード（名前付きキーのみ。1文字英数字は ord で導出）
KEY_VK = {
    "shift": VK_SHIFT,
    "ctrl": VK_CONTROL,
    "alt": VK_MENU,
    "win": VK_LWIN,
    "tab": VK_TAB,
    "enter": VK_RETURN,
    "esc": VK_ESCAPE,
    "backspace": VK_BACK,
    "delete": VK_DELETE,
    "left": VK_LEFT,
    "up": VK_UP,
    "down": VK_DOWN,
    "right": VK_RIGHT,
    "home": VK_HOME,
    "end": VK_END,
    "pageup": VK_PRIOR,
    "pagedown": VK_NEXT,
}

# トークン名 → ボタン/ツールチップ表示文字列
_TOKEN_DISPLAY = {
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "win": "Win",
    "tab": "Tab",
    "enter": "Enter",
    "esc": "Esc",
    "backspace": "Backspace",
    "delete": "Delete",
    "left": "←",
    "up": "↑",
    "down": "↓",
    "right": "→",
    "home": "Home",
    "end": "End",
    "pageup": "PgUp",
    "pagedown": "PgDn",
}
```

`keysender.py` 末尾（`send_text` の後）に関数を追加:

```python
def _resolve_token(token: str) -> int:
    """キートークン名を仮想キーコードに解決する。

    名前付きキーは KEY_VK を引く。1文字の英数字は ord(大文字) で導出する。
    未知のトークンは ValueError。
    """
    t = token.strip().lower()
    if t in KEY_VK:
        return KEY_VK[t]
    if len(t) == 1 and (t.isalpha() or t.isdigit()):
        return ord(t.upper())
    raise ValueError(f"unknown key token: {token!r}")


def send_keys(tokens: list[str]) -> None:
    """トークン名の並びをキーの組み合わせとして送る（例: ["ctrl","c"]）。"""
    if not tokens:
        return
    vks = [_resolve_token(t) for t in tokens]
    send_combo(vks)


def keys_to_label(tokens: list[str]) -> str:
    """トークンの並びを人間可読なラベルにする（例: ["ctrl","c"] → "Ctrl+C"）。"""
    return "+".join(_TOKEN_DISPLAY.get(t.lower(), t.upper()) for t in tokens)
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m pytest tests/test_keysender.py -v`
Expected: PASS（5件）

- [ ] **Step 6: コミット**

```bash
git add keysender.py tests/test_keysender.py requirements-dev.txt
git commit -m "feat: キートークン解決と汎用キー送出 send_keys を追加"
```

---

### Task 2: config — 特殊キーの既定値とマージ

**Files:**
- Modify: `config.py`（docstring `config.py:6-12`、`DEFAULT_CONFIG` `config.py:25-47`、`_merge_defaults` `config.py:60-71`）
- Create: `tests/test_config.py`

- [ ] **Step 1: 失敗するテストを書く**

Create `tests/test_config.py`:

```python
import config


def test_default_config_has_keys():
    keys = config.DEFAULT_CONFIG["keys"]
    assert isinstance(keys, list) and len(keys) >= 1
    first = keys[0]
    assert "label" in first and "keys" in first
    assert first["keys"] == ["shift", "tab"]


def test_merge_supplies_keys_when_missing():
    merged = config._merge_defaults({"phrases": [], "commands": []})
    assert merged["keys"] == config.DEFAULT_CONFIG["keys"]


def test_merge_keeps_existing_keys():
    custom = {"keys": [{"label": "⏎", "keys": ["enter"]}]}
    merged = config._merge_defaults(custom)
    assert merged["keys"] == [{"label": "⏎", "keys": ["enter"]}]


def test_merge_ignores_non_list_keys():
    merged = config._merge_defaults({"keys": "broken"})
    assert merged["keys"] == config.DEFAULT_CONFIG["keys"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL（`DEFAULT_CONFIG` に `keys` が無い）

- [ ] **Step 3: 最小実装を追加**

`config.py` の `DEFAULT_CONFIG` に `"phrases"` の前（`config.py:26` の直前）へ `keys` を追加:

```python
    "keys": [
        {"label": "⇧Tab", "keys": ["shift", "tab"]},
        {"label": "←", "keys": ["left"]},
        {"label": "↑", "keys": ["up"]},
        {"label": "↓", "keys": ["down"]},
        {"label": "→", "keys": ["right"]},
        {"label": "⌃C", "keys": ["ctrl", "c"]},
        {"label": "⌫", "keys": ["backspace"]},
    ],
```

`_merge_defaults`（`config.py:60-71`）の `cfg["window"].update(...)` 行の前に追加:

```python
    if isinstance(loaded.get("keys"), list):
        cfg["keys"] = loaded["keys"]
```

docstring のスキーマ（`config.py:6-12`）を更新し、`"keys": [{"label": str, "keys": [str]}],` の行を `"phrases"` の前に追記する。

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS（4件）

- [ ] **Step 5: コミット**

```bash
git add config.py tests/test_config.py
git commit -m "feat: 特殊キー設定 keys の既定値と後方互換マージを追加"
```

---

### Task 3: mainbar — 特殊キーを設定から動的描画

**Files:**
- Modify: `mainbar.py`（`_build_ui` の特殊キー行 `mainbar.py:133-159`）

このタスクは UI 描画のため自動テストは行わず、手動確認（Task 5）で検証する。

- [ ] **Step 1: ハードコード特殊キー行を置き換える**

`mainbar.py` の特殊キーブロック（`mainbar.py:133-159`、`# --- 特殊キー: Shift+Tab と矢印 ---` から `self._root.addLayout(special)` まで）を以下で置き換える:

```python
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
```

- [ ] **Step 2: 構文チェック**

Run: `python -c "import ast; ast.parse(open('mainbar.py',encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: 起動して描画を確認**

Run: `python main.py`（数秒表示して確認後、✕ で閉じる）
Expected: 既定の操作キー（⇧Tab・←↑↓→・⌃C・⌫）がグリッドで表示され、各ボタンが従来どおり動作する。

- [ ] **Step 4: コミット**

```bash
git add mainbar.py
git commit -m "feat: 操作キーを設定から動的生成しグリッド折り返し表示"
```

---

### Task 4: settings_dialog — 操作キー編集と並び替え

**Files:**
- Modify: `settings_dialog.py`（import、`__init__` `settings_dialog.py:40-48`、新規メソッド群、`_row_buttons` `settings_dialog.py:154-163`、`result_config` `settings_dialog.py:175-204`）
- Create: `tests/test_catalog.py`

- [ ] **Step 1: 候補プリセットの整合テストを書く（失敗）**

Create `tests/test_catalog.py`:

```python
import keysender
from settings_dialog import KEY_CATALOG


def test_catalog_entries_are_resolvable():
    # 候補の全トークンが keysender で解決できること
    for label, tokens in KEY_CATALOG:
        assert tokens, f"{label} has empty tokens"
        for t in tokens:
            keysender._resolve_token(t)  # raises if unknown


def test_catalog_has_enter():
    labels = [label for label, _ in KEY_CATALOG]
    assert any("Enter" in label or "⏎" in label for label in labels)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `set QT_QPA_PLATFORM=offscreen && python -m pytest tests/test_catalog.py -v`（PowerShell では `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_catalog.py -v`）
Expected: FAIL（`KEY_CATALOG` が未定義で ImportError）

- [ ] **Step 3: import とカタログ定数を追加**

`settings_dialog.py` の import 群（`settings_dialog.py:12-28`）に以下を追加:

```python
from PySide6.QtWidgets import (
    QComboBox,
    QMenu,
)
```

（既存の import ブロックへ `QComboBox` と `QMenu` を追記。重複に注意。）

import 直後、`class SettingsDialog` の前に `keysender` の import とカタログを追加:

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_catalog.py -v`
Expected: PASS（2件）

- [ ] **Step 5: コミット（カタログ）**

```bash
git add settings_dialog.py tests/test_catalog.py
git commit -m "feat: 設定画面の操作キー候補カタログを追加"
```

- [ ] **Step 6: 操作キーグループとカスタムダイアログを実装**

`settings_dialog.py` の `__init__` 内、`root.addWidget(self._build_phrases_group())`（`settings_dialog.py:41`）の前に追加:

```python
        root.addWidget(self._build_keys_group())
```

`class SettingsDialog` 内に以下のメソッドを追加（`_build_phrases_group` の前あたり）:

```python
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
```

`settings_dialog.py` の末尾（`class SettingsDialog` の外）に `CustomKeyDialog` を追加:

```python
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
```

- [ ] **Step 7: 3テーブル共通の並び替えを実装**

`settings_dialog.py` に `_move_row` を追加（`_remove_selected` の後 `settings_dialog.py:168` 付近）:

```python
    def _move_row(self, table: QTableWidget, delta: int) -> None:
        rows = sorted({idx.row() for idx in table.selectedIndexes()})
        if len(rows) != 1:
            return
        r = rows[0]
        target = r + delta
        if target < 0 or target >= table.rowCount():
            return
        # 行内容（各列の text / UserRole / セル widget）を入れ替える
        self._swap_rows(table, r, target)
        table.selectRow(target)

    def _swap_rows(self, table: QTableWidget, a: int, b: int) -> None:
        for col in range(table.columnCount()):
            wa = table.cellWidget(a, col)
            wb = table.cellWidget(b, col)
            if wa is not None or wb is not None:
                # セル widget（チェックボックス）はチェック状態を入れ替える
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
```

既存の定型文・コマンドの行ボタンにも ▲▼ を追加する。`_row_buttons`（`settings_dialog.py:154-163`）を以下に置き換える:

```python
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
```

- [ ] **Step 8: result_config で keys を収集**

`result_config`（`settings_dialog.py:175-204`）の `self._cfg["phrases"] = phrases` 行の前に追加:

```python
        keys = []
        for r in range(self.keys_table.rowCount()):
            key_item = self.keys_table.item(r, 1)
            tokens = key_item.data(Qt.UserRole) if key_item is not None else None
            if not tokens:
                continue
            label = self._cell_text(self.keys_table, r, 0) or keysender.keys_to_label(tokens)
            keys.append({"label": label, "keys": list(tokens)})
        self._cfg["keys"] = keys
```

- [ ] **Step 9: 構文チェックとテスト**

Run: `python -c "import ast; ast.parse(open('settings_dialog.py',encoding='utf-8').read()); print('OK')"`
Expected: `OK`

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -v`
Expected: 全テスト PASS

- [ ] **Step 10: コミット**

```bash
git add settings_dialog.py
git commit -m "feat: 操作キー編集・カスタムキー作成・3テーブル並び替えを追加"
```

---

### Task 5: 手動検証とビルド

**Files:** なし（検証とビルドのみ）

- [ ] **Step 1: 起動して総合動作を確認**

Run: `python main.py`
確認項目:
- 操作キーが既定セットでグリッド表示される。
- 設定画面の「操作キー」で候補から「⏎ Enter」を追加 → OK → Enter ボタンが増え、押すと改行送信される。
- ←→ を削除 → 左右矢印が消える。
- ▲▼ で操作キー・定型文・コマンドの並び替えができる。
- カスタムで Ctrl+Shift+P 等を作成でき、押下で送信される。
- 設定は閉じて再起動しても保持される。

- [ ] **Step 2: 既存プロセスを終了してビルド**

Run（PowerShell）:
```powershell
Stop-Process -Name Shiftab -Force -ErrorAction SilentlyContinue
```
Run: `pyinstaller --noconfirm Shiftab.spec`
Expected: `Build complete!`

- [ ] **Step 3: ビルド済み exe を起動して最終確認**

Run（PowerShell）: `Start-Process .\dist\Shiftab.exe`
Expected: ソースと同じ動作。

- [ ] **Step 4: 全テストを最終実行**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -v`
Expected: 全 PASS

---

## Self-Review

**Spec coverage:**
- データモデル `keys` → Task 2 ✓
- `send_keys` / トークン解決 → Task 1 ✓
- mainbar 動的描画＋列折り返し → Task 3 ✓
- 操作キーグループ・候補メニュー・カスタムビルダー → Task 4 ✓
- 3テーブル並び替え → Task 4（Step 7）✓
- result_config の keys 収集 → Task 4（Step 8）✓
- 後方互換マージ → Task 2 ✓
- テスト方針（keysender / config / カタログ整合）→ Task 1,2,4 ✓
- 当初要望（Enter追加・左右非表示・1列目設定化）→ Task 5 手動確認で網羅 ✓

**Placeholder scan:** プレースホルダなし。各コードステップに実コードを記載。

**Type consistency:**
- `keysender._resolve_token` / `send_keys` / `keys_to_label`：Task 1 で定義、Task 3/4 で同名利用 ✓
- `KEY_CATALOG` / `CustomKeyDialog` / `_MODIFIERS` / `_BASE_KEYS`：Task 4 内で定義・利用 ✓
- `_move_row(table, delta)` / `_swap_rows` / `_checkbox_state` / `_set_checkbox_state`：Task 4 で定義、`_row_buttons` と `_key_row_buttons` から利用 ✓
- config キー名 `keys` / エントリ `{"label","keys"}`：Task 2/3/4 で一貫 ✓
