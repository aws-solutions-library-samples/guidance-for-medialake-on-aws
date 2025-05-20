"""
Example Lambda function demonstrating the use of the lambda_error_handler module.

This file shows how to use the various features of the lambda_error_handler module:
1. Checking response status codes
2. Using custom exception classes
3. Using the with_error_handling decorator
4. Handling API responses
5. Validating environment variables
"""

import os
import json
import sys
import requests
from typing import Dict, Any

# Add common_libraries to path for importing shared modules
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'common_libraries'))

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from lambda_error_handler import (
    check_response_status,
    handle_api_response,
    with_error_handling,
    validate_response,
    ResponseError,
    ApiError,
    ValidationError,
    ConfigurationError,
    check_required_env_vars
)

# Initialize logger
logger = Logger()

# Example function that uses check_response_status
def process_opensearch_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process an OpenSearch response, checking for errors.
    
    Args:
        response: The OpenSearch response
        
    Returns:
        Processed response data
        
    Raises:
        ResponseError: If the response status is not successful
    """
    # Check if the response is successful
    check_response_status(response, "OpenSearch", "search")
    
    # Process the response
    hits = response.get("hits", {}).get("hits", [])
    return {
        "count": len(hits),
        "results": hits
    }


# Example function that uses handle_api_response
def call_external_api(url: str) -> Dict[str, Any]:
    """
    Call an external API and handle the response.
    
    Args:
        url: The API URL to call
        
    Returns:
        Processed API response
        
    Raises:
        ApiError: If the API call fails
    """
    try:
        response = requests.get(url, timeout=10)
        # This will check the status code and raise ApiError if not successful
        return handle_api_response(response, "External", url)
    except requests.RequestException as e:
        # Convert requests exceptions to our ApiError
        raise ApiError(
            message=f"API request failed: {str(e)}",
            status_code=500,
            api_name="External",
            endpoint=url,
            response={"error": str(e)}
        )


# Example function that validates input
def validate_search_params(params: Dict[str, Any]) -> None:
    """
    Validate search parameters.
    
    Args:
        params: Search parameters
        
    Raises:
        ValidationError: If parameters are invalid
    """
    if "query" not in params:
        raise ValidationError("Missing required parameter", "query", None)
    
    if params.get("size", 0) < 0:
        raise ValidationError("Size must be non-negative", "size", params["size"])


# Example function that uses the validate_response decorator
@validate_response(service="OpenSearch", operation="index")
def index_document(doc_id: str, document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Index a document in OpenSearch.
    
    This is a mock function that demonstrates the use of the validate_response decorator.
    
    Args:
        doc_id: Document ID
        document: Document to index
        
    Returns:
        OpenSearch response
    """
    # This is a mock response - in a real function, this would be the result of an OpenSearch API call
    return {
        "status": 201,
        "_id": doc_id,
        "_index": "my_index",
        "result": "created"
    }


# Main Lambda handler with error handling
@with_error_handling
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Example Lambda handler with comprehensive error handling.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Lambda response
    """
    try:
        # Check required environment variables
        check_required_env_vars(["OPENSEARCH_ENDPOINT", "INDEX_NAME"])
        
        # Extract parameters from the event
        params = event.get("queryStringParameters", {}) or {}
        
        # Validate parameters
        validate_search_params(params)
        
        # Process based on the operation
        operation = params.get("operation", "search")
        
        if operation == "search":
            # Example of handling a search operation
            mock_response = {
                "status": 200,
                "hits": {
                    "total": {"value": 2},
                    "hits": [
                        {"_id": "1", "_source": {"title": "Document 1"}},
                        {"_id": "2", "_source": {"title": "Document 2"}}
                    ]
                }
            }
            result = process_opensearch_response(mock_response)
            
        elif operation == "index":
            # Example of indexing a document
            document = event.get("body", {})
            if isinstance(document, str):
                document = json.loads(document)
            
            doc_id = params.get("id", "auto-id")
            result = index_document(doc_id, document)
            
        elif operation == "external":
            # Example of calling an external API
            url = params.get("url", "https://jsonplaceholder.typicode.com/posts/1")
            result = call_external_api(url)
            
        else:
            raise ValidationError("Invalid operation", "operation", operation)
        
        # Return successful response
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result)
        }
        
    except ValidationError as e:
        # The with_error_handling decorator will catch this and format the response
        logger.warning(f"Validation error: {e.message}", extra={
            "field": e.field,
            "value": e.value
        })
        raise
        
    except (ResponseError, ApiError) as e:
        # The with_error_handling decorator will catch this and format the response
        # We can add additional logging if needed
        logger.error(f"API error: {e.message}", extra={
            "status_code": e.status_code,
            "service": e.service
        })
        raise
        
    except ConfigurationError as e:
        # The with_error_handling decorator will catch this and format the response
        logger.error(f"Configuration error: {e.message}", extra={
            "missing_configs": e.missing_configs
        })
        raise
        
    except Exception as e:
        # Catch any other exceptions
        logger.exception("Unexpected error")
        raise