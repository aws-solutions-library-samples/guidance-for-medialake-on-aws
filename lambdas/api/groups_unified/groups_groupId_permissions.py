"""
GET  /groups/{groupId}/permissions - Get group permissions
PUT  /groups/{groupId}/permissions - Update group permissions (auto-syncs Permission Set)
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, field_validator

VALID_ACTIONS = {
    "view",
    "create",
    "edit",
    "delete",
    "upload",
    "download",
    "publish",
}

VALID_RESOURCES = {
    "dashboard",
    "default_dashboard",
    "assets",
    "collections",
    "pipelines",
    "connectors",
    "users",
    "groups",
    "settings",
    "integrations",
}


class Permission(BaseModel):
    """Model for a permission within a permission set"""

    action: str = Field(
        ..., description="The action (e.g., 'view', 'create', 'edit', 'delete')"
    )
    resource: str = Field(..., description="The resource (e.g., 'assets', 'pipelines')")
    effect: Literal["Allow", "Deny"] = Field(
        ..., description="Whether to allow or deny ('Allow' or 'Deny')"
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v.lower() not in VALID_ACTIONS:
            raise ValueError(
                f"Invalid action '{v}'. Must be one of: {', '.join(sorted(VALID_ACTIONS))}"
            )
        return v.lower()

    @field_validator("resource")
    @classmethod
    def validate_resource(cls, v: str) -> str:
        if v.lower() not in VALID_RESOURCES:
            raise ValueError(
                f"Invalid resource '{v}'. Must be one of: {', '.join(sorted(VALID_RESOURCES))}"
            )
        return v.lower()


class UpdatePermissionsRequest(BaseModel):
    """Model for group permissions update request"""

    permissions: List[Permission] = Field(
        ..., description="List of permissions for the group"
    )


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class SuccessResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Response data")


CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "OPTIONS,GET,PUT,POST,DELETE,PATCH",
}


def _create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create standardized error response"""
    error_response = ErrorResponse(status=str(status_code), message=message, data={})
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": error_response.model_dump_json(),
    }


def _get_group_metadata(table, group_id: str) -> Optional[Dict[str, Any]]:
    """Get group metadata from DynamoDB"""
    response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"})
    return response.get("Item")


def _get_permission_set(table, permission_set_id: str) -> Optional[Dict[str, Any]]:
    """Get a permission set from DynamoDB by ID"""
    response = table.get_item(Key={"PK": f"PS#{permission_set_id}", "SK": "METADATA"})
    return response.get("Item")


def _create_permission_set_for_group(
    table,
    group_id: str,
    group_name: str,
    permissions: List[Dict[str, Any]],
    created_by: str,
) -> str:
    """
    Create a new Permission Set linked to a group.
    Returns the new permission set ID.
    """
    permission_set_id = str(uuid.uuid4())
    current_time = datetime.now(timezone.utc).isoformat()

    permission_set_item = {
        "PK": f"PS#{permission_set_id}",
        "SK": "METADATA",
        "id": permission_set_id,
        "name": group_name,
        "description": f"Auto-managed permission set for group: {group_name}",
        "permissions": permissions,
        "isSystem": False,
        "linkedGroupId": group_id,
        "createdBy": created_by,
        "createdAt": current_time,
        "updatedAt": current_time,
        "type": "PERMISSION_SET",
        "GSI1PK": "PERMISSION_SETS",
        "GSI1SK": f"PS#{permission_set_id}",
    }

    table.put_item(Item=permission_set_item)

    return permission_set_id


def _update_permission_set_permissions(
    table,
    permission_set_id: str,
    permissions: List[Dict[str, Any]],
    updated_by: str,
) -> Dict[str, Any]:
    """Update an existing Permission Set's permissions"""
    current_time = datetime.now(timezone.utc).isoformat()

    response = table.update_item(
        Key={"PK": f"PS#{permission_set_id}", "SK": "METADATA"},
        UpdateExpression="SET #permissions = :permissions, #updatedAt = :updatedAt, #updatedBy = :updatedBy",
        ExpressionAttributeNames={
            "#permissions": "permissions",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":permissions": permissions,
            ":updatedAt": current_time,
            ":updatedBy": updated_by,
        },
        ReturnValues="ALL_NEW",
    )

    return response.get("Attributes", {})


