from textkit.articles import article_url, preview


def test_simple_title_url():
    assert article_url("Hello World") == "/articles/hello-world"


def test_short_preview_unchanged():
    assert preview("short text") == "short text"
