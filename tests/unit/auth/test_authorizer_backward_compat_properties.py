"""
Property-based tests for Webhook Authorizer non-HMAC backward compatibility.

These tests verify that for any pipeline with authMethod == "api_key" or "basic_auth",
the authorizer performs credential verification and includes authMethod in context.

**Feature: hmac-sha256-webhook-auth, Property 12: Non-HMAC backward compatibility**
**Validates: Requirements 2.3, 10.1, 10.2, 10.3**
"""

import base64
import json
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

# Strategy for method ARNs
method_arn_st = st.just(
    "arn:aws:execute-api:us-east-1:123456789012:api-id/stage/POST/webhooks/*"
)

# ASCII-safe alphabet for credentials (realistic for API keys and passwords)
_ascii_credential_alphabet = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)

# Strategy for non-empty API key strings
api_key_st = st.text(
    min_size=1,
    max_size=128,
    alphabet=_ascii_credential_alphabet,
)

# Strategy for basic auth usernames (no colons)
username_st = st.text(
    min_size=1,
    max_size=64,
    alphabet=_ascii_credential_alphabet,
)

# Strategy for basic auth passwords
password_st = st.text(
    min_size=1,
    max_size=128,
    alphabet=_ascii_credential_alphabet,
)

# Strategy for wrong credentials that differ from the correct ones
wrong_credential_st = st.text(
    min_size=1,
    max_size=128,
    alphabet=_ascii_credential_alphabet,
)


# =============================================================================
# Helpers
# =============================================================================


def _assert_allow(result, method_arn):
    """Helper to assert an Allow policy was returned."""
    assert (
        result["policyDocument"]["Statement"][0]["Effect"] == "Allow"
    ), f"Expected Allow policy, got {result['policyDocument']['Statement'][0]['Effect']}"
    assert result["policyDocument"]["Statement"][0]["Resource"] == method_arn


def _assert_deny(result, method_arn):
    """Helper to assert a Deny policy was returned."""
    assert (
        result["policyDocument"]["Statement"][0]["Effect"] == "Deny"
    ), f"Expected Deny policy, got {result['policyDocument']['Statement'][0]['Effect']}"
    assert result["policyDocument"]["Statement"][0]["Resource"] == method_arn