def _link_permission_set_to_group(table, group_id: str, permission_set_id: str) -> None:
    """Update the group metadata to link a permission set"""
    current_time = datetime.now(timezone.utc).isoformat()

    table.update_item(
        Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"},
        UpdateExpression="SET #psId = :psId, #aps = :aps, #updatedAt = :updatedAt",
        ExpressionAttributeNames={
            "#psId": "permissionSetId",
            "#aps": "assignedPermissionSets",
            "#updatedAt": "updatedAt",
        },
        ExpressionAttributeValues={
            ":psId": permission_set_id,
            ":aps": [permission_set_id],
            ":updatedAt": current_time,
        },
    )


def _transform_permissions(permissions_data) -> List[Dict[str, Any]]:
    """
    Transform permissions from various stored formats to a standard array format.
    Handles both object format (resource.action: true) and array format.
    """
    if isinstance(permissions_data, list):
        # Validate each item has the required keys
        validated = []
        for item in permissions_data:
            if isinstance(item, dict) and all(
                k in item for k in ("action", "resource", "effect")
            ):
                validated.append(item)
        return validated

    if isinstance(permissions_data, dict):
        permissions_array = []
        for key, value in permissions_data.items():
            if isinstance(value, dict):
                # Nested format: { "assets": { "view": true, "edit": true } }
                # or settings sub-resources: { "settings": { "users": { "view": true } } }
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        # Double-nested: e.g. settings.users.view
                        for action_key, action_value in sub_value.items():
                            if isinstance(action_value, bool) and action_value:
                                permissions_array.append(
                                    {
                                        "action": action_key,
                                        "resource": (
                                            sub_key if key == "settings" else key
                                        ),
                                        "effect": "Allow",
                                    }
                                )
                    elif isinstance(sub_value, bool) and sub_value:
                        # Single-nested: e.g. assets.view = true
                        permissions_array.append(
                            {
                                "action": sub_key,
                                "resource": key,
                                "effect": "Allow",
                            }
                        )
            elif isinstance(value, bool):
                # Flat format: { "assets.view": true } (dot-separated key)
                parts = key.split(".", 1)
                if len(parts) == 2:
                    resource, action = parts
                else:
                    resource = key
                    action = "view"
                if value:
                    permissions_array.append(
                        {
                            "action": action,
                            "resource": resource,
                            "effect": "Allow",
                        }
                    )
        return permissions_array

    return []


