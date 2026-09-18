"""Inert validation of untrusted GitHub repository URLs and workspace handles.

Only canonical ``https://github.com/<owner>/<repository>`` URLs are accepted:
no credentials, ports, query strings, fragments, sub-paths, or other hosts,
so a URL can never smuggle git options, local paths, or alternate protocols.
"""

import re
from urllib.parse import urlsplit

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.errors import RepositoryInvalid

_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
MAX_URL_LENGTH = 300


class GitHubRepository(AnalysisModel):
    """A validated public GitHub repository reference."""

    owner: str = Field(pattern=_OWNER.pattern)
    name: str = Field(pattern=_NAME.pattern)

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


def parse_github_url(raw: str) -> GitHubRepository:
    """Parse ``raw`` or raise ``RepositoryInvalid`` with a user-safe message."""
    value = raw.strip()
    if not value or len(value) > MAX_URL_LENGTH or any(c.isspace() for c in value):
        raise RepositoryInvalid("Enter a GitHub repository URL")
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.netloc.lower() not in {
        "github.com",
        "www.github.com",
    }:
        raise RepositoryInvalid("Use an https://github.com/<owner>/<repo> URL")
    if parts.query or parts.fragment:
        raise RepositoryInvalid("Repository URLs cannot contain queries or fragments")
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) != 2:
        raise RepositoryInvalid("URL must name exactly one owner and one repository")
    owner, name = segments[0], segments[1].removesuffix(".git")
    if not _OWNER.fullmatch(owner) or not _NAME.fullmatch(name):
        raise RepositoryInvalid("Invalid GitHub owner or repository name")
    if name in {".", ".."} or name.startswith("."):
        raise RepositoryInvalid("Invalid GitHub repository name")
    return GitHubRepository(owner=owner, name=name)


class RepositoryHandle(AnalysisModel):
    """Where a workflow's repository snapshot lives and where it came from.

    ``path`` is RepoAgent's isolated workspace copy; the original remote is
    never modified. ``commit`` is the exact fetched revision when known.
    """

    source: str = Field(max_length=MAX_URL_LENGTH + 700)
    name: str = Field(max_length=200)
    path: str
    commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
