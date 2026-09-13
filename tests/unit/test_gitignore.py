"""GitIgnore pattern matching behavior."""

from repoagent.analysis.gitignore import GitIgnore


def matches(patterns, path, is_dir=False):
    return GitIgnore(patterns).matches(path, is_dir)


def test_comments_and_blank_lines_are_ignored():
    assert not matches(["# comment", "", "   "], "anything.txt")


def test_unanchored_patterns_match_any_depth():
    assert matches(["build"], "build", True)
    assert matches(["build"], "deep/nested/build", False)
    assert not matches(["build"], "build/output.txt", False)
    assert matches(["*.pyc"], "a/b.pyc")
    assert matches(["temp?.txt"], "temp1.txt")
    assert not matches(["temp?.txt"], "temp10.txt")


def test_directory_only_and_anchored_patterns():
    assert matches(["logs/"], "logs", True)
    assert not matches(["logs/"], "logs", False)
    assert matches(["/top.txt"], "top.txt")
    assert not matches(["/top.txt"], "sub/top.txt")
    assert matches(["src/generated.py"], "src/generated.py")
    assert not matches(["src/generated.py"], "other/src/generated.py")


def test_doublestar_patterns():
    assert matches(["data/**/*.csv"], "data/x.csv")
    assert matches(["data/**/*.csv"], "data/x/y.csv")
    assert matches(["a/**/b"], "a/x/y/b", True)
    assert not matches(["data/**/*.csv"], "other/data/x.csv")


def test_negation_last_rule_wins():
    assert not matches(["*.log", "!keep.log"], "keep.log")
    assert matches(["*.log", "!keep.log"], "other.log")
    assert matches(["!keep.log", "*.log"], "keep.log")
    assert not matches(["!only.log"], "keep.log")
