# Shiftab — アーキテクチャ／技術詳細

ユーザー向けの概要は [README.md](../README.md) を参照。ここでは仕組み・全操作・設定ファイル・ビルドの詳細をまとめる。

## 動作の仕組み

- **フォーカスを奪わない**: Windows のスクリーンキーボード（osk.exe）と同様、ウィンドウに `WS_EX_NOACTIVATE` を付与する。バーをクリックしても入力フォーカスはターミナル側に残るため、送ったキーは裏のターミナル（Claude Code）に届く。
- **キー送出**: win32 `SendInput`（ctypes 経由）。
  - 文字列は `KEYEVENTF_UNICODE` で1文字ずつ送出するため、IME の状態に依存せず日本語も入力でき、クリップボードも汚さない。
  - 単発キー・組み合わせは仮想キーコード（VK）の down/up で送る。修飾キーを含む組み合わせ（例: Ctrl+Shift+P）は先頭から押下し逆順に解放する。
- **送信中の IME 自動オフ**: 定型文・コマンドの送信中だけ、送信先ターミナルの IME を一時的にオフにし、送り終えたら元の状態へ戻す（`WM_IME_CONTROL`）。ターミナルがひらがな入力中でも、文字の重複や、Enter が「変換確定」に吸われて送信されない不具合を防ぐ。
- **ウィンドウ位置の復元**: 終了時に位置を保存し、次回復元する。保存座標がどの画面にも乗っていない場合（マルチモニタ構成の変更など）は、自動でプライマリ画面内へ補正して表示する。

## 操作キーの仕組み（v0.4.0〜）

操作キー（1列目）は設定で自由に追加・並び替え・削除できる。各キーは「表示名 ＋ キートークンの並び」で表現する。

- 単発キーも組み合わせも、トークンの並びとして統一的に扱う（単発キーは長さ1の並び）。
- 候補から選ぶ（⇧Tab / ⏎ Enter / Esc / Tab / 矢印 / ⌃C / ⌃V / Home / End / PgUp / PgDn / Delete / ⌫）か、カスタムビルダーで「Ctrl/Shift/Alt/Win ＋ 任意キー」を組み立てる。
- 利用できるトークン名: `shift, ctrl, alt, win, tab, enter, esc, backspace, delete, left, up, down, right, home, end, pageup, pagedown` と、1文字の英数字（`a`〜`z`, `0`〜`9`）。

### ボタンの種類

| 種類 | 動作 |
|---|---|
| 操作キー | 押すとそのキー／組み合わせを送る |
| 定型文 | 「文字列 ＋ Enter」を送る（例: OK / いいよ / 進めて / 続けて / 今どういう状況？） |
| コマンド（単独実行 ON） | `コマンド + Enter`（例: `/model` でピッカーを開く） |
| コマンド（単独実行 OFF） | `コマンド + 半角スペース` のみ（Enter なし）。続けて定型文ボタンを押すと `/btw 今どういう状況？` のように補完して Enter 送信される |

## 設定ファイル

`%APPDATA%\Shiftab\config.json` に保存される。設定画面（右上の ⚙）から編集するのが基本だが、直接編集も可能。初回起動時に既定値が生成される。

スキーマ:

```jsonc
{
  "keys":     [{"label": "string", "keys": ["token", ...]}],
  "phrases":  [{"label": "string", "text": "string"}],
  "commands": [{"label": "string", "command": "string", "auto_enter": true}],
  "window":   {
    "x": 0, "y": 0,            // null なら既定位置
    "opacity": 0.95,
    "button_size": 56,
    "columns": 6
  }
}
```

## ソースからビルドする（exe 化）

[PyInstaller](https://pyinstaller.org/) で単一実行ファイルを作成する。アイコン設定を含む `Shiftab.spec` を使う。

```sh
pip install pyinstaller
pyinstaller --noconfirm Shiftab.spec
```

`dist\Shiftab.exe` が生成される。アプリアイコンは `icon.ico`（角丸・マルチ解像度）を埋め込み・同梱する。差し替えるときは `icon.ico` を置き換えて再ビルドする。

## プロジェクト構成

| ファイル | 役割 |
|---|---|
| `main.py` | エントリポイント。QApplication 起動とアイコン設定 |
| `mainbar.py` | フローティングバー本体（ウィンドウ生成・ボタン描画・ドラッグ・位置保存） |
| `settings_dialog.py` | 設定画面（操作キー／定型文／コマンド／外観の編集、並び替え、カスタムキー作成） |
| `keysender.py` | OS レベルのキーストローク送出（SendInput / IME 制御 / トークン解決） |
| `config.py` | 設定の読み込み・保存・既定値・後方互換マージ |
| `Shiftab.spec` | PyInstaller 設定 |
| `tests/` | 単体テスト（pytest） |

## テスト

```sh
pip install -r requirements-dev.txt
python -m pytest -v
```

GUI 描画を伴うコンポーネントはオフスクリーン（`QT_QPA_PLATFORM=offscreen`）で起動確認する。純粋ロジック（キートークン解決・設定マージ・候補カタログの整合）は pytest で検証している。
