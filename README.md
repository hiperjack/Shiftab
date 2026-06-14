# Shiftab

Claude Code をターミナルで操作するための、必要なキーだけを並べた小型ソフトキーボード（Windows専用）。常時最前面に浮かぶフローティングバーで、ボタンを押すと**フォーカスを奪わずに**裏で開いているターミナル（Claude Code）へキーを送ります。

## できること

- **⇧Tab** ボタン … Shift+Tab を1回で送る（モード切替など）
- **矢印** ←↑↓→ … カーソル移動（`/model` のピッカー選択などに）
- **定型文ボタン** … 「文字列 ＋ Enter」を送信（例: OK / いいよ / 進めて / 続けて / 今どういう状況？）
- **コマンドボタン** … スラッシュコマンドを送信。コマンドごとに動作を選べる
  - **単独実行（Enter）ON**: `コマンド + Enter`（例: `/model` でピッカーを開く）
  - **単独実行 OFF**: `コマンド + 半角スペース` のみ（Enterを押さない）。続けて定型文ボタンを押すと
    `/btw 今どういう状況？` のように補完して Enter 送信される

## 仕組み

- Windows のスクリーンキーボード(osk.exe)と同じく、ウィンドウに `WS_EX_NOACTIVATE` を付与。
  クリックしてもバー側はフォーカスを取らないため、ターミナルのフォーカスが外れません。
- キー送出は win32 `SendInput`（ctypes）。文字列は `KEYEVENTF_UNICODE` で1文字ずつ送るので、
  IME の状態に依存せず日本語も入力でき、クリップボードも汚しません。

## セットアップ

```sh
pip install -r requirements.txt
python main.py
```

## 使い方

1. `python main.py` でバーが画面最前面に表示されます。
2. タイトル部分（⠿ Shiftab）をドラッグして好きな位置へ移動できます。位置は保存されます。
3. Claude Code のターミナルを開いた状態で、各ボタンを押すとそちらへキーが届きます。
4. 右上の **⚙** で設定画面を開き、定型文・コマンド・外観（不透明度／ボタンサイズ／列数）を編集できます。
5. 右上の **✕** で終了します（タスクバーには表示されません）。

## 配布版（exe）

[Releases](https://github.com/hiperjack/Shiftab/releases) から `Shiftab.exe` をダウンロードすれば、Python のインストール不要でそのまま起動できます。

## 自分でビルドする（exe化）

[PyInstaller](https://pyinstaller.org/) で単一実行ファイルを作成できます。

```sh
pip install pyinstaller
pyinstaller --noconfirm --windowed --onefile --name Shiftab main.py
```

`dist\Shiftab.exe` が生成されます。

## 設定ファイル

`%APPDATA%\Shiftab\config.json` に保存されます。設定画面から編集するのが基本ですが、
直接編集も可能です。

## 動作要件

- Windows 10 / 11
- Python 3.10 以降
- PySide6
