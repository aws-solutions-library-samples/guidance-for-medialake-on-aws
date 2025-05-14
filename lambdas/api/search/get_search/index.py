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
    asset_size_lte: int = None
    asset_size_gte: int = None
    ingested_date_lte: datetime = None
    ingested_date_gte: datetime = None
    extension: str = None
    content_type: str = None
    format: str = None
    type: str = None


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


def get_opensearch_client() -> OpenSearch:
    """Create and return an OpenSearch client with optimized settings."""
    host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
    region = os.environ["AWS_REGION"]
    service_scope = os.environ["SCOPE"]

    auth = RequestsAWSV4SignerAuth(
        boto3.Session().get_credentials(), region, service_scope
    )

    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        region=region,
        timeout=30,
        max_retries=2,
        retry_on_timeout=True,
        maxsize=10,
    )


def build_semantic_query(params: SearchParams) -> Dict:
    from twelvelabs import TwelveLabs
    from twelvelabs.models.embed import SegmentEmbedding

    logger.info(f"Building semantic query for: {params.q}")

    # Get the API key from Secrets Manager
    api_key = get_api_key()
    if not api_key:
        raise SearchException("Search provider API key not configured or provider not enabled")

    # Get the endpoint from the configuration
    endpoint = get_endpoint()

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

            print(json.dumps(query))
            logger.info(f"Semantic query size: {query['size']}, k: {query['query']['bool']['must'][0]['knn']['embedding']['k']}")
            return query
        else:
            raise SearchException("Failed to generate embedding for search term")
    except Exception as e:
        logger.exception("Error generating embedding for search term")
        raise SearchException(f"Error generating embedding: {str(e)}")


