"""設定の読み込み・保存。

設定は JSON ファイルに保存する。保存先は %APPDATA%\\Shiftab\\config.json。
初回起動時は既定値を生成する。

スキーマ:
{
  "phrases":  [{"label": str, "text": str}],
  "commands": [{"label": str, "command": str, "auto_enter": bool}],
  "window":   {"x": int|None, "y": int|None, "opacity": float,
               "button_size": int, "columns": int}
}
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

APP_NAME = "Shiftab"

# 既定設定
DEFAULT_CONFIG: dict = {
    "phrases": [
        {"label": "OK", "text": "OK"},
        {"label": "いいよ", "text": "いいよ"},
        {"label": "進めて", "text": "進めて"},
        {"label": "続けて", "text": "続けて"},
        {"label": "今どういう状況？", "text": "今どういう状況？"},
    ],
    "commands": [
        # auto_enter=True : コマンド + Enter（単独実行）
        # auto_enter=False: コマンド + 半角スペース（Enterなし、後続の文章ボタンで補完）
        {"label": "/model", "command": "/model", "auto_enter": True},
        {"label": "/effort", "command": "/effort", "auto_enter": True},
        {"label": "/btw …", "command": "/btw", "auto_enter": False},
    ],
    "window": {
        "x": None,
        "y": None,
        "opacity": 0.95,
        "button_size": 56,
        "columns": 6,
    },
}


def config_dir() -> Path:
    """設定ディレクトリ（%APPDATA%\\Shiftab）。"""
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def _merge_defaults(loaded: dict) -> dict:
    """欠けているキーを既定値で補う（後方互換）。"""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(loaded, dict):
        return cfg
    if isinstance(loaded.get("phrases"), list):
        cfg["phrases"] = loaded["phrases"]
    if isinstance(loaded.get("commands"), list):
        cfg["commands"] = loaded["commands"]
    if isinstance(loaded.get("window"), dict):
        cfg["window"].update(loaded["window"])
    return cfg


def load_config() -> dict:
    """設定を読み込む。無ければ既定値を生成して保存する。"""
    path = config_path()
    if not path.exists():
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        save_config(cfg)
        return cfg
    try:
        with path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        return _merge_defaults(loaded)
    except (json.JSONDecodeError, OSError):
        # 壊れていたら既定値で再生成
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        save_config(cfg)
        return cfg


def save_config(cfg: dict) -> None:
    """設定を JSON で保存する。"""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
