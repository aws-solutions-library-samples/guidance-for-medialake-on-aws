"""
Property-based tests for HMAC SHA-256 invalid signature rejection.

These tests verify that for any random body, secret, and a signature
not computed from that body+secret combination, the Webhook Ingress
rejects the request with (False, "Invalid signature").

**Feature: hmac-sha256-webhook-auth, Property 2: Invalid signature rejection**
**Validates: Requirement 3.4**
"""

import hashlib
import hmac as hmac_mod
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# =============================================================================
# Environment variables required by the ingress module
# =============================================================================

os.environ.setdefault("PIPELINES_EVENT_BUS_NAME", "test-event-bus")
os.environ.setdefault("PIPELINE_TABLE_NAME", "test-pipeline-table")

# =============================================================================
# Mock boto3 and set up imports
# =============================================================================

mock_boto3 = MagicMock()
mock_dynamodb_resource = MagicMock()
mock_events_client = MagicMock()
mock_secretsmanager_client = MagicMock()
mock_boto3.resource.return_value = mock_dynamodb_resource
mock_boto3.client.side_effect = lambda svc, **kw: (
    mock_events_client if svc == "events" else mock_secretsmanager_client
)
sys.modules["boto3"] = mock_boto3

# Add the webhook_ingress Lambda directory to path
_ingress_dir = str(
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "lambdas"
    / "nodes"
    / "webhook_ingress"
)
if _ingress_dir not in sys.path:
    sys.path.insert(0, _ingress_dir)

# Force re-import of the index module with our mocks in place
if "index" in sys.modules:
    del sys.modules["index"]

import index  # noqa: E402
from index import _verify_hmac_signature  # noqa: E402

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for non-empty request body strings (realistic webhook payloads)
body_st = st.text(min_size=1, max_size=1000).filter(lambda x: x.strip())

# Strategy for non-empty signing secrets
secret_st = st.text(min_size=1, max_size=256).filter(lambda x: x.strip())

# Strategy for valid Secrets Manager ARNs
secret_arn_st = st.just("arn:aws:secretsmanager:us-east-1:123456789012:secret:test")

# Strategy for signature header names
sig_header_st = st.sampled_from(
    [
        "X-Hub-Signature-256",
        "X-Signature",
        "Stripe-Signature",
        "X-Webhook-Signature",
    ]
)

# Strategy for random hex strings that look like SHA-256 digests (64 hex chars)
wrong_signature_st = st.text(
    alphabet="0123456789abcdef",
    min_size=64,
    max_size=64,
)


# =============================================================================
# Property Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestHmacInvalidSignatureRejectionProperty:
    """
    Property 2: Invalid signature rejection.

    For any random body, secret, and a signature not computed from that
    body+secret combination, the ingress rejects with (False, "Invalid signature").

    **Validates: Requirement 3.4**
    """

    @pytest.fixture(autouse=True)
    def _bind_mocks(self):
        """Re-bind mocks to the index module before every test."""
        global index, _verify_hmac_signature
        if "index" in sys.modules:
            del sys.modules["index"]
        if _ingress_dir not in sys.path or sys.path[0] != _ingress_dir:
            if _ingress_dir in sys.path:
                sys.path.remove(_ingress_dir)
            sys.path.insert(0, _ingress_dir)
        import index as _idx

        index = _idx
        _verify_hmac_signature = _idx._verify_hmac_signature
        index.dynamodb = mock_dynamodb_resource
        index.events = mock_events_client
        index.secretsmanager = mock_secretsmanager_client

    @given(
        body=body_st,
        secret=secret_st,
        wrong_sig=wrong_signature_st,
        secret_arn=secret_arn_st,
        sig_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_invalid_raw_hex_signature_rejected(
        self,
        body: str,
        secret: str,
        wrong_sig: str,
        secret_arn: str,
        sig_header: str,
    ):
        """
        For any body, secret, and a random hex signature that does not
        match HMAC-SHA256(secret, body), verification returns
        (False, "Invalid signature").

        **Validates: Requirement 3.4**
        """
        # Compute the correct signature so we can ensure wrong_sig differs
        correct_sig = hmac_mod.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Ensure the wrong signature is actually different from the correct one
        assume(wrong_sig != correct_sig)

        # Mock Secrets Manager to return the secret
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "current": {
                        "hmacSecret": secret,
                        "signatureHeader": sig_header,
                    },
                    "previous": {},
                    "graceUntil": None,
                }
            )
        }

        headers = {sig_header: wrong_sig}

        # Act
        is_valid, error = _verify_hmac_signature(body, secret_arn, headers)

        # Assert
        assert is_valid is False, (
            f"Expected (False, 'Invalid signature') but got ({is_valid}, {error!r}) "
            f"for body={body!r}, secret={secret!r}, wrong_sig={wrong_sig!r}"
        )
        assert error == "Invalid signature"

    @given(
        body=body_st,
        secret=secret_st,
        wrong_sig=wrong_signature_st,
        secret_arn=secret_arn_st,
        sig_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_invalid_prefixed_signature_rejected(
        self,
        body: str,
        secret: str,
        wrong_sig: str,
        secret_arn: str,
        sig_header: str,
    ):
        """
        For any body, secret, and a random hex signature (with sha256= prefix)
        that does not match HMAC-SHA256(secret, body), verification returns
        (False, "Invalid signature").

        **Validates: Requirement 3.4**
        """
        # Compute the correct signature so we can ensure wrong_sig differs
        correct_sig = hmac_mod.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Ensure the wrong signature is actually different from the correct one
        assume(wrong_sig != correct_sig)

        # Mock Secrets Manager to return the secret
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "current": {
                        "hmacSecret": secret,
                        "signatureHeader": sig_header,
                    },
                    "previous": {},
                    "graceUntil": None,
                }
            )
        }

        # Pass the wrong signature with sha256= prefix
        headers = {sig_header: f"sha256={wrong_sig}"}

        # Act
        is_valid, error = _verify_hmac_signature(body, secret_arn, headers)

        # Assert
        assert is_valid is False, (
            f"Expected (False, 'Invalid signature') but got ({is_valid}, {error!r}) "
            f"for body={body!r}, secret={secret!r}, wrong_sig=sha256={wrong_sig!r}"
        )
        assert error == "Invalid signature"
