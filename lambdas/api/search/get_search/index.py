import concurrent.futures
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from opensearchpy import (
    NotFoundError,
    OpenSearch,
    RequestError,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)
from pydantic import BaseModel, ConfigDict, Field, conint
from search_utils import (
    generate_presigned_url,
    generate_presigned_urls_batch,
    parse_search_query,
)

# Global flag to enable/disable clip logic
CLIP_LOGIC_ENABLED = True

# Initialize AWS clients and utilities
logger = Logger()
metrics = Metrics()

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)


class SearchException(Exception):
    """Custom exception for search-related errors"""


class BaseModelWithConfig(BaseModel):
    """Base model with JSON configuration"""

    model_config = ConfigDict(json_encoders={datetime: str})


class SearchParams(BaseModelWithConfig):
    """Pydantic model for search parameters"""

    q: str = Field(..., min_length=1)
    page: conint(gt=0) = Field(default=1)  # type: ignore
    pageSize: conint(gt=0, le=500) = Field(default=50)  # type: ignore
    min_score: float = Field(default=0.01)
    filters: Optional[List[Dict]] = None
    search_fields: Optional[List[str]] = None
    semantic: bool = Field(default=False)

    # New facet parameters
    type: Optional[str] = None
    extension: Optional[str] = None
    LargerThan: Optional[int] = None
    asset_size_lte: Optional[int] = None
    asset_size_gte: Optional[int] = None
    ingested_date_lte: Optional[str] = None
    ingested_date_gte: Optional[str] = None
    filename: Optional[str] = None

    # For asset explorer
    storageIdentifier: Optional[str] = None

    @property
    def from_(self) -> int:
        """Calculate the from_ value based on page and pageSize"""
        return (self.page - 1) * self.pageSize

    @property
    def size(self) -> int:
        """Return the pageSize as size"""
        return self.pageSize


class StorageInfo(BaseModelWithConfig):
    """Model for storage information"""

    status: str
    storageType: str
    bucket: str
    path: str
    fullPath: str
    fileSize: Optional[int]
    hashValue: Optional[str]
    createDate: Optional[datetime]


class AssetRepresentation(BaseModelWithConfig):
    """Model for asset representation"""

    id: str
    type: str
    format: str
    purpose: str
    storageInfo: StorageInfo


class AssetMetadata(BaseModelWithConfig):
    """Model for asset metadata"""

    embedded: Optional[Dict[str, Any]]
    generated: Optional[Dict[str, Any]]
    consolidated: Optional[Dict[str, Any]]


class AssetSearchResult(BaseModelWithConfig):
    """Model for search result with presigned URL"""

    InventoryID: str
    DigitalSourceAsset: Dict[str, Any]
    DerivedRepresentations: List[Dict[str, Any]]
    FileHash: str
    Metadata: Dict[str, Any]
    score: float
    thumbnailUrl: Optional[str] = None
    proxyUrl: Optional[str] = None
    clips: Optional[List[Dict[str, Any]]] = None


class SearchMetadata(BaseModelWithConfig):
    """Model for search metadata"""

    totalResults: int
    page: int
    pageSize: int
    searchTerm: str
    facets: Optional[Dict[str, Any]] = None
    suggestions: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModelWithConfig):
    """Model for search response"""

    status: str
    message: str
    data: Dict[str, Any]


# Cache for OpenSearch client
_opensearch_client = None


def get_opensearch_client() -> OpenSearch:
    """Create and return a cached OpenSearch client with optimized settings."""
    global _opensearch_client

    if _opensearch_client is None:
        host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
        region = os.environ["AWS_REGION"]
        service_scope = os.environ["SCOPE"]

        auth = RequestsAWSV4SignerAuth(
            boto3.Session().get_credentials(), region, service_scope
        )

        _opensearch_client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            region=region,
            timeout=30,
            max_retries=2,
            retry_on_timeout=True,
            maxsize=20,  # Increased connection pool size
        )

    return _opensearch_client


