"""OS レベルのキーストローク送出（Windows / SendInput）。

ctypes で win32 の SendInput を直接呼び出す。
- send_text: KEYEVENTF_UNICODE で1文字ずつ送る。IME に依存せず日本語も入力でき、
  クリップボードも汚さない。
- tap_vk / send_combo / send_enter / send_arrow: 仮想キーコード(VK)の down/up で送る。

非アクティブ化ウィンドウ（mainbar）からクリックされるため、フォーカスは
操作対象（ターミナル等）に残ったままになり、SendInput はそこへ届く。
"""

from __future__ import annotations

import contextlib
import ctypes
import time
from ctypes import wintypes

# --- 仮想キーコード（必要なものだけ） ---
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_C = 0x43
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

# --- IME 制御（WM_IME_CONTROL）関連の定数 ---
WM_IME_CONTROL = 0x0283
IMC_GETOPENSTATUS = 0x0005
IMC_SETOPENSTATUS = 0x0006

# IME を閉じた直後、未確定処理が落ち着くまでの待ち（秒）
_IME_SETTLE_DELAY = 0.02

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

# --- IME 状態の取得／変更に使う関数 ---
# ImmGetDefaultIMEWnd は imm32.dll、それ以外は user32.dll。
_imm32 = ctypes.WinDLL("imm32", use_last_error=True)
_user32.GetForegroundWindow.restype = wintypes.HWND
_imm32.ImmGetDefaultIMEWnd.argtypes = (wintypes.HWND,)
_imm32.ImmGetDefaultIMEWnd.restype = wintypes.HWND
_user32.SendMessageW.argtypes = (
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
_user32.SendMessageW.restype = wintypes.LPARAM


def _send(inputs: list[INPUT]) -> None:
    """INPUT のリストをまとめて送出する。"""
    if not inputs:
        return
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    sent = _SendInput(n, arr, ctypes.sizeof(INPUT))
    if sent != n:
        raise ctypes.WinError(ctypes.get_last_error())


def _ime_window():
    """前面ウィンドウ（送信先）の既定 IME ウィンドウを返す。取れなければ None。"""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    ime_wnd = _imm32.ImmGetDefaultIMEWnd(hwnd)
    return ime_wnd or None


def _get_ime_open(ime_wnd) -> bool:
    """IME が開いている（変換待ち＝オン）かどうかを返す。"""
    return bool(
        _user32.SendMessageW(ime_wnd, WM_IME_CONTROL, IMC_GETOPENSTATUS, 0)
    )


def _set_ime_open(ime_wnd, open_: bool) -> None:
    """IME のオン／オフを設定する。"""
    _user32.SendMessageW(
        ime_wnd, WM_IME_CONTROL, IMC_SETOPENSTATUS, 1 if open_ else 0
    )


@contextlib.contextmanager
def ime_disabled():
    """送信中だけ送信先の IME をオフにし、抜けるときに元の状態へ戻す。

    端末側 IME がオン（ひらがな変換待ち）だと、注入した Unicode 文字が
    未確定バッファに巻き込まれて重複したり、Enter が「変換確定」に吸われて
    改行（送信）として届かない。送信の間だけ IME を閉じることで回避する。

    IME ウィンドウが取れない／元からオフの場合は何もしない。
    """
    ime_wnd = _ime_window()
    restore = False
    if ime_wnd is not None and _get_ime_open(ime_wnd):
        _set_ime_open(ime_wnd, False)
        time.sleep(_IME_SETTLE_DELAY)
        restore = True
    try:
        yield
    finally:
        if restore:
            _set_ime_open(ime_wnd, True)


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


def send_ctrl_c() -> None:
    """Ctrl+C を送る（ターミナルの中断など）。"""
    send_combo([VK_CONTROL, VK_C])


def send_backspace() -> None:
    """Backspace を送る。"""
    tap_vk(VK_BACK)


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
