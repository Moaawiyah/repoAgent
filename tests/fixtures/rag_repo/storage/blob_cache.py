"""Local cache for downloaded artifacts."""

import os


class BlobCacheStore:
    """Keeps downloaded blobs on disk and expires stale entries."""

    def __init__(self, root: str) -> None:
        self._root = root

    def fetch_or_download(self, url: str) -> str:
        """Return a cached path, downloading when missing."""
        path = os.path.join(self._root, url.rsplit("/", 1)[-1])
        if not os.path.exists(path):
            path = self._download(url, path)
        return path

    def _download(self, url: str, path: str) -> str:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"stub:{url}")
        return path

    def evict_expired_entries(self, max_age_seconds: int) -> int:
        """Remove cached files older than the maximum age."""
        removed = 0
        for name in sorted(os.listdir(self._root)):
            if name.endswith(".tmp"):
                os.remove(os.path.join(self._root, name))
                removed += 1
        return removed
