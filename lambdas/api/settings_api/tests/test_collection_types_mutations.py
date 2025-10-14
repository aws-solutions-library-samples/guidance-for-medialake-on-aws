"""Tests for Collection Types PUT, DELETE, and MIGRATE endpoints."""

import json

from .test_helpers import seed_collection, seed_collection_type


class TestUpdateCollectionType:
    """Tests for PUT /settings/collection-types/{id} endpoint."""

    def test_update_collection_type_success(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test successful update of collection type."""
        from index import lambda_handler

        # Seed a type
        seed_collection_type(dynamodb_table, sample_collection_type)

        admin_event["httpMethod"] = "PUT"
        admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}"
        )
        admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}
        admin_event["body"] = json.dumps(
            {
                "name": "Updated Name",
                "color": "#388e3c",
                "icon": "Campaign",
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["data"]["name"] == "Updated Name"
        assert body["data"]["color"] == "#388e3c"
        assert body["data"]["icon"] == "Campaign"

    def test_update_collection_type_not_found(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test updating non-existent collection type."""
        from index import lambda_handler

        admin_event["httpMethod"] = "PUT"
        admin_event["path"] = "/settings/collection-types/colltype_nonexistent"
        admin_event["pathParameters"] = {"type_id": "colltype_nonexistent"}
        admin_event["body"] = json.dumps(
            {
                "name": "Updated Name",
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["success"] is False

    def test_update_collection_type_system_type_forbidden(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test that system types cannot be updated."""
        from index import lambda_handler

        # Seed a system type
        system_type = {
            "id": "colltype_system",
            "name": "System Type",
            "color": "#1976d2",
            "icon": "Folder",
            "isActive": True,
            "isSystem": True,
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
        seed_collection_type(dynamodb_table, system_type)

        admin_event["httpMethod"] = "PUT"
        admin_event["path"] = "/settings/collection-types/colltype_system"
        admin_event["pathParameters"] = {"type_id": "colltype_system"}
        admin_event["body"] = json.dumps(
            {
                "name": "Updated Name",
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "system" in body["error"]["message"].lower()

    def test_update_collection_type_validation_error(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test validation errors in update."""
        from index import lambda_handler

        seed_collection_type(dynamodb_table, sample_collection_type)

        admin_event["httpMethod"] = "PUT"
        admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}"
        )
        admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}
        admin_event["body"] = json.dumps(
            {
                "color": "invalid-color",
            }
        )

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["success"] is False

    def test_update_collection_type_non_admin_forbidden(
        self, dynamodb_table, non_admin_event, lambda_context, sample_collection_type
    ):
        """Test that non-admin users cannot update types."""
        from index import lambda_handler

        seed_collection_type(dynamodb_table, sample_collection_type)

        non_admin_event["httpMethod"] = "PUT"
        non_admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}"
        )
        non_admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}
        non_admin_event["body"] = json.dumps(
            {
                "name": "Updated Name",
            }
        )

        response = lambda_handler(non_admin_event, lambda_context)

        assert response["statusCode"] == 403


class TestDeleteCollectionType:
    """Tests for DELETE /settings/collection-types/{id} endpoint."""

    def test_delete_collection_type_success(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test successful deletion of unused collection type."""
        from index import lambda_handler

        seed_collection_type(dynamodb_table, sample_collection_type)

        admin_event["httpMethod"] = "DELETE"
        admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}"
        )
        admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 204
        assert response["body"] == ""

        # Verify it's deleted from DynamoDB
        db_response = dynamodb_table.get_item(
            Key={"PK": "SYSTEM", "SK": f"COLLTYPE#{sample_collection_type['id']}"}
        )
        assert "Item" not in db_response

    def test_delete_collection_type_in_use(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test that types in use cannot be deleted without migration."""
        from index import lambda_handler

        # Seed a type and a collection using it
        seed_collection_type(dynamodb_table, sample_collection_type)
        seed_collection(dynamodb_table, "coll_001", sample_collection_type["id"])

        admin_event["httpMethod"] = "DELETE"
        admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}"
        )
        admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 409
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error"]["code"] == "TYPE_IN_USE"
        assert len(body["error"]["details"]) > 0
        assert "usageCount" in body["error"]["details"][0]["field"]

    def test_delete_collection_type_system_type_forbidden(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test that system types cannot be deleted."""
        from index import lambda_handler

        # Seed a system type
        system_type = {
            "id": "colltype_system",
            "name": "System Type",
            "color": "#1976d2",
            "icon": "Folder",
            "isActive": True,
            "isSystem": True,
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
        seed_collection_type(dynamodb_table, system_type)

        admin_event["httpMethod"] = "DELETE"
        admin_event["path"] = "/settings/collection-types/colltype_system"
        admin_event["pathParameters"] = {"type_id": "colltype_system"}

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "system" in body["error"]["message"].lower()

    def test_delete_collection_type_not_found(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test deleting non-existent collection type."""
        from index import lambda_handler

        admin_event["httpMethod"] = "DELETE"
        admin_event["path"] = "/settings/collection-types/colltype_nonexistent"
        admin_event["pathParameters"] = {"type_id": "colltype_nonexistent"}

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 404

    def test_delete_collection_type_non_admin_forbidden(
        self, dynamodb_table, non_admin_event, lambda_context, sample_collection_type
    ):
        """Test that non-admin users cannot delete types."""
        from index import lambda_handler

        seed_collection_type(dynamodb_table, sample_collection_type)

        non_admin_event["httpMethod"] = "DELETE"
        non_admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}"
        )
        non_admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}

        response = lambda_handler(non_admin_event, lambda_context)

        assert response["statusCode"] == 403


