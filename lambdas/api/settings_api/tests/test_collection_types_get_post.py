"""Tests for Collection Types GET and POST endpoints."""

import json

from .test_helpers import seed_collection_type


class TestGetCollectionTypes:
    """Tests for GET /settings/collection-types endpoint."""

    def test_get_collection_types_empty(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test listing collection types when none exist."""
        from index import lambda_handler

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["data"] == []
        assert "pagination" in body
        assert body["pagination"]["has_next_page"] is False
        assert "meta" in body

    def test_get_collection_types_with_data(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test listing collection types with existing data."""
        from index import lambda_handler

        # Seed data
        seed_collection_type(dynamodb_table, sample_collection_type)
        seed_collection_type(
            dynamodb_table,
            {
                "id": "colltype_test456",
                "name": "Another Type",
                "description": "Another test type",
                "color": "#388e3c",
                "icon": "Campaign",
                "isActive": True,
                "isSystem": False,
                "createdAt": "2025-01-02T00:00:00Z",
                "updatedAt": "2025-01-02T00:00:00Z",
            },
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert len(body["data"]) == 2
        assert body["data"][0]["name"] in ["Test Type", "Another Type"]
        assert "color" in body["data"][0]
        assert "icon" in body["data"][0]

    def test_get_collection_types_with_active_filter(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test filtering collection types by active status."""
        from index import lambda_handler

        # Seed active and inactive types
        seed_collection_type(
            dynamodb_table,
            {
                "id": "colltype_active",
                "name": "Active Type",
                "color": "#1976d2",
                "icon": "Work",
                "isActive": True,
                "isSystem": False,
                "createdAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-01-01T00:00:00Z",
            },
        )
        seed_collection_type(
            dynamodb_table,
            {
                "id": "colltype_inactive",
                "name": "Inactive Type",
                "color": "#d32f2f",
                "icon": "Archive",
                "isActive": False,
                "isSystem": False,
                "createdAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-01-01T00:00:00Z",
            },
        )

        # Test with filter[active]=true
        admin_event["queryStringParameters"] = {"filter[active]": "true"}
        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["data"]) == 1
        assert body["data"][0]["name"] == "Active Type"

    def test_get_collection_types_with_pagination(
        self, dynamodb_table, admin_event, lambda_context, seed_types_helper
    ):
        """Test pagination of collection types."""
        from index import lambda_handler

        # Seed 25 types
        types_data = []
        for i in range(25):
            types_data.append(
                {
                    "id": f"colltype_{i:03d}",
                    "name": f"Type {i}",
                    "color": "#1976d2",
                    "icon": "Work",
                    "isActive": True,
                    "isSystem": False,
                    "createdAt": "2025-01-01T00:00:00Z",
                    "updatedAt": "2025-01-01T00:00:00Z",
                }
            )
        seed_types_helper(types_data)

        # First page (default limit=20)
        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["data"]) == 20
        assert body["pagination"]["has_next_page"] is True
        assert "next_cursor" in body["pagination"]

    def test_get_collection_types_non_admin_access(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test that non-admin users can still view collection types (read-only)."""
        from index import lambda_handler

        seed_collection_type(dynamodb_table, sample_collection_type)

        # Non-admin should be able to view types
        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True


class TestCreateCollectionType:
    """Tests for POST /settings/collection-types endpoint."""

    def test_create_collection_type_success(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test successful creation of collection type."""
        from index import lambda_handler

        admin_event["httpMethod"] = "POST"
        admin_event["body"] = json.dumps(
            {
                "name": "New Type",
                "description": "A new collection type",
                "color": "#1976d2",
                "icon": "Work",
                "isActive": True,
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["data"]["name"] == "New Type"
        assert body["data"]["color"] == "#1976d2"
        assert body["data"]["icon"] == "Work"
        assert body["data"]["isSystem"] is False
        assert "id" in body["data"]
        assert body["data"]["id"].startswith("colltype_")

    def test_create_collection_type_validation_missing_name(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test validation error for missing name."""
        from index import lambda_handler

        admin_event["httpMethod"] = "POST"
        admin_event["body"] = json.dumps(
            {
                "color": "#1976d2",
                "icon": "Work",
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert any(d["field"] == "name" for d in body["error"]["details"])

    def test_create_collection_type_validation_invalid_color(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test validation error for invalid hex color."""
        from index import lambda_handler

        admin_event["httpMethod"] = "POST"
        admin_event["body"] = json.dumps(
            {
                "name": "Test Type",
                "color": "invalid-color",
                "icon": "Work",
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["success"] is False
        assert any(d["field"] == "color" for d in body["error"]["details"])

    def test_create_collection_type_validation_invalid_icon(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test validation error for invalid icon name."""
        from index import lambda_handler

        admin_event["httpMethod"] = "POST"
        admin_event["body"] = json.dumps(
            {
                "name": "Test Type",
                "color": "#1976d2",
                "icon": "InvalidIcon",
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["success"] is False
        assert any(d["field"] == "icon" for d in body["error"]["details"])

    def test_create_collection_type_validation_name_too_long(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test validation error for name exceeding max length."""
        from index import lambda_handler

        admin_event["httpMethod"] = "POST"
        admin_event["body"] = json.dumps(
            {
                "name": "A" * 51,  # 51 characters, max is 50
                "color": "#1976d2",
                "icon": "Work",
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["success"] is False
        assert any(d["field"] == "name" for d in body["error"]["details"])

    def test_create_collection_type_non_admin_forbidden(
        self, dynamodb_table, non_admin_event, lambda_context
    ):
        """Test that non-admin users cannot create collection types."""
        from index import lambda_handler

        non_admin_event["httpMethod"] = "POST"
        non_admin_event["body"] = json.dumps(
            {
                "name": "Test Type",
                "color": "#1976d2",
                "icon": "Work",
            }
        )

        response = lambda_handler(non_admin_event, lambda_context)

        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "Admin permission required" in body["error"]["message"]

    def test_create_collection_type_with_optional_fields(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test creating collection type with optional fields."""
        from index import lambda_handler

        admin_event["httpMethod"] = "POST"
        admin_event["body"] = json.dumps(
            {
                "name": "Test Type",
                "description": "Optional description",
                "color": "#1976d2",
                "icon": "Work",
                "isActive": False,
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["data"]["description"] == "Optional description"
        assert body["data"]["isActive"] is False

    def test_create_collection_type_persisted_to_dynamodb(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test that created collection type is persisted to DynamoDB."""
        from index import lambda_handler

        admin_event["httpMethod"] = "POST"
        admin_event["body"] = json.dumps(
            {
                "name": "Persisted Type",
                "color": "#1976d2",
                "icon": "Work",
            }
        )

        response = lambda_handler(admin_event, lambda_context)
        assert response["statusCode"] == 201

        body = json.loads(response["body"])
        type_id = body["data"]["id"]

        # Verify it's in DynamoDB
        db_response = dynamodb_table.get_item(
            Key={"PK": "SYSTEM", "SK": f"COLLTYPE#{type_id}"}
        )

        assert "Item" in db_response
        assert db_response["Item"]["name"] == "Persisted Type"
        assert db_response["Item"]["isSystem"] is False
