"""Shared constants and helper functions for portal handlers.

Portal *validation* (slug/appearance/structure rules) is the single source of
truth in the ``common_libraries`` layer module ``portal_validation`` so the
admin API, the pipeline deployer, and the ``manage_portal`` node all agree.
This module re-exports those symbols for backwards compatibility with the
handlers that import them from here.
"""

import os
import sys

# Make the shared ``portal_validation`` module importable both at Lambda runtime
# (it ships in the common_libraries layer at /opt/python, already on sys.path)
# and when this file is loaded directly from source in unit tests. The repo's
# layout is lambdas/api/portals/portal_utils.py → lambdas/common_libraries.
_COMMON_LIBS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "common_libraries",
)
if os.path.isdir(_COMMON_LIBS_DIR) and _COMMON_LIBS_DIR not in sys.path:
    sys.path.insert(0, _COMMON_LIBS_DIR)

from portal_validation import (  # noqa: E402
    ACCESS_CONTROL_FIELDS,
    MAX_PORTAL_ITEM_SIZE_BYTES,
    PORTAL_CONFIG_FIELDS,
    SLUG_PATTERN,
    _validate_portal_structure,
    select_portal_config_fields,
    validate_portal_config,
    validate_portal_structure,
)

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
