import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    validate_collection_access,
)

# Import centralized utilities
from user_auth import extract_user_context

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-rule-creation",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-rule-creation")
metrics = Metrics(namespace="medialake", service="collection-rule-creation")

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
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000
VALID_RULE_TYPES = ["semantic", "metadata", "keyword", "composite"]
VALID_METADATA_OPERATORS = [
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "greater_equal",
    "less_equal",
    "in",
    "not_in",
    "contains",
    "not_contains",
]
VALID_MATCH_TYPES = ["any", "all"]
VALID_COMPOSITE_OPERATORS = ["AND", "OR"]
MAX_PRIORITY = 999999


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
def generate_rule_id() -> str:
    """
    Generate a unique rule ID

    Returns:
        Unique rule ID string
    """
    # Generate a short UUID-based ID with rule prefix
    short_uuid = str(uuid.uuid4())[:8]
    rule_id = f"rule_{short_uuid}"

    logger.debug(
        {
            "message": "Generated rule ID",
            "rule_id": rule_id,
            "operation": "generate_rule_id",
        }
    )

    return rule_id


@tracer.capture_method
def validate_request_data(request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Validate collection rule creation request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate required fields
    if not request_data.get("name"):
        errors.append(
            {
                "field": "name",
                "message": "Rule name is required",
                "code": "REQUIRED_FIELD",
            }
        )
    elif len(request_data["name"]) > MAX_NAME_LENGTH:
        errors.append(
            {
                "field": "name",
                "message": f"Rule name must be {MAX_NAME_LENGTH} characters or less",
                "code": "INVALID_LENGTH",
            }
        )

    if not request_data.get("ruleType"):
        errors.append(
            {
                "field": "ruleType",
                "message": "Rule type is required",
                "code": "REQUIRED_FIELD",
            }
        )
    elif request_data["ruleType"] not in VALID_RULE_TYPES:
        errors.append(
            {
                "field": "ruleType",
                "message": f"Invalid rule type. Valid options: {', '.join(VALID_RULE_TYPES)}",
                "code": "INVALID_VALUE",
            }
        )

    if not request_data.get("criteria"):
        errors.append(
            {
                "field": "criteria",
                "message": "Rule criteria is required",
                "code": "REQUIRED_FIELD",
            }
        )
    elif not isinstance(request_data["criteria"], dict):
        errors.append(
            {
                "field": "criteria",
                "message": "Criteria must be a valid JSON object",
                "code": "INVALID_TYPE",
            }
        )

    # Validate optional fields
    if (
        request_data.get("description")
        and len(request_data["description"]) > MAX_DESCRIPTION_LENGTH
    ):
        errors.append(
            {
                "field": "description",
                "message": f"Description must be {MAX_DESCRIPTION_LENGTH} characters or less",
                "code": "INVALID_LENGTH",
            }
        )

    # Validate priority if provided
    if request_data.get("priority") is not None:
        try:
            priority = int(request_data["priority"])
            if priority < 0 or priority > MAX_PRIORITY:
                errors.append(
                    {
                        "field": "priority",
                        "message": f"Priority must be between 0 and {MAX_PRIORITY}",
                        "code": "INVALID_RANGE",
                    }
                )
        except (ValueError, TypeError):
            errors.append(
                {
                    "field": "priority",
                    "message": "Priority must be a valid integer",
                    "code": "INVALID_TYPE",
                }
            )

    logger.debug(
        {
            "message": "Request data validation completed",
            "error_count": len(errors),
            "errors": errors,
            "operation": "validate_request_data",
        }
    )

    return errors


@tracer.capture_method
def validate_rule_criteria(
    rule_type: str, criteria: Dict[str, Any]
) -> List[Dict[str, str]]:
    """
    Validate rule criteria based on rule type

    Args:
        rule_type: Type of rule (semantic, metadata, keyword, composite)
        criteria: Rule criteria object

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if rule_type == "semantic":
        # Validate semantic rule criteria
        if not criteria.get("searchPhrase"):
            errors.append(
                {
                    "field": "criteria.searchPhrase",
                    "message": "Search phrase is required for semantic rules",
                    "code": "REQUIRED_FIELD",
                }
            )

        if "threshold" in criteria:
            try:
                threshold = float(criteria["threshold"])
                if threshold < 0.0 or threshold > 1.0:
                    errors.append(
                        {
                            "field": "criteria.threshold",
                            "message": "Threshold must be between 0.0 and 1.0",
                            "code": "INVALID_RANGE",
                        }
                    )
            except (ValueError, TypeError):
                errors.append(
                    {
                        "field": "criteria.threshold",
                        "message": "Threshold must be a valid number",
                        "code": "INVALID_TYPE",
                    }
                )

    elif rule_type == "metadata":
        # Validate metadata rule criteria
        if not criteria.get("conditions"):
            errors.append(
                {
                    "field": "criteria.conditions",
                    "message": "Conditions are required for metadata rules",
                    "code": "REQUIRED_FIELD",
                }
            )
        elif not isinstance(criteria["conditions"], list):
            errors.append(
                {
                    "field": "criteria.conditions",
                    "message": "Conditions must be an array",
                    "code": "INVALID_TYPE",
                }
            )
        else:
            # Validate each condition
            for i, condition in enumerate(criteria["conditions"]):
                if not isinstance(condition, dict):
                    errors.append(
                        {
                            "field": f"criteria.conditions[{i}]",
                            "message": "Each condition must be an object",
                            "code": "INVALID_TYPE",
                        }
                    )
                    continue

                if not condition.get("field"):
                    errors.append(
                        {
                            "field": f"criteria.conditions[{i}].field",
                            "message": "Field name is required",
                            "code": "REQUIRED_FIELD",
                        }
                    )

                if not condition.get("operator"):
                    errors.append(
                        {
                            "field": f"criteria.conditions[{i}].operator",
                            "message": "Operator is required",
                            "code": "REQUIRED_FIELD",
                        }
                    )
                elif condition["operator"] not in VALID_METADATA_OPERATORS:
                    errors.append(
                        {
                            "field": f"criteria.conditions[{i}].operator",
                            "message": f"Invalid operator. Valid options: {', '.join(VALID_METADATA_OPERATORS)}",
                            "code": "INVALID_VALUE",
                        }
                    )

                if "value" not in condition:
                    errors.append(
                        {
                            "field": f"criteria.conditions[{i}].value",
                            "message": "Value is required",
                            "code": "REQUIRED_FIELD",
                        }
                    )

        # Validate matchAll if provided
        if "matchAll" in criteria and not isinstance(criteria["matchAll"], bool):
            errors.append(
                {
                    "field": "criteria.matchAll",
                    "message": "matchAll must be a boolean",
                    "code": "INVALID_TYPE",
                }
            )

    elif rule_type == "keyword":
        # Validate keyword rule criteria
        if not criteria.get("keywords"):
            errors.append(
                {
                    "field": "criteria.keywords",
                    "message": "Keywords are required for keyword rules",
                    "code": "REQUIRED_FIELD",
                }
            )
        elif not isinstance(criteria["keywords"], list):
            errors.append(
                {
                    "field": "criteria.keywords",
                    "message": "Keywords must be an array",
                    "code": "INVALID_TYPE",
                }
            )
        elif len(criteria["keywords"]) == 0:
            errors.append(
                {
                    "field": "criteria.keywords",
                    "message": "At least one keyword is required",
                    "code": "INVALID_VALUE",
                }
            )
        else:
            # Validate each keyword is a string
            for i, keyword in enumerate(criteria["keywords"]):
                if not isinstance(keyword, str):
                    errors.append(
                        {
                            "field": f"criteria.keywords[{i}]",
                            "message": "Each keyword must be a string",
                            "code": "INVALID_TYPE",
                        }
                    )

        # Validate matchType if provided
        if "matchType" in criteria and criteria["matchType"] not in VALID_MATCH_TYPES:
            errors.append(
                {
                    "field": "criteria.matchType",
                    "message": f"Invalid match type. Valid options: {', '.join(VALID_MATCH_TYPES)}",
                    "code": "INVALID_VALUE",
                }
            )

    elif rule_type == "composite":
        # Validate composite rule criteria
        if not criteria.get("rules"):
            errors.append(
                {
                    "field": "criteria.rules",
                    "message": "Nested rules are required for composite rules",
                    "code": "REQUIRED_FIELD",
                }
            )
        elif not isinstance(criteria["rules"], list):
            errors.append(
                {
                    "field": "criteria.rules",
                    "message": "Rules must be an array",
                    "code": "INVALID_TYPE",
                }
            )
        elif len(criteria["rules"]) < 2:
            errors.append(
                {
                    "field": "criteria.rules",
                    "message": "At least two nested rules are required",
                    "code": "INVALID_VALUE",
                }
            )

        # Validate operator if provided
        if (
            "operator" in criteria
            and criteria["operator"] not in VALID_COMPOSITE_OPERATORS
        ):
            errors.append(
                {
                    "field": "criteria.operator",
                    "message": f"Invalid operator. Valid options: {', '.join(VALID_COMPOSITE_OPERATORS)}",
                    "code": "INVALID_VALUE",
                }
            )

    logger.debug(
        {
            "message": "Rule criteria validation completed",
            "rule_type": rule_type,
            "error_count": len(errors),
            "errors": errors,
            "operation": "validate_rule_criteria",
        }
    )

    return errors


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
def get_next_priority(table, collection_id: str) -> int:
    """
    Get the next available priority for a new rule

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID

    Returns:
        Next available priority number
    """
    try:
        # Query existing rules to find the highest priority
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": RULE_SK_PREFIX,
            },
            ProjectionExpression="priority",
            ScanIndexForward=False,  # Descending order
            Limit=1,
        )

        items = response.get("Items", [])
        if items and "priority" in items[0]:
            highest_priority = items[0]["priority"]
            next_priority = highest_priority + 1
        else:
            next_priority = 1  # First rule gets priority 1

        logger.debug(
            {
                "message": "Next priority calculated",
                "collection_id": collection_id,
                "next_priority": next_priority,
                "operation": "get_next_priority",
            }
        )

        return min(next_priority, MAX_PRIORITY)

    except Exception as e:
        logger.warning(
            {
                "message": "Failed to calculate next priority, using default",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "get_next_priority",
            }
        )
        return 1


@tracer.capture_method
def format_rule_response(
    item: Dict[str, Any], rule_id: str, user_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format DynamoDB item to API response format

    Args:
        item: DynamoDB item
        rule_id: Rule ID
        user_context: User context information

    Returns:
        Formatted rule object
    """
    formatted_item = {
        "id": rule_id,
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "ruleType": item.get("ruleType", ""),
        "criteria": item.get("criteria", {}),
        "isActive": item.get("isActive", True),
        "priority": item.get("priority", 0),
        "matchCount": item.get("matchCount", 0),
        "lastEvaluatedAt": item.get("lastEvaluatedAt"),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
        "createdBy": item.get("createdBy", ""),
    }

    return formatted_item


@app.post("/collections/<collection_id>/rules")
@tracer.capture_method
def create_collection_rule(collection_id: str):
    """Create a new collection rule"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection rule creation attempted without valid user context",
                    "collection_id": collection_id,
                    "operation": "create_collection_rule",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to create collection rules",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Get request body from the event
        request_data = app.current_event.json_body
        logger.debug(
            {
                "message": "Processing collection rule creation request",
                "collection_id": collection_id,
                "request_data": request_data,
                "user_id": user_id,
                "operation": "create_collection_rule",
            }
        )

        # Validate request data
        validation_errors = validate_request_data(request_data)

        # Validate rule criteria if basic validation passed
        if (
            not validation_errors
            and request_data.get("ruleType")
            and request_data.get("criteria")
        ):
            criteria_errors = validate_rule_criteria(
                request_data["ruleType"], request_data["criteria"]
            )
            validation_errors.extend(criteria_errors)

        if validation_errors:
            logger.warning(
                {
                    "message": "Collection rule creation request validation failed",
                    "collection_id": collection_id,
                    "errors": validation_errors,
                    "operation": "create_collection_rule",
                }
            )

            metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)

            return {
                "statusCode": 422,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "The request could not be processed due to validation errors",
                            "details": validation_errors,
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

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
                            "message": "You don't have permission to create rules for this collection",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Generate unique rule ID
        rule_id = generate_rule_id()
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        # Get priority (use provided or calculate next)
        priority = request_data.get("priority")
        if priority is None:
            priority = get_next_priority(table, collection_id)
        else:
            priority = int(priority)

        # Create zero-padded priority for sort key
        padded_priority = f"{priority:06d}"

        # Prepare rule item
        rule_item = {
            "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "SK": f"{RULE_SK_PREFIX}{padded_priority}#{rule_id}",
            "ruleId": rule_id,
            "name": request_data["name"],
            "ruleType": request_data["ruleType"],
            "criteria": request_data["criteria"],
            "isActive": request_data.get("isActive", True),
            "priority": priority,
            "matchCount": 0,
            "lastEvaluatedAt": None,
            "createdAt": current_timestamp,
            "updatedAt": current_timestamp,
            "createdBy": user_id,
        }

        # Add optional fields if provided
        if request_data.get("description"):
            rule_item["description"] = request_data["description"]

        logger.debug(
            {
                "message": "Prepared rule item for creation",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "priority": priority,
                "operation": "create_collection_rule",
            }
        )

        # Execute write operation
        try:
            table.put_item(
                Item=rule_item,
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    {
                        "message": "Collection rule creation failed - rule already exists",
                        "collection_id": collection_id,
                        "rule_id": rule_id,
                        "error": str(e),
                        "operation": "create_collection_rule",
                    }
                )
                return {
                    "statusCode": 409,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "RULE_ALREADY_EXISTS",
                                "message": "Rule with this priority already exists",
                            },
                            "meta": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "version": "v1",
                                "request_id": app.current_event.request_context.request_id,
                            },
                        }
                    ),
                }
            else:
                raise  # Re-raise other ClientErrors

        logger.info(
            {
                "message": "Collection rule created successfully in DynamoDB",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "rule_name": request_data["name"],
                "rule_type": request_data["ruleType"],
                "priority": priority,
                "user_id": user_id,
                "operation": "create_collection_rule",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionRuleCreations", unit=MetricUnit.Count, value=1
        )

        # Format response data
        response_data = format_rule_response(rule_item, rule_id, user_context)

        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "success": True,
                    "data": response_data,
                    "meta": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "version": "v1",
                        "request_id": app.current_event.request_context.request_id,
                    },
                }
            ),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection rule creation",
                "collection_id": collection_id,
                "error_code": error_code,
                "error_message": error_message,
                "rule_name": request_data.get("name"),
                "user_id": user_context.get("user_id"),
                "operation": "create_collection_rule",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionRuleCreations", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection rule creation",
                "collection_id": collection_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "rule_name": request_data.get("name"),
                "user_id": user_context.get("user_id"),
                "operation": "create_collection_rule",
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
