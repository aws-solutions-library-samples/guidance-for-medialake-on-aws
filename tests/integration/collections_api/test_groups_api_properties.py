"""
Property-based tests for Collection Groups API error handling.

Tests API layer error responses using Hypothesis for property-based testing.
Verifies consistent error handling across all endpoints.
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Property 14: Test API error response codes (403, 404, 400)


@pytest.mark.property
class TestGroupsAPIErrorProperties:
    """Property-based tests for API error handling."""

    @given(
        group_id=st.text(min_size=1, max_size=50),
        user_id=st.text(min_size=1, max_size=50),
        owner_id=st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=100)
    def test_property_14_unauthorized_access_returns_403(
        self, group_id, user_id, owner_id
    ):
        """
        Property 14: API returns 403 for unauthorized access.

        When a user tries to modify a group they don't own,
        the API should return 403 Forbidden.
        """
        # Ensure user is not the owner
        assume(user_id != owner_id)
        assume(group_id.strip() != "")
        assume(user_id.strip() != "")
        assume(owner_id.strip() != "")

        from lambdas.api.collections_api.handlers.groups_ID_put import lambda_handler

        # Mock the group metadata to show different owner
        mock_group = {
            "id": group_id,
            "name": "Test Group",
            "ownerId": owner_id,
            "isPublic": True,
            "collectionIds": [],
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        event = {
            "pathParameters": {"groupId": group_id},
            "body": json.dumps({"name": "Updated Name"}),
            "requestContext": {
                "authorizer": {"claims": {"sub": user_id, "cognito:username": user_id}}
            },
        }

        with patch(
            "lambdas.api.collections_api.handlers.groups_ID_put.get_collection_group_metadata"
        ) as mock_get:
            mock_get.return_value = mock_group

            response = lambda_handler(event, {})

            # Should return 403 Forbidden
            assert response["statusCode"] == 403
            body = json.loads(response["body"])
            assert "error" in body or "message" in body

    @given(group_id=st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_property_14_nonexistent_group_returns_404(self, group_id):
        """
        Property 14: API returns 404 for non-existent groups.

        When requesting a group that doesn't exist,
        the API should return 404 Not Found.
        """
        assume(group_id.strip() != "")

        from lambdas.api.collections_api.handlers.groups_ID_get import lambda_handler

        event = {
            "pathParameters": {"groupId": group_id},
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "user123", "cognito:username": "user123"}
                }
            },
        }

        with patch(
            "lambdas.api.collections_api.handlers.groups_ID_get.get_collection_group_metadata"
        ) as mock_get:
            mock_get.return_value = None

            response = lambda_handler(event, {})

            # Should return 404 Not Found
            assert response["statusCode"] == 404
            body = json.loads(response["body"])
            assert "error" in body or "message" in body

    @given(
        name=st.one_of(st.none(), st.just(""), st.text(max_size=0)),
    )
    @settings(max_examples=100)
    def test_property_14_invalid_input_returns_400(self, name):
        """
        Property 14: API returns 400 for invalid input.

        When providing invalid data (e.g., missing required fields),
        the API should return 400 Bad Request.
        """
        from lambdas.api.collections_api.handlers.groups_post import lambda_handler

        # Create request with invalid name
        request_data = {}
        if name is not None:
            request_data["name"] = name

        event = {
            "body": json.dumps(request_data),
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "user123", "cognito:username": "user123"}
                }
            },
        }

        response = lambda_handler(event, {})

        # Should return 400 Bad Request for validation error
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body or "message" in body

    @given(
        collection_ids=st.lists(
            st.text(min_size=1, max_size=50), min_size=1, max_size=10
        )
    )
    @settings(max_examples=100)
    def test_property_14_invalid_collection_ids_returns_400(self, collection_ids):
        """
        Property 14: API returns 400 for invalid collection IDs.

        When adding non-existent collections to a group,
        the API should return 400 Bad Request with details.
        """
        assume(all(cid.strip() != "" for cid in collection_ids))

        from lambdas.api.collections_api.handlers.groups_ID_collections_post import (
            lambda_handler,
        )

        group_id = "test-group-123"
        user_id = "user123"

        mock_group = {
            "id": group_id,
            "name": "Test Group",
            "ownerId": user_id,
            "isPublic": True,
            "collectionIds": [],
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        event = {
            "pathParameters": {"groupId": group_id},
            "body": json.dumps({"collectionIds": collection_ids}),
            "requestContext": {
                "authorizer": {"claims": {"sub": user_id, "cognito:username": user_id}}
            },
        }

        with patch(
            "lambdas.api.collections_api.handlers.groups_ID_collections_post.get_collection_group_metadata"
        ) as mock_get, patch(
            "lambdas.api.collections_api.handlers.groups_ID_collections_post.validate_collection_ids"
        ) as mock_validate:
            mock_get.return_value = mock_group
            # Simulate all collections are invalid
            mock_validate.return_value = (False, collection_ids)

            response = lambda_handler(event, {})

            # Should return 400 Bad Request
            assert response["statusCode"] == 400
            body = json.loads(response["body"])
            assert "error" in body or "message" in body
            # Should mention invalid collection IDs
            assert (
                "collection" in body.get("message", "").lower()
                or "collection" in body.get("error", "").lower()
            )

    @given(
        error_type=st.sampled_from(
            ["DynamoDB", "Validation", "Authorization", "NotFound"]
        )
    )
    @settings(max_examples=100)
    def test_property_14_error_response_format_consistency(self, error_type):
        """
        Property 14: All error responses have consistent format.

        All API errors should return a consistent JSON structure
        with appropriate status codes and error messages.
        """
        from lambdas.api.collections_api.handlers.groups_get import lambda_handler

        event = {
            "queryStringParameters": {},
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "user123", "cognito:username": "user123"}
                }
            },
        }

        # Simulate different error types
        with patch(
            "lambdas.api.collections_api.handlers.groups_get.list_collection_groups"
        ) as mock_list:
            if error_type == "DynamoDB":
                mock_list.side_effect = Exception("DynamoDB error")
            elif error_type == "Validation":
                mock_list.side_effect = ValueError("Invalid parameter")
            elif error_type == "Authorization":
                mock_list.side_effect = PermissionError("Not authorized")
            else:
                mock_list.return_value = {"groups": [], "nextToken": None}

            response = lambda_handler(event, {})

            # All responses should have statusCode
            assert "statusCode" in response
            assert isinstance(response["statusCode"], int)

            # All responses should have body
            assert "body" in response
            body = json.loads(response["body"])

            # Error responses should have error or message field
            if response["statusCode"] >= 400:
                assert "error" in body or "message" in body

            # Success responses should have expected structure
            if response["statusCode"] == 200:
                assert "groups" in body
