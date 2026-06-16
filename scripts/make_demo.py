"""README 用デモ GIF を生成する。

Shiftab の実バー画像（Qt で grab）と擬似ターミナルを並べ、カーソルが
ボタンを押す→ターミナルに文字が届く流れをフレーム合成して GIF 化する。
実画面の録画ではなく、実物の見た目を使った再現アニメーション。

実行:  python scripts/make_demo.py
出力:  docs/assets/demo.gif
"""

from __future__ import annotations

import os
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ASSETS = os.path.join(ROOT, "docs", "assets")

# --- 1) Shiftab バーの実画像を grab ---
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
import config  # noqa: E402
from mainbar import MainBar  # noqa: E402

_bar = MainBar()
_bar.resize(_bar.sizeHint())
_bar_path = os.path.join(ASSETS, "_bar_frame.png")
_bar.grab().save(_bar_path)
bar_img = Image.open(_bar_path).convert("RGBA")
BAR_W, BAR_H = bar_img.size

# --- レイアウト定数 ---
MARGIN = 16
GAP = 24
TERM_W = 470
BAR_X, BAR_Y = MARGIN, MARGIN
TERM_X = BAR_X + BAR_W + GAP
TERM_Y = MARGIN
TERM_H = BAR_H
CANVAS_W = TERM_X + TERM_W + MARGIN
CANVAS_H = max(BAR_H, TERM_H) + MARGIN * 2

BG = (13, 17, 23, 255)          # GitHub ダーク
TERM_BG = (22, 27, 34, 255)
TERM_BORDER = (48, 54, 61, 255)
FG = (201, 209, 217, 255)
GREEN = (63, 185, 80, 255)
DIM = (139, 148, 158, 255)
SEL = (88, 166, 255, 255)

# ボタン中心（キャンバス座標）= バー内座標 + バーオフセット
def bcenter(bx, by, bw, bh):
    return (BAR_X + bx + bw // 2, BAR_Y + by + bh // 2)

P_OK = bcenter(6, 178, 124, 56)
P_MODEL = bcenter(6, 260, 124, 56)
P_DOWN = bcenter(261, 36, 81, 56)
# 押下ハイライト用の矩形（キャンバス座標）
R_OK = (BAR_X + 6, BAR_Y + 178, 124, 56)
R_MODEL = (BAR_X + 6, BAR_Y + 260, 124, 56)
R_DOWN = (BAR_X + 261, BAR_Y + 36, 81, 56)

# --- フォント ---
def load_font(size):
    for name in ("consola.ttf", "cour.ttf", "arial.ttf"):
        p = os.path.join("C:\\Windows\\Fonts", name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

FONT = load_font(16)
FONT_SM = load_font(13)

LINE_H = 22


def draw_cursor(d, x, y):
    """矢印カーソル（先端が (x,y)）を描く。"""
    pts = [(0, 0), (0, 19), (5, 14), (9, 21), (12, 20), (8, 13), (15, 13)]
    poly = [(x + px, y + py) for px, py in pts]
    d.polygon(poly, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))


def render(cursor, press_rect, term_lines):
    """1フレームを描画して RGBA Image を返す。"""
    img = Image.new("RGBA", (CANVAS_W, CANVAS_H), BG)
    d = ImageDraw.Draw(img)

    # ターミナルパネル
    d.rounded_rectangle(
        [TERM_X, TERM_Y, TERM_X + TERM_W, TERM_Y + TERM_H],
        radius=10, fill=TERM_BG, outline=TERM_BORDER, width=1,
    )
    # タイトルバー（信号機 + タイトル）
    cy = TERM_Y + 18
    for i, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx = TERM_X + 18 + i * 18
        d.ellipse([cx, cy - 6, cx + 12, cy + 6], fill=col)
    d.text((TERM_X + 90, cy - 8), "Claude Code - terminal", font=FONT_SM, fill=DIM)
    d.line([TERM_X, TERM_Y + 36, TERM_X + TERM_W, TERM_Y + 36],
           fill=TERM_BORDER, width=1)

    # ターミナル本文
    tx = TERM_X + 16
    ty = TERM_Y + 50
    for i, (kind, text) in enumerate(term_lines):
        y = ty + i * LINE_H
        if kind == "prompt":
            d.text((tx, y), ">", font=FONT, fill=GREEN)
            d.text((tx + 18, y), text, font=FONT, fill=FG)
        elif kind == "sel":
            d.text((tx + 18, y), "> " + text, font=FONT, fill=SEL)
        elif kind == "opt":
            d.text((tx + 18, y), "  " + text, font=FONT, fill=DIM)
        else:
            d.text((tx + 18, y), text, font=FONT, fill=DIM)

    # バー画像
    img.paste(bar_img, (BAR_X, BAR_Y), bar_img)

    # 押下ハイライト
    if press_rect is not None:
        x, y, w, h = press_rect
        ov = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rounded_rectangle([x, y, x + w, y + h], radius=6,
                             fill=(88, 166, 255, 70), outline=(88, 166, 255, 230), width=2)
        img = Image.alpha_composite(img, ov)
        d = ImageDraw.Draw(img)

    # カーソル
    if cursor is not None:
        draw_cursor(d, cursor[0], cursor[1])
    return img


def lerp(a, b, t):
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t))


# --- ターミナル状態（段階別） ---
T0 = [("prompt", "█")]
T1 = [("prompt", "OK"), ("prompt", "█")]
T2 = [("prompt", "OK"), ("prompt", "/model"),
      ("opt", "Select model:"), ("sel", "Opus 4.8"), ("opt", "Sonnet 4.6")]
T3 = [("prompt", "OK"), ("prompt", "/model"),
      ("opt", "Select model:"), ("opt", "Opus 4.8"), ("sel", "Sonnet 4.6")]

frames = []      # (PIL image, duration_ms)
START = (TERM_X + 200, TERM_Y + 150)


def add(img, ms):
    frames.append((img.convert("RGB"), ms))


def move(p0, p1, steps, press_rect, term, hold_last=0):
    for s in range(steps + 1):
        t = s / steps
        add(render(lerp(p0, p1, t), None, term), 40)
    if hold_last:
        add(render(p1, None, term), hold_last)


# 1) アイドル
add(render(START, None, T0), 900)
# 2) OK へ移動 → 押下 → 送信
move(START, P_OK, 8, None, T0)
add(render(P_OK, R_OK, T0), 160)
add(render(P_OK, R_OK, T0), 160)
add(render(P_OK, None, T1), 900)
# 3) /model へ移動 → 押下 → ピッカー表示
move(P_OK, P_MODEL, 6, None, T1)
add(render(P_MODEL, R_MODEL, T1), 160)
add(render(P_MODEL, R_MODEL, T1), 160)
add(render(P_MODEL, None, T2), 800)
# 4) ↓ へ移動 → 押下 → 選択が動く
move(P_MODEL, P_DOWN, 8, None, T2)
add(render(P_DOWN, R_DOWN, T2), 160)
add(render(P_DOWN, None, T3), 1400)

# --- GIF 書き出し（縮小） ---
scale = 0.72
imgs = []
durations = []
for im, ms in frames:
    w, h = im.size
    imgs.append(im.resize((round(w * scale), round(h * scale)), Image.LANCZOS))
    durations.append(ms)

out = os.path.join(ASSETS, "demo.gif")
imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=durations,
             loop=0, optimize=True, disposal=2)

os.remove(_bar_path)
print("wrote", out, "frames:", len(imgs), "size:", imgs[0].size)
