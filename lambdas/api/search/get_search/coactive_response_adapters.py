"""
Coactive response adapter pattern for handling multiple API response formats.

Each adapter translates a specific Coactive API response structure into
normalized field accessors used by CoactiveSearchProvider. This isolates
all response-format knowledge so the core search logic remains format-agnostic.

Supported formats:
- V1: Original format with data[], total_count, nested video/shot structures
- V2: New flat format with results[], composite_slice_score, top-level timing
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CoactiveResponseAdapter(ABC):
    """
    Abstract base class for translating Coactive API responses into
    normalized field accessors.

    Each concrete adapter handles a specific Coactive response format version.
    The CoactiveSearchProvider delegates all response parsing to the active adapter,
    keeping the core search logic format-agnostic.
    """

    @abstractmethod
    def get_format_version(self) -> str:
        """Return the format version identifier (e.g., 'v1', 'v2')"""

    @abstractmethod
    def get_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract the results array from the raw API response."""

    @abstractmethod
    def get_total_count(
        self, response: Dict[str, Any], results: List[Dict[str, Any]]
    ) -> int:
        """Extract or derive the total result count from the response."""

    @abstractmethod
    def get_medialake_uuid(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract the MediaLake UUID from a single result item."""

    @abstractmethod
    def get_score(self, result: Dict[str, Any], rank: int) -> float:
        """
        Extract the relevance score from a single result item.

        Args:
            result: A single result item from the response
            rank: 1-based rank position (used as fallback if no explicit score)

        Returns:
            Relevance score as a float
        """

    @abstractmethod
    def get_media_type(self, result: Dict[str, Any]) -> str:
        """Extract the media type string (e.g., 'video', 'image') from a result."""

    @abstractmethod
    def get_timing_info(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract timing/clip information from a result.

        Returns:
            Dict with keys: start_time_ms, end_time_ms, timestamp_ms, shot_id
            or None if no timing info is available.
        """

    @abstractmethod
    def get_coactive_asset_id(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract the Coactive-internal asset ID (for deletion lookups)."""

    @abstractmethod
    def get_video_group_key(self, result: Dict[str, Any]) -> Optional[str]:
        """
        Get the key used to group multiple results under the same video asset.
        For images, returns None (no grouping needed).
        """

    @abstractmethod
    def get_coactive_metadata(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all Coactive-specific metadata from a result that should be
        preserved through the enrichment pipeline.
        """


class CoactiveV1ResponseAdapter(CoactiveResponseAdapter):
    """
    Adapter for the original Coactive API response format (V1).

    Response structure:
    {
        "data": [
            {
                "coactiveImageId": "...",
                "metadata": {"medialake_uuid": "...", "media_type": "image"},
                "relevance_score": 0.95,
                "score": 0.95
            },
            {
                "video": {
                    "coactiveVideoId": "...",
                    "metadata": {"medialake_uuid": "...", "media_type": "video"}
                },
                "shot": {"shot_id": "...", "start_time_ms": 12000, "end_time_ms": 18000},
                "timestamp": 15000,
                "relevance_score": 0.9
            }
        ],
        "total_count": 42
    }
    """

    def get_format_version(self) -> str:
        return "v1"

    def get_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        return response.get("data", [])

    def get_total_count(
        self, response: Dict[str, Any], results: List[Dict[str, Any]]
    ) -> int:
        return response.get("total_count", len(results))

    def get_medialake_uuid(self, result: Dict[str, Any]) -> Optional[str]:
        # Images: UUID directly in metadata
        uuid = result.get("metadata", {}).get("medialake_uuid")
        if uuid:
            return uuid

        # Videos: UUID nested in video.metadata
        uuid = result.get("video", {}).get("metadata", {}).get("medialake_uuid")
        return uuid

    def get_score(self, result: Dict[str, Any], rank: int) -> float:
        raw_score = result.get("relevance_score") or result.get("score")
        if raw_score is not None:
            return float(raw_score)
        # Derive from rank: rank 1 = 1.0, rank 2 = 0.5, etc.
        return 1.0 / rank

    def get_media_type(self, result: Dict[str, Any]) -> str:
        # Video results have a nested "video" key
        if "video" in result:
            return (
                result.get("video", {}).get("metadata", {}).get("media_type", "video")
            )
        return result.get("metadata", {}).get("media_type", "image")

    def get_timing_info(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        shot = result.get("shot")
        if not shot:
            return None

        return {
            "start_time_ms": shot.get("start_time_ms", 0),
            "end_time_ms": shot.get("end_time_ms", 0),
            "timestamp_ms": result.get("timestamp", 0),
            "shot_id": shot.get("shot_id"),
        }

    def get_coactive_asset_id(self, result: Dict[str, Any]) -> Optional[str]:
        # Images
        if "coactiveImageId" in result:
            return result["coactiveImageId"]
        # Videos
        return result.get("video", {}).get("coactiveVideoId")

    def get_video_group_key(self, result: Dict[str, Any]) -> Optional[str]:
        if "video" in result:
            return result["video"].get("coactiveVideoId")
        return None

    def get_coactive_metadata(self, result: Dict[str, Any]) -> Dict[str, Any]:
        metadata = {}

        if "video" in result:
            # Video result
            metadata = result.get("video", {}).get("metadata", {}).copy()
            if result.get("shot"):
                metadata.update(
                    {
                        "start_time_ms": result["shot"].get("start_time_ms", 0),
                        "end_time_ms": result["shot"].get("end_time_ms", 0),
                        "timestamp_ms": result.get("timestamp", 0),
                        "shot_id": result["shot"].get("shot_id"),
                    }
                )
            if result.get("video", {}).get("coactiveVideoId"):
                metadata["coactive_video_id"] = result["video"]["coactiveVideoId"]
        else:
            # Image result
            metadata = result.get("metadata", {}).copy()

        return metadata


class CoactiveV2ResponseAdapter(CoactiveResponseAdapter):
    """
    Adapter for the new Coactive API response format (V2).

    Response structure:
    {
        "results": [
            {
                "id": "7a3079fa-...",
                "index": 0,
                "start_frame_num": 0,
                "end_frame_num": 20910,
                "start_time_ms": 0,
                "end_time_ms": 871250,
                "composite_id": "ba53b654-...",
                "composite_type": "shot",
                "composite_slice_score": 0.2558,
                "video_id": "098c509b-...",
                "source_path": "s3://...",
                "metadata": {
                    "data": {
                        "medialake_uuid": "b50b11b5-ea36-4b76-aaff-b70b39cee45c",
                        "media_type": "video",
                        "file_format": "MOV",
                        ...
                    }
                }
            }
        ]
    }
    """

    def get_format_version(self) -> str:
        return "v2"

    def get_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        return response.get("results", [])

    def get_total_count(
        self, response: Dict[str, Any], results: List[Dict[str, Any]]
    ) -> int:
        # V2 does not include total_count; derive from results length
        return len(results)

    def get_medialake_uuid(self, result: Dict[str, Any]) -> Optional[str]:
        return result.get("metadata", {}).get("data", {}).get("medialake_uuid")

    def get_score(self, result: Dict[str, Any], rank: int) -> float:
        raw_score = result.get("composite_slice_score")
        if raw_score is not None:
            return float(raw_score)
        # Fallback to generic score fields
        raw_score = result.get("relevance_score") or result.get("score")
        if raw_score is not None:
            return float(raw_score)
        return 1.0 / rank

    def get_media_type(self, result: Dict[str, Any]) -> str:
        return (
            result.get("metadata", {})
            .get("data", {})
            .get("media_type", "video")
            .lower()
        )

    def get_timing_info(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # V2 has timing at the top level
        start_ms = result.get("start_time_ms")
        end_ms = result.get("end_time_ms")

        if start_ms is None and end_ms is None:
            return None

        return {
            "start_time_ms": start_ms or 0,
            "end_time_ms": end_ms or 0,
            "timestamp_ms": (((start_ms or 0) + (end_ms or 0)) // 2),  # Derive midpoint
            "shot_id": result.get("composite_id"),
            # V2-specific fields
            "start_frame_num": result.get("start_frame_num"),
            "end_frame_num": result.get("end_frame_num"),
            "composite_type": result.get("composite_type"),
        }

    def get_coactive_asset_id(self, result: Dict[str, Any]) -> Optional[str]:
        # V2 uses a top-level "id" field
        return result.get("id")

    def get_video_group_key(self, result: Dict[str, Any]) -> Optional[str]:
        # V2 uses video_id for grouping video clips
        return result.get("video_id")

    def get_coactive_metadata(self, result: Dict[str, Any]) -> Dict[str, Any]:
        metadata = result.get("metadata", {}).get("data", {}).copy()

        # Add timing info at the top level
        timing = self.get_timing_info(result)
        if timing:
            metadata.update(timing)

        # Add V2-specific fields
        if result.get("video_id"):
            metadata["coactive_video_id"] = result["video_id"]
        if result.get("composite_id"):
            metadata["composite_id"] = result["composite_id"]
        if result.get("composite_type"):
            metadata["composite_type"] = result["composite_type"]
        if result.get("source_path"):
            metadata["source_path"] = result["source_path"]
        if result.get("index") is not None:
            metadata["result_index"] = result["index"]

        return metadata


# --- Adapter Registry ---

# Default Coactive endpoints for each format version
COACTIVE_DEFAULT_ENDPOINTS = {
    "v1": {
        "search": "https://api.coactive.ai/api/v1/search/text-to-image",
        "dataset": "https://app.coactive.ai/api/v1",
        "auth": "https://api.coactive.ai/api/v0/login",
    },
    "v2": {
        "search": "https://api.coactive.ai/api/v1/search/text-to-image",
        "dataset": "https://app.coactive.ai/api/v1",
        "auth": "https://api.coactive.ai/api/v0/login",
    },
}

# Registry mapping format version to adapter class
_ADAPTER_REGISTRY: Dict[str, type] = {
    "v1": CoactiveV1ResponseAdapter,
    "v2": CoactiveV2ResponseAdapter,
}


def get_response_adapter(response_format: str) -> CoactiveResponseAdapter:
    """
    Get the appropriate response adapter for the given format version.

    Args:
        response_format: Format version string ('v1' or 'v2')

    Returns:
        An instance of the appropriate adapter

    Raises:
        ValueError: If the format version is not recognized
    """
    adapter_class = _ADAPTER_REGISTRY.get(response_format)
    if not adapter_class:
        raise ValueError(
            f"Unknown Coactive response format: '{response_format}'. "
            f"Supported formats: {list(_ADAPTER_REGISTRY.keys())}"
        )
    return adapter_class()


def detect_response_format(response: Dict[str, Any]) -> str:
    """
    Auto-detect the response format from the raw API response.

    Heuristic:
    - If 'results' key exists → V2
    - If 'data' key exists → V1
    - Default → V1 (backward compatibility)
    """
    if "results" in response:
        return "v2"
    if "data" in response:
        return "v1"
    return "v1"


def get_default_endpoints(response_format: str = "v1") -> Dict[str, str]:
    """
    Get the default Coactive endpoints for a given response format version.

    Returns dict with keys: search, dataset, auth
    """
    return COACTIVE_DEFAULT_ENDPOINTS.get(
        response_format, COACTIVE_DEFAULT_ENDPOINTS["v1"]
    ).copy()
