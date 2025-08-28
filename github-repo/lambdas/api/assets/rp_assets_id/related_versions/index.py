import json
import os
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from opensearchpy import (
    NotFoundError,
    OpenSearch,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)
from pydantic import BaseModel, Field, conint, validator

# Initialize metrics and logger only
metrics = Metrics(namespace="medialake", service="related-versions")
logger = Logger(service="related-versions", level=os.getenv("LOG_LEVEL", "INFO"))

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
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)


# Initialize OpenSearch client
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


class QueryParams(BaseModel):
    """Pydantic model for query parameters"""

    page: conint(gt=0) = Field(default=1)  # type: ignore
    pageSize: conint(gt=0, le=500) = Field(default=50)  # type: ignore
    min_score: float = Field(default=0.01)

    @validator("pageSize")
    @classmethod
    def validate_page_size(cls, v):
        if v > 500:
            raise ValueError("pageSize must be less than or equal to 500")
        return v

    @property
    def from_(self) -> int:
        """Calculate the from_ value based on page and pageSize"""
        return (self.page - 1) * self.pageSize

    @property
    def size(self) -> int:
        """Return the pageSize as size"""
        return self.pageSize


class AssetSearchResult(BaseModel):
    """Model for search result with presigned URL"""

    InventoryID: str
    DigitalSourceAsset: Dict[str, Any]
    DerivedRepresentations: List[Dict[str, Any]]
    FileHash: str
    Metadata: Dict[str, Any]
    score: float
    thumbnailUrl: Optional[str] = None
    proxyUrl: Optional[str] = None


class SearchMetadata(BaseModel):
    """Model for search metadata"""

    totalResults: int
    page: int
    pageSize: int
    facets: Optional[Dict[str, Any]] = None


class APIError(Exception):
    """Custom API error class"""

    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# Regional S3 client configuration for better cross-region support
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}  # {region → client}


def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    """
    Return an S3 client **pinned to the bucket's actual region**.
    Clients are cached to reuse TCP connections across warm invocations.
    """
    generic = _S3_CLIENT_CACHE.setdefault(
        "us-east-1",
        boto3.client("s3", region_name="us-east-1", config=_SIGV4_CFG),
    )

    try:
        region = (
            generic.get_bucket_location(Bucket=bucket).get("LocationConstraint")
            or "us-east-1"
        )
    except generic.exceptions.NoSuchBucket:
        raise ValueError(f"S3 bucket {bucket!r} does not exist")

    if region not in _S3_CLIENT_CACHE:
        _S3_CLIENT_CACHE[region] = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=_ENDPOINT_TMPL.format(region=region),
            config=_SIGV4_CFG,
        )
    return _S3_CLIENT_CACHE[region]


def generate_presigned_url(
    bucket: str, key: str, expiration: int = 3600
) -> Optional[str]:
    """Generate a presigned URL for an S3 object with region-aware client"""
    try:
        # Get region-specific S3 client
        s3_client = _get_s3_client_for_bucket(bucket)

        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expiration,
        )

        logger.info(
            f"Generated presigned URL for s3://{bucket}/{key} (region {s3_client.meta.region_name}) valid {expiration}s"
        )

        return url
    except Exception as e:
        logger.error(
            f"Error generating presigned URL: {str(e)}",
            extra={"bucket": bucket, "key": key, "error": str(e)},
        )
        return None


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


