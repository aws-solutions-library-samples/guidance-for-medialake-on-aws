import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-rule-deletion",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-rule-deletion")
metrics = Metrics(namespace="medialake", service="collection-rule-deletion")

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

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")

# Get environment variables
TABLE_NAME = os.environ["COLLECTIONS_TABLE_NAME"]

# Constants
COLLECTION_PK_PREFIX = "COLL#"
RULE_SK_PREFIX = "RULE#"
METADATA_SK = "METADATA"


@tracer.capture_method
def extract_user_context(event: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Extract user information from JWT token in event context

    Args:
        event: Lambda event

    Returns:
        Dictionary with user_id and username
    """
    try:
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        claims = authorizer.get("claims", {})

        user_id = claims.get("sub")
        username = claims.get("cognito:username")

        logger.debug(
            {
                "message": "User context extracted",
                "user_id": user_id,
                "username": username,
                "operation": "extract_user_context",
            }
        )

        return {"user_id": user_id, "username": username}
    except Exception as e:
        logger.warning(
            {
                "message": "Failed to extract user context",
                "error": str(e),
                "operation": "extract_user_context",
            }
        )
        return {"user_id": None, "username": None}


@tracer.capture_method
def validate_collection_access(table, collection_id: str, user_id: str) -> bool:
    """
    Validate that the collection exists and user has write access

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to validate
        user_id: User ID requesting access

    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if collection exists
        response = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        )

        item = response.get("Item")
        if not item:
            logger.warning(
                {
                    "message": "Collection not found",
                    "collection_id": collection_id,
                    "operation": "validate_collection_access",
                }
            )
            return False

        # Check if collection is active
        if item.get("status") != "ACTIVE":
            logger.warning(
                {
                    "message": "Collection is not active",
                    "collection_id": collection_id,
                    "status": item.get("status"),
                    "operation": "validate_collection_access",
                }
            )
            return False

        # Check if user has write access (owner or has edit permissions)
        if item.get("ownerId") == user_id:
            logger.debug(
                {
                    "message": "Collection write access granted - user is owner",
                    "collection_id": collection_id,
                    "operation": "validate_collection_access",
                }
            )
            return True

        # TODO: Check user permissions for non-owned collections
        # For now, deny write access for non-owners (simplified logic)
        logger.warning(
            {
                "message": "Collection write access denied - user is not owner",
                "collection_id": collection_id,
                "user_id": user_id,
                "owner_id": item.get("ownerId"),
                "operation": "validate_collection_access",
            }
        )
        return False

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to validate collection access",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "validate_collection_access",
            }
        )
        return False


@tracer.capture_method
def find_rule_by_id(
    table, collection_id: str, rule_id: str
) -> Optional[Dict[str, Any]]:
    """
    Find an existing rule by ID

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        rule_id: Rule ID to find

    Returns:
        Rule item if found, None otherwise
    """
    try:
        # Query all rules for the collection to find the one with matching ruleId
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": RULE_SK_PREFIX,
            },
        )

        items = response.get("Items", [])
        for item in items:
            if item.get("ruleId") == rule_id:
                logger.debug(
                    {
                        "message": "Rule found",
                        "collection_id": collection_id,
                        "rule_id": rule_id,
                        "rule_sk": item["SK"],
                        "operation": "find_rule_by_id",
                    }
                )
                return item

        logger.warning(
            {
                "message": "Rule not found",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "operation": "find_rule_by_id",
            }
        )
        return None

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to find rule",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "error": str(e),
                "operation": "find_rule_by_id",
            }
        )
        return None


@tracer.capture_method
def delete_rule(table, rule_item: Dict[str, Any]) -> bool:
    """
    Delete a rule from DynamoDB

    Args:
        table: DynamoDB table resource
        rule_item: Rule item to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        table.delete_item(
            Key={"PK": rule_item["PK"], "SK": rule_item["SK"]},
            ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
        )

        logger.info(
            {
                "message": "Rule deleted successfully",
                "rule_id": rule_item.get("ruleId"),
                "rule_sk": rule_item["SK"],
                "operation": "delete_rule",
            }
        )
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning(
                {
                    "message": "Rule deletion failed - rule does not exist",
                    "rule_id": rule_item.get("ruleId"),
                    "rule_sk": rule_item["SK"],
                    "operation": "delete_rule",
                }
            )
            return False
        else:
            logger.error(
                {
                    "message": "Failed to delete rule",
                    "rule_id": rule_item.get("ruleId"),
                    "error": str(e),
                    "operation": "delete_rule",
                }
            )
            raise


@app.delete("/collections/<collection_id>/rules/<rule_id>")
@tracer.capture_method
def delete_collection_rule(collection_id: str, rule_id: str):
    """Delete a collection rule"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection rule deletion attempted without valid user context",
                    "collection_id": collection_id,
                    "rule_id": rule_id,
                    "operation": "delete_collection_rule",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to delete collection rules",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        logger.debug(
            {
                "message": "Processing collection rule deletion request",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "user_id": user_id,
                "operation": "delete_collection_rule",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Validate collection access
        if not validate_collection_access(table, collection_id, user_id):
            return {
                "statusCode": 403,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INSUFFICIENT_PERMISSIONS",
                            "message": "You don't have permission to delete rules from this collection",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Find existing rule
        existing_rule = find_rule_by_id(table, collection_id, rule_id)
        if not existing_rule:
            return {
                "statusCode": 404,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "RULE_NOT_FOUND",
                            "message": f"Rule '{rule_id}' not found in collection '{collection_id}'",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Delete the rule
        if not delete_rule(table, existing_rule):
            # Rule was already deleted by another request
            return {
                "statusCode": 404,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "RULE_NOT_FOUND",
                            "message": f"Rule '{rule_id}' not found in collection '{collection_id}'",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        logger.info(
            {
                "message": "Collection rule deleted successfully",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "rule_name": existing_rule.get("name"),
                "rule_priority": existing_rule.get("priority"),
                "user_id": user_id,
                "operation": "delete_collection_rule",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionRuleDeletions", unit=MetricUnit.Count, value=1
        )

        # Return 204 No Content on successful deletion
        return {"statusCode": 204, "body": ""}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection rule deletion",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "error_code": error_code,
                "error_message": error_message,
                "user_id": user_context.get("user_id"),
                "operation": "delete_collection_rule",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionRuleDeletions", unit=MetricUnit.Count, value=1
        )

        # Map specific DynamoDB errors to appropriate HTTP status codes
        status_code = 500
        if error_code in ["ValidationException", "ConditionalCheckFailedException"]:
            status_code = 400

        return {
            "statusCode": status_code,
            "body": json.dumps(
                {
                    "success": False,
                    "error": {"code": error_code, "message": error_message},
                    "meta": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "version": "v1",
                        "request_id": app.current_event.request_context.request_id,
                    },
                }
            ),
        }

    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error during collection rule deletion",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "user_id": user_context.get("user_id"),
                "operation": "delete_collection_rule",
                "status": "failed",
            }
        )

        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "success": False,
                    "error": {
                        "code": "InternalServerError",
                        "message": "An unexpected error occurred",
                    },
                    "meta": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "version": "v1",
                        "request_id": app.current_event.request_context.request_id,
                    },
                }
            ),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    logger.debug(
        {
            "message": "Lambda handler invoked",
            "event": event,
            "operation": "lambda_handler",
        }
    )
    return app.resolve(event, context)
