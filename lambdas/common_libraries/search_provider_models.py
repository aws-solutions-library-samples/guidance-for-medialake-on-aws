"""
Search Provider Models and Enums
===============================
Core models and enums for the search provider plugin architecture.
These are shared across all search providers and consumers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class SearchArchitectureType(Enum):
    """Types of search architectures supported"""

    PROVIDER_PLUS_STORE = "provider_plus_store"  # TwelveLabs + OpenSearch/S3Vector
    EXTERNAL_SEMANTIC_SERVICE = "external_semantic_service"  # Coactive


class ProviderLocation(Enum):
    """Location where the provider runs"""

    INTERNAL = "internal"  # runs inside customer AWS account
    EXTERNAL = "external"  # SaaS provider called by MediaLake


class SearchType(Enum):
    """Types of search operations"""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass
class SearchProviderConfig:
    """Configuration for a search provider"""

    provider: str
    provider_location: ProviderLocation
    architecture: SearchArchitectureType
    auth: Optional[Dict[str, Any]] = None
    endpoint: Optional[str] = None
    store: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    metadata_mapping: Optional[Dict[str, Any]] = None
    callbacks: Optional[Dict[str, Any]] = None
    dataset_id: Optional[str] = None


@dataclass
class SearchQuery:
    """Search query parameters"""

    query_text: str
    search_type: SearchType
    media_types: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None


@dataclass
class SearchHit:
    """Individual search result"""

    asset_id: str
    score: float
    source: Dict[str, Any]
    media_type: str
    highlights: Optional[Dict[str, List[str]]] = None
    clips: Optional[List[Dict[str, Any]]] = None
    provider_metadata: Optional[Dict[str, Any]] = None


@dataclass
class SearchResult:
    """Search results container"""

    hits: List[SearchHit]
    total_results: int
    max_score: float
    took_ms: int
    provider: str
    architecture_type: SearchArchitectureType
    provider_location: ProviderLocation
    facets: Optional[Dict[str, Any]] = None


@dataclass
class MediaType:
    """Media type constants"""

    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    ALL = "all"


def create_search_query_from_params(query_params: Dict[str, Any]) -> SearchQuery:
    """Create SearchQuery from HTTP query parameters"""
    # Extract basic parameters
    query_text = query_params.get("q", "")
    page = int(query_params.get("page", 1))
    page_size = int(query_params.get("pageSize", 50))
    semantic = query_params.get("semantic", "false").lower() == "true"

    # Calculate page offset
    page_offset = (page - 1) * page_size

    return SearchQuery(
        query_text=query_text,
        search_type=SearchType.SEMANTIC if semantic else SearchType.KEYWORD,
        media_types=None,
        filters=None,
        limit=page_size,
        offset=page_offset,
    )


def create_search_provider_config(
    provider_data: Dict[str, Any],
) -> SearchProviderConfig:
    """Create a SearchProviderConfig from dictionary data"""
    return SearchProviderConfig(
        provider=provider_data.get("provider", ""),
        provider_location=ProviderLocation(
            provider_data.get("provider_location", "external")
        ),
        architecture=SearchArchitectureType(
            provider_data.get("architecture", "provider_plus_store")
        ),
        auth=provider_data.get("auth"),
        endpoint=provider_data.get("endpoint"),
        store=provider_data.get("store"),
        capabilities=provider_data.get("capabilities"),
        metadata_mapping=provider_data.get("metadata_mapping"),
        callbacks=provider_data.get("callbacks"),
        dataset_id=provider_data.get("dataset_id"),
    )


class AssetDeletionResult:
    """Result of asset deletion from external service"""

    def __init__(
        self,
        success: bool,
        message: str = "",
        deleted_count: int = 0,
        errors: Optional[List[str]] = None,
    ):
        self.success = success
        self.message = message
        self.deleted_count = deleted_count
        self.errors = errors or []


class ExternalServicePlugin(ABC):
    """Base class for external service plugins that handle asset lifecycle events"""

    def __init__(self, config: Dict[str, Any], logger, metrics):
        self.config = config
        self.logger = logger
        self.metrics = metrics

    @abstractmethod
    def get_service_name(self) -> str:
        """Return the name of the external service"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the service is available and properly configured"""

    @abstractmethod
    def delete_asset(
        self, asset_record: Dict[str, Any], inventory_id: str
    ) -> AssetDeletionResult:
        """Delete asset from external service"""

    def supports_asset_type(self, asset_type: str) -> bool:
        """Check if this plugin supports the given asset type"""
        capabilities = self.config.get("capabilities", {})
        supported_media = capabilities.get("media", [])
        return asset_type.lower() in [media.lower() for media in supported_media]
