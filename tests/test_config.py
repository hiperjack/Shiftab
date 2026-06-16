import config


def test_default_config_has_keys():
    keys = config.DEFAULT_CONFIG["keys"]
    assert isinstance(keys, list) and len(keys) >= 1
    first = keys[0]
    assert "label" in first and "keys" in first
    assert first["keys"] == ["shift", "tab"]
    assert all(
        isinstance(k, dict) and "label" in k and isinstance(k.get("keys"), list) and k["keys"]
        for k in keys
    )


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
