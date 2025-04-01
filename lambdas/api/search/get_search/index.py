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
            # Extract the embedding as a flat list of floats
            embedding = list(res.text_embedding.segments[0].embeddings_float)
            
            # Verify it's a flat list of numbers
            if not all(isinstance(x, (int, float)) for x in embedding):
                raise SearchException("Invalid embedding format")
                
            # Increased size to get more results for grouping
            return {
                "size": params.pageSize * 20,  # Further increase size to get more results
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": embedding,
                                        "k": params.pageSize * 20  # Further increase k to get more results
                                    }
                                }
                            }
                        ]
                        # Removed the must_not clause to include clips
                    }
                },
                "_source": {
                    "excludes": ["embedding"]
                }
            }
        else:
            raise SearchException("Failed to generate embedding for search term")
    except Exception as e:
        logger.exception("Error generating embedding for search term")
        raise SearchException(f"Error generating embedding: {str(e)}")


def build_search_query(params: SearchParams) -> Dict:
    """Build OpenSearch query from search parameters"""
    logger.info("Building search query with params:", extra={"params": params.model_dump()})
    
    if params.semantic:
        return build_semantic_query(params)

    # Parse the search query for special keywords
    clean_query, parsed_filters = parse_search_query(params.q)
    logger.info("Parsed search query:", extra={"clean_query": clean_query, "filters": parsed_filters})

    # Define core search fields with boosts
    name_fields = [
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name^3",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath^2"
    ]
    
    type_fields = [
        "DigitalSourceAsset.Type^2",
        "DigitalSourceAsset.MainRepresentation.Format^2",
        "Metadata.Embedded.S3.ContentType"
    ]

    # Build the main query
    if clean_query:
        query = {
            "bool": {
                "should": [
                    # Name matching
                    {
                        "multi_match": {
                            "query": clean_query,
                            "fields": name_fields,
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                            "prefix_length": 1,
                            "minimum_should_match": "20%",
                            "boost": 2
                        }
                    },
                    # Prefix matching for partial searches
                    {
                        "match_phrase_prefix": {
                            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name": {
                                "query": clean_query,
                                "boost": 1.5
                            }
                        }
                    },
                    # Type and format matching
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
                    # Partial word matching
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
                "filter": []
            }
        }
    else:
        query = {
            "bool": {
                "must": [{"match_all": {}}],
                "filter": []
            }
        }

    # Add filters from parsed keywords
    if parsed_filters:
        # Media type filter
        if 'type' in parsed_filters:
            query["bool"]["filter"].append({
                "term": {"DigitalSourceAsset.Type.keyword": parsed_filters['type'][0]}
            })

        # Format filter
        if 'format' in parsed_filters:
            query["bool"]["filter"].append({
                "term": {"DigitalSourceAsset.MainRepresentation.Format.keyword": parsed_filters['format'][0]}
            })
            
        # connector filter
        if 'storageIdentifier' in parsed_filters:
            path_value = parsed_filters['storageIdentifier']
            # Add wildcard if not already present
            if isinstance(path_value, str) and not path_value.endswith('*'):
                path_value = f"{path_value}*"
                
            logger.info(f"Applying Connector Bucket filter: {path_value}")
            query["bool"]["filter"].append({
                "wildcard": {
                    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket.keyword": {
                        "value": path_value[0]
                    }
                }
            })

        # Size filter
        if 'size' in parsed_filters:
            for size_filter in parsed_filters['size']:
                range_operator = '>=' if size_filter['operator'].startswith('>=') else '<=' if size_filter['operator'].startswith('<=') else '>' if size_filter['operator'].startswith('>') else '<'
                query["bool"]["filter"].append({
                    "range": {
                        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize": {
                            range_operator: size_filter['value']
                        }
                    }
                })

        # Date filter
        if 'date' in parsed_filters:
            for date_filter in parsed_filters['date']:
                range_operator = '>=' if date_filter['operator'].startswith('>=') else '<=' if date_filter['operator'].startswith('<=') else '>' if date_filter['operator'].startswith('>') else '<'
                query["bool"]["filter"].append({
                    "range": {
                        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate": {
                            range_operator: date_filter['value']
                        }
                    }
                })

        # Metadata filters
        if 'metadata' in parsed_filters:
            for metadata_filter in parsed_filters['metadata']:
                query["bool"]["filter"].append({
                    "term": {
                        f"Metadata.Consolidated.{metadata_filter['key']}.keyword": metadata_filter['value']
                    }
                })

    # Add any additional filters from params
    if params.filters:
        for filter_item in params.filters:
            if filter_item.get("operator") == "term":
                query["bool"]["filter"].append(
                    {"term": {filter_item["field"]: filter_item["value"]}}
                )
            elif filter_item.get("operator") == "range":
                query["bool"]["filter"].append(
                    {"range": {filter_item["field"]: filter_item["value"]}}
                )

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

    # Generate thumbnail URL if applicable
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
    
    Args:
        clip_hit: The clip hit from OpenSearch
        
    Returns:
        Processed clip with all relevant fields
    """
    source = clip_hit["_source"]
    
    # Create a base result with standard fields
    result = {
        "DigitalSourceAsset": source.get("DigitalSourceAsset", {}),
        "score": clip_hit["_score"],
    }
    
    # Add all clip-specific fields
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
    
    # Add any other fields that might be present
    for key, value in source.items():
        if key not in result and key not in ["DigitalSourceAsset"]:
            result[key] = value
    
    return result


def process_semantic_results_parallel(hits: List[Dict]) -> List[Dict]:
    """
    Process semantic search results using parallel processing for better performance.
    Group clips with their parent assets and keep only the top 30 clips per parent.
    
    Args:
        hits: List of search hits from OpenSearch
        
    Returns:
        List of processed results with clips grouped by parent asset
    """
    # Separate parent assets and clips
    parent_assets = {}
    clips_by_asset = defaultdict(list)
    standalone_hits = []
    
    for hit in hits:
        source = hit["_source"]
        if source.get("embedding_scope") == "clip":
            # This is a clip
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                clips_by_asset[asset_id].append({
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit
                })
        else:
            # This is a parent asset
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                parent_assets[asset_id] = {
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit
                }
            else:
                # This is a standalone hit (not a parent or clip)
                standalone_hits.append(hit)
    
    logger.info(f"Found {len(parent_assets)} parent assets, clips for {len(clips_by_asset)} assets, and {len(standalone_hits)} standalone hits")
    
    # Process each parent asset and its clips in parallel
    def process_asset_with_clips(asset_id):
        # Process parent asset if it exists
        if asset_id in parent_assets:
            try:
                result = process_search_hit(parent_assets[asset_id]["hit"])
                result_dict = result.model_dump(by_alias=True)
                result_dict["clips"] = []
                
                # Add clips if available
                if asset_id in clips_by_asset:
                    # Sort clips by score and take top 30
                    asset_clips = sorted(clips_by_asset[asset_id], key=lambda x: x["score"], reverse=True)[:30]
                    
                    # Process clips using our custom clip processor to preserve all fields
                    for clip in asset_clips:
                        try:
                            clip_result = process_clip(clip["hit"])
                            result_dict["clips"].append(clip_result)
                        except Exception as e:
                            logger.warning(f"Error processing clip: {str(e)}")
                
                return result_dict
            except Exception as e:
                logger.warning(f"Error processing parent asset {asset_id}: {str(e)}")
                return None
        
        return None
    
    # Process standalone hits
    def process_standalone_hit(hit):
        try:
            result = process_search_hit(hit)
            return result.model_dump(by_alias=True)
        except Exception as e:
            logger.warning(f"Error processing standalone hit: {str(e)}")
            return None
    
    # Process all parent assets (not just those with clips)
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
    
    # Process standalone hits
    with concurrent.futures.ThreadPoolExecutor() as executor:
        standalone_futures = [executor.submit(process_standalone_hit, hit) for hit in standalone_hits]
        
        for future in concurrent.futures.as_completed(standalone_futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error processing standalone hit: {str(e)}")
    
    # Sort results by score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
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
        
        if params.semantic:
            # Use the parallel processing function for semantic search
            processed_results = process_semantic_results_parallel(response["hits"]["hits"])
            
            # Calculate total results (for pagination)
            total_results = len(processed_results)
            
            # Limit results to pageSize
            start_idx = (params.page - 1) * params.pageSize
            end_idx = start_idx + params.pageSize
            
            # Make sure we don't go out of bounds
            if start_idx >= total_results:
                start_idx = 0
                end_idx = min(params.pageSize, total_results)
            
            paged_results = processed_results[start_idx:end_idx]
            
            logger.info(f"Successfully processed semantic search results: {total_results} total, {len(paged_results)} returned")
            
            # Use the original total count from OpenSearch for better pagination
            original_total = response["hits"]["total"]["value"]
            
            search_metadata = SearchMetadata(
                totalResults=max(total_results, original_total),  # Use the larger of the two counts
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
            # Standard processing for non-semantic search
            hits = []
            for hit in response["hits"]["hits"]:
                try:
                    result = process_search_hit(hit)
                    hits.append(result)
                except Exception as e:
                    logger.warning(f"Error processing hit: {str(e)}", extra={"hit": hit})
                    continue

            logger.info(f"Successfully processed hits: {len(hits)}")

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
                    "results": [hit.model_dump(by_alias=True) for hit in hits],
                },
            }

    except (RequestError, NotFoundError) as e:
        logger.warning(f"OpenSearch error: {str(e)}")
        # Check if the error is due to missing field mapping
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
            # For other types of RequestError or NotFoundError, still return empty results
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
    """Lambda handler function"""
    return app.resolve(event, context)
