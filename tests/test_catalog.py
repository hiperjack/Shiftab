import keysender
from settings_dialog import KEY_CATALOG


def test_catalog_entries_are_resolvable():
    for label, tokens in KEY_CATALOG:
        assert tokens, f"{label} has empty tokens"
        for t in tokens:
            keysender._resolve_token(t)  # raises if unknown


def test_catalog_has_enter():
    labels = [label for label, _ in KEY_CATALOG]
    assert any("Enter" in label or "⏎" in label for label in labels)
