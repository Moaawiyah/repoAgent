from settings_app.loader import load_settings


def test_defaults():
    assert load_settings({}) == {"debug": False, "workers": 4}


def test_debug_enabled():
    assert load_settings({"APP_DEBUG": "true"})["debug"] is True
