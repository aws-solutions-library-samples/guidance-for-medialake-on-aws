"""
Pydantic V2 models for Collections API.

This package contains all data models for request/response validation.
"""

from .collection_models import (
    CollectionListResponse,
    CollectionMetadata,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from .common_models import (
    ApiResponse,
    CollectionStatus,
    GetCollectionAssetsQueryParams,
    ListCollectionsQueryParams,
    RelationshipType,
    SortDirection,
)
from .item_models import (
    AddItemToCollectionRequest,
    CollectionItem,
)
from .share_models import (
    ShareCollectionRequest,
)

__all__ = [
    # Collection models
    "CollectionMetadata",
    "CreateCollectionRequest",
    "UpdateCollectionRequest",
    "CollectionListResponse",
    # Item models
    "AddItemToCollectionRequest",
    "CollectionItem",
    # Share models
    "ShareCollectionRequest",
    # Common models
    "ApiResponse",
    "CollectionStatus",
    "RelationshipType",
    "SortDirection",
    "ListCollectionsQueryParams",
    "GetCollectionAssetsQueryParams",
]
