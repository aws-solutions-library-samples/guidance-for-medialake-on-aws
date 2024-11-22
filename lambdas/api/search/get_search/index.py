from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, conint, ConfigDict
import os
import boto3

from opensearchpy import (
    RequestsHttpConnection,
    RequestsAWSV4SignerAuth,
    OpenSearch,
    OpenSearchException,
)
from datetime import datetime
import json
from utils import generate_presigned_url

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
    pageSize: conint(gt=0, le=100) = Field(default=20)  # type: ignore
    min_score: float = Field(default=0.1)
    filters: Optional[List[Dict]] = None
    search_fields: Optional[List[str]] = None

    @property
    def from_(self) -> int:
        """Calculate the from_ value based on page and pageSize"""
        return (self.page - 1) * self.pageSize

    @property
    def size(self) -> int:
        """Return the pageSize as size"""
        return self.pageSize


class AssetStorage(BaseModelWithConfig):
    """Model for asset storage information"""

    storageType: str
    bucket: str
    path: str
    status: str
    fileSize: Optional[int]
    hashValue: Optional[str]


class ImageSpec(BaseModelWithConfig):
    """Model for image specifications"""

    colorSpace: Optional[str]
    width: Optional[int]
    height: Optional[int]
    dpi: Optional[int]


class AssetRepresentation(BaseModelWithConfig):
    """Model for asset representation"""

    id: str
    type: str
    format: str
    purpose: str
    storage: AssetStorage
    imageSpec: ImageSpec


class AssetMetadata(BaseModelWithConfig):
    """Model for asset metadata"""

    embedded: Optional[Dict[str, Any]]
    generated: Optional[Dict[str, Any]]
    consolidated: Optional[Dict[str, Any]]


class AssetSearchResult(BaseModelWithConfig):
    """Model for search result with presigned URL"""

    inventoryId: str
    assetId: str
    assetType: str
    createDate: datetime
    mainRepresentation: AssetRepresentation
    derivedRepresentations: List[AssetRepresentation] = []
    metadata: Optional[AssetMetadata] = None
    score: float
    thumbnailUrl: Optional[str] = None


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
    """Create and return an OpenSearch client."""
    host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
    region = os.environ["AWS_REGION"]
    service_scope = os.environ["SCOPE"]

    auth = RequestsAWSV4SignerAuth(boto3.Session().get_credentials(), region, service_scope)

    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        region=region,
    )


def build_search_query(params: SearchParams) -> Dict:
    """Build OpenSearch query from search parameters"""
    search_fields = params.search_fields or [
        "mainRepresentation.storage.path^2",  # Boosted field
        "assetType",
        "metadata.consolidated.description",
        "metadata.consolidated.keywords",
        "*",  # This will search all indexed fields
    ]

    # Build base query with multi_match
    query = {
        "bool": {
            "should": [
                {
                    "multi_match": {
                        "query": params.q,
                        "fields": search_fields,
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                        "prefix_length": 2,
                    }
                },
                # Keep wildcard search for exact path matches
                {"wildcard": {"mainRepresentation.storage.path": f"*{params.q}*"}},
            ],
            "minimum_should_match": 1,
        }
    }

    # Add filters if they exist
    if params.filters:
        filters = []
        for filter_item in params.filters:
            if filter_item.get("operator") == "term":
                filters.append({"term": {filter_item["field"]: filter_item["value"]}})
            elif filter_item.get("operator") == "range":
                filters.append({"range": {filter_item["field"]: filter_item["value"]}})
        query["bool"]["filter"] = filters

    return {
        "query": query,
        "min_score": params.min_score,
        "size": params.size,
        "from": params.from_,
        "aggs": {
            "file_types": {"terms": {"field": "mainRepresentation.format.keyword"}},
            "asset_types": {"terms": {"field": "assetType.keyword"}},
        },
        "suggest": {
            "text": params.q,
            "simple_phrase": {
                "phrase": {
                    "field": "mainRepresentation.storage.path",
                    "size": 1,
                    "gram_size": 3,
                    "direct_generator": [
                        {
                            "field": "mainRepresentation.storage.path",
                            "suggest_mode": "always",
                        }
                    ],
                    "highlight": {"pre_tag": "<em>", "post_tag": "</em>"},
                }
            },
        },
    }


def process_search_hit(hit: Dict) -> AssetSearchResult:
    """Process a single search hit and add presigned URL if thumbnail representation exists"""
    source = hit["_source"]

    # Find proxy representation if it exists
    thumbnail_url = None

    for rep in source.get("derivedRepresentations", []):
        if rep.get("purpose") == "thumbnail":
            storage = rep.get("storage", {})
            if storage.get("storageType") == "s3":
                thumbnail_url = generate_presigned_url(
                    bucket=storage["bucket"], key=storage["path"]
                )
                break

    return AssetSearchResult(
        inventoryId=source.get("inventoryId"),
        assetId=source.get("assetId"),
        assetType=source.get("assetType"),
        createDate=source.get("createDate"),
        mainRepresentation=source.get("mainRepresentation"),
        derivedRepresentations=source.get("derivedRepresentations", []),
        metadata=source.get("metadata"),
        score=hit["_score"],
        thumbnailUrl=thumbnail_url,
    )


def perform_search(params: SearchParams) -> Dict:
    """Perform search operation in OpenSearch with proper error handling."""
    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    try:
        search_body = build_search_query(params)
        # Log the search query being sent to OpenSearch
        logger.info("OpenSearch query body:", extra={"query": search_body})

        response = client.search(body=search_body, index=index_name)

        # Log total hits and response from OpenSearch
        logger.info(f"Total hits from OpenSearch: {response['hits']['total']['value']}")
        logger.info("OpenSearch response:", extra={"response": response})

        hits = []
        for hit in response["hits"]["hits"]:
            try:
                result = process_search_hit(hit)
                hits.append(result)
            except Exception as e:
                # Enhanced error logging
                logger.warning(f"Error processing hit: {str(e)}", extra={"hit": hit})
                continue

        # Log processed hits count
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

    except OpenSearchException as e:
        logger.error(f"OpenSearch error: {str(e)}")
        raise SearchException(f"Search operation failed: {str(e)}")
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
