"""
Property-based tests for HMAC SHA-256 prefix format invariance.

These tests verify that for any valid HMAC hex digest, verification
produces the same result whether the signature is provided as
``sha256=<hex>`` (prefixed) or as raw ``<hex>`` (unprefixed).

**Feature: hmac-sha256-webhook-auth, Property 3: Prefix format invariance**
**Validates: Requirements 4.1, 4.2**
"""

import hashlib
import hmac as hmac_mod
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
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


# =============================================================================
# Property Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestHmacPrefixFormatInvarianceProperty:
    """
    Property 3: Prefix format invariance.

    For any valid HMAC hex digest, verification produces the same result
    whether provided as ``sha256=<hex>`` or raw ``<hex>``.

    **Validates: Requirements 4.1, 4.2**
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
        secret_arn=secret_arn_st,
        sig_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_correct_signature_same_result_with_and_without_prefix(
        self,
        body: str,
        secret: str,
        secret_arn: str,
        sig_header: str,
    ):
        """
        For any body and secret, computing the correct HMAC-SHA256 hex
        digest and calling _verify_hmac_signature with the raw hex and
        with the ``sha256=`` prefix both return (True, None).

        **Validates: Requirements 4.1, 4.2**
        """
        # Arrange: compute the correct HMAC signature
        hex_digest = hmac_mod.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        secret_payload = json.dumps(
            {
                "current": {
                    "hmacSecret": secret,
                    "signatureHeader": sig_header,
                },
                "previous": {},
                "graceUntil": None,
            }
        )

        # Act: verify with raw hex digest
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": secret_payload,
        }
        raw_result = _verify_hmac_signature(body, secret_arn, {sig_header: hex_digest})

        # Act: verify with sha256= prefixed digest
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": secret_payload,
        }
        prefixed_result = _verify_hmac_signature(
            body, secret_arn, {sig_header: f"sha256={hex_digest}"}
        )

        # Assert: both return the same successful result
        assert raw_result == (
            True,
            None,
        ), f"Raw hex verification failed: got {raw_result!r}"
        assert prefixed_result == (
            True,
            None,
        ), f"Prefixed verification failed: got {prefixed_result!r}"
        assert raw_result == prefixed_result

    @given(
        body=body_st,
        secret=secret_st,
        secret_arn=secret_arn_st,
        sig_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_wrong_signature_same_result_with_and_without_prefix(
        self,
        body: str,
        secret: str,
        secret_arn: str,
        sig_header: str,
    ):
        """
        For any body and secret, a wrong signature (all zeros) returns
        (False, "Invalid signature") regardless of whether it is provided
        as raw hex or with the ``sha256=`` prefix.

        **Validates: Requirements 4.1, 4.2**
        """
        # Arrange: use a fixed wrong signature (64 hex zeros)
        wrong_sig = "0" * 64

        secret_payload = json.dumps(
            {
                "current": {
                    "hmacSecret": secret,
                    "signatureHeader": sig_header,
                },
                "previous": {},
                "graceUntil": None,
            }
        )

        # Act: verify with raw wrong hex digest
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": secret_payload,
        }
        raw_result = _verify_hmac_signature(body, secret_arn, {sig_header: wrong_sig})

        # Act: verify with sha256= prefixed wrong digest
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": secret_payload,
        }
        prefixed_result = _verify_hmac_signature(
            body, secret_arn, {sig_header: f"sha256={wrong_sig}"}
        )

        # Assert: both return the same rejection result
        assert raw_result == (
            False,
            "Invalid signature",
        ), f"Raw wrong sig should be rejected: got {raw_result!r}"
        assert prefixed_result == (
            False,
            "Invalid signature",
        ), f"Prefixed wrong sig should be rejected: got {prefixed_result!r}"
        assert raw_result == prefixed_result
