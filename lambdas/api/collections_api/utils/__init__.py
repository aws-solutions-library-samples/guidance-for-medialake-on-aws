"""
Collections API Utilities.

Shared utilities used across multiple handler files.
"""

from .formatting_utils import (
    format_asset_as_search_result,
    format_collection_item,
    format_collection_type,
    format_rule,
    format_share,
)
from .item_utils import (
    generate_asset_sk,
)
from .opensearch_utils import (
    fetch_assets_from_opensearch,
    get_all_clips_for_asset,
    get_opensearch_client,
)
from .pagination_utils import (
    apply_sorting,
    create_cursor,
    parse_cursor,
)

__all__ = [
    # OpenSearch utilities
    "get_opensearch_client",
    "get_all_clips_for_asset",
    "fetch_assets_from_opensearch",
    # Formatting utilities
    "format_collection_item",
    "format_asset_as_search_result",
    "format_share",
    "format_rule",
    "format_collection_type",
    # Item utilities
    "generate_asset_sk",
    # Pagination utilities
    "parse_cursor",
    "create_cursor",
    "apply_sorting",
]
