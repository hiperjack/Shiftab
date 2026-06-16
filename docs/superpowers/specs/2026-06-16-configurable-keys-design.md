# 特殊キーの設定化＋全セクション並び替え — 設計

作成日: 2026-06-16

## 背景と目的

Shiftab のボタンは現在3種類ある。

1. **特殊キー行**（⇧Tab・←↑↓→・⌃C・⌫）: `mainbar.py` にハードコードされ、表示内容も並び順も変更できない。
2. **定型文**: 設定画面で追加・編集・削除できる。
3. **コマンド**: 設定画面で追加・編集・削除できる。

ユーザー要望は「キーを自由に追加・並び替え・削除したい」。具体的には Enter ボタンの追加、左右矢印の非表示、1列目（特殊キー行）の設定化。要望の核心は **特殊キー行が固定で変えられない点** と **並び替え手段が無い点** に集約される。

本設計では、特殊キー行を定型文・コマンドと同等にユーザー設定可能にし、3セクションすべてに並び替えを追加する。

## スコープ

- 特殊キー行を `config` 駆動にする（候補から選択＋任意のキー組み立ての両対応）。
- 特殊キーは「列数」設定に従ってグリッド状に折り返す（定型文・コマンドと同じ見た目）。
- 操作キー・定型文・コマンドの3テーブルに並び替え（▲▼）を追加。

非スコープ:

- 定型文・コマンドのデータ構造変更（現状維持）。
- 全ボタンの単一リストへの統合（今回は行わない）。

## データモデル（config.py）

新キー `keys` を追加する。各エントリは「表示名＋キートークンの並び」。

```json
"keys": [
  {"label": "⇧Tab", "keys": ["shift", "tab"]},
  {"label": "←", "keys": ["left"]},
  {"label": "↑", "keys": ["up"]},
  {"label": "↓", "keys": ["down"]},
  {"label": "→", "keys": ["right"]},
  {"label": "⌃C", "keys": ["ctrl", "c"]},
  {"label": "⌫", "keys": ["backspace"]}
]
```

- 既定値（`DEFAULT_CONFIG["keys"]`）は現状のハードコード一式。Enter は既定には含めず、候補として用意する。
- 単独キーも組み合わせも「トークンの並び」に統一。単独キーは長さ1の並びとして扱う。
- 後方互換: 既存 config に `keys` が無ければ `_merge_defaults` が既定を補う。`isinstance(loaded.get("keys"), list)` のときのみ採用。
- スキーマ docstring（config.py 冒頭）に `keys` を追記する。

## キー送出（keysender.py）

トークン名 → VK のマップ `KEY_VK` を定義し、汎用関数 `send_keys(tokens: list[str])` を追加する。内部は既存の `send_combo` に委譲する。

```python
KEY_VK = {
    "shift": VK_SHIFT, "ctrl": VK_CONTROL, "alt": VK_MENU, "win": VK_LWIN,
    "tab": VK_TAB, "enter": VK_RETURN, "esc": VK_ESCAPE,
    "backspace": VK_BACK, "delete": VK_DELETE,
    "left": VK_LEFT, "up": VK_UP, "down": VK_DOWN, "right": VK_RIGHT,
    "home": VK_HOME, "end": VK_END, "pageup": VK_PRIOR, "pagedown": VK_NEXT,
    # a-z, 0-9 は ord() ベースで動的に解決（"a"→0x41 等）
}

def send_keys(tokens: list[str]) -> None:
    vks = [_resolve_token(t) for t in tokens]
    send_combo(vks)
```

- `_resolve_token`: `KEY_VK` を引き、無ければ1文字英数字なら `ord(token.upper())` で VK を導出。未知トークンは `ValueError`。
- 追加で必要な VK 定数（`VK_MENU=0x12`, `VK_LWIN=0x5B`, `VK_ESCAPE=0x1B`, `VK_DELETE=0x2E`, `VK_HOME=0x24`, `VK_END=0x23`, `VK_PRIOR=0x21`, `VK_NEXT=0x22`, `VK_V=0x56` など）を定義。
- 既存の `send_shift_tab` / `send_ctrl_c` / `send_backspace` / `send_arrow` / `send_enter` はそのまま残す（互換のため）。UI からの呼び出しは `send_keys` に一本化する。