def handle_get_group_permissions(
    group_id: str, dynamodb, table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    GET /groups/{groupId}/permissions
    Returns the permission set associated with the group.
    """
    try:
        if not group_id:
            return _create_error_response(400, "Missing group ID")

        table = dynamodb.Table(table_name)

        # 1. Get group metadata
        group_item = _get_group_metadata(table, group_id)
        if not group_item:
            return _create_error_response(404, f"Group '{group_id}' not found")

        # 2. Check if group has a linked permission set
        permission_set_id = group_item.get("permissionSetId")
        assigned_ps = group_item.get("assignedPermissionSets", [])

        # If no direct link, try the first assigned permission set
        if not permission_set_id and assigned_ps:
            permission_set_id = assigned_ps[0]

        permissions = []
        ps_item = None

        if permission_set_id:
            # 3. Fetch the permission set
            ps_item = _get_permission_set(table, permission_set_id)
            if ps_item:
                raw_permissions = ps_item.get("permissions", [])
                permissions = _transform_permissions(raw_permissions)

        response_data = {
            "groupId": group_id,
            "permissionSetId": permission_set_id,
            "permissions": permissions,
            "updatedAt": (
                ps_item.get("updatedAt") if permission_set_id and ps_item else None
            ),
        }

        response = SuccessResponse(
            status="200",
            message="Group permissions retrieved successfully",
            data=response_data,
        )

        logger.info(
            "Retrieved group permissions",
            extra={
                "group_id": group_id,
                "permission_set_id": permission_set_id,
                "permission_count": len(permissions),
            },
        )
        metrics.add_metric(
            name="SuccessfulGetGroupPermissions", unit=MetricUnit.Count, value=1
        )

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": response.model_dump_json(),
        }

    except Exception:
        logger.exception("Error getting group permissions")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, "Internal server error")


def handle_put_group_permissions(
    group_id: str, app, dynamodb, table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    PUT /groups/{groupId}/permissions
    Updates the group's permissions by auto-syncing a linked Permission Set.

    Logic:
    1. If the group has an existing linked Permission Set, update it.
    2. If not, create a new Permission Set and link it to the group.
    """
    try:
        if not group_id:
            return _create_error_response(400, "Missing group ID")

        # Extract user ID from authorizer context
        request_context = app.current_event.raw_event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        user_id = authorizer.get("userId") or authorizer.get("sub")

        if not user_id:
            claims_raw = authorizer.get("claims", {})
            if isinstance(claims_raw, str):
                try:
                    import json as _json

                    claims = _json.loads(claims_raw)
                    user_id = claims.get("sub")
                except (Exception,):
                    pass
            elif isinstance(claims_raw, dict):
                user_id = claims_raw.get("sub")

        if not user_id:
            user_id = request_context.get("authorizer", {}).get("principalId")

        if not user_id:
            return _create_error_response(400, "Unable to identify user")

        # Parse request body
        try:
            body = app.current_event.json_body
            update_request = UpdatePermissionsRequest(**body)
        except Exception as e:
            logger.error(f"Invalid request body: {str(e)}")
            return _create_error_response(400, f"Invalid request: {str(e)}")

        table = dynamodb.Table(table_name)

        # 1. Get group metadata
        group_item = _get_group_metadata(table, group_id)
        if not group_item:
            return _create_error_response(404, f"Group '{group_id}' not found")

        group_name = group_item.get("name", group_id)
        permissions_list = [p.model_dump() for p in update_request.permissions]

        # 2. Check if group has a linked permission set
        permission_set_id = group_item.get("permissionSetId")
        assigned_ps = group_item.get("assignedPermissionSets", [])

        if not permission_set_id and assigned_ps:
            permission_set_id = assigned_ps[0]

        if permission_set_id:
            # 3a. Update existing permission set
            logger.info(
                f"Updating existing permission set",
                extra={
                    "group_id": group_id,
                    "permission_set_id": permission_set_id,
                },
            )
            _update_permission_set_permissions(
                table, permission_set_id, permissions_list, user_id
            )
        else:
            # 3b. Create a new permission set and link it
            logger.info(
                f"Creating new permission set for group",
                extra={"group_id": group_id},
            )
            permission_set_id = _create_permission_set_for_group(
                table, group_id, group_name, permissions_list, user_id
            )

            # Link the new permission set to the group
            _link_permission_set_to_group(table, group_id, permission_set_id)

        response_data = {
            "groupId": group_id,
            "permissionSetId": permission_set_id,
            "permissions": permissions_list,
        }

        response = SuccessResponse(
            status="200",
            message="Group permissions updated successfully",
            data=response_data,
        )

        logger.info(
            "Updated group permissions",
            extra={
                "group_id": group_id,
                "permission_set_id": permission_set_id,
                "permission_count": len(permissions_list),
            },
        )
        metrics.add_metric(
            name="SuccessfulUpdateGroupPermissions", unit=MetricUnit.Count, value=1
        )

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": response.model_dump_json(),
        }

    except ClientError:
        logger.exception("DynamoDB error updating group permissions")
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, "Database error")
    except Exception:
        logger.exception("Error updating group permissions")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, "Internal server error")
