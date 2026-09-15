"""Application settings assembled from an environment mapping."""

from settings_app.parse import parse_bool, parse_int


def load_settings(env: dict[str, str]) -> dict:
    """Build settings; missing keys use safe defaults."""
    return {
        "debug": parse_bool(env.get("APP_DEBUG", "")),
        "workers": parse_int(env.get("APP_WORKERS", ""), 4),
    }