def _mock_pipeline(pipeline_id, auth_method, secret_arn):
    """Set up DynamoDB mock to return an active, deployed pipeline."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "id": pipeline_id,
            "active": True,
            "deploymentStatus": "DEPLOYED",
            "webhookAuthMethod": auth_method,
            "webhookSecretArn": secret_arn,
        }
    }
    mock_dynamodb_resource.Table.return_value = mock_table


def _mock_secret_api_key(api_key):
    """Set up Secrets Manager mock to return an api_key secret."""
    mock_secretsmanager_client.reset_mock()
    mock_secretsmanager_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "current": {"apiKey": api_key},
                "previous": {},
                "graceUntil": None,
            }
        )
    }


def _mock_secret_basic_auth(username, password):
    """Set up Secrets Manager mock to return a basic_auth secret."""
    mock_secretsmanager_client.reset_mock()
    mock_secretsmanager_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "current": {
                    "basicAuthUsername": username,
                    "basicAuthPassword": password,
                },
                "previous": {},
                "graceUntil": None,
            }
        )
    }


# =============================================================================
# Property Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestAuthorizerBackwardCompatProperty:
    """
    Property 12: Non-HMAC backward compatibility.

    For any pipeline with authMethod == "api_key" or "basic_auth",
    the authorizer performs credential verification and includes
    authMethod in context.

    **Validates: Requirements 2.3, 10.1, 10.2, 10.3**
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
        api_key=api_key_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_api_key_correct_credentials_returns_allow_with_auth_method(
        self,
        pipeline_id: str,
        secret_arn: str,
        api_key: str,
        method_arn: str,
    ):
        """
        For any active, deployed api_key pipeline with correct credentials
        provided via X-Api-Key header, the authorizer returns Allow with
        authMethod="api_key" in context.

        **Validates: Requirements 2.3, 10.1**
        """
        # Arrange
        _mock_pipeline(pipeline_id, "api_key", secret_arn)
        _mock_secret_api_key(api_key)

        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": {"X-Api-Key": api_key},
        }

        # Act
        result = lambda_handler(event, None)

        # Assert: Allow with authMethod in context
        _assert_allow(result, method_arn)
        assert "context" in result, "Allow policy must include context"
        assert (
            result["context"]["authMethod"] == "api_key"
        ), f"Expected authMethod='api_key', got '{result['context'].get('authMethod')}'"

    @given(
        pipeline_id=pipeline_id_st,
        secret_arn=secret_arn_st,
        api_key=api_key_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_api_key_bearer_header_returns_allow_with_auth_method(
        self,
        pipeline_id: str,
        secret_arn: str,
        api_key: str,
        method_arn: str,
    ):
        """
        For any active, deployed api_key pipeline with correct credentials
        provided via Authorization: Bearer header, the authorizer returns
        Allow with authMethod="api_key" in context.

        **Validates: Requirements 2.3, 10.1**
        """
        # Arrange
        _mock_pipeline(pipeline_id, "api_key", secret_arn)
        _mock_secret_api_key(api_key)

        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": {"Authorization": f"Bearer {api_key}"},
        }

        # Act
        result = lambda_handler(event, None)

        # Assert
        _assert_allow(result, method_arn)
        assert "context" in result
        assert result["context"]["authMethod"] == "api_key"

    @given(
        pipeline_id=pipeline_id_st,
        secret_arn=secret_arn_st,
        username=username_st,
        password=password_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_basic_auth_correct_credentials_returns_allow_with_auth_method(
        self,
        pipeline_id: str,
        secret_arn: str,
        username: str,
        password: str,
        method_arn: str,
    ):
        """
        For any active, deployed basic_auth pipeline with correct credentials
        provided via Authorization: Basic header, the authorizer returns Allow
        with authMethod="basic_auth" in context.

        **Validates: Requirements 2.3, 10.2**
        """
        # Arrange
        _mock_pipeline(pipeline_id, "basic_auth", secret_arn)
        _mock_secret_basic_auth(username, password)

        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": {"Authorization": f"Basic {encoded}"},
        }

        # Act
        result = lambda_handler(event, None)

        # Assert: Allow with authMethod in context
        _assert_allow(result, method_arn)
        assert "context" in result, "Allow policy must include context"
        assert (
            result["context"]["authMethod"] == "basic_auth"
        ), f"Expected authMethod='basic_auth', got '{result['context'].get('authMethod')}'"

    @given(
        pipeline_id=pipeline_id_st,
        secret_arn=secret_arn_st,
        stored_key=api_key_st,
        wrong_key=wrong_credential_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_api_key_wrong_credentials_returns_deny(
        self,
        pipeline_id: str,
        secret_arn: str,
        stored_key: str,
        wrong_key: str,
        method_arn: str,
    ):
        """
        For any active, deployed api_key pipeline with wrong credentials,
        the authorizer returns Deny.

        **Validates: Requirements 10.1, 10.3**
        """
        from hypothesis import assume

        assume(stored_key != wrong_key)

        # Arrange
        _mock_pipeline(pipeline_id, "api_key", secret_arn)
        _mock_secret_api_key(stored_key)

        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": {"X-Api-Key": wrong_key},
        }

        # Act
        result = lambda_handler(event, None)

        # Assert
        _assert_deny(result, method_arn)

    @given(
        pipeline_id=pipeline_id_st,
        secret_arn=secret_arn_st,
        stored_user=username_st,
        stored_pass=password_st,
        wrong_user=wrong_credential_st,
        wrong_pass=wrong_credential_st,
        method_arn=method_arn_st,
    )
    @settings(max_examples=100)
    def test_basic_auth_wrong_credentials_returns_deny(
        self,
        pipeline_id: str,
        secret_arn: str,
        stored_user: str,
        stored_pass: str,
        wrong_user: str,
        wrong_pass: str,
        method_arn: str,
    ):
        """
        For any active, deployed basic_auth pipeline with wrong credentials,
        the authorizer returns Deny.

        **Validates: Requirements 10.2, 10.3**
        """
        from hypothesis import assume

        assume(stored_user != wrong_user or stored_pass != wrong_pass)

        # Arrange
        _mock_pipeline(pipeline_id, "basic_auth", secret_arn)
        _mock_secret_basic_auth(stored_user, stored_pass)

        encoded = base64.b64encode(f"{wrong_user}:{wrong_pass}".encode()).decode()
        event = {
            "methodArn": method_arn,
            "pathParameters": {"pipelineId": pipeline_id},
            "headers": {"Authorization": f"Basic {encoded}"},
        }

        # Act
        result = lambda_handler(event, None)

        # Assert
        _assert_deny(result, method_arn)