class TestMigrateCollectionType:
    """Tests for POST /settings/collection-types/{id}/migrate endpoint."""

    def test_migrate_collection_type_success(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test successful migration of collections between types."""
        from index import lambda_handler

        # Seed source and target types
        source_type = sample_collection_type
        target_type = {
            "id": "colltype_target",
            "name": "Target Type",
            "color": "#388e3c",
            "icon": "Campaign",
            "isActive": True,
            "isSystem": False,
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
        seed_collection_type(dynamodb_table, source_type)
        seed_collection_type(dynamodb_table, target_type)

        # Seed collections using source type
        seed_collection(dynamodb_table, "coll_001", source_type["id"])
        seed_collection(dynamodb_table, "coll_002", source_type["id"])
        seed_collection(dynamodb_table, "coll_003", source_type["id"])

        admin_event["httpMethod"] = "POST"
        admin_event["path"] = f"/settings/collection-types/{source_type['id']}/migrate"
        admin_event["pathParameters"] = {"type_id": source_type["id"]}
        admin_event["body"] = json.dumps({"targetTypeId": target_type["id"]})

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["data"]["migratedCount"] == 3

        # Verify collections now use target type
        coll_response = dynamodb_table.get_item(
            Key={"PK": "COLLECTION#coll_001", "SK": "METADATA#"}
        )
        assert coll_response["Item"]["collectionTypeId"] == target_type["id"]

    def test_migrate_collection_type_source_not_found(
        self, dynamodb_table, admin_event, lambda_context
    ):
        """Test migration with non-existent source type."""
        from index import lambda_handler

        # Seed target type
        target_type = {
            "id": "colltype_target",
            "name": "Target Type",
            "color": "#388e3c",
            "icon": "Campaign",
            "isActive": True,
            "isSystem": False,
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
        seed_collection_type(dynamodb_table, target_type)

        admin_event["httpMethod"] = "POST"
        admin_event["path"] = "/settings/collection-types/colltype_nonexistent/migrate"
        admin_event["pathParameters"] = {"type_id": "colltype_nonexistent"}
        admin_event["body"] = json.dumps({"targetTypeId": target_type["id"]})

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 404

    def test_migrate_collection_type_target_not_found(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test migration with non-existent target type."""
        from index import lambda_handler

        seed_collection_type(dynamodb_table, sample_collection_type)

        admin_event["httpMethod"] = "POST"
        admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}/migrate"
        )
        admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}
        admin_event["body"] = json.dumps({"targetTypeId": "colltype_nonexistent"})

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 404

    def test_migrate_collection_type_target_inactive(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test migration to inactive target type."""
        from index import lambda_handler

        # Seed source and inactive target types
        source_type = sample_collection_type
        target_type = {
            "id": "colltype_inactive",
            "name": "Inactive Type",
            "color": "#d32f2f",
            "icon": "Archive",
            "isActive": False,
            "isSystem": False,
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
        seed_collection_type(dynamodb_table, source_type)
        seed_collection_type(dynamodb_table, target_type)

        admin_event["httpMethod"] = "POST"
        admin_event["path"] = f"/settings/collection-types/{source_type['id']}/migrate"
        admin_event["pathParameters"] = {"type_id": source_type["id"]}
        admin_event["body"] = json.dumps({"targetTypeId": target_type["id"]})

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "not active" in body["error"]["message"].lower()

    def test_migrate_collection_type_missing_target(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test migration without providing target type ID."""
        from index import lambda_handler

        seed_collection_type(dynamodb_table, sample_collection_type)

        admin_event["httpMethod"] = "POST"
        admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}/migrate"
        )
        admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}
        admin_event["body"] = json.dumps({})

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 400

    def test_migrate_collection_type_non_admin_forbidden(
        self, dynamodb_table, non_admin_event, lambda_context, sample_collection_type
    ):
        """Test that non-admin users cannot migrate types."""
        from index import lambda_handler

        seed_collection_type(dynamodb_table, sample_collection_type)

        non_admin_event["httpMethod"] = "POST"
        non_admin_event["path"] = (
            f"/settings/collection-types/{sample_collection_type['id']}/migrate"
        )
        non_admin_event["pathParameters"] = {"type_id": sample_collection_type["id"]}
        non_admin_event["body"] = json.dumps({"targetTypeId": "colltype_target"})

        response = lambda_handler(non_admin_event, lambda_context)

        assert response["statusCode"] == 403

    def test_migrate_collection_type_zero_collections(
        self, dynamodb_table, admin_event, lambda_context, sample_collection_type
    ):
        """Test migration when no collections use the source type."""
        from index import lambda_handler

        # Seed source and target types
        source_type = sample_collection_type
        target_type = {
            "id": "colltype_target",
            "name": "Target Type",
            "color": "#388e3c",
            "icon": "Campaign",
            "isActive": True,
            "isSystem": False,
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
        seed_collection_type(dynamodb_table, source_type)
        seed_collection_type(dynamodb_table, target_type)

        admin_event["httpMethod"] = "POST"
        admin_event["path"] = f"/settings/collection-types/{source_type['id']}/migrate"
        admin_event["pathParameters"] = {"type_id": source_type["id"]}
        admin_event["body"] = json.dumps({"targetTypeId": target_type["id"]})

        response = lambda_handler(admin_event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"]["migratedCount"] == 0
