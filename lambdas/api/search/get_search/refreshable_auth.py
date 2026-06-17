"""Refreshable AWS credentials for long-lived OpenSearch clients.

Lambda containers can live for hours, but IAM temporary credentials expire
after ~1 hour.  The standard pattern of caching a ``boto3.Session`` snapshot
bakes stale credentials into the ``RequestsAWSV4SignerAuth`` signer.

This module provides ``get_refreshable_credentials()`` which returns a thin
wrapper that the opensearch-py ``AWSV4Signer`` calls on every request via
``get_frozen_credentials()``.  The wrapper re-reads credentials from a fresh
``boto3.Session`` only when the current ones are within *REFRESH_WINDOW* of
expiry, so the hot path is a cheap timestamp comparison.
"""

import threading
import time

import boto3

# Refresh credentials when they are within this many seconds of expiry.
# Lambda runtime rotates env-var credentials ~15 min before the old ones
# expire, so 5 min gives plenty of headroom.
REFRESH_WINDOW_SECONDS = 300

# Credentials fetched from the Lambda environment don't carry an explicit
# expiry timestamp.  We conservatively assume they last this long and
# force a refresh after this interval.
DEFAULT_TTL_SECONDS = 2700  # 45 minutes


class _RefreshableLambdaCredentials:
    """Credentials wrapper that transparently refreshes before expiry.

    Implements the interface expected by ``opensearch-py``'s
    ``AWSV4Signer.sign()`` — specifically ``get_frozen_credentials()``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._access_key: str = ""
        self._secret_key: str = ""
        self._token: str | None = None
        self._fetched_at: float = 0.0
        # Force an immediate fetch on first use.
        self._refresh()

    # ------------------------------------------------------------------
    # Public interface consumed by AWSV4Signer
    # ------------------------------------------------------------------

    @property
    def access_key(self) -> str:
        self._ensure_fresh()
        return self._access_key

    @property
    def secret_key(self) -> str:
        self._ensure_fresh()
        return self._secret_key

    @property
    def token(self) -> str | None:
        self._ensure_fresh()
        return self._token

    def get_frozen_credentials(self):
        """Return *self* after ensuring credentials are fresh.

        ``AWSV4Signer.sign()`` calls this and then reads ``access_key``,
        ``secret_key``, and ``token`` from the returned object.
        """
        self._ensure_fresh()
        return self

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_fresh(self) -> None:
        elapsed = time.monotonic() - self._fetched_at
        if elapsed < (DEFAULT_TTL_SECONDS - REFRESH_WINDOW_SECONDS):
            return  # Still fresh — fast path, no lock needed.
        with self._lock:
            # Double-check after acquiring the lock.
            elapsed = time.monotonic() - self._fetched_at
            if elapsed < (DEFAULT_TTL_SECONDS - REFRESH_WINDOW_SECONDS):
                return
            self._refresh()

    def _refresh(self) -> None:
        creds = boto3.Session().get_credentials()
        if creds is None:
            raise RuntimeError("Unable to obtain AWS credentials from boto3 session")
        frozen = creds.get_frozen_credentials()
        self._access_key = frozen.access_key
        self._secret_key = frozen.secret_key
        self._token = frozen.token
        self._fetched_at = time.monotonic()


def get_refreshable_credentials() -> _RefreshableLambdaCredentials:
    """Return a credentials object safe for long-lived cached clients."""
    return _RefreshableLambdaCredentials()
