import pytest

import keysender


def test_resolve_named_token():
    assert keysender._resolve_token("enter") == keysender.VK_RETURN
    assert keysender._resolve_token("ctrl") == keysender.VK_CONTROL
    assert keysender._resolve_token("left") == keysender.VK_LEFT


def test_resolve_single_char_token():
    assert keysender._resolve_token("c") == 0x43
    assert keysender._resolve_token("v") == 0x56
    assert keysender._resolve_token("7") == 0x37


def test_resolve_is_case_insensitive():
    assert keysender._resolve_token("Ctrl") == keysender.VK_CONTROL
    assert keysender._resolve_token("ENTER") == keysender.VK_RETURN


def test_resolve_unknown_raises():
    with pytest.raises(ValueError):
        keysender._resolve_token("nope")


def test_keys_to_label():
    assert keysender.keys_to_label(["ctrl", "c"]) == "Ctrl+C"
    assert keysender.keys_to_label(["shift", "tab"]) == "Shift+Tab"
    assert keysender.keys_to_label(["left"]) == "←"
