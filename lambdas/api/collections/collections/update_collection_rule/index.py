import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-rule-update",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-rule-update")
metrics = Metrics(namespace="medialake", service="collection-rule-update")

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
def validate_update_request_data(request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Validate collection rule update request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate optional fields if provided
    if request_data.get("name") is not None:
        if not request_data["name"]:
            errors.append(
                {
                    "field": "name",
                    "message": "Rule name cannot be empty",
                    "code": "INVALID_VALUE",
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

    if (
        request_data.get("description") is not None
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

    # Validate isActive if provided
    if request_data.get("isActive") is not None and not isinstance(
        request_data["isActive"], bool
    ):
        errors.append(
            {
                "field": "isActive",
                "message": "isActive must be a boolean",
                "code": "INVALID_TYPE",
            }
        )

    # Validate criteria if provided
    if request_data.get("criteria") is not None and not isinstance(
        request_data["criteria"], dict
    ):
        errors.append(
            {
                "field": "criteria",
                "message": "Criteria must be a valid JSON object",
                "code": "INVALID_TYPE",
            }
        )

    logger.debug(
        {
            "message": "Update request data validation completed",
            "error_count": len(errors),
            "errors": errors,
            "operation": "validate_update_request_data",
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
def update_rule_with_priority_change(
    table,
    collection_id: str,
    existing_rule: Dict[str, Any],
    updates: Dict[str, Any],
    new_priority: int,
) -> Dict[str, Any]:
    """
    Update a rule when priority changes (requires delete and recreate)

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        existing_rule: Existing rule item
        updates: Updates to apply
        new_priority: New priority value

    Returns:
        Updated rule item
    """
    current_timestamp = datetime.utcnow().isoformat() + "Z"

    # Create new rule item with updated values
    new_rule = existing_rule.copy()
    new_rule.update(updates)
    new_rule["priority"] = new_priority
    new_rule["updatedAt"] = current_timestamp

    # Create new sort key with new priority
    padded_priority = f"{new_priority:06d}"
    new_rule["SK"] = f"{RULE_SK_PREFIX}{padded_priority}#{existing_rule['ruleId']}"

    # Use transaction to delete old item and create new one
    transact_items = [
        {
            "Delete": {
                "TableName": TABLE_NAME,
                "Key": {"PK": existing_rule["PK"], "SK": existing_rule["SK"]},
                "ConditionExpression": "attribute_exists(PK) AND attribute_exists(SK)",
            }
        },
        {
            "Put": {
                "TableName": TABLE_NAME,
                "Item": new_rule,
                "ConditionExpression": "attribute_not_exists(PK) OR attribute_not_exists(SK)",
            }
        },
    ]

    try:
        dynamodb.meta.client.transact_write_items(TransactItems=transact_items)
        logger.info(
            {
                "message": "Rule updated with priority change",
                "collection_id": collection_id,
                "rule_id": existing_rule["ruleId"],
                "old_priority": existing_rule.get("priority"),
                "new_priority": new_priority,
                "old_sk": existing_rule["SK"],
                "new_sk": new_rule["SK"],
                "operation": "update_rule_with_priority_change",
            }
        )
        return new_rule
    except ClientError as e:
        logger.error(
            {
                "message": "Failed to update rule with priority change",
                "collection_id": collection_id,
                "rule_id": existing_rule["ruleId"],
                "error": str(e),
                "operation": "update_rule_with_priority_change",
            }
        )
        raise


@tracer.capture_method
def update_rule_in_place(
    table, existing_rule: Dict[str, Any], updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update a rule in place (no priority change)

    Args:
        table: DynamoDB table resource
        existing_rule: Existing rule item
        updates: Updates to apply

    Returns:
        Updated rule item
    """
    current_timestamp = datetime.utcnow().isoformat() + "Z"
    updates["updatedAt"] = current_timestamp

    # Build update expression
    update_expression_parts = []
    expression_attribute_values = {}
    expression_attribute_names = {}

    for key, value in updates.items():
        if key in ["name", "description", "criteria", "isActive", "updatedAt"]:
            update_expression_parts.append(f"#{key} = :{key}")
            expression_attribute_names[f"#{key}"] = key
            expression_attribute_values[f":{key}"] = value

    if not update_expression_parts:
        # No updates to apply
        return existing_rule

    update_expression = "SET " + ", ".join(update_expression_parts)

    try:
        response = table.update_item(
            Key={"PK": existing_rule["PK"], "SK": existing_rule["SK"]},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
            ReturnValues="ALL_NEW",
        )

        updated_rule = response["Attributes"]
        logger.info(
            {
                "message": "Rule updated in place",
                "rule_id": existing_rule["ruleId"],
                "updated_fields": list(updates.keys()),
                "operation": "update_rule_in_place",
            }
        )
        return updated_rule

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to update rule in place",
                "rule_id": existing_rule["ruleId"],
                "error": str(e),
                "operation": "update_rule_in_place",
            }
        )
        raise


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


@app.put("/collections/<collection_id>/rules/<rule_id>")
@tracer.capture_method
def update_collection_rule(collection_id: str, rule_id: str):
    """Update an existing collection rule"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection rule update attempted without valid user context",
                    "collection_id": collection_id,
                    "rule_id": rule_id,
                    "operation": "update_collection_rule",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to update collection rules",
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
                "message": "Processing collection rule update request",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "request_data": request_data,
                "user_id": user_id,
                "operation": "update_collection_rule",
            }
        )

        # Validate request data
        validation_errors = validate_update_request_data(request_data)

        if validation_errors:
            logger.warning(
                {
                    "message": "Collection rule update request validation failed",
                    "collection_id": collection_id,
                    "rule_id": rule_id,
                    "errors": validation_errors,
                    "operation": "update_collection_rule",
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
                            "message": "You don't have permission to update rules for this collection",
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

        # Validate rule criteria if provided and rule type is being changed or criteria is being updated
        if request_data.get("criteria"):
            rule_type = existing_rule.get("ruleType")
            criteria_errors = validate_rule_criteria(
                rule_type, request_data["criteria"]
            )
            if criteria_errors:
                logger.warning(
                    {
                        "message": "Rule criteria validation failed",
                        "collection_id": collection_id,
                        "rule_id": rule_id,
                        "errors": criteria_errors,
                        "operation": "update_collection_rule",
                    }
                )

                return {
                    "statusCode": 422,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "The request could not be processed due to validation errors",
                                "details": criteria_errors,
                            },
                            "meta": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "version": "v1",
                                "request_id": app.current_event.request_context.request_id,
                            },
                        }
                    ),
                }

        # Check if priority is changing
        new_priority = request_data.get("priority")
        current_priority = existing_rule.get("priority")
        priority_changed = (
            new_priority is not None and int(new_priority) != current_priority
        )

        # Prepare updates dictionary (exclude priority if it's changing)
        updates = {}
        for key in ["name", "description", "criteria", "isActive"]:
            if request_data.get(key) is not None:
                updates[key] = request_data[key]

        # Update the rule
        if priority_changed:
            # Priority changed - need to delete old item and create new one
            updated_rule = update_rule_with_priority_change(
                table, collection_id, existing_rule, updates, int(new_priority)
            )
        else:
            # Priority not changed - update in place
            updated_rule = update_rule_in_place(table, existing_rule, updates)

        logger.info(
            {
                "message": "Collection rule updated successfully",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "priority_changed": priority_changed,
                "updated_fields": list(updates.keys()),
                "user_id": user_id,
                "operation": "update_collection_rule",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionRuleUpdates", unit=MetricUnit.Count, value=1
        )

        # Format response data
        response_data = format_rule_response(updated_rule, rule_id, user_context)

        return {
            "statusCode": 200,
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
                "message": "DynamoDB client error during collection rule update",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "error_code": error_code,
                "error_message": error_message,
                "user_id": user_context.get("user_id"),
                "operation": "update_collection_rule",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionRuleUpdates", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection rule update",
                "collection_id": collection_id,
                "rule_id": rule_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "user_id": user_context.get("user_id"),
                "operation": "update_collection_rule",
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
