"""API security policy: repository allowlists, execution gating, bearer token."""

import secrets
from pathlib import Path

from repoagent.config import Settings
from repoagent.domain.errors import RepoAgentError


class ApiForbidden(RepoAgentError):
    """The request is not permitted by the API security policy."""


class ApiUnauthorized(RepoAgentError):
    """The request lacks a valid bearer token."""


class ApiPolicy:
    """Only allowlisted local repositories; execution only for a stricter list."""

    def __init__(self, settings: Settings) -> None:
        self._roots = [p.expanduser().resolve() for p in settings.api_allowed_roots]
        self._execution = [
            p.expanduser().resolve() for p in settings.api_execution_repositories
        ]
        self._token = settings.api_token

    def authorize(self, header: str | None) -> None:
        if self._token is None:
            return
        expected = f"Bearer {self._token.get_secret_value()}"
        if not header or not secrets.compare_digest(header, expected):
            raise ApiUnauthorized("Missing or invalid bearer token")

    def repository(self, raw: str) -> Path:
        """Resolve symlinks first so allowlist checks cannot be bypassed."""
        if "://" in raw or raw.startswith("git@"):
            raise ApiForbidden("Only allowlisted local repositories are accepted")
        path = Path(raw).expanduser().resolve()
        if not any(path == root or path.is_relative_to(root) for root in self._roots):
            raise ApiForbidden("Repository is outside the API allowed roots")
        if not path.is_dir():
            raise ApiForbidden("Repository is not an accessible directory")
        return path

    def execution(self, raw: str) -> Path:
        path = self.repository(raw)
        if path not in self._execution:
            raise ApiForbidden(
                "Sandboxed execution is limited to configured demo repositories"
            )
        return path

    @property
    def execution_repositories(self) -> list[str]:
        return [str(path) for path in self._execution]
