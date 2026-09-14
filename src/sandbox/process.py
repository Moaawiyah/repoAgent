"""Bounded host process execution used only to drive the Docker CLI.

Output is streamed into fixed-size head/tail buffers so a hostile command
cannot exhaust host memory or disk, and processes are killed on timeout.
"""

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import IO, Protocol

CHUNK_BYTES = 65536
DOCKER_ENV_KEYS = (
    "PATH",
    "HOME",
    "LANG",
    "DOCKER_HOST",
    "DOCKER_CONTEXT",
    "DOCKER_CONFIG",
    "DOCKER_CERT_PATH",
    "DOCKER_TLS_VERIFY",
)
TRUNCATION_MARKER = b"\n...[output truncated by RepoAgent]...\n"


class BoundedCapture:
    """Keeps the first and last ``limit // 2`` bytes of a stream."""

    def __init__(self, limit: int) -> None:
        self._head_limit = limit // 2
        self._tail_limit = limit - self._head_limit
        self._head, self._tail = bytearray(), bytearray()
        self.truncated = False

    def feed(self, chunk: bytes) -> None:
        room = self._head_limit - len(self._head)
        if room > 0:
            self._head.extend(chunk[:room])
            chunk = chunk[room:]
        if not chunk:
            return
        self._tail.extend(chunk)
        if len(self._tail) > self._tail_limit:
            self.truncated = True
            del self._tail[: len(self._tail) - self._tail_limit]

    def text(self) -> str:
        middle = TRUNCATION_MARKER if self.truncated else b""
        return (bytes(self._head) + middle + bytes(self._tail)).decode(
            "utf-8", errors="replace"
        )


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    duration_seconds: float


class ProcessRunner(Protocol):
    def run(self, argv: list[str], timeout: float, max_output: int) -> ProcessResult:
        """Run an argv vector (never a shell string) with hard bounds."""
        ...


def minimal_environment() -> dict[str, str]:
    """Only what the Docker CLI needs; never forwards API keys or secrets."""
    return {key: os.environ[key] for key in DOCKER_ENV_KEYS if key in os.environ}


class SubprocessRunner:
    """``subprocess`` implementation with ``shell=False`` and group kill."""

    def run(self, argv: list[str], timeout: float, max_output: int) -> ProcessResult:
        start = time.monotonic()
        captures = [BoundedCapture(max_output // 2), BoundedCapture(max_output // 2)]
        process = subprocess.Popen(  # noqa: S603 - argv list from trusted builders
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=minimal_environment(),
            start_new_session=True,
        )
        readers = [
            threading.Thread(target=_drain, args=(stream, capture), daemon=True)
            for stream, capture in zip(
                (process.stdout, process.stderr), captures, strict=True
            )
        ]
        for reader in readers:
            reader.start()
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(process)
        for reader in readers:
            reader.join(timeout=5)
        return ProcessResult(
            exit_code=None if timed_out else process.returncode,
            stdout=captures[0].text(),
            stderr=captures[1].text(),
            timed_out=timed_out,
            truncated=any(capture.truncated for capture in captures),
            duration_seconds=time.monotonic() - start,
        )


def _drain(stream: IO[bytes], capture: BoundedCapture) -> None:
    with stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            capture.feed(chunk)


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()
