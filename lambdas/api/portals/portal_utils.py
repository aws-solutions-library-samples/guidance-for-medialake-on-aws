"""Shared constants and helper functions for portal handlers."""

PORTAL_PK_PREFIX = "UPLOADPORTAL#"
PORTAL_SLUG_PK_PREFIX = "UPLOADPORTAL_SLUG#"
METADATA_SK = "METADATA"
DEST_SK_PREFIX = "DEST#"
TOKEN_SK_PREFIX = "TOKEN#"
INDEX_SK = "INDEX"
GSI1_PK_VALUE = "UPLOADPORTALS"


def get_portal_pk(portal_id: str) -> str:
    return f"{PORTAL_PK_PREFIX}{portal_id}"


def get_slug_pk(slug: str) -> str:
    return f"{PORTAL_SLUG_PK_PREFIX}{slug}"


def get_dest_sk(dest_id: str) -> str:
    return f"{DEST_SK_PREFIX}{dest_id}"


def get_token_sk(token_id: str) -> str:
    return f"{TOKEN_SK_PREFIX}{token_id}"
