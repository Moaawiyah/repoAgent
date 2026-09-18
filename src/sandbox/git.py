"""Hardened git invocation shared by every host-side repository fetch.

Git runs on the host only to download data, never target code: hooks,
symlink checkout, LFS filters, credential helpers and every protocol other
than HTTPS are disabled.
"""

HARDENING = (
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.symlinks=false",
    "-c", "protocol.allow=never",
    "-c", "protocol.https.allow=always",
    "-c", "filter.lfs.smudge=",
    "-c", "filter.lfs.process=",
    "-c", "filter.lfs.required=false",
    "-c", "advice.detachedHead=false",
)  # fmt: skip

NO_CREDENTIALS = ("-c", "credential.helper=")
