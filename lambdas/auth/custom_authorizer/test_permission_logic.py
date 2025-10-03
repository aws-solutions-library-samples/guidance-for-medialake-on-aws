#!/usr/bin/env python3
"""
Simplified test script for the enhanced API key permission validation logic.
This script tests the core logic without requiring AWS Lambda dependencies.
"""

from typing import Dict, Optional


def create_permission_mapping() -> Dict[str, str]:
    """
    Create a mapping between HTTP methods/resource paths and required permissions.

    Returns:
        Dictionary mapping resource patterns to required permissions
    """
    return {
        # Assets endpoints
        "get /api/assets": "assets:read",
        "post /api/assets/upload": "assets:create",
        "delete /api/assets/{id}": "assets:delete",
        "put /api/assets/{id}": "assets:update",
        "get /api/assets/{id}": "assets:read",
        "post /api/assets/{id}/rename": "assets:update",
        "get /api/assets/{id}/transcript": "assets:read",
        "get /api/assets/{id}/related_versions": "assets:read",
        "post /api/assets/generate_presigned_url": "assets:create",
        # Download endpoints
        "get /api/download/bulk": "assets:download",
        "post /api/download/bulk": "assets:download",
        "get /api/download/bulk/{jobId}": "assets:download",
        "put /api/download/bulk/{jobId}/downloaded": "assets:download",
        "delete /api/download/bulk/{jobId}": "assets:download",
        "get /api/download/bulk/user": "assets:download",
        # Settings endpoints
        "get /api/settings/api_keys": "settings:read",  #  pragma: allowlist secret
        "post /api/settings/api_keys": "settings:create",  #  pragma: allowlist secret
        "put /api/settings/api_keys/{id}": "settings:update",
        "delete /api/settings/api_keys/{id}": "settings:delete",
        # Permissions endpoints
        "get /api/permissions": "permissions:read",
        "post /api/permissions": "permissions:create",
        "put /api/permissions/{id}": "permissions:update",
        "delete /api/permissions/{id}": "permissions:delete",
    }


def normalize_resource_path(
    resource_path: str, path_parameters: Dict[str, str] = None
) -> str:
    """
    Normalize a resource path by replacing path parameters with placeholders.

    Args:
        resource_path: The original resource path (e.g., "/api/assets/123")
        path_parameters: Dictionary of path parameters (e.g., {"id": "123"})

    Returns:
        Normalized path with placeholders (e.g., "/api/assets/{id}")
    """
    if not path_parameters:
        return resource_path

    normalized_path = resource_path

    # Replace path parameter values with placeholders
    for param_name, param_value in path_parameters.items():
        # Replace the actual value with the parameter placeholder
        normalized_path = normalized_path.replace(
            f"/{param_value}", f"/{{{param_name}}}"
        )

    return normalized_path


def _paths_match(path1: str, path2: str) -> bool:
    """
    Check if two paths match, considering parameter placeholders.

    Args:
        path1: First path to compare
        path2: Second path to compare

    Returns:
        True if paths match, False otherwise
    """
    # Split paths into segments
    segments1 = [s for s in path1.split("/") if s]
    segments2 = [s for s in path2.split("/") if s]

    # Must have same number of segments
    if len(segments1) != len(segments2):
        return False

    # Compare each segment
    for seg1, seg2 in zip(segments1, segments2):
        # If either segment is a parameter placeholder, it matches
        if seg1.startswith("{") and seg1.endswith("}"):
            continue
        if seg2.startswith("{") and seg2.endswith("}"):
            continue
        # Otherwise, segments must match exactly
        if seg1 != seg2:
            return False

    return True


def get_required_permission(
    http_method: str, resource_path: str, path_parameters: Dict[str, str] = None
) -> Optional[str]:
    """
    Get the required permission for a given HTTP method and resource path.

    Args:
        http_method: HTTP method (e.g., "get", "post")
        resource_path: Resource path (e.g., "/api/assets/123")
        path_parameters: Dictionary of path parameters

    Returns:
        Required permission string or None if no specific permission is required
    """
    permission_mapping = create_permission_mapping()

    # Normalize the resource path
    normalized_path = normalize_resource_path(resource_path, path_parameters)

    # Create the action key
    action_key = f"{http_method.lower()} {normalized_path}"

    # Try exact match first
    required_permission = permission_mapping.get(action_key)

    if required_permission:
        print(f"Found exact permission match: {action_key} -> {required_permission}")
        return required_permission

    # Try pattern matching for common cases
    # Handle cases where the path might have different parameter names
    for pattern, permission in permission_mapping.items():
        if pattern.startswith(f"{http_method.lower()} "):
            pattern_path = pattern[len(f"{http_method.lower()} ") :]
            if _paths_match(normalized_path, pattern_path):
                print(f"Found pattern permission match: {pattern} -> {permission}")
                return permission

    print(f"No specific permission found for: {action_key}")
    return None


def validate_api_key_permissions(
    api_key_item: Dict[str, any], required_permission: str
) -> bool:
    """
    Validate that an API key has the required permission for the requested action.

    Args:
        api_key_item: API key item from DynamoDB
        required_permission: The permission required for this action

    Returns:
        True if API key has the required permission, False otherwise
    """
    # Get permissions from API key
    permissions = api_key_item.get("permissions", {})

    if not permissions:
        print(f"API key {api_key_item['id']} has no permissions defined")
        return False

    # Check if the required permission exists and is enabled
    permission_granted = permissions.get(required_permission, False)

    if permission_granted:
        print(
            f"API key {api_key_item['id']} has required permission: {required_permission}"
        )
    else:
        print(
            f"API key {api_key_item['id']} lacks required permission: {required_permission}. "
            f"Available permissions: {list(permissions.keys())}"
        )

    return permission_granted


