"""Legacy setuptools metadata (setup.cfg / tox.ini), read via configparser only."""

import configparser


def read_ini(text: str) -> configparser.ConfigParser:
    """Parse INI-style content; empty/unparseable content reads as empty."""
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error:
        pass
    return parser


def declares_pytest(config: configparser.ConfigParser) -> bool:
    return config.has_section("tool:pytest") or config.has_section("pytest")


def install_requires_lines(config: configparser.ConfigParser) -> list[str]:
    """Dependencies from ``[options] install_requires`` (the standard
    setuptools key) and ``[metadata] requires-dist`` (an accepted alias some
    projects use instead), each a newline-separated value block."""
    lines = []
    for section, key in (
        ("options", "install_requires"),
        ("metadata", "requires-dist"),
    ):
        if config.has_option(section, key):
            lines.extend(config.get(section, key).splitlines())
    return lines
