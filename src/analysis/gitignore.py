"""Minimal .gitignore-style matching for repository discovery."""

import re


class GitIgnore:
    """Ordered .gitignore rules where the last matching rule wins.

    Supports comments, blank lines, ``!`` negation, directory-only patterns
    (trailing ``/``), anchored patterns (leading ``/`` or embedded ``/``),
    and ``*``, ``?``, and ``**`` wildcards. Unanchored patterns match a
    path segment at any depth.
    """

    def __init__(self, lines: list[str]) -> None:
        self._rules: list[tuple[re.Pattern[str], bool, bool]] = []
        for raw in lines:
            rule = raw.strip()
            if not rule or rule.startswith("#"):
                continue
            negated = rule.startswith("!")
            rule = rule.lstrip("!")
            dir_only = rule.endswith("/")
            rule = rule.rstrip("/")
            anchored = rule.startswith("/")
            rule = rule.lstrip("/")
            if not rule:
                continue
            pattern = self._regex(rule)
            if anchored or "/" in rule:
                pattern = rf"^{pattern}$"
            else:
                pattern = rf"^(?:.*/)?{pattern}$"
            self._rules.append((re.compile(pattern), dir_only, negated))

    @staticmethod
    def _regex(rule: str) -> str:
        parts: list[str] = []
        index = 0
        while index < len(rule):
            if rule.startswith("**/", index):
                parts.append("(?:[^/]+/)*")
                index += 3
            elif rule.startswith("/**", index):
                parts.append("(?:/[^/]+)*")
                index += 3
            elif rule.startswith("**", index):
                parts.append(".*")
                index += 2
            elif rule[index] == "*":
                parts.append("[^/]*")
                index += 1
            elif rule[index] == "?":
                parts.append("[^/]")
                index += 1
            else:
                parts.append(re.escape(rule[index]))
                index += 1
        return "".join(parts)

    def matches(self, relative_path: str, is_dir: bool) -> bool:
        """Return whether the repository-relative path is ignored."""
        ignored = False
        for regex, dir_only, negated in self._rules:
            if dir_only and not is_dir:
                continue
            if regex.match(relative_path):
                ignored = not negated
        return ignored