def build_search_query(params: SearchParams) -> Dict:
    """Build OpenSearch query from search parameters"""
    print("this is printing extension",params.extension)
    print("this is printing type",params.type)
    print("this is printing size gte",params.asset_size_gte)
    print("this is printing date gte",params.ingested_date_gte)
    print("this is printing format",params.format)
    logger.info("Building search query with params:", extra={"params": params.model_dump()})

    if params.semantic:
        return build_semantic_query(params)

    clean_query, parsed_filters = parse_search_query(params.q)
    print(clean_query,parsed_filters)
    logger.info("Parsed search query:", extra={"clean_query": clean_query, "filters": parsed_filters})


    name_fields = [
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name^3",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath^2"
    ]

    type_fields = [
        "DigitalSourceAsset.Type^2",
        "DigitalSourceAsset.MainRepresentation.Format^2",
        "Metadata.Embedded.S3.ContentType"
    ]

    # Handle multi-keyword search by splitting the query into terms
    if clean_query:
        terms = clean_query.split()
        query = {
            "bool": {
                "must": [
                    {
                        "exists": {
                            "field": "InventoryID"
                        }
                    },
                    {
                        "bool": {
                            "must_not": {
                                "term": {
                                    "InventoryID": ""
                                }
                            }
                        }
                    }
                ],
                "should": [
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
                        "match_phrase_prefix": {
                            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name": {
                                "query": clean_query,
                                "boost": 1.5
                            }
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
                ],
                "minimum_should_match": 1,
                "must_not": [
                    {
                        "term": {
                            "embedding_scope": "clip"
                        }
                    }
                ],
                "filter": [
                ]
            }
        }
        
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
    else:
        query = {
            "bool": {
                "must": [
                    {"match_all": {}},
                    {
                        "exists": {
                            "field": "InventoryID"
                        }
                    },
                    {
                        "bool": {
                            "must_not": {
                                "term": {
                                    "InventoryID": ""
                                }
                            }
                        }
                    }
                ],
                "must_not": [
                    {
                        "term": {
                            "embedding_scope": "clip"
                        }
                    }
                ],
                "filter": [

         ]
            }
        }


    if params.type is not None:
        query["bool"]["filter"].append(
                           {
                                "term": {"DigitalSourceAsset.Type.keyword": 
                                        {"value":params.type,
                                        "case_insensitive": True
                                        }
                                        }
                            }
    
        )
  
    if params.extension is not None:
        query["bool"]["filter"].append(
                           {
                                "term": {"DigitalSourceAsset.MainRepresentation.Format.keyword": 
                                        {"value":params.extension,
                                        "case_insensitive": True
                                        }
                                        }
                            }
    
        )

    if params.asset_size_lte is not None and params.asset_size_gte is not None:
        try:
            query["bool"]["filter"].append({
                "range": {
                    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size": {
                        "gte": params.asset_size_gte,
                        "lte": params.asset_size_lte
                    }
                }
            })
        except ValueError:
            logger.warning(f"Invalid values for asset size: {params.asset_size_gte,params.asset_size_lte}")

    
    return {
        "query": query,
        "min_score": params.min_score,
        "size": params.size,
        "from": params.from_,
        "aggs": {
            "file_types": {
                "terms": {
                    "field": "DigitalSourceAsset.MainRepresentation.Format.keyword",
                    "size": 20
                }
            },
            "asset_types": {
                "terms": {
                    "field": "DigitalSourceAsset.Type.keyword",
                    "size": 20
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
                "DigitalSourceAsset.CreateDate",
                "DerivedRepresentations.Purpose",
                "DerivedRepresentations.StorageInfo.PrimaryLocation",
                "FileHash",
                "Metadata.Consolidated.type"
            ]
        }
    }


def process_search_hit(hit: Dict) -> AssetSearchResult:
    """Process a single search hit and add presigned URL if thumbnail representation exists"""
    source = hit["_source"]
    digital_source_asset = source.get("DigitalSourceAsset", {})
    derived_representations = source.get("DerivedRepresentations", [])
    main_rep = digital_source_asset.get("MainRepresentation", {})
    storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})

    asset_id = digital_source_asset.get("ID", "unknown")
    original_score = hit.get("_score", 0)
    logger.info(f"Original OpenSearch score for asset {asset_id}: {original_score}")

    thumbnail_url = None
    proxy_url = None

    for representation in derived_representations:
        purpose = representation.get("Purpose")
        storage_info = representation.get("StorageInfo", {}).get("PrimaryLocation", {})

        if storage_info.get("StorageType") == "s3":
            presigned_url = generate_presigned_url(
                bucket=storage_info.get("Bucket", ""),
                key=storage_info.get("ObjectKey", {}).get("FullPath", ""),
            )

            if purpose == "thumbnail":
                thumbnail_url = presigned_url
            elif purpose == "proxy":
                proxy_url = presigned_url

        if thumbnail_url and proxy_url:
            break

    return AssetSearchResult(
        InventoryID=source.get("InventoryID", ""),
        DigitalSourceAsset=digital_source_asset,
        DerivedRepresentations=derived_representations,
        FileHash=source.get("FileHash", ""),
        Metadata=source.get("Metadata", {}),
        score=hit["_score"],
        thumbnailUrl=thumbnail_url,
        proxyUrl=proxy_url,
    )


def process_clip(clip_hit: Dict) -> Dict:
    """
    Process a clip hit to preserve all clip-specific fields.
    """
    source = clip_hit["_source"]
    asset_id = source.get("DigitalSourceAsset", {}).get("ID", "unknown")
    original_score = clip_hit.get("_score", 0)
    logger.info(f"Original OpenSearch score for clip of asset {asset_id}: {original_score}")

    result = {
        "DigitalSourceAsset": source.get("DigitalSourceAsset", {}),
        "score": clip_hit["_score"],
    }

    if "embedding_scope" in source:
        result["embedding_scope"] = source["embedding_scope"]
    if "start_timecode" in source:
        result["start_timecode"] = source["start_timecode"]
    if "end_timecode" in source:
        result["end_timecode"] = source["end_timecode"]
    if "type" in source:
        result["type"] = source["type"]
    if "timestamp" in source:
        result["timestamp"] = source["timestamp"]

    for key, value in source.items():
        if key not in result and key not in ["DigitalSourceAsset"]:
            result[key] = value

    return result


