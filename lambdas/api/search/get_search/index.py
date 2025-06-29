from xmlrpc import client
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, conint, ConfigDict
import os
import boto3
import concurrent.futures
from collections import defaultdict

from opensearchpy import (
    RequestsHttpConnection,
    RequestsAWSV4SignerAuth,
    OpenSearch,
    OpenSearchException,
    RequestError,
    NotFoundError,
    helpers,
)
from datetime import datetime
import json
from search_utils import (
    generate_presigned_url,
    parse_search_query,
    parse_size_value,
    parse_date_value,
    parse_metadata_value,
    replace_decimals,
    CustomEncoder
)
from api_utils import get_api_key, get_endpoint

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
    pass


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


def build_semantic_query(params: SearchParams) -> Dict:
    from twelvelabs import TwelveLabs
    from twelvelabs.models.embed import SegmentEmbedding

    logger.info(f"Building semantic query for: {params.q}")

    # Get the API key from Secrets Manager
    api_key = get_api_key()
    if not api_key:
        raise SearchException("Search provider API key not configured or provider not enabled")

    # Initialize the Twelve Labs client
    twelve_labs_client = TwelveLabs(api_key=api_key)

    try:
        # Create embedding for the search query
        res = twelve_labs_client.embed.create(
            model_name="Marengo-retrieval-2.7",
            text=params.q,
        )

        if res.text_embedding is not None and res.text_embedding.segments is not None:
            embedding = list(res.text_embedding.segments[0].embeddings_float)
            if not all(isinstance(x, (int, float)) for x in embedding):
                raise SearchException("Invalid embedding format")

            logger.info(f"Generated embedding for query: {params.q} (length: {len(embedding)})")

            query = {
                "size": params.pageSize * 20,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": embedding,
                                        "k": params.pageSize * 20
                                    }
                                }
                            }
                        ]
                    }
                },
                "_source": {
                    "excludes": ["embedding"]
                }
            }
            # If clip logic is disabled, exclude clip hits in the semantic query
            if not CLIP_LOGIC_ENABLED:
                query["query"]["bool"]["must_not"] = [
                    {"term": {"embedding_scope": "clip"}}
                ]

            logger.info(f"Semantic query size: {query['size']}, k: {query['query']['bool']['must'][0]['knn']['embedding']['k']}")
            return query
        else:
            raise SearchException("Failed to generate embedding for search term")
    except Exception as e:
        logger.exception("Error generating embedding for search term")
        raise SearchException(f"Error generating embedding: {str(e)}")


