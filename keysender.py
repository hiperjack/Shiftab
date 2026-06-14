"""OS レベルのキーストローク送出（Windows / SendInput）。

ctypes で win32 の SendInput を直接呼び出す。
- send_text: KEYEVENTF_UNICODE で1文字ずつ送る。IME に依存せず日本語も入力でき、
  クリップボードも汚さない。
- tap_vk / send_combo / send_enter / send_arrow: 仮想キーコード(VK)の down/up で送る。

非アクティブ化ウィンドウ（mainbar）からクリックされるため、フォーカスは
操作対象（ターミナル等）に残ったままになり、SendInput はそこへ届く。
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

# --- 仮想キーコード（必要なものだけ） ---
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

# 方向名 → VK
ARROW_VK = {
    "up": VK_UP,
    "down": VK_DOWN,
    "left": VK_LEFT,
    "right": VK_RIGHT,
}

# --- SendInput 関連の定数 ---
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# 連続送出時の取りこぼし対策の極小ディレイ（秒）
_KEY_DELAY = 0.005


# --- 構造体定義 ---
# ULONG_PTR はポインタ幅の符号なし整数。wintypes.WPARAM (UINT_PTR) を使う。
ULONG_PTR = wintypes.WPARAM


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTunion(ctypes.Union):
    # SendInput が期待する INPUT のサイズ(cbSize)を満たすため、
    # 全メンバ（最大は MOUSEINPUT）を定義しておく。
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUTunion),
    ]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_SendInput = _user32.SendInput
_SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_SendInput.restype = wintypes.UINT


def _send(inputs: list[INPUT]) -> None:
    """INPUT のリストをまとめて送出する。"""
    if not inputs:
        return
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    sent = _SendInput(n, arr, ctypes.sizeof(INPUT))
    if sent != n:
        raise ctypes.WinError(ctypes.get_last_error())


def _vk_input(vk: int, key_up: bool = False) -> INPUT:
    """仮想キーコードの down / up INPUT を作る。"""
    flags = KEYEVENTF_KEYUP if key_up else 0
    ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return INPUT(type=INPUT_KEYBOARD, u=_INPUTunion(ki=ki))


def _unicode_input(code: int, key_up: bool = False) -> INPUT:
    """Unicode コードポイントの down / up INPUT を作る（KEYEVENTF_UNICODE）。"""
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
    ki = KEYBDINPUT(wVk=0, wScan=code, dwFlags=flags, time=0, dwExtraInfo=0)
    return INPUT(type=INPUT_KEYBOARD, u=_INPUTunion(ki=ki))


def tap_vk(vk: int) -> None:
    """単一の仮想キーを1回押して離す。"""
    _send([_vk_input(vk, False)])
    time.sleep(_KEY_DELAY)
    _send([_vk_input(vk, True)])
    time.sleep(_KEY_DELAY)


def send_combo(vks: list[int]) -> None:
    """修飾キーを含む組み合わせを送る（例: Shift+Tab）。

    先頭から順に押下し、逆順に解放する。
    """
    for vk in vks:
        _send([_vk_input(vk, False)])
        time.sleep(_KEY_DELAY)
    for vk in reversed(vks):
        _send([_vk_input(vk, True)])
        time.sleep(_KEY_DELAY)


def send_shift_tab() -> None:
    """Shift+Tab を送る。"""
    send_combo([VK_SHIFT, VK_TAB])


def send_enter() -> None:
    """Enter を送る。"""
    tap_vk(VK_RETURN)


def send_arrow(direction: str) -> None:
    """方向名（up/down/left/right）で矢印キーを送る。"""
    vk = ARROW_VK.get(direction)
    if vk is None:
        raise ValueError(f"unknown arrow direction: {direction}")
    tap_vk(vk)


def send_text(text: str) -> None:
    """任意の文字列を Unicode 直接送出で入力する（IME非依存）。

    サロゲートペア（絵文字等）にも対応する。
    """
    for ch in text:
        code = ord(ch)
        if code > 0xFFFF:
            # BMP外はサロゲートペアに分解して送る
            code -= 0x10000
            high = 0xD800 + (code >> 10)
            low = 0xDC00 + (code & 0x3FF)
            for c in (high, low):
                _send([_unicode_input(c, False)])
                _send([_unicode_input(c, True)])
        else:
            _send([_unicode_input(code, False)])
            _send([_unicode_input(code, True)])
        time.sleep(_KEY_DELAY)