def build_search_query(params: SearchParams) -> Dict:
    """Build search query from search parameters"""
    start_time = time.time()
    logger.info(
        f"[PERF] Starting search query build - semantic: {params.semantic}, query: {params.q}"
    )

    if params.semantic:
        # Use embedding store factory for semantic search
        from embedding_store_factory import EmbeddingStoreFactory

        factory = EmbeddingStoreFactory(logger, metrics)
        embedding_store = factory.create_embedding_store()

        # Get the search result from the embedding store
        search_result = embedding_store.search(params)

        # Return the result in a format that can be processed by perform_search
        result = {
            "embedding_store_result": search_result,
            "store_type": factory.get_embedding_store_setting(),
        }

        logger.info(
            f"[PERF] Total search query build time (semantic): {time.time() - start_time:.3f}s"
        )
        return result

    # ────────────────────────────────────────────────────────────────
    # Asset explorer case exact “storageIdentifier:” lookups
    if params.q.startswith("storageIdentifier:"):
        # split off the identifier

        bucket_name = params.q.split(":", 1)[1]
        print(bucket_name)
        return {
            "query": {
                "match_phrase": {
                    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket": bucket_name
                }
            },
            "size": params.size,
        }
    # ─────────────────────────────────────────────────────────────────

    parse_start = time.time()
    clean_query, parsed_filters = parse_search_query(params.q)
    logger.info(f"[PERF] Query parsing took: {time.time() - parse_start:.3f}s")
    logger.info("Parsed search query", extra={"clean_query": clean_query})

    name_fields = [
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name^3",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath^2",
    ]

    type_fields = [
        "DigitalSourceAsset.Type^2",
        "DigitalSourceAsset.MainRepresentation.Format^2",
        "Metadata.Embedded.S3.ContentType",
    ]

    # Base query structure
    query = {
        "bool": {
            "must": [
                {"exists": {"field": "InventoryID"}},
                {"bool": {"must_not": {"term": {"InventoryID": ""}}}},
            ],
            "must_not": [{"term": {"embedding_scope": "clip"}}],
            "filter": [],
        }
    }

    # Handle search terms
    if clean_query:
        terms = clean_query.split()
        query["bool"]["should"] = [
            # Exact prefix match on the file name with highest boost
            {
                "prefix": {
                    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.keyword": {
                        "value": clean_query,
                        "boost": 4.0,
                    }
                }
            },
            # Enhanced phrase prefix matching
            {
                "match_phrase_prefix": {
                    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name": {
                        "query": clean_query,
                        "boost": 3.0,
                    }
                }
            },
            {
                "multi_match": {
                    "query": clean_query,
                    "fields": name_fields,
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "prefix_length": 10,
                    "minimum_should_match": "80%",
                    "boost": 2,
                }
            },
            {
                "multi_match": {
                    "query": clean_query,
                    "fields": type_fields,
                    "type": "cross_fields",
                    "operator": "or",
                    "minimum_should_match": "1",
                    "boost": 1,
                }
            },
            {
                "query_string": {
                    "query": f"*{clean_query}*",
                    "fields": name_fields,
                    "analyze_wildcard": True,
                    "boost": 0.7,
                }
            },
        ]

        # Add individual term matches for multi-keyword search with OR logic
        if len(terms) > 1:
            for term in terms:
                query["bool"]["should"].append(
                    {
                        "multi_match": {
                            "query": term,
                            "fields": name_fields + type_fields,
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                            "boost": 0.5,
                        }
                    }
                )

        query["bool"]["minimum_should_match"] = 1
    else:
        query["bool"]["must"].append({"match_all": {}})

    # Process Facet filters efficiently
    filters_to_add = []

    if params.type:
        var_type = params.type.split(",")
        filters_to_add.append({"terms": {"DigitalSourceAsset.Type": var_type}})

    if params.extension:
        var_ext = params.extension.split(",")
        filters_to_add.append(
            {"terms": {"DigitalSourceAsset.MainRepresentation.Format": var_ext}}
        )

    if params.asset_size_lte is not None or params.asset_size_gte is not None:
        filters_to_add.append(
            {
                "range": {
                    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size": {
                        "gte": params.asset_size_gte,
                        "lte": params.asset_size_lte,
                    }
                }
            }
        )

    if params.ingested_date_lte is not None or params.ingested_date_gte is not None:
        filters_to_add.append(
            {
                "range": {
                    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate": {
                        "gte": params.ingested_date_gte,
                        "lte": params.ingested_date_lte,
                    }
                }
            }
        )

    # Process generic filters
    if params.filters:
        for filter_item in params.filters:
            if filter_item.get("operator") == "term":
                filters_to_add.append(
                    {"term": {filter_item["field"]: filter_item["value"]}}
                )
            elif filter_item.get("operator") == "range":
                filters_to_add.append(
                    {"range": {filter_item["field"]: filter_item["value"]}}
                )

    # Add all filters at once
    query["bool"]["filter"].extend(filters_to_add)

    # Build the complete OpenSearch query with aggregations for facets
    return {
        "query": query,
        "min_score": params.min_score,
        "size": params.size,
        "from": params.from_,
        "aggs": {
            "file_types": {
                "terms": {
                    "field": "DigitalSourceAsset.MainRepresentation.Format.keyword",
                    "size": 50,
                }
            },
            "asset_types": {
                "terms": {"field": "DigitalSourceAsset.Type.keyword", "size": 20}
            },
            "file_extensions": {
                "terms": {
                    "field": "DigitalSourceAsset.MainRepresentation.Format.keyword",
                    "size": 50,
                }
            },
            "file_size_ranges": {
                "range": {
                    "field": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
                    "ranges": [
                        {"to": 1024 * 100},  # < 100KB
                        {"from": 1024 * 100, "to": 1024 * 1024},  # 100KB - 1MB
                        {"from": 1024 * 1024, "to": 10 * 1024 * 1024},  # 1MB - 10MB
                        {
                            "from": 10 * 1024 * 1024,
                            "to": 100 * 1024 * 1024,
                        },  # 10MB - 100MB
                        {"from": 100 * 1024 * 1024},  # > 100MB
                    ],
                }
            },
            "ingestion_date": {
                "date_histogram": {
                    "field": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
                    "calendar_interval": "month",
                    "format": "yyyy-MM-dd",
                }
            },
        },
        "_source": {
            "includes": [
                "InventoryID",
                "DigitalSourceAsset.Type",
                "DigitalSourceAsset.MainRepresentation.Format",
                "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey",
                "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo",
                "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
                "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
                "DigitalSourceAsset.CreateDate",
                "DerivedRepresentations.Purpose",
                "DerivedRepresentations.StorageInfo.PrimaryLocation",
                "FileHash",
                "Metadata.Consolidated.type",
            ]
        },
    }

    logger.info(
        f"[PERF] Total search query build time (regular): {time.time() - start_time:.3f}s"
    )


