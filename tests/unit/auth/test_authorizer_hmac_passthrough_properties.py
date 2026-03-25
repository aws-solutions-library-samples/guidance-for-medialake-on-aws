"""
Property-based tests for Webhook Authorizer HMAC SHA-256 passthrough.

These tests verify that for any active, deployed pipeline with authMethod == "hmac_sha256",
the authorizer returns an Allow policy with authMethod and webhookSecretArn in context,
without inspecting credential headers or calling Secrets Manager.

**Feature: hmac-sha256-webhook-auth, Property 8: Authorizer HMAC passthrough**
**Validates: Requirements 2.1, 2.2**
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

# Strategy for arbitrary HTTP header dictionaries (random credential headers)
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


# =============================================================================
# Property Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestAuthorizerHmacPassthroughProperty:
    """
    Property 8: Authorizer HMAC passthrough.

    For any active, deployed pipeline with authMethod == "hmac_sha256",
    the authorizer returns Allow with authMethod and webhookSecretArn in context,
    without inspecting credential headers.

    **Validates: Requirements 2.1, 2.2**
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
        secret_arn=secret_arn_st,
        headers=random_headers_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_hmac_pipeline_returns_allow_with_context(
        self,
        pipeline_id: str,
        secret_arn: str,
        headers: dict,
        method_arn: str,
    ):
        """
        Property 8: For any active, deployed HMAC pipeline, the authorizer
        returns Allow with authMethod and webhookSecretArn in context.

        **Validates: Requirements 2.1, 2.2**
        """
        # Arrange: mock DynamoDB to return an active, deployed HMAC pipeline
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "id": pipeline_id,
                "active": True,
                "deploymentStatus": "DEPLOYED",
                "webhookAuthMethod": "hmac_sha256",
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

        # Assert: Allow policy returned
        assert result["policyDocument"]["Statement"][0]["Effect"] == "Allow"
        assert result["policyDocument"]["Statement"][0]["Resource"] == method_arn

        # Assert: context contains authMethod and webhookSecretArn
        assert "context" in result, "Allow policy must include context"
        ctx = result["context"]
        assert (
            ctx["authMethod"] == "hmac_sha256"
        ), f"context.authMethod should be 'hmac_sha256', got '{ctx.get('authMethod')}'"
        assert ctx["webhookSecretArn"] == secret_arn, (
            f"context.webhookSecretArn should be '{secret_arn}', "
            f"got '{ctx.get('webhookSecretArn')}'"
        )

    @given(
        pipeline_id=pipeline_id_st,
        secret_arn=secret_arn_st,
        headers=random_headers_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_hmac_pipeline_does_not_call_secrets_manager(
        self,
        pipeline_id: str,
        secret_arn: str,
        headers: dict,
        method_arn: str,
    ):
        """
        Property 8: For any HMAC pipeline, the authorizer does NOT call
        Secrets Manager (credential verification is deferred to ingress).

        **Validates: Requirement 2.2**
        """
        # Arrange
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "id": pipeline_id,
                "active": True,
                "deploymentStatus": "DEPLOYED",
                "webhookAuthMethod": "hmac_sha256",
                "webhookSecretArn": secret_arn,
            }
        }
        mock_dynamodb_resource.Table.return_value = mock_table
        mock_secretsmanager_client.reset_mock()

        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": headers,
        }

        # Act
        lambda_handler(event, None)

        # Assert: Secrets Manager was never called
        mock_secretsmanager_client.get_secret_value.assert_not_called()
