from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, conint
import os
import boto3
from aws_lambda_powertools.event_handler.openapi.params import Query
from aws_lambda_powertools.logging import correlation_paths
from opensearchpy import (
    RequestsHttpConnection,
    RequestsAWSV4SignerAuth,
    OpenSearch,
    OpenSearchException,
)

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
    size: conint(gt=0, le=100) = Field(default=10)  # type: ignore
    from_: conint(ge=0) = Field(default=0, alias="from")  # type: ignore
    fuzzy_max_expansions: conint(ge=1, le=50) = Field(default=10)  # type: ignore
    min_score: float = Field(default=0.1)


class SearchResult(BaseModel):
    """Pydantic model for search results"""

    id: str
    title: str
    content: str
    score: float


class SearchResponse(BaseModel):
    """Pydantic model for the search response"""

    total: int
    hits: List[SearchResult]
    took: int


def get_opensearch_client() -> OpenSearch:
    """Create and return an OpenSearch client."""
    host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
    region = os.environ["AWS_REGION"]

    auth = RequestsAWSV4SignerAuth(
        boto3.Session().get_credentials(), "us-east-1", "aoss"
    )

    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        region="us-east-1",
    )


@tracer.capture_method
def perform_search(params: SearchParams) -> SearchResponse:
    """
    Perform search operation in OpenSearch with proper error handling.
    """
    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    search_body = {
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": params.q,
                            "fields": [
                                "title^3",
                                "content^2",
                                "description",
                                "tags^1.5",
                                "metadata.*",
                            ],
                            "fuzziness": "AUTO",
                            "prefix_length": 2,
                            "max_expansions": params.fuzzy_max_expansions,
                            "type": "best_fields",
                            "tie_breaker": 0.3,
                            "minimum_should_match": "75%",
                        }
                    },
                    {
                        "multi_match": {
                            "query": params.q,
                            "fields": ["title^2", "content"],
                            "type": "phrase_prefix",
                            "boost": 1.2,
                        }
                    },
                ]
            }
        },
        "min_score": params.min_score,
    }

    try:
        response = client.search(
            body=search_body, index=index_name, size=params.size, from_=params.from_
        )

        hits = [
            SearchResult(
                id=hit["_id"],
                title=hit["_source"].get("title", ""),
                content=hit["_source"].get("content", ""),
                score=hit["_score"],
            )
            for hit in response["hits"]["hits"]
        ]

        return SearchResponse(
            total=response["hits"]["total"]["value"], hits=hits, took=response["took"]
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
            "body": {"error": str(e)},
            "headers": {"Content-Type": "application/json"},
        }
    except SearchException as e:
        logger.error(f"Search error: {str(e)}")
        return {
            "statusCode": 500,
            "body": {"error": str(e)},
            "headers": {"Content-Type": "application/json"},
        }


@metrics.log_metrics
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