def add_common_fields(result: Dict, prefix: str = "") -> Dict:
    """Add commonly needed fields to the root level of the result object"""
    # Access the nested structure
    digital_source_asset = result.get(f"{prefix}DigitalSourceAsset", {})
    main_rep = digital_source_asset.get("MainRepresentation", {})
    storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
    object_key = storage_info.get("ObjectKey", {})
    inventory_id = result.get("InventoryID", "")

    # Add ID fields
    if inventory_id:
        # Extract the UUID part from the inventory ID
        if ":" in inventory_id:
            uuid_part = inventory_id.split(":")[-1]
            result["id"] = uuid_part
        else:
            result["id"] = inventory_id

    # Add asset metadata fields
    result["assetType"] = digital_source_asset.get("Type", "")
    result["format"] = main_rep.get("Format", "")
    result["objectName"] = object_key.get("Name", "")
    result["fullPath"] = object_key.get("FullPath", "")
    result["bucket"] = storage_info.get("Bucket", "")

    # Handle file size - check different locations
    file_size = storage_info.get("FileSize", 0)
    if not file_size and "FileInfo" in storage_info:
        file_size = storage_info.get("FileInfo", {}).get("Size", 0)
    result["fileSize"] = file_size

    # Handle creation date - check different locations
    created_date = storage_info.get("CreateDate", "")
    if not created_date and "FileInfo" in storage_info:
        created_date = storage_info.get("FileInfo", {}).get("CreateDate", "")
    if not created_date:
        created_date = digital_source_asset.get("CreateDate", "")
    result["createdAt"] = created_date

    # Include consolidated metadata directly
    if "Metadata" in result and "Consolidated" in result.get("Metadata", {}):
        result["metadata"] = result["Metadata"].get("Consolidated", {})

    return result


