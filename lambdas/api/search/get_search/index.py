from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, conint
import os
import boto3
from opensearchpy import (
    RequestsHttpConnection,
    RequestsAWSV4SignerAuth,
    OpenSearch,
    OpenSearchException,
)
from datetime import datetime

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayRestResolver()


class SearchException(Exception):
    """Custom exception for search-related errors"""

    pass


class SearchParams(BaseModel):
    """Pydantic model for search parameters"""

    q: str = Field(..., min_length=1)
    size: conint(gt=0, le=100) = Field(default=20)  # type: ignore
    from_: conint(ge=0) = Field(default=0, alias="from")  # type: ignore
    min_score: float = Field(default=0.1)
    filters: Optional[List[Dict]] = None
    search_fields: Optional[List[str]] = None


class AssetLocation(BaseModel):
    storage_type: str
    bucket: str
    object_key: Dict[str, str]
    status: str
    file_info: Dict[str, Any]


class AssetRepresentation(BaseModel):
    id: str
    type: str
    format: str
    purpose: str
    storage_info: Dict[str, AssetLocation]
    image_spec: Optional[Dict[str, Any]]


class AssetMetadata(BaseModel):
    embedded: Optional[Dict[str, Any]]
    generated: Optional[Dict[str, Any]]
    consolidated: Optional[Dict[str, Any]]


class AssetSearchResult(BaseModel):
    inventory_id: str
    asset_id: str
    type: str
    create_date: datetime
    main_representation: AssetRepresentation
    derived_representations: Optional[List[AssetRepresentation]]
    metadata: AssetMetadata
    score: float


class SearchMetadata(BaseModel):
    totalResults: int
    page: int
    pageSize: int
    searchTerm: str
    facets: Optional[Dict[str, Any]] = None
    suggestions: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    status: str
    message: str
    data: Dict[str, Any]


def get_opensearch_client() -> OpenSearch:
    """Create and return an OpenSearch client."""
    host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
    region = os.environ["AWS_REGION"]

    auth = RequestsAWSV4SignerAuth(boto3.Session().get_credentials(), region, "aoss")

    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        region=region,
    )


@tracer.capture_method
def build_search_query(params: SearchParams) -> Dict:
    """Build OpenSearch query from search parameters"""
    should_queries = []
    search_fields = params.search_fields or [
        "name",
        "metadata.consolidated.description",
        "metadata.consolidated.keywords",
    ]

    # Add search fields
    for field in search_fields:
        should_queries.append(
            {
                "match_phrase_prefix": {
                    field: {"query": params.q, "slop": 2, "max_expansions": 50}
                }
            }
        )

    # Build filters
    filters = []
    if params.filters:
        for filter_item in params.filters:
            if filter_item.get("operator") == "term":
                filters.append({"term": {filter_item["field"]: filter_item["value"]}})
            elif filter_item.get("operator") == "range":
                filters.append({"range": {filter_item["field"]: filter_item["value"]}})

    query = {
        "bool": {
            "should": should_queries,
            "minimum_should_match": 1,
            "filter": filters if filters else [],
        }
    }

    return {
        "query": query,
        "min_score": params.min_score,
        "size": params.size,
        "from": params.from_,
        "aggs": {
            "file_types": {"terms": {"field": "main_representation.format.keyword"}},
            "asset_types": {"terms": {"field": "type.keyword"}},
        },
        "suggest": {
            "text": params.q,
            "simple_phrase": {
                "phrase": {
                    "field": "name",
                    "size": 1,
                    "gram_size": 3,
                    "direct_generator": [{"field": "name", "suggest_mode": "always"}],
                    "highlight": {"pre_tag": "<em>", "post_tag": "</em>"},
                }
            },
        },
    }


@tracer.capture_method
def perform_search(params: SearchParams) -> SearchResponse:
    """Perform search operation in OpenSearch with proper error handling."""
    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    try:
        search_body = build_search_query(params)
        response = client.search(body=search_body, index=index_name)

        hits = [
            AssetSearchResult(
                inventory_id=hit["_source"].get("inventoryId"),
                asset_id=hit["_source"].get("assetId"),
                type=hit["_source"].get("type"),
                create_date=hit["_source"].get("createDate"),
                main_representation=hit["_source"].get("mainRepresentation"),
                derived_representations=hit["_source"].get("derivedRepresentations"),
                metadata=hit["_source"].get("metadata", {}),
                score=hit["_score"],
            )
            for hit in response["hits"]["hits"]
        ]

        search_metadata = SearchMetadata(
            totalResults=response["hits"]["total"]["value"],
            page=(params.from_ // params.size) + 1,
            pageSize=params.size,
            searchTerm=params.q,
            facets=response.get("aggregations"),
            suggestions=response.get("suggest"),
        )

        return SearchResponse(
            status="200",
            message="ok",
            data={
                "searchMetadata": search_metadata.model_dump(),
                "results": [hit.model_dump() for hit in hits],
            },
        )

    except OpenSearchException as e:
        logger.error(f"OpenSearch error: {str(e)}")
        raise SearchException(f"Search operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise SearchException("An unexpected error occurred")


@app.get("/search")
@tracer.capture_method
def handle_search():
    """Handle search requests with validated parameters."""
    try:
        params = SearchParams(**app.current_event.get("queryStringParameters", {}))
        results = perform_search(params)

        return {
            "statusCode": 200,
            "body": results.model_dump(),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
        }
    except ValueError as e:
        logger.warning(f"Invalid input parameters: {str(e)}")
        return {
            "statusCode": 400,
            "body": {"status": "400", "message": str(e), "data": None},
            "headers": {"Content-Type": "application/json"},
        }
    except SearchException as e:
        logger.error(f"Search error: {str(e)}")
        return {
            "statusCode": 500,
            "body": {"status": "500", "message": str(e), "data": None},
            "headers": {"Content-Type": "application/json"},
        }


@metrics.log_metrics
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler function"""
    return app.resolve(event, context)