def build_search_query(params: SearchParams) -> Dict:
    """Build OpenSearch query from search parameters"""
    logger.info("Building search query", extra={"semantic": params.semantic, "query": params.q})

    if params.semantic:
        return build_semantic_query(params)

    clean_query, parsed_filters = parse_search_query(params.q)
    logger.info("Parsed search query", extra={"clean_query": clean_query})

    name_fields = [
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name^3",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath^2"
    ]

    type_fields = [
        "DigitalSourceAsset.Type^2",
        "DigitalSourceAsset.MainRepresentation.Format^2",
        "Metadata.Embedded.S3.ContentType"
    ]

    # Base query structure
    query = {
        "bool": {
            "must": [
                {"exists": {"field": "InventoryID"}},
                {"bool": {"must_not": {"term": {"InventoryID": ""}}}}
            ],
            "must_not": [{"term": {"embedding_scope": "clip"}}],
            "filter": []
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
                        "boost": 4.0
                    }
                }
            },
            # Enhanced phrase prefix matching
            {
                "match_phrase_prefix": {
                    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name": {
                        "query": clean_query,
                        "boost": 3.0
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
                    "boost": 2
                }
            },
            {
                "multi_match": {
                    "query": clean_query,
                    "fields": type_fields,
                    "type": "cross_fields",
                    "operator": "or",
                    "minimum_should_match": "1",
                    "boost": 1
                }
            },
            {
                "query_string": {
                    "query": f"*{clean_query}*",
                    "fields": name_fields,
                    "analyze_wildcard": True,
                    "boost": 0.7
                }
            }
        ]
        
        # Add individual term matches for multi-keyword search with OR logic
        if len(terms) > 1:
            for term in terms:
                query["bool"]["should"].append({
                    "multi_match": {
                        "query": term,
                        "fields": name_fields + type_fields,
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                        "boost": 0.5
                    }
                })
        
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
        filters_to_add.append({"terms": {"DigitalSourceAsset.MainRepresentation.Format": var_ext}})

    if params.asset_size_lte is not None and params.asset_size_gte is not None:
        filters_to_add.append({
            "range": {
                "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size": {
                    "gte": params.asset_size_gte,
                    "lte": params.asset_size_lte
                }
            }
        })

    if params.ingested_date_lte is not None and params.ingested_date_gte is not None:
        filters_to_add.append({
            "range": {
                "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate": {
                    "gte": params.ingested_date_gte,
                    "lte": params.ingested_date_lte
                }
            }
        })

    # Process generic filters
    if params.filters:
        for filter_item in params.filters:
            if filter_item.get("operator") == "term":
                filters_to_add.append({"term": {filter_item["field"]: filter_item["value"]}})
            elif filter_item.get("operator") == "range":
                filters_to_add.append({"range": {filter_item["field"]: filter_item["value"]}})

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
                    "size": 50
                }
            },
            "asset_types": {
                "terms": {
                    "field": "DigitalSourceAsset.Type.keyword",
                    "size": 20
                }
            },
            "file_extensions": {
                "terms": {
                    "field": "DigitalSourceAsset.MainRepresentation.Format.keyword",
                    "size": 50
                }
            },
            "file_size_ranges": {
                "range": {
                    "field": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
                    "ranges": [
                        { "to": 1024 * 100 },                  # < 100KB
                        { "from": 1024 * 100, "to": 1024 * 1024 },      # 100KB - 1MB
                        { "from": 1024 * 1024, "to": 10 * 1024 * 1024 },  # 1MB - 10MB
                        { "from": 10 * 1024 * 1024, "to": 100 * 1024 * 1024 },  # 10MB - 100MB
                        { "from": 100 * 1024 * 1024 }          # > 100MB
                    ]
                }
            },
            "ingestion_date": {
                "date_histogram": {
                    "field": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
                    "calendar_interval": "month",
                    "format": "yyyy-MM-dd"
                }
            }
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
                "Metadata.Consolidated.type"
            ]
        }
    }


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


def process_search_hit(hit: Dict) -> Dict:
    """Process a single search hit and add presigned URL if thumbnail representation exists"""
    source = hit["_source"]
    digital_source_asset = source.get("DigitalSourceAsset", {})
    derived_representations = source.get("DerivedRepresentations", [])
    main_rep = digital_source_asset.get("MainRepresentation", {})
    storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})

    asset_id = digital_source_asset.get("ID", "unknown")
    logger.debug(f"Processing asset {asset_id} with score {hit.get('_score', 0)}")

    thumbnail_url = None
    proxy_url = None

    # Process derived representations for thumbnails and proxies
    for representation in derived_representations:
        purpose = representation.get("Purpose")
        rep_storage_info = representation.get("StorageInfo", {}).get("PrimaryLocation", {})

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
    logger.debug(f"Processing clip for asset {asset_id} with score {clip_hit.get('_score', 0)}")

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
    clip_fields = ["embedding_scope", "start_timecode", "end_timecode", "type", "timestamp"]
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
                    "must_not": [{"term": {"embedding_scope": "clip"}}]
                }
            },
            "size": 1
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
                    clips_by_asset[asset_id].append({
                        "source": source,
                        "score": hit["_score"],
                        "hit": hit
                    })
                    orphaned_clip_assets.add(asset_id)
        else:
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                parent_assets[asset_id] = {
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit
                }
                orphaned_clip_assets.discard(asset_id)  # More efficient than remove with check
            else:
                standalone_hits.append(hit)

    logger.info(f"Found {len(parent_assets)} parent assets, clips for {len(clips_by_asset)} assets, {len(standalone_hits)} standalone hits, {len(orphaned_clip_assets)} orphaned clip assets")

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
                        "must_not": [{"term": {"embedding_scope": "clip"}}]
                    }
                },
                "size": len(orphan_ids)
            }
            
            try:
                resp = client.search(body=batch_query, index=index_name)
                for hit in resp["hits"]["hits"]:
                    src = hit["_source"]
                    pid = src["DigitalSourceAsset"]["ID"]
                    highest_clip_score = max(
                        (c["score"] for c in clips_by_asset.get(pid, [])),
                        default=0
                    )
                    parent_assets[pid] = {
                        "source": src,
                        "score": highest_clip_score,
                        "hit": hit
                    }
                    logger.debug(f"Fetched parent asset for orphaned clips: {pid} with score {highest_clip_score}")
            except Exception as e:
                logger.warning(f"Error batch fetching parent assets: {str(e)}")

    def process_asset_with_clips(asset_id):
        if asset_id not in parent_assets:
            return None
            
        try:
            parent_hit = parent_assets[asset_id]["hit"]
            result = process_search_hit(parent_hit)
            parent_score = parent_hit["_score"]
            
            if asset_id in clips_by_asset:
                asset_clips = clips_by_asset[asset_id]
                highest_clip_score = max(c["score"] for c in asset_clips)
                
                # Use highest clip score
                result["score"] = min(highest_clip_score, 1.0)
                
                # Sort clips by score and process them
                sorted_clips = sorted(asset_clips, key=lambda x: x["score"], reverse=True)
                result["clips"] = [process_clip(c["hit"]) for c in sorted_clips]
                
                logger.debug(f"Processed asset {asset_id} with {len(result['clips'])} clips, final score: {result['score']}")
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
            executor.submit(process_standalone_hit, hit) 
            for hit in standalone_hits
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