def collect_presigned_url_requests(hits: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Collect all presigned URL requests from search hits without generating URLs.
    Returns tuple of (processed_hits_data, url_requests)
    """
    processed_hits = []
    url_requests = []

    for hit in hits:
        source = hit["_source"]
        digital_source_asset = source.get("DigitalSourceAsset", {})
        derived_representations = source.get("DerivedRepresentations", [])

        asset_id = digital_source_asset.get("ID", "unknown")
        hit_data = {
            "hit": hit,
            "source": source,
            "asset_id": asset_id,
            "thumbnail_request_id": None,
            "proxy_request_id": None,
        }

        # Collect URL requests for derived representations
        for representation in derived_representations:
            purpose = representation.get("Purpose")
            rep_storage_info = representation.get("StorageInfo", {}).get(
                "PrimaryLocation", {}
            )

            if rep_storage_info.get("StorageType") == "s3":
                bucket = rep_storage_info.get("Bucket", "")
                key = rep_storage_info.get("ObjectKey", {}).get("FullPath", "")

                if bucket and key:
                    request_id = f"{asset_id}_{purpose}_{len(url_requests)}"

                    url_requests.append(
                        {"request_id": request_id, "bucket": bucket, "key": key}
                    )

                    if purpose == "thumbnail":
                        hit_data["thumbnail_request_id"] = request_id
                    elif purpose == "proxy":
                        hit_data["proxy_request_id"] = request_id

        processed_hits.append(hit_data)

    return processed_hits, url_requests


def process_search_hit_with_urls(
    hit_data: Dict, presigned_urls: Dict[str, Optional[str]]
) -> Dict:
    """Process a single search hit with pre-generated presigned URLs"""
    hit = hit_data["hit"]
    source = hit_data["source"]

    # Get presigned URLs from the batch results
    thumbnail_url = None
    proxy_url = None

    if hit_data["thumbnail_request_id"]:
        thumbnail_url = presigned_urls.get(hit_data["thumbnail_request_id"])

    if hit_data["proxy_request_id"]:
        proxy_url = presigned_urls.get(hit_data["proxy_request_id"])

    # Create base result object
    result = AssetSearchResult(
        InventoryID=source.get("InventoryID", ""),
        DigitalSourceAsset=source.get("DigitalSourceAsset", {}),
        DerivedRepresentations=source.get("DerivedRepresentations", []),
        FileHash=source.get("FileHash", ""),
        Metadata=source.get("Metadata", {}),
        score=hit["_score"],
        thumbnailUrl=thumbnail_url,
        proxyUrl=proxy_url,
    )

    # Convert to dictionary and add common fields
    result_dict = result.model_dump(by_alias=True)
    return add_common_fields(result_dict)


def process_search_hit(hit: Dict) -> Dict:
    """Process a single search hit and add presigned URL if thumbnail representation exists"""
    source = hit["_source"]
    digital_source_asset = source.get("DigitalSourceAsset", {})
    derived_representations = source.get("DerivedRepresentations", [])
    main_rep = digital_source_asset.get("MainRepresentation", {})
    main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})

    asset_id = digital_source_asset.get("ID", "unknown")
    logger.debug(f"Processing asset {asset_id} with score {hit.get('_score', 0)}")

    thumbnail_url = None
    proxy_url = None

    # Process derived representations for thumbnails and proxies
    for representation in derived_representations:
        purpose = representation.get("Purpose")
        rep_storage_info = representation.get("StorageInfo", {}).get(
            "PrimaryLocation", {}
        )

        if rep_storage_info.get("StorageType") == "s3":
            presigned_url = generate_presigned_url(
                bucket=rep_storage_info.get("Bucket", ""),
                key=rep_storage_info.get("ObjectKey", {}).get("FullPath", ""),
            )

            if purpose == "thumbnail":
                thumbnail_url = presigned_url
            elif purpose == "proxy":
                proxy_url = presigned_url

        if thumbnail_url and proxy_url:
            break

    # Create base result object
    result = AssetSearchResult(
        InventoryID=source.get("InventoryID", ""),
        DigitalSourceAsset=digital_source_asset,
        DerivedRepresentations=derived_representations,
        FileHash=source.get("FileHash", ""),
        Metadata=source.get("Metadata", {}),
        score=hit["_score"],
        thumbnailUrl=thumbnail_url,
        proxyUrl=proxy_url,
    )

    # Convert to dictionary and add common fields
    result_dict = result.model_dump(by_alias=True)
    return add_common_fields(result_dict)


def process_clip(clip_hit: Dict) -> Dict:
    """Process a clip hit to preserve all clip-specific fields."""
    source = clip_hit["_source"]
    digital_source_asset = source.get("DigitalSourceAsset", {})
    main_rep = digital_source_asset.get("MainRepresentation", {})
    storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
    object_key = storage_info.get("ObjectKey", {})

    asset_id = digital_source_asset.get("ID", "unknown")
    logger.debug(
        f"Processing clip for asset {asset_id} with score {clip_hit.get('_score', 0)}"
    )

    result = {
        "DigitalSourceAsset": digital_source_asset,
        "score": clip_hit["_score"],
    }

    # Add the same root-level fields as in process_search_hit for consistency
    result["assetType"] = digital_source_asset.get("Type", "")
    result["format"] = main_rep.get("Format", "")
    result["objectName"] = object_key.get("Name", "")
    result["fullPath"] = object_key.get("FullPath", "")
    result["bucket"] = storage_info.get("Bucket", "")

    # Handle different possible locations of file size
    file_size = storage_info.get("FileSize", 0)
    if not file_size and "FileInfo" in storage_info:
        file_size = storage_info.get("FileInfo", {}).get("Size", 0)
    result["fileSize"] = file_size

    # Handle different possible locations of creation date
    created_date = storage_info.get("CreateDate", "")
    if not created_date and "FileInfo" in storage_info:
        created_date = storage_info.get("FileInfo", {}).get("CreateDate", "")
    if not created_date:
        created_date = digital_source_asset.get("CreateDate", "")
    result["createdAt"] = created_date

    # Include any consolidated metadata if available
    if "Metadata" in source and "Consolidated" in source.get("Metadata", {}):
        result["metadata"] = source["Metadata"].get("Consolidated", {})

    # Add clip-specific fields efficiently
    clip_fields = [
        "embedding_scope",
        "start_timecode",
        "end_timecode",
        "type",
        "timestamp",
    ]
    for field in clip_fields:
        if field in source:
            result[field] = source[field]

    # Include any other fields from the source that might be clip-specific
    for key, value in source.items():
        if key not in result and key not in ["DigitalSourceAsset", "Metadata"]:
            result[key] = value

    return result


def get_parent_asset(client, index_name, asset_id):
    """Fetch a parent asset by its ID from OpenSearch."""
    try:
        query = {
            "query": {
                "bool": {
                    "must": [{"term": {"DigitalSourceAsset.ID.keyword": asset_id}}],
                    "must_not": [{"term": {"embedding_scope": "clip"}}],
                }
            },
            "size": 1,
        }

        response = client.search(body=query, index=index_name)

        if response["hits"]["total"]["value"] > 0:
            return response["hits"]["hits"][0]

        return None
    except Exception as e:
        logger.warning(f"Error fetching parent asset {asset_id}: {str(e)}")
        return None


def process_semantic_results_parallel(hits: List[Dict]) -> List[Dict]:
    """
    Process semantic search results using parallel processing for better performance.
    Group clips with their parent assets and keep only the top clips per parent.
    Only Video and Audio assets can have clips.
    """
    parent_assets = {}
    clips_by_asset = defaultdict(list)
    standalone_hits = []
    orphaned_clip_assets = set()

    logger.info(f"Processing {len(hits)} semantic search hits")

    # Categorize hits efficiently
    for hit in hits:
        source = hit["_source"]
        if source.get("embedding_scope") == "clip":
            asset_type = source.get("type", "").lower()
            if asset_type in ["video", "audio"]:
                asset_id = source.get("DigitalSourceAsset", {}).get("ID")
                if asset_id:
                    clips_by_asset[asset_id].append(
                        {"source": source, "score": hit["_score"], "hit": hit}
                    )
                    orphaned_clip_assets.add(asset_id)
        else:
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                parent_assets[asset_id] = {
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit,
                }
                orphaned_clip_assets.discard(
                    asset_id
                )  # More efficient than remove with check
            else:
                standalone_hits.append(hit)

    logger.info(
        f"Found {len(parent_assets)} parent assets, "
        f"clips for {len(clips_by_asset)} assets, "
        f"{len(standalone_hits)} standalone hits, "
        f"{len(orphaned_clip_assets)} orphaned clip assets"
    )

    # Batch fetch orphaned parents if any exist
    if orphaned_clip_assets:
        client = get_opensearch_client()
        index_name = os.environ["OPENSEARCH_INDEX"]

        orphan_ids = list(orphaned_clip_assets - parent_assets.keys())
        if orphan_ids:
            batch_query = {
                "query": {
                    "bool": {
                        "must": [{"terms": {"DigitalSourceAsset.ID": orphan_ids}}],
                        "must_not": [{"term": {"embedding_scope": "clip"}}],
                    }
                },
                "size": len(orphan_ids),
            }

            try:
                resp = client.search(body=batch_query, index=index_name)
                for hit in resp["hits"]["hits"]:
                    src = hit["_source"]
                    pid = src["DigitalSourceAsset"]["ID"]
                    highest_clip_score = max(
                        (c["score"] for c in clips_by_asset.get(pid, [])), default=0
                    )
                    parent_assets[pid] = {
                        "source": src,
                        "score": highest_clip_score,
                        "hit": hit,
                    }
                    logger.debug(
                        f"Fetched parent asset for orphaned clips: {pid} with score {highest_clip_score}"
                    )
            except Exception as e:
                logger.warning(f"Error batch fetching parent assets: {str(e)}")

    def process_asset_with_clips(asset_id):
        if asset_id not in parent_assets:
            return None

        try:
            parent_hit = parent_assets[asset_id]["hit"]
            result = process_search_hit(parent_hit)
            parent_hit["_score"]

            if asset_id in clips_by_asset:
                asset_clips = clips_by_asset[asset_id]
                highest_clip_score = max(c["score"] for c in asset_clips)

                # Use highest clip score
                result["score"] = min(highest_clip_score, 1.0)

                # Sort clips by score and process them
                sorted_clips = sorted(
                    asset_clips, key=lambda x: x["score"], reverse=True
                )
                result["clips"] = [process_clip(c["hit"]) for c in sorted_clips]

                logger.debug(
                    f"Processed asset {asset_id} with {len(result['clips'])} clips, final score: {result['score']}"
                )
            else:
                result["clips"] = []

            return result
        except Exception as e:
            logger.warning(f"Error processing parent asset {asset_id}: {str(e)}")
            return None

    def process_standalone_hit(hit):
        try:
            return process_search_hit(hit)
        except Exception as e:
            logger.warning(f"Error processing standalone hit: {str(e)}")
            return None

    # Process all assets in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Process parent assets with clips
        result_futures = {
            executor.submit(process_asset_with_clips, asset_id): asset_id
            for asset_id in parent_assets.keys()
        }

        # Process standalone hits
        standalone_futures = [
            executor.submit(process_standalone_hit, hit) for hit in standalone_hits
        ]

        # Collect results from parent assets
        for future in concurrent.futures.as_completed(result_futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                asset_id = result_futures[future]
                logger.warning(f"Error processing asset {asset_id}: {str(e)}")

        # Collect results from standalone hits
        for future in concurrent.futures.as_completed(standalone_futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error processing standalone hit: {str(e)}")

    # Sort results by score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    logger.info(f"Successfully processed {len(results)} semantic search results")
    return results


def create_search_metadata(
    total_results: int, params: SearchParams, aggregations=None, suggestions=None
) -> SearchMetadata:
    """Create search metadata object"""
    return SearchMetadata(
        totalResults=total_results,
        page=params.page,
        pageSize=params.pageSize,
        searchTerm=params.q,
        facets=aggregations,
        suggestions=suggestions,
    )


def perform_search(params: SearchParams) -> Dict:
    """Perform search operation in OpenSearch with proper error handling."""
    overall_start = time.time()
    logger.info(f"[PERF] Starting search operation for query: {params.q}")

    client_start = time.time()
    client = get_opensearch_client()
    logger.info(
        f"[PERF] OpenSearch client retrieval took: {time.time() - client_start:.3f}s"
    )

    index_name = os.environ["OPENSEARCH_INDEX"]

    try:
        query_build_start = time.time()
        search_body = build_search_query(params)
        logger.info(
            f"[PERF] Search query building took: {time.time() - query_build_start:.3f}s"
        )

        # Handle semantic search with embedding stores
        if params.semantic and "embedding_store_result" in search_body:
            embedding_result = search_body["embedding_store_result"]
            store_type = search_body["store_type"]

            logger.info(f"Using {store_type} embedding store for semantic search")

            hits = embedding_result.hits
            total_results = embedding_result.total_results
            aggregations = embedding_result.aggregations
            suggestions = embedding_result.suggestions

            logger.info(
                f"{store_type} returned {len(hits)} hits from {total_results} total"
            )
        else:
            # Regular OpenSearch query
            logger.info(
                "Executing OpenSearch query", extra={"semantic": params.semantic}
            )
            opensearch_start = time.time()
            response = client.search(body=search_body, index=index_name)
            opensearch_time = time.time() - opensearch_start
            logger.info(
                f"[PERF] OpenSearch query execution took: {opensearch_time:.3f}s"
            )

            hits = response.get("hits", {}).get("hits", [])
            total_results = response["hits"]["total"]["value"]
            aggregations = response.get("aggregations")
            suggestions = response.get("suggest")

            logger.info(
                f"OpenSearch returned {len(hits)} hits from {total_results} total"
            )

        if params.semantic:
            if CLIP_LOGIC_ENABLED:
                # Check if we're using S3 Vector Store which already processes clips
                store_type = search_body.get("store_type", "")
                if store_type == "s3-vector":
                    logger.info(
                        "Using S3 Vector Store - clips already processed, processing individual hits for UI format"
                    )
                    semantic_processing_start = time.time()
                    # S3 Vector Store already has clips grouped, just process each hit for UI format while preserving clips
                    processed_results = []
                    for hit in hits:
                        # Preserve the clips array before processing
                        clips = hit.get("clips", None)
                        processed_hit = process_search_hit(hit)
                        # Restore the clips array after processing
                        processed_hit["clips"] = clips
                        processed_results.append(processed_hit)
                    logger.info(
                        f"[PERF] S3 Vector results processing took: {time.time() - semantic_processing_start:.3f}s"
                    )
                else:
                    logger.info(
                        "Using OpenSearch - processing clips with process_semantic_results_parallel"
                    )
                    semantic_processing_start = time.time()
                    processed_results = process_semantic_results_parallel(hits)
                    logger.info(
                        f"[PERF] Semantic results processing took: {time.time() - semantic_processing_start:.3f}s"
                    )

                # Add common fields to each result and clips
                common_fields_start = time.time()
                for result in processed_results:
                    add_common_fields(result)
                    if "clips" in result and result["clips"]:
                        for clip in result["clips"]:
                            add_common_fields(clip)
                logger.info(
                    f"[PERF] Adding common fields took: {time.time() - common_fields_start:.3f}s"
                )

                # Handle pagination for semantic results
                total_results = len(processed_results)
                start_idx = (params.page - 1) * params.pageSize
                end_idx = start_idx + params.pageSize

                if start_idx >= total_results:
                    start_idx = 0
                    end_idx = min(params.pageSize, total_results)

                paged_results = processed_results[start_idx:end_idx]

                # Calculate total count for pagination
                if params.page > 1 and len(paged_results) < params.pageSize:
                    total_count = (params.page - 1) * params.pageSize + len(
                        paged_results
                    )
                else:
                    total_count = total_results

                search_metadata = create_search_metadata(
                    total_count,
                    params,
                    aggregations,
                    suggestions,
                )

                logger.info(
                    f"Semantic search completed: {total_results} total, {len(paged_results)} returned"
                )
                logger.info(
                    f"[PERF] Total semantic search time: {time.time() - overall_start:.3f}s"
                )

                return {
                    "status": "200",
                    "message": "ok",
                    "data": {
                        "searchMetadata": search_metadata.model_dump(by_alias=True),
                        "results": paged_results,
                    },
                }
            else:
                # Semantic search without clip logic - with batch presigned URL generation
                batch_processing_start = time.time()

                # Step 1: Collect all presigned URL requests
                url_collection_start = time.time()
                processed_hits_data, url_requests = collect_presigned_url_requests(hits)
                logger.info(
                    f"[PERF] Semantic URL request collection took: {time.time() - url_collection_start:.3f}s"
                )
                logger.info(
                    f"Collected {len(url_requests)} presigned URL requests for {len(processed_hits_data)} semantic hits"
                )

                # Step 2: Generate all presigned URLs in parallel
                if url_requests:
                    batch_url_start = time.time()
                    presigned_urls = generate_presigned_urls_batch(url_requests)
                    logger.info(
                        f"[PERF] Semantic batch presigned URL generation took: {time.time() - batch_url_start:.3f}s"
                    )
                    logger.info(
                        f"Generated {len([url for url in presigned_urls.values() if url])} successful URLs out of {len(url_requests)} requests"
                    )
                else:
                    presigned_urls = {}

                # Step 3: Process all hits with pre-generated URLs
                results_processing_start = time.time()
                results = []
                for hit_data in processed_hits_data:
                    try:
                        result = process_search_hit_with_urls(hit_data, presigned_urls)
                        results.append(result)
                    except Exception as e:
                        logger.warning(f"Error processing semantic hit: {str(e)}")
                        continue

                logger.info(
                    f"[PERF] Semantic results processing took: {time.time() - results_processing_start:.3f}s"
                )
                logger.info(
                    f"[PERF] Total semantic batch processing took: {time.time() - batch_processing_start:.3f}s"
                )

                # Handle pagination
                total_results = len(results)
                start_idx = (params.page - 1) * params.pageSize
                end_idx = start_idx + params.pageSize

                if start_idx >= total_results:
                    start_idx = 0
                    end_idx = min(params.pageSize, total_results)

                paged_results = results[start_idx:end_idx]

                search_metadata = create_search_metadata(
                    total_results,
                    params,
                    aggregations,
                    suggestions,
                )

                return {
                    "status": "200",
                    "message": "ok",
                    "data": {
                        "searchMetadata": search_metadata.model_dump(by_alias=True),
                        "results": paged_results,
                    },
                }
        else:
            # Regular text search with batch presigned URL generation
            batch_processing_start = time.time()

            # Step 1: Collect all presigned URL requests
            url_collection_start = time.time()
            processed_hits_data, url_requests = collect_presigned_url_requests(hits)
            logger.info(
                f"[PERF] URL request collection took: {time.time() - url_collection_start:.3f}s"
            )
            logger.info(
                f"Collected {len(url_requests)} presigned URL requests for {len(processed_hits_data)} hits"
            )

            # Step 2: Generate all presigned URLs in parallel
            if url_requests:
                batch_url_start = time.time()
                presigned_urls = generate_presigned_urls_batch(url_requests)
                logger.info(
                    f"[PERF] Batch presigned URL generation took: {time.time() - batch_url_start:.3f}s"
                )
                logger.info(
                    f"Generated {len([url for url in presigned_urls.values() if url])} successful URLs out of {len(url_requests)} requests"
                )
            else:
                presigned_urls = {}

            # Step 3: Process all hits with pre-generated URLs
            results_processing_start = time.time()
            results = []
            for hit_data in processed_hits_data:
                try:
                    result = process_search_hit_with_urls(hit_data, presigned_urls)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Error processing hit: {str(e)}")
                    continue

            logger.info(
                f"[PERF] Results processing took: {time.time() - results_processing_start:.3f}s"
            )
            logger.info(
                f"[PERF] Total batch processing took: {time.time() - batch_processing_start:.3f}s"
            )
            logger.info(f"Regular search completed: {len(results)} results processed")

            search_metadata = create_search_metadata(
                total_results,
                params,
                aggregations,
                suggestions,
            )

            return {
                "status": "200",
                "message": "ok",
                "data": {
                    "searchMetadata": search_metadata.model_dump(by_alias=True),
                    "results": results,
                },
            }

        total_time = time.time() - overall_start
        logger.info(f"[PERF] Total search operation time: {total_time:.3f}s")

    except (RequestError, NotFoundError) as e:
        logger.warning(f"OpenSearch error: {str(e)}")

        empty_metadata = create_search_metadata(0, params)

        if "no mapping found for field" in str(e):
            return {
                "status": "200",
                "message": "ok",
                "data": {
                    "searchMetadata": empty_metadata.model_dump(by_alias=True),
                    "results": [],
                },
            }
        else:
            return {
                "status": "200",
                "message": "No results found",
                "data": {
                    "searchMetadata": empty_metadata.model_dump(by_alias=True),
                    "results": [],
                },
            }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise SearchException("An unexpected error occurred")


@app.get("/search")
def handle_search():
    """Handle search requests with validated parameters."""
    handler_start = time.time()
    try:
        logger.info(f"[PERF] Starting search handler")

        param_start = time.time()
        query_params = app.current_event.get("queryStringParameters") or {}

        # Ensure required parameter exists
        if "q" not in query_params:
            return {
                "status": "400",
                "message": "Missing required parameter 'q'",
                "data": None,
            }

        params = SearchParams(**query_params)
        logger.info(
            f"[PERF] Parameter validation took: {time.time() - param_start:.3f}s"
        )

        search_start = time.time()
        result = perform_search(params)
        logger.info(f"[PERF] Search execution took: {time.time() - search_start:.3f}s")

        total_handler_time = time.time() - handler_start
        logger.info(f"[PERF] Total handler time: {total_handler_time:.3f}s")
        logger.info(f"Search completed successfully for query: {params.q}")
        return result

    except ValueError as e:
        logger.warning(f"Invalid input parameters: {str(e)}")
        return {"status": "400", "message": str(e), "data": None}
    except SearchException as e:
        logger.error(f"Search error: {str(e)}")
        return {"status": "500", "message": str(e), "data": None}


@metrics.log_metrics
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler function"""
    lambda_start = time.time()
    logger.info(f"[PERF] Lambda handler started")

    result = app.resolve(event, context)

    total_lambda_time = time.time() - lambda_start
    logger.info(f"[PERF] Total Lambda execution time: {total_lambda_time:.3f}s")

    return result
