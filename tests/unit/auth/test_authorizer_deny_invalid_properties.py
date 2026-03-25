"""
Property-based tests for Webhook Authorizer deny on invalid pipelines.

These tests verify that for any pipeline that does not exist, is not active,
or has deploymentStatus != "DEPLOYED", the authorizer returns a Deny policy
regardless of auth method.

**Feature: hmac-sha256-webhook-auth, Property 9: Authorizer deny for invalid pipelines**
**Validates: Requirement 2.4**
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# =============================================================================
# Mock boto3 and set up imports
# =============================================================================

mock_boto3 = MagicMock()
mock_dynamodb_resource = MagicMock()
mock_secretsmanager_client = MagicMock()
mock_boto3.resource.return_value = mock_dynamodb_resource
mock_boto3.client.return_value = mock_secretsmanager_client
sys.modules["boto3"] = mock_boto3

# Add the webhook_authorizer Lambda directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "lambdas"
        / "auth"
        / "webhook_authorizer"
    ),
)


# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for valid pipeline IDs (non-empty alphanumeric + dashes)
pipeline_id_st = st.text(
    min_size=1,
    max_size=64,
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="-_",
    ),
).filter(lambda x: x.strip())

# Strategy for valid Secrets Manager ARNs
secret_arn_st = st.builds(
    lambda region, account, name: (
        f"arn:aws:secretsmanager:{region}:{account}:secret:{name}"
    ),
    region=st.sampled_from(["us-east-1", "eu-west-1", "ap-southeast-1"]),
    account=st.from_regex(r"[0-9]{12}", fullmatch=True),
    name=st.text(
        min_size=1,
        max_size=40,
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            whitelist_characters="/-_",
        ),
    ).filter(lambda x: x.strip()),
)

# Strategy for auth methods including hmac_sha256, api_key, basic_auth, and unknowns
auth_method_st = st.sampled_from(["hmac_sha256", "api_key", "basic_auth"])

# Strategy for arbitrary HTTP header dictionaries
header_key_st = st.sampled_from(
    [
        "X-Api-Key",
        "Authorization",
        "x-api-key",
        "authorization",
        "X-Custom-Header",
        "Content-Type",
        "Accept",
        "X-Hub-Signature-256",
        "Stripe-Signature",
    ]
)
header_value_st = st.text(min_size=1, max_size=200).filter(lambda x: x.strip())

random_headers_st = st.dictionaries(
    keys=header_key_st,
    values=header_value_st,
    max_size=6,
)

# Strategy for method ARNs
method_arn_st = st.just(
    "arn:aws:execute-api:us-east-1:123456789012:api-id/stage/POST/webhooks/*"
)

# Strategy for deployment statuses that are NOT "DEPLOYED"
non_deployed_status_st = st.sampled_from(
    [
        "PENDING",
        "DEPLOYING",
        "FAILED",
        "UNDEPLOYED",
        "DRAFT",
    ]
)


def _assert_deny(result, method_arn):
    """Helper to assert a Deny policy was returned."""
    assert (
        result["policyDocument"]["Statement"][0]["Effect"] == "Deny"
    ), f"Expected Deny policy, got {result['policyDocument']['Statement'][0]['Effect']}"
    assert result["policyDocument"]["Statement"][0]["Resource"] == method_arn


# =============================================================================
# Property Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestAuthorizerDenyInvalidPipelinesProperty:
    """
    Property 9: Authorizer deny for invalid pipelines.

    For any pipeline that does not exist, is not active, or has
    deploymentStatus != "DEPLOYED", the authorizer returns Deny
    regardless of auth method.

    **Validates: Requirement 2.4**
    """

    @pytest.fixture(autouse=True)
    def _bind_mocks(self):
        """Re-bind this file's mocks to the index module before every test."""
        global index, lambda_handler
        _auth_dir = str(
            Path(__file__).parent.parent.parent.parent
            / "lambdas"
            / "auth"
            / "webhook_authorizer"
        )
        if "index" in sys.modules:
            del sys.modules["index"]
        if _auth_dir not in sys.path or sys.path[0] != _auth_dir:
            if _auth_dir in sys.path:
                sys.path.remove(_auth_dir)
            sys.path.insert(0, _auth_dir)
        import index as _idx

        index = _idx
        lambda_handler = _idx.lambda_handler
        index.dynamodb = mock_dynamodb_resource
        index.secretsmanager = mock_secretsmanager_client

    @given(
        pipeline_id=pipeline_id_st,
        auth_method=auth_method_st,
        headers=random_headers_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_deny_when_pipeline_not_found(
        self,
        pipeline_id: str,
        auth_method: str,
        headers: dict,
        method_arn: str,
    ):
        """
        For any auth method, when the pipeline does not exist in DynamoDB,
        the authorizer returns Deny.

        **Validates: Requirement 2.4**
        """
        # Arrange: DynamoDB returns no Item
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb_resource.Table.return_value = mock_table

        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": headers,
        }

        # Act
        result = lambda_handler(event, None)

        # Assert
        _assert_deny(result, method_arn)

    @given(
        pipeline_id=pipeline_id_st,
        secret_arn=secret_arn_st,
        auth_method=auth_method_st,
        headers=random_headers_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_deny_when_pipeline_not_active(
        self,
        pipeline_id: str,
        secret_arn: str,
        auth_method: str,
        headers: dict,
        method_arn: str,
    ):
        """
        For any auth method, when the pipeline exists but is not active,
        the authorizer returns Deny.

        **Validates: Requirement 2.4**
        """
        # Arrange: pipeline exists but active=False
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "id": pipeline_id,
                "active": False,
                "deploymentStatus": "DEPLOYED",
                "webhookAuthMethod": auth_method,
                "webhookSecretArn": secret_arn,
            }
        }
        mock_dynamodb_resource.Table.return_value = mock_table

        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": headers,
        }

        # Act
        result = lambda_handler(event, None)

        # Assert
        _assert_deny(result, method_arn)

    @given(
        pipeline_id=pipeline_id_st,
        secret_arn=secret_arn_st,
        auth_method=auth_method_st,
        non_deployed_status=non_deployed_status_st,
        headers=random_headers_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_deny_when_pipeline_not_deployed(
        self,
        pipeline_id: str,
        secret_arn: str,
        auth_method: str,
        non_deployed_status: str,
        headers: dict,
        method_arn: str,
    ):
        """
        For any auth method, when the pipeline is active but deploymentStatus
        is not "DEPLOYED", the authorizer returns Deny.

        **Validates: Requirement 2.4**
        """
        # Arrange: pipeline is active but not deployed
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "id": pipeline_id,
                "active": True,
                "deploymentStatus": non_deployed_status,
                "webhookAuthMethod": auth_method,
                "webhookSecretArn": secret_arn,
            }
        }
        mock_dynamodb_resource.Table.return_value = mock_table

        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": headers,
        }

        # Act
        result = lambda_handler(event, None)

        # Assert
        _assert_deny(result, method_arn)
