"""
Unit tests for get_my_assets Lambda function
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

# Set env vars before import
os.environ.setdefault("MEDIALAKE_CONNECTOR_TABLE", "test-table")
os.environ.setdefault("PERSONAL_ASSETS_BUCKET_SSM_PARAM", "/test/param")
os.environ.setdefault("REGION", "us-east-1")

# Create pass-through decorator mocks so lambda_handler stays callable
_mock_logger = MagicMock()
_mock_logger.inject_lambda_context = lambda: (lambda f: f)
_mock_logger.inject_lambda_context = MagicMock(side_effect=lambda f: f)
_mock_logger.exception = MagicMock()
_mock_logger.error = MagicMock()

_mock_tracer = MagicMock()
_mock_tracer.capture_lambda_handler = MagicMock(side_effect=lambda f: f)

_mock_powertools = MagicMock()
_mock_powertools.Logger.return_value = _mock_logger
_mock_powertools.Tracer.return_value = _mock_tracer

sys.modules["aws_lambda_powertools"] = _mock_powertools
sys.modules["aws_lambda_powertools.utilities"] = MagicMock()
sys.modules["aws_lambda_powertools.utilities.typing"] = MagicMock()

# Mock boto3
_mock_boto3 = MagicMock()
sys.modules["boto3"] = _mock_boto3
sys.modules["boto3.dynamodb"] = MagicMock()
sys.modules["boto3.dynamodb.conditions"] = MagicMock()


# Mock botocore with a real exception class
class _ClientError(Exception):
    def __init__(self, error_response, operation_name=""):
        self.response = error_response
        super().__init__(str(error_response))


_mock_botocore = MagicMock()
_mock_botocore_exc = MagicMock()
_mock_botocore_exc.ClientError = _ClientError
sys.modules["botocore"] = _mock_botocore
sys.modules["botocore.exceptions"] = _mock_botocore_exc

import index
import pytest

# Patch ClientError in the index module so except clauses work
index.ClientError = _ClientError

from index import build_connector_item, format_connector, get_user_id_from_event

# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


class TestGetUserIdFromEvent:
    def test_valid_sub_present(self):
        event = {"requestContext": {"authorizer": {"sub": "user-123"}}}
        assert get_user_id_from_event(event) == "user-123"

    def test_missing_sub_raises_value_error(self):
        event = {"requestContext": {"authorizer": {}}}
        with pytest.raises(ValueError):
            get_user_id_from_event(event)

    def test_missing_authorizer_raises_value_error(self):
        event = {"requestContext": {}}
        with pytest.raises(ValueError):
            get_user_id_from_event(event)

    def test_empty_sub_raises_value_error(self):
        event = {"requestContext": {"authorizer": {"sub": ""}}}
        with pytest.raises(ValueError):
            get_user_id_from_event(event)

    def test_claims_dict_sub(self):
        event = {"requestContext": {"authorizer": {"claims": {"sub": "user-456"}}}}
        assert get_user_id_from_event(event) == "user-456"

    def test_claims_json_string_sub(self):
        event = {
            "requestContext": {
                "authorizer": {"claims": json.dumps({"sub": "user-789"})}
            }
        }
        assert get_user_id_from_event(event) == "user-789"

    def test_claims_invalid_json_string_raises(self):
        event = {"requestContext": {"authorizer": {"claims": "not-json"}}}
        with pytest.raises(ValueError):
            get_user_id_from_event(event)

    def test_direct_sub_takes_precedence_over_claims(self):
        event = {
            "requestContext": {
                "authorizer": {"sub": "direct-user", "claims": {"sub": "claims-user"}}
            }
        }
        assert get_user_id_from_event(event) == "direct-user"


class TestBuildConnectorItem:
    def test_correct_id_format(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        assert item["id"] == "my-assets-user-123"

    def test_object_prefix(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        assert item["objectPrefix"] == "personal/user-123/"

    def test_type_is_my_assets(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        assert item["type"] == "my-assets"

    def test_is_internal_false(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        assert item["isInternal"] is False

    def test_storage_identifier_matches_bucket(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        assert item["storageIdentifier"] == "my-bucket"

    def test_region_matches(self):
        item = build_connector_item("user-123", "my-bucket", "eu-west-1")
        assert item["region"] == "eu-west-1"

    def test_timestamps_present(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        assert item["createdAt"].endswith("Z")
        assert item["updatedAt"].endswith("Z")


class TestFormatConnector:
    def test_all_fields_present(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        result = format_connector(item)
        assert result["id"] == "my-assets-user-123"
        assert result["name"] == "My Assets"
        assert result["type"] == "my-assets"
        assert result["storageIdentifier"] == "my-bucket"
        assert result["region"] == "us-east-1"
        assert result["objectPrefix"] == "personal/user-123/"
        assert "settings" in result
        assert "configuration" in result

    def test_missing_fields_default_to_empty_string(self):
        result = format_connector({})
        assert result["id"] == ""
        assert result["name"] == ""
        assert result["type"] == ""
        assert result["storageIdentifier"] == ""
        assert result["sqsArn"] == ""

    def test_settings_path_equals_object_prefix(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        result = format_connector(item)
        assert result["settings"]["path"] == item["objectPrefix"]

    def test_settings_bucket_equals_storage_identifier(self):
        item = build_connector_item("user-123", "my-bucket", "us-east-1")
        result = format_connector(item)
        assert result["settings"]["bucket"] == "my-bucket"


# ---------------------------------------------------------------------------
# Handler-level tests
# ---------------------------------------------------------------------------

EXISTING_ITEM = {
    "id": "my-assets-user-123",
    "type": "my-assets",
    "name": "My Assets",
    "status": "active",
    "storageIdentifier": "test-bucket",
    "objectPrefix": "personal/user-123/",
    "region": "us-east-1",
    "userId": "user-123",
    "createdAt": "2026-01-01T00:00:00Z",
    "updatedAt": "2026-01-01T00:00:00Z",
    "isInternal": False,
}


def _event(sub="user-123"):
    return {"requestContext": {"authorizer": {"sub": sub}}}


def _ctx():
    ctx = MagicMock()
    ctx.aws_request_id = "test-req-id"
    return ctx


class TestLambdaHandler:
    """Handler-level tests that mock DynamoDB and SSM."""

    @patch.object(index, "MEDIALAKE_CONNECTOR_TABLE", "test-table")
    @patch.object(index, "_cached_bucket_name", None)
    def test_existing_connector_returns_200_without_write(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": EXISTING_ITEM}
        index.dynamodb.Table.return_value = table

        result = index.lambda_handler(_event(), _ctx())

        assert result["status"] == "200"
        assert result["data"]["connector"]["id"] == "my-assets-user-123"
        table.put_item.assert_not_called()

    @patch.object(index, "MEDIALAKE_CONNECTOR_TABLE", "test-table")
    @patch.object(index, "_cached_bucket_name", None)
    @patch.object(index, "REGION", "us-east-1")
    def test_missing_connector_creates_then_returns_200(self):
        table = MagicMock()
        table.get_item.return_value = {}
        table.put_item.return_value = {}
        index.dynamodb.Table.return_value = table
        index.ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "test-bucket"}
        }

        result = index.lambda_handler(_event(), _ctx())

        assert result["status"] == "200"
        assert result["data"]["connector"]["id"] == "my-assets-user-123"
        table.put_item.assert_called_once()

    @patch.object(index, "MEDIALAKE_CONNECTOR_TABLE", "test-table")
    @patch.object(index, "_cached_bucket_name", None)
    @patch.object(index, "REGION", "us-east-1")
    def test_conditional_conflict_returns_existing_item(self):
        table = MagicMock()
        table.get_item.side_effect = [{}, {"Item": EXISTING_ITEM}]
        table.put_item.side_effect = _ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}
        )
        index.dynamodb.Table.return_value = table
        index.ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "test-bucket"}
        }

        result = index.lambda_handler(_event(), _ctx())

        assert result["status"] == "200"
        assert result["data"]["connector"]["id"] == "my-assets-user-123"

    @patch.object(index, "MEDIALAKE_CONNECTOR_TABLE", "test-table")
    @patch.object(index, "_cached_bucket_name", None)
    @patch.object(index, "REGION", "us-east-1")
    def test_conditional_conflict_missing_item_returns_500(self):
        table = MagicMock()
        table.get_item.side_effect = [{}, {}]  # both empty
        table.put_item.side_effect = _ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}
        )
        index.dynamodb.Table.return_value = table
        index.ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "test-bucket"}
        }

        result = index.lambda_handler(_event(), _ctx())

        assert result["status"] == "500"

    def test_missing_user_id_returns_401(self):
        event = {"requestContext": {"authorizer": {}}}
        result = index.lambda_handler(event, _ctx())

        assert result["status"] == "401"
        assert result["message"] == "Unauthorized"

    @patch.object(index, "MEDIALAKE_CONNECTOR_TABLE", "test-table")
    @patch.object(index, "_cached_bucket_name", None)
    def test_unexpected_dependency_failure_returns_500(self):
        table = MagicMock()
        table.get_item.side_effect = Exception("DynamoDB unavailable")
        index.dynamodb.Table.return_value = table

        result = index.lambda_handler(_event(), _ctx())

        assert result["status"] == "500"
        assert result["message"] == "Internal server error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
