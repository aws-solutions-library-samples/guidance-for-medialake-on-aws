"""
Unified search data models and enums for MediaLake search architecture.
Supports both provider+store and external semantic service patterns.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class SearchType(Enum):
    """Type of search to perform"""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"


class SearchArchitectureType(Enum):
    """Architecture pattern for search execution"""

    PROVIDER_PLUS_STORE = "provider_plus_store"  # TwelveLabs + OpenSearch/S3Vector
    EXTERNAL_SEMANTIC_SERVICE = "external_semantic_service"  # Coactive


class ProviderLocation(Enum):
    """Location of the search provider relative to MediaLake"""

    INTERNAL = "internal"  # runs inside customer AWS account
    EXTERNAL = "external"  # SaaS provider called by MediaLake


class MediaType(Enum):
    """Supported media types for search"""

    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    ALL = "all"


@dataclass
class SearchQuery:
    """Unified search query model"""

    query_text: str
    search_type: SearchType = SearchType.KEYWORD
    page_size: int = 50  # default=50, max=200; future: cursor-based
    page_offset: int = 0
    filters: Optional[List[Dict]] = (
        None  # Unified filters (includes mediaType, facets, ranges)
    )
    threshold: float = 0.7
    include_clips: bool = True
    fields: Optional[List[str]] = None  # Fields to return to FE (used in enrichment)

    def __post_init__(self):
        """Validate query parameters"""
        if self.page_size > 200:
            self.page_size = 200
        if self.page_size < 1:
            self.page_size = 1
        if self.page_offset < 0:
            self.page_offset = 0
        if self.threshold < 0:
            self.threshold = 0.0
        if self.threshold > 1:
            self.threshold = 1.0


@dataclass
class SearchHit:
    """Unified search result hit"""

    asset_id: str
    score: float
    source: Dict[str, Any]
    media_type: MediaType
    highlights: Optional[Dict[str, List[str]]] = None
    clips: Optional[List[Dict[str, Any]]] = None
    provider_metadata: Optional[Dict[str, Any]] = None


@dataclass
class SearchResult:
    """Unified search result"""

    hits: List[SearchHit]
    total_results: int
    max_score: float
    took_ms: int
    provider: str
    architecture_type: SearchArchitectureType
    provider_location: ProviderLocation
    facets: Optional[Dict[str, Any]] = None


@dataclass
class SearchProviderConfig:
    """Configuration for a search provider"""

    provider: str
    provider_location: ProviderLocation
    architecture: SearchArchitectureType
    capabilities: Dict[str, Any]
    endpoint: Optional[str] = None
    store: Optional[str] = None  # For provider_plus_store architecture
    auth: Optional[Dict[str, Any]] = None
    metadata_mapping: Optional[Dict[str, str]] = None
    callbacks: Optional[Dict[str, str]] = None
    dataset_id: Optional[str] = None  # For external services like Coactive


def parse_filters_from_query_params(query_params: Dict[str, Any]) -> List[Dict]:
    """
    Parse filters from query parameters into unified filter format.
    Handles both new unified filters and legacy parameters.
    """
    filters = []

    # Parse JSON filters if provided
    if "filters" in query_params and query_params["filters"]:
        import json

        try:
            parsed_filters = json.loads(query_params["filters"])
            if isinstance(parsed_filters, dict):
                # Convert dict format to list format
                for key, value in parsed_filters.items():
                    if key == "mediaType" and isinstance(value, list):
                        filters.append(
                            {"key": "mediaType", "operator": "in", "value": value}
                        )
                    elif isinstance(value, dict) and "gte" in value or "lte" in value:
                        # Range filter
                        filters.append(
                            {"key": key, "operator": "range", "value": value}
                        )
                    else:
                        # Exact match filter
                        filters.append({"key": key, "operator": "==", "value": value})
            elif isinstance(parsed_filters, list):
                filters.extend(parsed_filters)
        except (json.JSONDecodeError, TypeError):
            pass

    # Handle legacy parameters for backward compatibility
    legacy_mappings = {
        "type": "DigitalSourceAsset.Type",
        "extension": "DigitalSourceAsset.MainRepresentation.Format",
        "media_types": "mediaType",
    }

    for param, field in legacy_mappings.items():
        if param in query_params and query_params[param]:
            value = query_params[param]
            if isinstance(value, str) and "," in value:
                value = value.split(",")

            filters.append(
                {
                    "key": field,
                    "operator": "in" if isinstance(value, list) else "==",
                    "value": value,
                }
            )

    # Handle size range filters
    if "asset_size_gte" in query_params or "asset_size_lte" in query_params:
        range_filter = {"key": "fileSize", "operator": "range", "value": {}}
        if "asset_size_gte" in query_params:
            range_filter["value"]["gte"] = query_params["asset_size_gte"]
        if "asset_size_lte" in query_params:
            range_filter["value"]["lte"] = query_params["asset_size_lte"]
        filters.append(range_filter)

    # Handle date range filters
    if "ingested_date_gte" in query_params or "ingested_date_lte" in query_params:
        range_filter = {"key": "createdAt", "operator": "range", "value": {}}
        if "ingested_date_gte" in query_params:
            range_filter["value"]["gte"] = query_params["ingested_date_gte"]
        if "ingested_date_lte" in query_params:
            range_filter["value"]["lte"] = query_params["ingested_date_lte"]
        filters.append(range_filter)

    return filters


def parse_fields_from_query_params(query_params: Dict[str, Any]) -> Optional[List[str]]:
    """Parse fields parameter from query parameters"""
    fields_param = query_params.get("fields")
    if fields_param:
        if isinstance(fields_param, str):
            return [field.strip() for field in fields_param.split(",") if field.strip()]
        elif isinstance(fields_param, list):
            return fields_param
    return None


def create_search_query_from_params(query_params: Dict[str, Any]) -> SearchQuery:
    """Create SearchQuery from HTTP query parameters"""
    # Extract basic parameters
    query_text = query_params.get("q", "")
    page = int(query_params.get("page", 1))
    page_size = int(query_params.get("pageSize", 50))
    semantic = query_params.get("semantic", "false").lower() == "true"
    threshold = float(query_params.get("threshold", 0.7))
    include_clips = query_params.get("includeClips", "true").lower() == "true"

    # Calculate page offset
    page_offset = (page - 1) * page_size

    # Parse filters and fields
    filters = parse_filters_from_query_params(query_params)
    fields = parse_fields_from_query_params(query_params)

    return SearchQuery(
        query_text=query_text,
        search_type=SearchType.SEMANTIC if semantic else SearchType.KEYWORD,
        page_size=page_size,
        page_offset=page_offset,
        filters=filters if filters else None,
        threshold=threshold,
        include_clips=include_clips,
        fields=fields,
    )
