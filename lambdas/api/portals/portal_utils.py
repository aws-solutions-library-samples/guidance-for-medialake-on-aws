"""Shared constants and helper functions for portal handlers."""

import json

PORTAL_PK_PREFIX = "UPLOADPORTAL#"
PORTAL_SLUG_PK_PREFIX = "UPLOADPORTAL_SLUG#"
PORTAL_THEME_PK_PREFIX = "PORTALTHEME#"
PORTAL_TEMPLATE_PK_PREFIX = "PORTALTEMPLATE#"
METADATA_SK = "METADATA"
DEST_SK_PREFIX = "DEST#"
TOKEN_SK_PREFIX = "TOKEN#"
INDEX_SK = "INDEX"
GSI1_PK_VALUE = "UPLOADPORTALS"
GSI1_PK_THEMES_VALUE = "PORTALTHEMES"
GSI1_PK_TEMPLATES_VALUE = "PORTALTEMPLATES"

# DynamoDB enforces a hard 400KB per-item limit. Because `pages` + `appearance`
# persist inline on the single METADATA item, an over-large config would fail
# the write at the DynamoDB layer. We reject anything above this safe budget
# (~350KB) with a clean 400 before the write so the failure is recoverable.
MAX_PORTAL_ITEM_SIZE_BYTES = 350 * 1024


def get_portal_pk(portal_id: str) -> str:
    return f"{PORTAL_PK_PREFIX}{portal_id}"


def get_slug_pk(slug: str) -> str:
    return f"{PORTAL_SLUG_PK_PREFIX}{slug}"


def get_theme_pk(theme_id: str) -> str:
    return f"{PORTAL_THEME_PK_PREFIX}{theme_id}"


def get_template_pk(template_id: str) -> str:
    return f"{PORTAL_TEMPLATE_PK_PREFIX}{template_id}"


def get_dest_sk(dest_id: str) -> str:
    return f"{DEST_SK_PREFIX}{dest_id}"


def get_token_sk(token_id: str) -> str:
    return f"{TOKEN_SK_PREFIX}{token_id}"


def _validate_portal_structure(body: dict) -> str | None:
    """Validate multi-page structural invariants. Returns an error message
    string on the first failure, or None when valid.

    Shared by both write handlers (``portals_post.py`` and
    ``portals_ID_put.py``) so the server-side trust boundary matches the
    client-side Zod ``portalPagesSchema``.

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
