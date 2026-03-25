"""
Unit tests for HMAC SHA-256 integration in the Webhook Ingress lambda_handler.

Verifies that the handler correctly reads authMethod from authorizer context,
calls _verify_hmac_signature for hmac_sha256 pipelines, returns 401 on failure
or missing config, and skips verification for non-HMAC auth methods.

**Feature: hmac-sha256-webhook-auth, Task 4.2**
**Validates: Requirements 3.1, 9.1, 9.2, 10.3**
"""

import hashlib
import hmac as hmac_mod
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Environment and mock setup (before importing the Lambda module)
# =============================================================================

os.environ.setdefault("PIPELINES_EVENT_BUS_NAME", "test-event-bus")
os.environ.setdefault("PIPELINE_TABLE_NAME", "test-pipeline-table")

mock_boto3 = MagicMock()
mock_dynamodb_resource = MagicMock()
mock_events_client = MagicMock()
mock_secretsmanager_client = MagicMock()
mock_boto3.resource.return_value = mock_dynamodb_resource
mock_boto3.client.side_effect = lambda svc, **kw: (
    mock_events_client if svc == "events" else mock_secretsmanager_client
)
sys.modules["boto3"] = mock_boto3

sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "lambdas"
        / "nodes"
        / "webhook_ingress"
    ),
)

import index
from index import lambda_handler

# =============================================================================
# Helpers
# =============================================================================

VALID_JSON_BODY = '{"event": "push"}'
SIGNING_SECRET = "test-secret-key-1234"
SIGNATURE_HEADER = "X-Hub-Signature-256"


def _make_secret_data(hmac_secret=SIGNING_SECRET, sig_header=SIGNATURE_HEADER):
    return {
        "current": {
            "hmacSecret": hmac_secret,
            "signatureHeader": sig_header,
        },
    }


def _compute_signature(body, secret, prefix=True):
    digest = hmac_mod.new(
        secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}" if prefix else digest


def _make_event(
    body=VALID_JSON_BODY,
    auth_method=None,
    webhook_secret_arn=None,
    headers=None,
    pipeline_id="pipeline-123",
):
    """Build a minimal API Gateway proxy event for the ingress handler."""
    if headers is None:
        headers = {"Content-Type": "application/json"}
    elif "Content-Type" not in {k for k in headers}:
        # Ensure Content-Type is present (case-sensitive key for test simplicity)
        has_ct = any(k.lower() == "content-type" for k in headers)
        if not has_ct:
            headers["Content-Type"] = "application/json"

    authorizer = {}
    if auth_method is not None:
        authorizer["authMethod"] = auth_method
    if webhook_secret_arn is not None:
        authorizer["webhookSecretArn"] = webhook_secret_arn

    return {
        "pathParameters": {"pipelineId": pipeline_id},
        "headers": headers,
        "body": body,
        "requestContext": {"authorizer": authorizer},
    }


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.unit
class TestIngressHmacIntegration:
    """Tests for HMAC verification integration in lambda_handler."""

    @pytest.fixture(autouse=True)
    def _bind_mocks(self):
        """Re-bind mocks to the index module before every test."""
        index.dynamodb = mock_dynamodb_resource
        index.events = mock_events_client
        index.secretsmanager = mock_secretsmanager_client
        mock_secretsmanager_client.reset_mock()
        mock_events_client.reset_mock()

    def test_hmac_valid_signature_proceeds_to_eventbridge(self):
        """
        Req 3.1: When authMethod is hmac_sha256 and signature is valid,
        the handler fetches the secret and proceeds to EventBridge publish.

        **Validates: Requirement 3.1**
        """
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        sig = _compute_signature(VALID_JSON_BODY, SIGNING_SECRET)

        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(_make_secret_data()),
        }
        mock_events_client.put_events.return_value = {
            "Entries": [{"EventId": "evt-123"}]
        }

        event = _make_event(
            auth_method="hmac_sha256",
            webhook_secret_arn=secret_arn,
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: sig,
            },
        )

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["eventId"] == "evt-123"
        mock_secretsmanager_client.get_secret_value.assert_called_once_with(
            SecretId=secret_arn
        )

    def test_hmac_invalid_signature_returns_401(self):
        """
        Req 9.1: When HMAC signature is invalid, return 401.

        **Validates: Requirement 9.1**
        """
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"

        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(_make_secret_data()),
        }

        event = _make_event(
            auth_method="hmac_sha256",
            webhook_secret_arn=secret_arn,
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: "sha256=0000000000000000000000000000000000000000000000000000000000000000",
            },
        )

        result = lambda_handler(event, None)

        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"] == "Unauthorized"
        assert body["message"] == "Invalid signature"
        # EventBridge should NOT be called
        mock_events_client.put_events.assert_not_called()

    def test_hmac_missing_secret_arn_returns_401(self):
        """
        Req 9.2: When webhookSecretArn is missing for hmac_sha256,
        return 401 with "Missing signing configuration".

        **Validates: Requirement 9.2**
        """
        event = _make_event(
            auth_method="hmac_sha256",
            webhook_secret_arn=None,  # no ARN
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: "sha256=abc123",
            },
        )

        result = lambda_handler(event, None)

        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"] == "Unauthorized"
        assert body["message"] == "Missing signing configuration"
        # Neither Secrets Manager nor EventBridge should be called
        mock_secretsmanager_client.get_secret_value.assert_not_called()
        mock_events_client.put_events.assert_not_called()

    def test_non_hmac_auth_skips_verification(self):
        """
        Req 10.3: When authMethod is not hmac_sha256, skip HMAC verification
        and proceed with existing processing logic.

        **Validates: Requirement 10.3**
        """
        mock_events_client.put_events.return_value = {
            "Entries": [{"EventId": "evt-456"}]
        }

        event = _make_event(
            auth_method="api_key",
            headers={"Content-Type": "application/json"},
        )

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["eventId"] == "evt-456"
        # Secrets Manager should NOT be called for non-HMAC
        mock_secretsmanager_client.get_secret_value.assert_not_called()

    def test_no_auth_method_skips_verification(self):
        """
        Req 10.3: When authMethod is absent from authorizer context,
        skip HMAC verification entirely.

        **Validates: Requirement 10.3**
        """
        mock_events_client.put_events.return_value = {
            "Entries": [{"EventId": "evt-789"}]
        }

        event = _make_event(
            auth_method=None,
            headers={"Content-Type": "application/json"},
        )

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        mock_secretsmanager_client.get_secret_value.assert_not_called()

    def test_hmac_secrets_manager_failure_returns_401(self):
        """
        Req 9.1: When Secrets Manager call fails, return 401 with
        "Failed to retrieve signing secret".

        **Validates: Requirement 9.1**
        """
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"

        mock_secretsmanager_client.get_secret_value.side_effect = Exception(
            "Access denied"
        )

        event = _make_event(
            auth_method="hmac_sha256",
            webhook_secret_arn=secret_arn,
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: "sha256=abc123",
            },
        )

        result = lambda_handler(event, None)

        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"] == "Unauthorized"
        assert body["message"] == "Failed to retrieve signing secret"
        mock_events_client.put_events.assert_not_called()

    def test_basic_auth_skips_hmac_verification(self):
        """
        Req 10.3: basic_auth pipelines skip HMAC verification.

        **Validates: Requirement 10.3**
        """
        mock_events_client.put_events.return_value = {
            "Entries": [{"EventId": "evt-basic"}]
        }

        event = _make_event(
            auth_method="basic_auth",
            headers={"Content-Type": "application/json"},
        )

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        mock_secretsmanager_client.get_secret_value.assert_not_called()