## 表示（mainbar.py）

`_build_ui` のハードコード特殊キー行を廃止し、`cfg["keys"]` をループしてボタン生成する。

- ボタンは「列数」(`columns`) 設定に従って `QGridLayout` で折り返す（定型文と同じ方式: `grid.addWidget(b, i // cols, i % cols)`）。
- 各ボタンの `clicked` は `lambda _=False, ks=item["keys"]: keysender.send_keys(ks)`。
- ツールチップはトークンを人間可読化（例: `["ctrl","c"]` → `Ctrl+C`）。共通ヘルパ `_keys_to_label(tokens)` を用意。
- 特殊キーが空（全削除）なら行ごと表示しない。
- グリッドのセル幅: 特殊キーは単キー幅（`size`）で生成する（定型文の `size*2` とは別）。

## 設定画面（settings_dialog.py）

### 操作キーグループ（新規・先頭に配置）

- テーブル列: 「表示名」「キー」。「キー」セルは編集不可表示（`Ctrl+C` 等の可読文字列）。実体のトークン列は `Qt.UserRole` に保持する。
- 「＋追加」は **QMenu** で候補と「カスタム…」を提示。
  - 候補: ⇧Tab / ⏎ Enter / Esc / Tab / ← / ↑ / ↓ / → / ⌃C / ⌃V / Home / End / PgUp / PgDn / Delete / ⌫。各候補は (label, tokens) のプリセット。
  - 「カスタム…」: 小ダイアログ（`CustomKeyDialog`）。Ctrl/Shift/Alt/Win のチェックボックス＋ベースキーのコンボボックス（英数字・矢印・Enter 等）→ トークン列と既定ラベルを生成。
- 表示名セルは編集可能（候補選択後にユーザーが上書きできる）。

### 並び替え（共通）

- 操作キー・定型文・コマンドの3テーブルに ▲▼ ボタンを追加。
- 既存の `_row_buttons(add_fn, table)` を拡張し、▲▼ を含める共通ヘルパにする（`_move_row(table, delta)`）。
- セル widget（コマンドのチェックボックス）を含む行の移動に対応するため、移動はモデル値の入れ替えで行うか、行全体を再構築する。チェックボックス列があるため、`_move_row` はセル widget も含めて再設定する実装にする。

### 結果反映（result_config）

- `keys` を新たに収集して `self._cfg["keys"]` に格納。各行から (label, tokens) を取り出す。トークンが空の行はスキップ。

## データフロー

```
config.json ──load_config──▶ cfg["keys"] ──_build_ui──▶ ボタン群
   ▲                                                        │ click
   │ save_config                                            ▼
SettingsDialog.result_config ◀── OK ── 設定編集    keysender.send_keys(tokens)
```

## エラーハンドリング

- 未知トークン: `send_keys` 内で `ValueError`。UI 生成時は候補/カスタムのみ生成するため実害は出ないが、手編集 config の不正値に備え、ボタン押下時に例外を握りつぶしてログ相当の無視（クラッシュさせない）。
- 不正な `keys`（dict でない等）: `_merge_defaults` で型チェックし、不正なら既定値。

## テスト方針

- `keysender._resolve_token` の単体テスト（既知トークン・英数字導出・未知トークンで ValueError）。
- `config._merge_defaults` が `keys` 欠落時に既定を補い、既存値を尊重することの確認。
- 設定画面の `result_config` が `keys` を正しく収集すること（トークン空行のスキップ含む）。
- 手動確認: 起動表示の折り返し、候補追加・カスタム追加・並び替え・削除、各キーの送出（Enter/矢印/Ctrl+C 等）。

## 当初要望との対応

- Enter ボタン追加 → 候補から「⏎ Enter」を追加。
- 左右矢印を隠す → ←→ 行を削除。
- 1列目を設定可能に → 操作キーグループで追加・並び替え・削除。