def test_permission_mapping():
    """Test that the permission mapping is created correctly."""
    print("Testing permission mapping creation...")

    mapping = create_permission_mapping()

    # Test some key mappings
    assert mapping["get /api/assets"] == "assets:read"
    assert mapping["post /api/assets/upload"] == "assets:create"
    assert mapping["delete /api/assets/{id}"] == "assets:delete"
    assert (
        mapping["get /api/settings/api_keys"]
        == "settings:read"  #  pragma: allowlist secret
    )

    print(f"✅ Permission mapping created with {len(mapping)} entries")


def test_normalize_resource_path():
    """Test resource path normalization."""
    print("\nTesting resource path normalization...")

    # Test with no parameters
    result = normalize_resource_path("/api/assets", None)
    assert result == "/api/assets"

    # Test with parameters
    result = normalize_resource_path("/api/assets/123", {"id": "123"})
    assert result == "/api/assets/{id}"

    # Test with multiple parameters
    result = normalize_resource_path(
        "/api/assets/123/versions/456", {"id": "123", "versionId": "456"}
    )
    assert result == "/api/assets/{id}/versions/{versionId}"

    print("✅ Resource path normalization working correctly")


def test_paths_match():
    """Test path matching logic."""
    print("\nTesting path matching...")

    # Test exact matches
    assert _paths_match("/api/assets", "/api/assets") == True
    assert _paths_match("/api/assets/123", "/api/assets/456") == False

    # Test parameter matching
    assert _paths_match("/api/assets/{id}", "/api/assets/123") == True
    assert _paths_match("/api/assets/123", "/api/assets/{id}") == True
    assert _paths_match("/api/assets/{id}", "/api/assets/{assetId}") == True

    # Test different lengths
    assert _paths_match("/api/assets", "/api/assets/123") == False
    assert _paths_match("/api/assets/{id}/versions", "/api/assets/{id}") == False

    print("✅ Path matching working correctly")


def test_get_required_permission():
    """Test getting required permissions for actions."""
    print("\nTesting required permission lookup...")

    # Test exact matches
    result = get_required_permission("get", "/api/assets", None)
    assert result == "assets:read"

    # Test with path parameters
    result = get_required_permission("delete", "/api/assets/123", {"id": "123"})
    assert result == "assets:delete"

    # Test pattern matching
    result = get_required_permission("get", "/api/assets/456", {"id": "456"})
    assert result == "assets:read"

    # Test non-existent permission
    result = get_required_permission("patch", "/api/nonexistent", None)
    assert result is None

    print("✅ Required permission lookup working correctly")


def test_validate_api_key_permissions():
    """Test API key permission validation."""
    print("\nTesting API key permission validation...")

    # Mock API key with permissions
    api_key_with_permissions = {
        "id": "test-key-1",
        "name": "Test Key",
        "permissions": {
            "assets:read": True,
            "assets:create": True,
            "assets:delete": False,
        },
    }

    # Mock API key without permissions
    api_key_no_permissions = {
        "id": "test-key-2",
        "name": "Test Key No Perms",
        "permissions": {},
    }

    # Test with valid permission
    result = validate_api_key_permissions(api_key_with_permissions, "assets:read")
    assert result == True

    # Test with denied permission
    result = validate_api_key_permissions(api_key_with_permissions, "assets:delete")
    assert result == False

    # Test with missing permission
    result = validate_api_key_permissions(api_key_with_permissions, "settings:read")
    assert result == False

    # Test with no permissions
    result = validate_api_key_permissions(api_key_no_permissions, "assets:read")
    assert result == False

    print("✅ API key permission validation working correctly")


def test_integration_scenarios():
    """Test complete integration scenarios."""
    print("\nTesting integration scenarios...")

    # Scenario 1: GET /api/assets/123 with assets:read permission
    print("\n--- Scenario 1: GET /api/assets/123 with assets:read permission ---")
    api_key = {"id": "integration-test-1", "permissions": {"assets:read": True}}

    required_perm = get_required_permission("get", "/api/assets/123", {"id": "123"})
    assert required_perm == "assets:read"

    has_permission = validate_api_key_permissions(api_key, required_perm)
    assert has_permission == True

    # Scenario 2: DELETE /api/assets/123 without assets:delete permission
    print(
        "\n--- Scenario 2: DELETE /api/assets/123 without assets:delete permission ---"
    )
    required_perm = get_required_permission("delete", "/api/assets/123", {"id": "123"})
    assert required_perm == "assets:delete"

    has_permission = validate_api_key_permissions(api_key, required_perm)
    assert has_permission == False

    # Scenario 3: POST /api/settings/api_keys with settings:create permission
    print(
        "\n--- Scenario 3: POST /api/settings/api_keys with settings:create permission ---"
    )
    api_key_admin = {
        "id": "admin-key",
        "permissions": {"settings:create": True, "settings:read": True},
    }

    required_perm = get_required_permission("post", "/api/settings/api_keys", None)
    assert required_perm == "settings:create"

    has_permission = validate_api_key_permissions(api_key_admin, required_perm)
    assert has_permission == True

    print("✅ Integration scenarios working correctly")


def main():
    """Run all tests."""
    print("🧪 Starting API Key Permission Validation Tests")
    print("=" * 60)

    try:
        test_permission_mapping()
        test_normalize_resource_path()
        test_paths_match()
        test_get_required_permission()
        test_validate_api_key_permissions()
        test_integration_scenarios()

        print("\n" + "=" * 60)
        print(
            "🎉 All tests passed! Enhanced permission validation is working correctly."
        )

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
