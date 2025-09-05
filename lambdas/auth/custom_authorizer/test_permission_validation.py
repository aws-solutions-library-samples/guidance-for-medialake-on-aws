#!/usr/bin/env python3
"""
Test script for the enhanced API key permission validation logic.
This script tests the new permission mapping and validation functions.
"""

import os
import sys

# Add the current directory to the path so we can import the authorizer
sys.path.insert(0, os.path.dirname(__file__))

# Import the functions we want to test
from index import (
    _paths_match,
    create_permission_mapping,
    get_required_permission,
    normalize_resource_path,
    validate_api_key_permissions,
)


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
        == "settings:read"  # pragma: allowlist secret
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
    result = validate_api_key_permissions(
        api_key_with_permissions, "assets:read", "test-correlation-id"
    )
    assert result == True

    # Test with denied permission
    result = validate_api_key_permissions(
        api_key_with_permissions, "assets:delete", "test-correlation-id"
    )
    assert result == False

    # Test with missing permission
    result = validate_api_key_permissions(
        api_key_with_permissions, "settings:read", "test-correlation-id"
    )
    assert result == False

    # Test with no permissions
    result = validate_api_key_permissions(
        api_key_no_permissions, "assets:read", "test-correlation-id"
    )
    assert result == False

    print("✅ API key permission validation working correctly")


def test_integration_scenarios():
    """Test complete integration scenarios."""
    print("\nTesting integration scenarios...")

    # Scenario 1: GET /api/assets/123 with assets:read permission
    api_key = {"id": "integration-test-1", "permissions": {"assets:read": True}}

    required_perm = get_required_permission("get", "/api/assets/123", {"id": "123"})
    assert required_perm == "assets:read"

    has_permission = validate_api_key_permissions(api_key, required_perm, "test-id")
    assert has_permission == True

    # Scenario 2: DELETE /api/assets/123 without assets:delete permission
    required_perm = get_required_permission("delete", "/api/assets/123", {"id": "123"})
    assert required_perm == "assets:delete"

    has_permission = validate_api_key_permissions(api_key, required_perm, "test-id")
    assert has_permission == False

    # Scenario 3: POST /api/settings/api_keys with settings:create permission
    api_key_admin = {
        "id": "admin-key",
        "permissions": {"settings:create": True, "settings:read": True},
    }

    required_perm = get_required_permission("post", "/api/settings/api_keys", None)
    assert required_perm == "settings:create"

    has_permission = validate_api_key_permissions(
        api_key_admin, required_perm, "test-id"
    )
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
        sys.exit(1)


if __name__ == "__main__":
    main()