def get_parent_asset(client, index_name, asset_id):
    """
    Fetch a parent asset by its ID from OpenSearch.
    """
    try:
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "DigitalSourceAsset.ID.keyword": asset_id
                            }
                        }
                    ],
                    "must_not": [
                        {
                            "term": {
                                "embedding_scope": "clip"
                            }
                        }
                    ]
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
    Group clips with their parent assets and keep only the top 30 clips per parent.
    Only Video and Audio assets can have clips.
    """
    parent_assets = {}
    clips_by_asset = defaultdict(list)
    standalone_hits = []
    orphaned_clip_assets = set()

    logger.info("All hit scores:")
    for i, hit in enumerate(hits):
        logger.info(f"Hit {i}: score={hit['_score']}, id={hit.get('_id')}, embedding_scope={hit.get('_source', {}).get('embedding_scope')}")

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
                    logger.info(f"Added clip for asset {asset_id} with score {hit['_score']}")
        else:
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                parent_assets[asset_id] = {
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit
                }
                logger.info(f"Added parent asset {asset_id} with score {hit['_score']}")
                if asset_id in orphaned_clip_assets:
                    orphaned_clip_assets.remove(asset_id)
                    logger.info(f"Removed {asset_id} from orphaned clips")
            else:
                standalone_hits.append(hit)
                logger.info(f"Added standalone hit with score {hit['_score']}")

    logger.info(f"Found {len(parent_assets)} parent assets, clips for {len(clips_by_asset)} assets, and {len(standalone_hits)} standalone hits")
    logger.info(f"Found {len(orphaned_clip_assets)} orphaned clip assets")

    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    for asset_id in orphaned_clip_assets:
        if asset_id not in parent_assets:
            parent_hit = get_parent_asset(client, index_name, asset_id)
            if parent_hit:
                highest_clip_score = max((clip["score"] for clip in clips_by_asset.get(asset_id, [])), default=0)
                parent_score = parent_hit["_score"]
                logger.info(f"Original scores for orphaned asset {asset_id}: parent={parent_score}, highest_clip={highest_clip_score}, clip_count={len(clips_by_asset.get(asset_id, []))}")
                use_clip_score = False
                if highest_clip_score > parent_score:
                    relevance_ratio = highest_clip_score / parent_score if parent_score > 0 else 2.0
                    if relevance_ratio > 1.2:
                        use_clip_score = True
                        logger.info(f"Using clip score for orphaned asset {asset_id}: parent={parent_score}, clip={highest_clip_score}, ratio={relevance_ratio:.2f}")
                    else:
                        logger.info(f"Clip not significantly more relevant for orphaned asset {asset_id}: parent={parent_score}, clip={highest_clip_score}, ratio={relevance_ratio:.2f}")
                final_score = highest_clip_score if use_clip_score else parent_score
                if final_score > 1.0:
                    logger.info(f"Normalizing unusually high score for orphaned asset {asset_id}: {final_score} -> 1.0")
                    final_score = 1.0
                parent_assets[asset_id] = {
                    "source": parent_hit["_source"],
                    "score": final_score,
                    "hit": parent_hit
                }
                logger.info(f"Fetched parent asset for orphaned clips: {asset_id} with score {parent_assets[asset_id]['score']} (original score: {parent_hit['_score']}, highest clip score: {highest_clip_score})")

    def process_asset_with_clips(asset_id):
        if asset_id in parent_assets:
            try:
                result = process_search_hit(parent_assets[asset_id]["hit"])
                result_dict = result.model_dump(by_alias=True)
                parent_score = result_dict.get("score", 0)
                digital_source = result_dict.get("DigitalSourceAsset", {})
                asset_type = digital_source.get("Type", "").lower()

                if asset_id in clips_by_asset:
                    asset_clips = sorted(clips_by_asset[asset_id], key=lambda x: x["score"], reverse=True)
                    highest_clip_score = asset_clips[0]["score"]

                    # Branch the logic based on asset type.
                    if asset_type == "audio":
                        # For audio, use the highest clip score directly as the asset score.
                        combined_score = highest_clip_score
                        logger.info(f"Audio asset {asset_id}: using highest clip score {highest_clip_score} as combined score.")
                    else:
                        # For video (or other types with their own embeddings), use a weighted average.
                        relevance_ratio = (highest_clip_score / parent_score) if parent_score > 0 else 2.0
                        if relevance_ratio > 1.2:
                            combined_score = (0.5 * parent_score) + (0.5 * highest_clip_score)
                            logger.info(f"Asset {asset_id}: Combining scores parent {parent_score} and clip {highest_clip_score} into {combined_score} (relevance ratio: {relevance_ratio:.2f}).")
                        else:
                            combined_score = parent_score
                            logger.info(f"Asset {asset_id}: Keeping parent's score {parent_score} (relevance ratio: {relevance_ratio:.2f}).")
                    
                    # Ensure the score does not exceed 1.0.
                    combined_score = min(combined_score, 1.0)
                    result_dict["score"] = combined_score

                    # Process and attach clips for transparency/debugging.
                    result_dict["clips"] = [process_clip(clip_hit["hit"]) for clip_hit in asset_clips]
                # Ensure the 'clips' key is always a list.
                result_dict["clips"] = result_dict.get("clips") or []
                return result_dict
            except Exception as e:
                logger.warning(f"Error processing parent asset {asset_id}: {str(e)}")
                return None
        return None

    def process_standalone_hit(hit):
        try:
            result = process_search_hit(hit)
            return result.model_dump(by_alias=True)
        except Exception as e:
            logger.warning(f"Error processing standalone hit: {str(e)}")
            return None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        result_futures = {
            executor.submit(process_asset_with_clips, asset_id): asset_id
            for asset_id in parent_assets.keys()
        }

        results = []
        for future in concurrent.futures.as_completed(result_futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                asset_id = result_futures[future]
                logger.warning(f"Error processing asset {asset_id}: {str(e)}")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        standalone_futures = [executor.submit(process_standalone_hit, hit) for hit in standalone_hits]
        for future in concurrent.futures.as_completed(standalone_futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error processing standalone hit: {str(e)}")

    logger.info("Scores before sorting:")
    for i, result in enumerate(results):
        asset_id = result.get("DigitalSourceAsset", {}).get("ID", "unknown")
        score = result.get("score", 0)
        clip_val = result.get("clips", [])
        clip_count = len(clip_val) if isinstance(clip_val, list) else 0
        logger.info(f"Result {i}: asset_id={asset_id}, score={score}, clip_count={clip_count}")

    for result in results:
        score = result.get("score", 0)
        if score > 1.0:
            logger.info(f"Final normalization: Capping score for asset {result.get('DigitalSourceAsset', {}).get('ID', 'unknown')}: {score} -> 1.0")
            result["score"] = 1.0

    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    logger.info("Scores after sorting (final order):")
    for i, result in enumerate(results):
        asset_id = result.get("DigitalSourceAsset", {}).get("ID", "unknown")
        score = result.get("score", 0)
        clip_val = result.get("clips", [])
        clip_count = len(clip_val) if isinstance(clip_val, list) else 0
        logger.info(f"Result {i}: asset_id={asset_id}, score={score}, clip_count={clip_count}")

    logger.info(f"Total processed results: {len(results)}")

    return results


def perform_search(params: SearchParams) -> Dict:
    """Perform search operation in OpenSearch with proper error handling."""
    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    try:
        search_body = build_search_query(params)
        logger.info("OpenSearch query body:", extra={"query": search_body})

        response = client.search(body=search_body, index=index_name)

        logger.info(f"Total hits from OpenSearch: {response['hits']['total']['value']}")

        # Use a fallback in case 'hits' or the 'hits' list is missing.
        hits = response.get("hits", {}).get("hits", [])
        if hits is None:
            hits = []

        if params.semantic:
            if CLIP_LOGIC_ENABLED:
                processed_results = process_semantic_results_parallel(hits)
                if processed_results is None:  # Safety check.
                    processed_results = []
                total_results = len(processed_results)
                start_idx = (params.page - 1) * params.pageSize
                end_idx = start_idx + params.pageSize
                if start_idx >= total_results:
                    start_idx = 0
                    end_idx = min(params.pageSize, total_results)
                paged_results = processed_results[start_idx:end_idx]
                logger.info(f"Successfully processed semantic search results: {total_results} total, {len(paged_results)} returned")
                if params.page > 1 and len(paged_results) < params.pageSize:
                    total_count = (params.page - 1) * params.pageSize + len(paged_results)
                else:
                    total_count = total_results
                logger.info(f"Calculated total count: {total_count} (original: {total_results})")
                search_metadata = SearchMetadata(
                    totalResults=total_count,
                    page=params.page,
                    pageSize=params.pageSize,
                    searchTerm=params.q,
                    facets=response.get("aggregations"),
                    suggestions=response.get("suggest"),
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
                results = []
                for hit in hits:
                    try:
                        result = process_search_hit(hit)
                        results.append(result.model_dump(by_alias=True))
                    except Exception as e:
                        logger.warning(f"Error processing hit: {str(e)}", extra={"hit": hit})
                        continue

                logger.info(f"Successfully processed semantic hits without clip logic: {len(results)}")
                total_results = len(results)
                start_idx = (params.page - 1) * params.pageSize
                end_idx = start_idx + params.pageSize
                if start_idx >= total_results:
                    start_idx = 0
                    end_idx = min(params.pageSize, total_results)
                paged_results = results[start_idx:end_idx]
                search_metadata = SearchMetadata(
                    totalResults=total_results,
                    page=params.page,
                    pageSize=params.pageSize,
                    searchTerm=params.q,
                    facets=response.get("aggregations"),
                    suggestions=response.get("suggest"),
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
            hits_list = []
            for hit in hits:
                try:
                    result = process_search_hit(hit)
                    hits_list.append(result)
                except Exception as e:
                    logger.warning(f"Error processing hit: {str(e)}", extra={"hit": hit})
                    continue

            logger.info(f"Successfully processed hits: {len(hits_list)}")
            search_metadata = SearchMetadata(
                totalResults=response["hits"]["total"]["value"],
                page=params.page,
                pageSize=params.pageSize,
                searchTerm=params.q,
                facets=response.get("aggregations"),
                suggestions=response.get("suggest"),
            )
            return {
                "status": "200",
                "message": "ok",
                "data": {
                    "searchMetadata": search_metadata.model_dump(by_alias=True),
                    "results": [hit.model_dump(by_alias=True) for hit in hits_list],
                },
            }

    except (RequestError, NotFoundError) as e:
        logger.warning(f"OpenSearch error: {str(e)}")
        if "no mapping found for field" in str(e):
            return {
                "status": "200",
                "message": "ok",
                "data": {
                    "searchMetadata": SearchMetadata(
                        totalResults=0,
                        page=params.page,
                        pageSize=params.pageSize,
                        searchTerm=params.q,
                    ).model_dump(by_alias=True),
                    "results": [],
                },
            }
        else:
            return {
                "status": "200",
                "message": "No results found",
                "data": {
                    "searchMetadata": SearchMetadata(
                        totalResults=0,
                        page=params.page,
                        pageSize=params.pageSize,
                        searchTerm=params.q,
                    ).model_dump(by_alias=True),
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
        params = SearchParams(**app.current_event.get("queryStringParameters", {}))
        print(params)
        return perform_search(params)
    except ValueError as e:
        logger.warning(f"Invalid input parameters: {str(e)}")
        return {"status": "400", "message": str(e), "data": None}
    except SearchException as e:
        logger.error(f"Search error: {str(e)}")
        return {"status": "500", "message": str(e), "data": None}


@metrics.log_metrics
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)

def lambda_handler(event: dict, context: LambdaContext) -> dict:
    print(event)
    print(context)
    """Lambda handler function"""
    return app.resolve(event, context)