def create_search_metadata(total_results: int, params: SearchParams, aggregations=None, suggestions=None) -> SearchMetadata:
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
    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    try:
        search_body = build_search_query(params)
        logger.info("Executing OpenSearch query", extra={"semantic": params.semantic})

        response = client.search(body=search_body, index=index_name)
        hits = response.get("hits", {}).get("hits", [])
        
        logger.info(f"OpenSearch returned {len(hits)} hits from {response['hits']['total']['value']} total")

        if params.semantic:
            if CLIP_LOGIC_ENABLED:
                processed_results = process_semantic_results_parallel(hits)
                
                # Add common fields to each result and clips
                for result in processed_results:
                    add_common_fields(result)
                    if "clips" in result and result["clips"]:
                        for clip in result["clips"]:
                            add_common_fields(clip)
                
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
                    total_count = (params.page - 1) * params.pageSize + len(paged_results)
                else:
                    total_count = total_results
                
                search_metadata = create_search_metadata(
                    total_count, params, response.get("aggregations"), response.get("suggest")
                )
                
                logger.info(f"Semantic search completed: {total_results} total, {len(paged_results)} returned")
                
                return {
                    "status": "200",
                    "message": "ok",
                    "data": {
                        "searchMetadata": search_metadata.model_dump(by_alias=True),
                        "results": paged_results,
                    },
                }
            else:
                # Semantic search without clip logic
                results = []
                for hit in hits:
                    try:
                        result = process_search_hit(hit)
                        results.append(result)
                    except Exception as e:
                        logger.warning(f"Error processing hit: {str(e)}")
                        continue

                # Handle pagination
                total_results = len(results)
                start_idx = (params.page - 1) * params.pageSize
                end_idx = start_idx + params.pageSize
                
                if start_idx >= total_results:
                    start_idx = 0
                    end_idx = min(params.pageSize, total_results)
                
                paged_results = results[start_idx:end_idx]
                
                search_metadata = create_search_metadata(
                    total_results, params, response.get("aggregations"), response.get("suggest")
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
            # Regular text search
            results = []
            for hit in hits:
                try:
                    result = process_search_hit(hit)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Error processing hit: {str(e)}")
                    continue

            logger.info(f"Regular search completed: {len(results)} results processed")
            
            search_metadata = create_search_metadata(
                response["hits"]["total"]["value"], params, 
                response.get("aggregations"), response.get("suggest")
            )
            
            return {
                "status": "200",
                "message": "ok",
                "data": {
                    "searchMetadata": search_metadata.model_dump(by_alias=True),
                    "results": results,
                },
            }

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
    try:
        query_params = app.current_event.get("queryStringParameters") or {}
        
        # Ensure required parameter exists
        if "q" not in query_params:
            return {"status": "400", "message": "Missing required parameter 'q'", "data": None}
        
        params = SearchParams(**query_params)
        result = perform_search(params)
        
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
    return app.resolve(event, context)