def perform_vector_search(asset_id: str, params: QueryParams) -> Dict:
    """Perform vector similarity search operation in OpenSearch."""
    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    try:
        # Extract the UUID portion from the asset ID
        uuid = asset_id.split(":")[-1]  # Gets the last part after the last colon

        logger.info(
            f"Starting vector search",
            extra={
                "full_asset_id": asset_id,
                "uuid_extracted": uuid,
                "search_target": f"Looking for document with ID containing: {uuid}",
                "index_name": index_name,
                "params": params.dict(),
            },
        )

        # Search for the UUID portion in DigitalSourceAsset.ID using match query
        # Also include DigitalAsset in the source to access nested embeddings
        initial_query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"DigitalSourceAsset.ID": uuid}},
                        {"match": {"InventoryID": uuid}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            "_source": {
                "includes": [
                    "InventoryID",
                    "DigitalSourceAsset",
                    "DigitalAsset.embedding",
                    "DigitalAsset.asset_id",
                    "DigitalAsset.embedding_scope",
                    "embedding",  # Keep checking for top-level embedding too
                    "embedding_scope",
                ]
            },
        }

        # Log the full initial query with all details
        logger.info(
            "Initial asset lookup query details",
            extra={
                "query_type": "initial_lookup",
                "full_query": json.dumps(initial_query, indent=2),
                "index": index_name,
                "uuid": uuid,
                "searching_for_asset_id": asset_id,
            },
        )

        asset_response = client.search(index=index_name, body=initial_query)

        # Extract document IDs from the response for logging
        found_doc_ids = []
        if asset_response.get("hits", {}).get("hits"):
            for hit in asset_response["hits"]["hits"]:
                found_doc_ids.append(hit.get("_id", "unknown"))

        # Log the full response from the initial query
        logger.info(
            "Initial asset lookup response details",
            extra={
                "query_type": "initial_lookup",
                "response": json.dumps(asset_response, indent=2),
                "total_hits": asset_response.get("hits", {})
                .get("total", {})
                .get("value", 0),
                "asset_id_searched_for": asset_id,
                "uuid_searched_for": uuid,
                "found_document_ids": found_doc_ids,
                "first_doc_id": found_doc_ids[0] if found_doc_ids else "none",
            },
        )

        # Check if we found any matches
        hits = asset_response.get("hits", {}).get("hits", [])
        if not hits:
            logger.warning(
                "No hits found for asset lookup",
                extra={
                    "asset_id": asset_id,
                    "uuid_searched": uuid,
                    "query_used": json.dumps(initial_query, indent=2),
                    "response": json.dumps(asset_response, indent=2),
                },
            )
            raise APIError("Asset not found", 404)

        # Log details about the found document
        found_doc = hits[0]
        source = found_doc["_source"]

        logger.info(
            "Found document details",
            extra={
                "document_id": found_doc.get("_id", "unknown"),
                "document_index": found_doc.get("_index", "unknown"),
                "document_score": found_doc.get("_score", "unknown"),
                "source_keys": list(source.keys()),
                "digital_source_asset_id": source.get("DigitalSourceAsset", {}).get(
                    "ID", "not_found"
                ),
                "inventory_id": source.get("InventoryID", "not_found"),
            },
        )

        # Get the complete document without field filtering to see full structure
        try:
            complete_doc_query = {"query": {"term": {"_id": found_doc["_id"]}}}

            complete_doc_response = client.search(
                index=index_name, body=complete_doc_query
            )

            if complete_doc_response.get("hits", {}).get("hits"):
                complete_doc = complete_doc_response["hits"]["hits"][0]
                complete_source = complete_doc["_source"]

                # Log basic structure
                logger.info(
                    "COMPLETE DOCUMENT STRUCTURE",
                    extra={
                        "document_id": complete_doc.get("_id", "unknown"),
                        "all_fields": list(complete_source.keys()),
                        "full_document": json.dumps(complete_source, indent=2),
                    },
                )

                # Log detailed field inspection
                field_details = {}
                for field_name, field_value in complete_source.items():
                    field_details[field_name] = {
                        "type": type(field_value).__name__,
                        "value": (
                            field_value
                            if not isinstance(field_value, (dict, list))
                            or len(str(field_value)) < 200
                            else f"[{type(field_value).__name__} with {len(field_value) if hasattr(field_value, '__len__') else 'unknown'} items]"
                        ),
                    }

                logger.info(
                    "DETAILED FIELD INSPECTION",
                    extra={
                        "document_id": complete_doc.get("_id", "unknown"),
                        "field_details": json.dumps(field_details, indent=2),
                    },
                )

                # Specifically look for any field that might contain embeddings
                embedding_candidates = {}
                for field_name, field_value in complete_source.items():
                    if "embed" in field_name.lower() or "vector" in field_name.lower():
                        embedding_candidates[field_name] = {
                            "type": type(field_value).__name__,
                            "length": (
                                len(field_value)
                                if hasattr(field_value, "__len__")
                                else "no_length"
                            ),
                            "first_few_items": (
                                field_value[:5]
                                if isinstance(field_value, list)
                                else str(field_value)[:100]
                            ),
                        }
                    elif isinstance(field_value, dict):
                        # Check nested dict for embedding fields
                        for nested_key, nested_value in field_value.items():
                            if (
                                "embed" in nested_key.lower()
                                or "vector" in nested_key.lower()
                            ):
                                embedding_candidates[f"{field_name}.{nested_key}"] = {
                                    "type": type(nested_value).__name__,
                                    "length": (
                                        len(nested_value)
                                        if hasattr(nested_value, "__len__")
                                        else "no_length"
                                    ),
                                    "first_few_items": (
                                        nested_value[:5]
                                        if isinstance(nested_value, list)
                                        else str(nested_value)[:100]
                                    ),
                                }
                    elif isinstance(field_value, list):
                        # Check list items for embedding fields
                        for i, item in enumerate(
                            field_value[:3]
                        ):  # Check first 3 items
                            if isinstance(item, dict):
                                for item_key, item_value in item.items():
                                    if (
                                        "embed" in item_key.lower()
                                        or "vector" in item_key.lower()
                                    ):
                                        embedding_candidates[
                                            f"{field_name}[{i}].{item_key}"
                                        ] = {
                                            "type": type(item_value).__name__,
                                            "length": (
                                                len(item_value)
                                                if hasattr(item_value, "__len__")
                                                else "no_length"
                                            ),
                                            "first_few_items": (
                                                item_value[:5]
                                                if isinstance(item_value, list)
                                                else str(item_value)[:100]
                                            ),
                                        }

                logger.info(
                    "EMBEDDING FIELD CANDIDATES",
                    extra={
                        "document_id": complete_doc.get("_id", "unknown"),
                        "embedding_candidates": json.dumps(
                            embedding_candidates, indent=2
                        ),
                        "candidates_found": len(embedding_candidates),
                    },
                )

            else:
                logger.warning("Could not retrieve complete document")

        except Exception as complete_doc_error:
            logger.warning(
                f"Failed to retrieve complete document: {str(complete_doc_error)}"
            )

        embedding = None
        embedding_path = None

        # First, check for top-level embedding (backward compatibility)
        if "embedding" in source and source["embedding"]:
            embedding = source["embedding"]
            embedding_path = "embedding"
            logger.info(
                "Using top-level embedding",
                extra={
                    "embedding_length": (
                        len(embedding) if isinstance(embedding, list) else "not_a_list"
                    ),
                    "document_id": found_doc.get("_id", "unknown"),
                },
            )

        # If no top-level embedding, look in nested DigitalAsset array
        elif "DigitalAsset" in source and isinstance(source["DigitalAsset"], list):
            for digital_asset in source["DigitalAsset"]:
                if (
                    isinstance(digital_asset, dict)
                    and "embedding" in digital_asset
                    and digital_asset["embedding"]
                ):
                    embedding = digital_asset["embedding"]
                    embedding_path = "DigitalAsset.embedding"
                    logger.info(
                        "Using nested DigitalAsset embedding",
                        extra={
                            "embedding_length": (
                                len(embedding)
                                if isinstance(embedding, list)
                                else "not_a_list"
                            ),
                            "digital_asset_id": digital_asset.get(
                                "asset_id", "unknown"
                            ),
                            "embedding_scope": digital_asset.get(
                                "embedding_scope", "unknown"
                            ),
                            "document_id": found_doc.get("_id", "unknown"),
                        },
                    )
                    break

        if not embedding:
            # Let's do a diagnostic query to see what embedding structures exist in the index
            diagnostic_query = {
                "size": 5,
                "query": {
                    "bool": {
                        "should": [
                            {"exists": {"field": "embedding"}},
                            {"exists": {"field": "DigitalAsset.embedding"}},
                        ]
                    }
                },
                "_source": {
                    "includes": [
                        "InventoryID",
                        "DigitalSourceAsset.ID",
                        "DigitalSourceAsset.Type",
                        "embedding",
                        "embedding_scope",
                        "DigitalAsset.embedding",
                        "DigitalAsset.asset_id",
                        "DigitalAsset.embedding_scope",
                    ]
                },
            }

            try:
                diagnostic_response = client.search(
                    index=index_name, body=diagnostic_query
                )

                # Extract document IDs from diagnostic response
                diag_doc_ids = []
                if diagnostic_response.get("hits", {}).get("hits"):
                    for hit in diagnostic_response["hits"]["hits"]:
                        diag_doc_ids.append(hit.get("_id", "unknown"))

                logger.info(
                    "Diagnostic query for embeddings in index",
                    extra={
                        "total_with_embeddings": diagnostic_response["hits"]["total"][
                            "value"
                        ],
                        "sample_doc_ids_with_embeddings": diag_doc_ids,
                        "sample_docs": json.dumps(
                            diagnostic_response["hits"]["hits"], indent=2
                        ),
                        "current_doc_id_without_embedding": found_doc.get(
                            "_id", "unknown"
                        ),
                    },
                )
            except Exception as diag_error:
                logger.warning(f"Diagnostic query failed: {str(diag_error)}")

            logger.warning(
                "No embedding found in asset document",
                extra={
                    "asset_id": asset_id,
                    "document_id_found": found_doc.get("_id", "unknown"),
                    "available_fields": list(source.keys()),
                    "digital_asset_present": "DigitalAsset" in source,
                    "digital_asset_type": (
                        type(source.get("DigitalAsset")).__name__
                        if "DigitalAsset" in source
                        else "not_present"
                    ),
                    "digital_asset_count": (
                        len(source["DigitalAsset"])
                        if isinstance(source.get("DigitalAsset"), list)
                        else "not_a_list"
                    ),
                    "query_used": json.dumps(initial_query, indent=2),
                },
            )

            # Return a more specific error for missing embeddings
            raise APIError(
                "This asset has not been processed for similarity search yet. Embeddings are not available.",
                422,
            )

        logger.info(
            "Retrieved embedding details",
            extra={
                "embedding_exists": embedding is not None,
                "embedding_type": type(embedding).__name__,
                "embedding_length": (
                    len(embedding) if isinstance(embedding, list) else "not_a_list"
                ),
                "embedding_path": embedding_path,
            },
        )

        # Build the vector search query - use nested query if embedding is in DigitalAsset
        if embedding_path == "DigitalAsset.embedding":
            search_body = {
                "size": params.size,
                "from": params.from_,
                "query": {
                    "nested": {
                        "path": "DigitalAsset",
                        "query": {
                            "knn": {
                                "DigitalAsset.embedding": {
                                    "vector": embedding,
                                    "k": params.size
                                    * 2,  # Get more results to account for filtering
                                }
                            }
                        },
                        "score_mode": "max",
                    }
                },
                "post_filter": {
                    "bool": {
                        "must_not": [
                            {"term": {"DigitalSourceAsset.ID.keyword": asset_id}},
                            {
                                "nested": {
                                    "path": "DigitalAsset",
                                    "query": {
                                        "term": {"DigitalAsset.embedding_scope": "clip"}
                                    },
                                }
                            },
                        ]
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
                        "Metadata.Consolidated.type",
                    ]
                },
            }
        else:
            # Use traditional top-level embedding search
            search_body = {
                "size": params.size,
                "from": params.from_,
                "query": {
                    "knn": {"embedding": {"vector": embedding, "k": params.size}}
                },
                "post_filter": {
                    "bool": {
                        "must_not": [
                            {"term": {"DigitalSourceAsset.ID.keyword": asset_id}},
                            {"term": {"embedding_scope": "clip"}},
                        ]
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
                        "Metadata.Consolidated.type",
                    ]
                },
            }

        # Log the full KNN search query with all details
        logger.info(
            "KNN search query details",
            extra={
                "query_type": "knn_search",
                "full_query": json.dumps(search_body, indent=2),
                "index": index_name,
                "asset_id": asset_id,
                "params": params.dict(),
                "embedding_path": embedding_path,
            },
        )

        response = client.search(body=search_body, index=index_name)

        # Log the full KNN search response
        logger.info(
            "KNN search response details",
            extra={
                "query_type": "knn_search",
                "total_hits": response["hits"]["total"]["value"],
                "actual_hits": len(response["hits"]["hits"]),
                "response": json.dumps(response, indent=2),
                "asset_id": asset_id,
            },
        )

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
            facets=response.get("aggregations"),
        )

        metrics.add_metric(
            name="RelatedVersionsRetrieved", value=len(hits), unit="Count"
        )

        # Modify the response structure to include statusCode and serialize the body
        response_data = {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "200",
                    "message": "ok",
                    "data": {
                        "searchMetadata": {
                            "totalResults": response["hits"]["total"]["value"],
                            "page": params.page,
                            "pageSize": params.pageSize,
                            "searchTerm": asset_id,
                        },
                        "results": [hit.model_dump(by_alias=True) for hit in hits],
                    },
                }
            ),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",  # Add CORS headers
            },
        }

        logger.info(
            "Preparing to return response",
            extra={
                "response_status": 200,
                "total_hits": response["hits"]["total"]["value"],
                "results_count": len(hits),
            },
        )

        # Before returning the response, let's log its structure
        logger.info(
            "Response structure details",
            extra={
                "response_keys": list(response_data.keys()),
                "body_type": type(response_data["body"]).__name__,
                "body_length": (
                    len(response_data["body"])
                    if isinstance(response_data["body"], str)
                    else "not_a_string"
                ),
                "headers": response_data.get("headers", {}),
                "status_code": response_data.get("statusCode"),
            },
        )

        # Verify the response structure matches API Gateway requirements
        if not isinstance(response_data.get("body"), str):
            logger.error(
                "Response body is not a string",
                extra={"body_type": type(response_data.get("body")).__name__},
            )
            raise APIError("Invalid response format", 500)

        if not response_data.get("statusCode"):
            logger.error(
                "Response missing statusCode",
                extra={"response_keys": list(response_data.keys())},
            )
            raise APIError("Invalid response format", 500)

        return response_data

    except APIError:
        # Re-raise APIError as-is to preserve the specific error message and status code
        raise
    except NotFoundError:
        logger.error("NotFoundError encountered")
        raise APIError("Asset not found", 404)
    except Exception as e:
        logger.error(
            "Unexpected error in perform_vector_search",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise APIError("An unexpected error occurred", 500)


def build_error_response(
    error: Exception, status_code: int, context: LambdaContext
) -> Dict[str, Any]:
    """Build standardized error response."""
    runtime_id = (
        context.aws_request_id if hasattr(context, "aws_request_id") else "UNKNOWN"
    )

    if isinstance(error, APIError):
        message = f"{error.message} (Runtime ID: {runtime_id})"
    else:
        message = f"An unexpected error occurred. Please try again later. (Runtime ID: {runtime_id})"

    return {
        "statusCode": status_code,
        "body": json.dumps({"status": "error", "message": message}),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
    }


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    try:
        # Extract asset_id from path parameters
        asset_id = event.get("pathParameters", {}).get("id")
        if not asset_id:
            raise APIError("Asset ID is required", 400)

        logger.info(f"Processing request for asset ID: {asset_id}")

        # Parse and validate query parameters
        query_params = QueryParams(**event.get("queryStringParameters", {}))

        logger.debug(f"Processed query parameters: {query_params.dict()}")

        # Log before calling perform_vector_search
        logger.info("Calling perform_vector_search")

        response = perform_vector_search(asset_id, query_params)

        # Log the complete response structure
        logger.info(
            "Complete response structure",
            extra={
                "response_keys": list(response.keys()),
                "body_type": type(response.get("body")).__name__,
                "headers": response.get("headers", {}),
                "status_code": response.get("statusCode"),
            },
        )

        # Verify response structure before returning
        if not isinstance(response.get("body"), str):
            logger.error(
                "Response body is not a string",
                extra={"body_type": type(response.get("body")).__name__},
            )
            raise APIError("Invalid response format", 500)

        return response

    except APIError as e:
        logger.warning(f"API Error: {str(e)}", exc_info=True)
        metrics.add_metric(name="RelatedVersionsClientErrors", value=1, unit="Count")
        error_response = build_error_response(e, e.status_code, context)

        # Log the complete error response structure
        logger.info(
            "Complete error response structure",
            extra={
                "error_response_keys": list(error_response.keys()),
                "error_body_type": type(error_response.get("body")).__name__,
                "error_headers": error_response.get("headers", {}),
                "error_status_code": error_response.get("statusCode"),
            },
        )

        return error_response

    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}", exc_info=True)
        metrics.add_metric(name="RelatedVersionsServerErrors", value=1, unit="Count")
        error_response = build_error_response(e, 500, context)

        # Log the complete error response structure
        logger.info(
            "Complete error response structure",
            extra={
                "error_response_keys": list(error_response.keys()),
                "error_body_type": type(error_response.get("body")).__name__,
                "error_headers": error_response.get("headers", {}),
                "error_status_code": error_response.get("statusCode"),
            },
        )

        return error_response
