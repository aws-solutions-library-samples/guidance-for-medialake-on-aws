"""Utilities for Settings API."""

from .permission_utils import check_admin_permission, extract_user_context
from .response_utils import (
    create_error_response,
    create_meta,
    create_pagination_response,
    create_success_response,
    decode_cursor,
    encode_cursor,
    generate_request_id,
    now_iso,
)
from .validation_utils import (
    ALLOWED_ICONS,
    validate_collection_type_data,
    validate_hex_color,
    validate_icon_name,
)

__all__ = [
    "check_admin_permission",
    "extract_user_context",
    "create_error_response",
    "create_meta",
    "create_pagination_response",
    "create_success_response",
    "decode_cursor",
    "encode_cursor",
    "generate_request_id",
    "now_iso",
    "ALLOWED_ICONS",
    "validate_collection_type_data",
    "validate_hex_color",
    "validate_icon_name",
]
