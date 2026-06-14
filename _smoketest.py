"""起動スモークテスト: UI生成とキー送出ロジックを実画面なしで検証。

- 各モジュールのimport
- MainBar生成・show（QTimerで即終了、ブロックしない）
- SettingsDialog生成と result_config の往復
- keysender の INPUT 構築（実送出はせず、構造体生成のみ確認）
"""

import os
import sys
import tempfile

# 設定を一時フォルダに隔離（実環境のconfigを汚さない）
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="shiftab_test_")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import config as config_mod
import keysender
from mainbar import MainBar
from settings_dialog import SettingsDialog


def test_config_roundtrip():
    cfg = config_mod.load_config()
    assert cfg["phrases"], "default phrases missing"
    assert cfg["commands"], "default commands missing"
    config_mod.save_config(cfg)
    cfg2 = config_mod.load_config()
    assert cfg2["phrases"] == cfg["phrases"]
    print("[OK] config roundtrip")


def test_keysender_structs():
    # 実送出はしない。INPUT構築が例外なく行えることだけ確認。
    i1 = keysender._vk_input(keysender.VK_TAB, False)
    i2 = keysender._unicode_input(ord("あ"), False)
    assert i1.type == keysender.INPUT_KEYBOARD
    assert i2.u.ki.dwFlags & keysender.KEYEVENTF_UNICODE
    print("[OK] keysender INPUT structs")


def test_ui(app):
    bar = MainBar()
    bar.show()
    # ボタンが生成されているか（少なくとも複数ある）
    from PySide6.QtWidgets import QPushButton
    btns = bar.findChildren(QPushButton)
    assert len(btns) >= 6, f"too few buttons: {len(btns)}"
    print(f"[OK] MainBar built with {len(btns)} buttons")

    dlg = SettingsDialog(bar.cfg, bar)
    out = dlg.result_config()
    assert out["phrases"] == bar.cfg["phrases"]
    assert out["commands"] == bar.cfg["commands"]
    print("[OK] SettingsDialog roundtrip")

    bar.close()
    dlg.close()


def main():
    app = QApplication(sys.argv)
    test_config_roundtrip()
    test_keysender_structs()
    test_ui(app)
    # イベントループに入らず即終了
    QTimer.singleShot(0, app.quit)
    app.exec()
    print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
