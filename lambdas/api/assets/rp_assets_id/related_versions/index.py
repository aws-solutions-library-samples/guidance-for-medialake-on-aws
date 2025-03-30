from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import boto3
import json
from pydantic import BaseModel, Field, conint, validator

from opensearchpy import (
    RequestsHttpConnection,
    RequestsAWSV4SignerAuth,
    OpenSearch,
    OpenSearchException,
    RequestError,
    NotFoundError,
    helpers,
)

# Initialize AWS X-Ray, metrics, and logger
tracer = Tracer(service="asset-service")
metrics = Metrics(namespace="media-lake-asset-service", service="asset-api")
logger = Logger(service="asset-api", level=os.getenv("LOG_LEVEL", "WARNING"))

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

@tracer.capture_method
def generate_presigned_url(bucket: str, key: str, expiration: int = 3600) -> Optional[str]:
    """Generate a presigned URL for an S3 object"""
    try:
        s3_client = boto3.client("s3")
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expiration,
        )
        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None

@tracer.capture_method
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

@tracer.capture_method
def perform_vector_search(asset_id: str, params: QueryParams) -> Dict:
    """Perform vector similarity search operation in OpenSearch."""
    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    try:
        # First, get the asset's embedding
        asset_response = client.get(
            index=index_name,
            id=asset_id,
            _source=["embedding"]
        )
        
        if "embedding" not in asset_response["_source"]:
            raise APIError("Asset not found or no embedding available", 404)

        embedding = asset_response["_source"]["embedding"]

        # Build the vector search query
        search_body = {
            "size": params.size,
            "from": params.from_,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding,
                        "k": params.size
                    }
                }
            },
            "post_filter": {
                "bool": {
                    "must_not": [
                        {"term": {"_id": asset_id}}
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
                    "Metadata.Consolidated.type"
                ]
            }
        }

        logger.info("OpenSearch query body:", extra={"query": search_body})

        response = client.search(body=search_body, index=index_name)

        logger.info(f"Total hits from OpenSearch: {response['hits']['total']['value']}")
        logger.info("OpenSearch response:", extra={"response": response})

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

        metrics.add_metric(name="RelatedVersionsRetrieved", value=len(hits), unit="Count")

        return {
            "statusCode": 200,
            "body": {
                "status": "success",
                "message": "Related versions retrieved successfully",
                "data": {
                    "hits": [hit.model_dump(by_alias=True) for hit in hits],
                    "totalResults": search_metadata.totalResults,
                    "page": search_metadata.page,
                    "pageSize": search_metadata.pageSize
                }
            }
        }

    except NotFoundError:
        raise APIError("Asset not found", 404)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise APIError("An unexpected error occurred", 500)

@tracer.capture_method
def build_error_response(error: Exception, status_code: int, context: LambdaContext) -> Dict[str, Any]:
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
        "body": {
            "status": "error",
            "message": message
        }
    }

@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
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

        # Perform vector search
        return perform_vector_search(asset_id, query_params)

    except APIError as e:
        logger.warning(f"API Error: {str(e)}", exc_info=True)
        metrics.add_metric(name="RelatedVersionsClientErrors", value=1, unit="Count")
        return build_error_response(e, e.status_code, context)

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        metrics.add_metric(name="RelatedVersionsServerErrors", value=1, unit="Count")
        return build_error_response(e, 500, context) 