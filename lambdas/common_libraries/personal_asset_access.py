"""Ownership checks for personal ("My Assets") storage.

Personal assets live under ``personal/{cognito_sub}/`` in the per-deployment personal
assets bucket. That layout is not a secret: the sub appears in the asset record, in search
results, and in the derived media URLs the UI renders. Any handler that returns or acts on
an asset must therefore verify the caller owns it, rather than relying on the path being
unguessable.

The rule is deliberately data-driven — derived from the asset's own storage location rather
than from a connector lookup — so it holds even when a caller supplies another user's
connector id, and needs no extra read to enforce.
"""

import json
from typing import Any, Dict, Optional

PERSONAL_PREFIX = "personal/"


def get_caller_sub(event: Any) -> Optional[str]:
    """Extract the caller's Cognito sub from the authorizer context.

    Checks ``requestContext.authorizer.sub`` first (the custom authorizer), then falls back
    to ``requestContext.authorizer.claims.sub`` (a Cognito authorizer, where claims may
    arrive as a JSON string). Returns None when it cannot be determined; callers decide how
    to handle that, and for ownership checks the only safe handling is to deny.
    """
    try:
        authorizer = (event.get("requestContext") or {}).get("authorizer") or {}
        if not isinstance(authorizer, dict):
            return None

        sub = authorizer.get("sub")
        if sub:
            return str(sub)

        claims = authorizer.get("claims")
        if isinstance(claims, str):
            try:
                claims = json.loads(claims)
            except (json.JSONDecodeError, ValueError):
                return None
        if isinstance(claims, dict):
            claim_sub = claims.get("sub")
            if claim_sub:
                return str(claim_sub)
    except AttributeError:
        return None
    return None


def _owner_sub_from_key(key: Any) -> Optional[str]:
    """Return the owning sub for a ``personal/{sub}/...`` key, or None.

    Handles exactly the three forms the fields read below actually take:

    * ``personal/{sub}/file``     — MainRepresentation ObjectKey.FullPath
    * ``personal/{sub}``          — MainRepresentation ObjectKey.Path
    * ``bucket:personal/{sub}/…`` — top-level StoragePath

    The prefix must sit at the root of the key. Two things depend on that:

    * S3 object keys may contain a colon, so the ``bucket:`` split is only applied when it
      actually yields a personal key. Splitting unconditionally turned
      ``personal/{sub}/foo:bar.jpg`` into ``bar.jpg``, which read as non-personal and
      therefore granted every caller access to an owned asset.
    * Searching for ``/personal/`` anywhere in the path would classify an ordinary
      connector object such as ``archive/personal/notes.txt`` as personal storage owned by
      nobody, denying access to an asset that is not personal at all.
    """
    if not isinstance(key, str) or not key:
        return None

    candidate = key.strip().lstrip("/")

    # StoragePath is "bucket:personal/{sub}/file". Only honour the split when what follows
    # the first colon is itself a personal key, so a colon inside a filename is ignored.
    if ":" in candidate:
        after_colon = candidate.split(":", 1)[1].lstrip("/")
        if after_colon.startswith(PERSONAL_PREFIX):
            candidate = after_colon

    if not candidate.startswith(PERSONAL_PREFIX):
        return None

    remainder = candidate[len(PERSONAL_PREFIX) :]
    owner = remainder.split("/", 1)[0].strip()
    return owner or None


def personal_owner_sub(asset: Dict[str, Any]) -> Optional[str]:
    """Return the sub that owns this asset, or None when it is not personal storage.

    Reads the main representation's location first and falls back to ``StoragePath``, since
    records written by different ingest paths do not populate both consistently.
    """
    if not isinstance(asset, dict):
        return None

    location = (
        ((asset.get("DigitalSourceAsset") or {}).get("MainRepresentation") or {}).get(
            "StorageInfo"
        )
        or {}
    ).get("PrimaryLocation") or {}
    object_key = location.get("ObjectKey") or {}

    for candidate in (
        object_key.get("FullPath"),
        object_key.get("Path"),
        asset.get("StoragePath"),
    ):
        owner = _owner_sub_from_key(candidate)
        if owner:
            return owner
    return None


def caller_owns_personal_asset(
    asset: Dict[str, Any], caller_sub: Optional[str]
) -> bool:
    """True when the asset is not personal, or is personal and owned by the caller.

    A missing caller sub never grants access to personal storage.
    """
    owner = personal_owner_sub(asset)
    if owner is None:
        return True
    return bool(caller_sub) and caller_sub == owner
