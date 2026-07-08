"""Shared upload-portal configuration validation.

This module is deployed in the ``common_libraries`` Lambda layer so it is the
single source of truth for portal validation across every place a portal can be
created or configured:

- the admin portal API (``lambdas/api/portals`` — create / update / a dedicated
  ``/validate`` endpoint),
- the pipeline deployer (``post_pipelines_async`` — fail a deploy early when a
  ``manage_portal`` node is misconfigured), and
- the ``manage_portal`` pipeline node (runtime last line of defence).

It is intentionally dependency-free (stdlib only). Passphrase hashing requires
``bcrypt`` and deliberately lives in the callers that need it (the node and the
admin handlers), not here, so the layer stays lightweight.

The structural rules mirror the client-side Zod ``portalPagesSchema`` used by
the frontend, so server and browser agree on what a valid portal looks like.
"""

import json
import re

# Slug: 3-50 chars, lowercase alphanumeric and hyphens, no leading/trailing hyphen.
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
SLUG_RULE_MESSAGE = "slug must be 3-50 chars, lowercase alphanumeric and hyphens"

# DynamoDB enforces a hard 400KB per-item limit. Because `pages` + `appearance`
# persist inline on the single METADATA item, an over-large config would fail
# the write at the DynamoDB layer. We reject anything above this safe budget
# (~350KB) with a clean error before the write so the failure is recoverable.
MAX_PORTAL_ITEM_SIZE_BYTES = 350 * 1024

# Access-control fields: mutating any of these bumps the portal's accessVersion
# (which invalidates issued session JWTs). Centralised so the node and the admin
# PUT handler agree on the set.
ACCESS_CONTROL_FIELDS = {
    "isActive",
    "expiresAt",
    "ipAllowlist",
    "accessMode",
    "allowedGroups",
    "passphrase",
    "tokenBypassesPassphrase",
}

# The portal-metadata fields a caller is allowed to set from a config payload.
# Used to allow-list incoming config (e.g. the node's merged config) instead of
# blindly persisting arbitrary keys. System-managed keys (PK/SK/portalId/slug/
# timestamps/accessVersion/GSI keys) are intentionally excluded.
PORTAL_CONFIG_FIELDS = {
    "name",
    "description",
    "accessMode",
    "expiresAt",
    "allowedGroups",
    "ipAllowlist",
    "metadataFields",
    "appearance",
    "pages",
    "passphrase",
    "tokenBypassesPassphrase",
    "structuredPathMode",
    "captchaEnabled",
    "formSubmissionEnabled",
    "isActive",
    "maxFileSizeBytes",
    "maxFilesPerSession",
    "automationTag",
    "allowedFileTypes",
}


def validate_portal_structure(body: dict) -> str | None:
    """Validate multi-page structural invariants. Returns an error message
    string on the first failure, or None when valid.

    Invariants:
      1. ``pageNumber`` values form the contiguous sequence 1..N (no gaps,
         no duplicates) where N is the page count.
      2. every ``metadataField.pageNumber`` references a real page.
      3. every ``destination.pageNumber`` references a real page.
      4. exactly one page hosts an ``elements`` entry with
         ``kind == "uploader"``.
      5. the serialized ``pages`` + ``appearance`` payload stays under a safe
         DynamoDB item-size budget so the METADATA write cannot fail on size.
    """
    pages = body.get("pages") or []

    # 1. pageNumbers contiguous from 1 (no gaps, no dupes).
    try:
        page_numbers = sorted(p.get("pageNumber") for p in pages)
    except TypeError:
        return "every page must have a numeric pageNumber"
    if any(not isinstance(n, int) or isinstance(n, bool) for n in page_numbers):
        return "every page must have an integer pageNumber"
    if page_numbers != list(range(1, len(pages) + 1)):
        return f"pageNumbers must be contiguous from 1 (got {page_numbers})"

    valid = set(page_numbers)

    # 2. every metadataField.pageNumber references a real page.
    for f in body.get("metadataFields") or []:
        if f.get("pageNumber") not in valid:
            return f"metadata field references unknown page {f.get('pageNumber')}"

    # 3. every destination.pageNumber references a real page.
    for d in body.get("destinations") or []:
        if d.get("pageNumber") not in valid:
            return f"destination references unknown page {d.get('pageNumber')}"

    # 4. exactly one page hosts the uploader element.
    uploader_pages = [
        p.get("pageNumber")
        for p in pages
        for e in (p.get("elements") or [])
        if isinstance(e, dict) and e.get("kind") == "uploader"
    ]
    if len(uploader_pages) != 1:
        return (
            "exactly one page must host the uploader " f"(found {len(uploader_pages)})"
        )

    # 5. serialized pages + appearance stay under the DynamoDB item-size budget.
    try:
        serialized = json.dumps(
            {"pages": pages, "appearance": body.get("appearance")},
            default=str,
        )
    except (TypeError, ValueError):
        return "pages and appearance must be JSON-serializable"
    payload_size = len(serialized.encode("utf-8"))
    if payload_size > MAX_PORTAL_ITEM_SIZE_BYTES:
        return (
            "pages and appearance payload is too large "
            f"({payload_size} bytes; limit {MAX_PORTAL_ITEM_SIZE_BYTES} bytes)"
        )

    return None


# Backwards-compatible alias: existing handlers import the underscore name.
_validate_portal_structure = validate_portal_structure


def validate_slug(slug) -> str | None:
    """Return an error message if ``slug`` is not a valid portal slug, else None."""
    if not isinstance(slug, str) or not SLUG_PATTERN.match(slug):
        return SLUG_RULE_MESSAGE
    return None


def validate_portal_config(config: dict, *, partial: bool = False) -> list[str]:
    """Validate a portal configuration payload and return ALL error messages.

    Returns an empty list when the config is valid.

    Args:
        config: the portal configuration (name, slug, appearance, pages, ...).
        partial: when True, fields that may legitimately be supplied later
            (``name`` / ``slug``) are not required, but any value that IS present
            is still format-checked. Used by update flows and by deploy-time
            validation of a ``manage_portal`` node whose final values may come
            from runtime field-mapping. When False (a full create), ``name`` and
            ``slug`` are required.
    """
    errors: list[str] = []

    if not isinstance(config, dict):
        return ["portal config must be an object"]

    name = config.get("name")
    slug = config.get("slug")

    if slug is not None and slug != "":
        slug_error = validate_slug(slug)
        if slug_error:
            errors.append(slug_error)
    elif not partial:
        errors.append("slug is required")

    if not name and not partial:
        errors.append("name is required")

    appearance = config.get("appearance")
    if appearance is not None and not isinstance(appearance, dict):
        errors.append("appearance must be an object")

    # Structural invariants only apply to the multi-page model. Validate them
    # only when structure-bearing fields are present (mirrors the admin PUT
    # handler), so a simple portal (just slug + name) isn't forced to carry a
    # full page layout.
    if any(k in config for k in ("pages", "metadataFields", "destinations")):
        structure_error = validate_portal_structure(config)
        if structure_error:
            errors.append(structure_error)

    return errors


def select_portal_config_fields(config: dict) -> dict:
    """Return only the allow-listed portal-config fields present in ``config``.

    Prevents arbitrary / misspelled keys from being persisted onto the portal
    metadata item. ``passphrase`` is included here but callers are expected to
    hash it before persisting (hashing lives with the bcrypt-bearing caller).
    """
    return {k: v for k, v in config.items() if k in PORTAL_CONFIG_FIELDS}
