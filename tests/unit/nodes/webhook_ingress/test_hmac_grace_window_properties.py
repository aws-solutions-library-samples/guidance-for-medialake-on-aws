"""
Property-based tests for HMAC SHA-256 secret rotation grace window.

These tests verify that:
- Property 5: For any two secrets, a graceUntil in the future, and a request
  signed with the previous secret, the ingress accepts the request.
- Property 6: For any two secrets, a graceUntil in the past, and a request
  signed with the previous secret, the ingress rejects with 401.

**Feature: hmac-sha256-webhook-auth, Properties 5 & 6: Grace window**
**Validates: Requirements 5.1, 5.2, 5.3**
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


# =============================================================================
# Property 5: Grace window acceptance
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestHmacGraceWindowAcceptanceProperty:
    """
    Property 5: Grace window acceptance.

    For any two secrets (current and previous), a graceUntil timestamp
    in the future, and a request signed with the previous secret, the
    ingress accepts the request.

    **Validates: Requirements 5.1, 5.2**
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
        current_secret=secret_st,
        previous_secret=secret_st,
        secret_arn=secret_arn_st,
        sig_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_previous_secret_accepted_within_grace_window(
        self,
        body: str,
        current_secret: str,
        previous_secret: str,
        secret_arn: str,
        sig_header: str,
    ):
        """
        For any body, current secret, and previous secret, signing with
        the previous secret while graceUntil is in the future results
        in (True, None).

        **Validates: Requirements 5.1, 5.2**
        """
        # Ensure current and previous secrets are different
        assume(current_secret != previous_secret)

        # Sign the body with the previous secret
        signature = hmac_mod.new(
            previous_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # graceUntil far in the future so the grace window is active
        grace_until = "2099-01-01T00:00:00Z"

        # Mock Secrets Manager to return both current and previous secrets
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "current": {
                        "hmacSecret": current_secret,
                        "signatureHeader": sig_header,
                    },
                    "previous": {
                        "hmacSecret": previous_secret,
                        "signatureHeader": sig_header,
                    },
                    "graceUntil": grace_until,
                }
            )
        }

        headers = {sig_header: signature}

        # Act
        is_valid, error = _verify_hmac_signature(body, secret_arn, headers)

        # Assert
        assert is_valid is True, (
            f"Expected (True, None) but got ({is_valid}, {error!r}) "
            f"for body={body!r}, previous_secret={previous_secret!r}, "
            f"graceUntil={grace_until}"
        )
        assert error is None

    @given(
        body=body_st,
        current_secret=secret_st,
        previous_secret=secret_st,
        secret_arn=secret_arn_st,
        sig_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_previous_secret_accepted_with_sha256_prefix_within_grace_window(
        self,
        body: str,
        current_secret: str,
        previous_secret: str,
        secret_arn: str,
        sig_header: str,
    ):
        """
        For any body, current secret, and previous secret, signing with
        the previous secret (sha256= prefixed) while graceUntil is in
        the future results in (True, None).

        **Validates: Requirements 5.1, 5.2**
        """
        # Ensure current and previous secrets are different
        assume(current_secret != previous_secret)

        # Sign the body with the previous secret, using sha256= prefix
        hex_digest = hmac_mod.new(
            previous_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signature = f"sha256={hex_digest}"

        # graceUntil far in the future so the grace window is active
        grace_until = "2099-01-01T00:00:00Z"

        # Mock Secrets Manager to return both current and previous secrets
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "current": {
                        "hmacSecret": current_secret,
                        "signatureHeader": sig_header,
                    },
                    "previous": {
                        "hmacSecret": previous_secret,
                        "signatureHeader": sig_header,
                    },
                    "graceUntil": grace_until,
                }
            )
        }

        headers = {sig_header: signature}

        # Act
        is_valid, error = _verify_hmac_signature(body, secret_arn, headers)

        # Assert
        assert is_valid is True, (
            f"Expected (True, None) but got ({is_valid}, {error!r}) "
            f"for body={body!r}, previous_secret={previous_secret!r}, "
            f"graceUntil={grace_until}"
        )
        assert error is None


# =============================================================================
# Property 6: Expired grace window rejection
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestHmacExpiredGraceWindowRejectionProperty:
    """
    Property 6: Expired grace window rejection.

    For any two secrets (current and previous), a graceUntil timestamp
    in the past, and a request signed with the previous secret, the
    ingress rejects with (False, "Invalid signature").

    **Validates: Requirement 5.3**
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
        current_secret=secret_st,
        previous_secret=secret_st,
        secret_arn=secret_arn_st,
        sig_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_previous_secret_rejected_after_grace_window_expires(
        self,
        body: str,
        current_secret: str,
        previous_secret: str,
        secret_arn: str,
        sig_header: str,
    ):
        """
        For any body, current secret, and previous secret, signing with
        the previous secret while graceUntil is in the past results in
        (False, "Invalid signature").

        **Validates: Requirement 5.3**
        """
        # Ensure current and previous secrets are different
        assume(current_secret != previous_secret)

        # Sign the body with the previous secret
        signature = hmac_mod.new(
            previous_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # graceUntil far in the past so the grace window has expired
        grace_until = "2020-01-01T00:00:00Z"

        # Mock Secrets Manager to return both current and previous secrets
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "current": {
                        "hmacSecret": current_secret,
                        "signatureHeader": sig_header,
                    },
                    "previous": {
                        "hmacSecret": previous_secret,
                        "signatureHeader": sig_header,
                    },
                    "graceUntil": grace_until,
                }
            )
        }

        headers = {sig_header: signature}

        # Act
        is_valid, error = _verify_hmac_signature(body, secret_arn, headers)

        # Assert
        assert is_valid is False, (
            f"Expected (False, 'Invalid signature') but got ({is_valid}, {error!r}) "
            f"for body={body!r}, previous_secret={previous_secret!r}, "
            f"graceUntil={grace_until}"
        )
        assert error == "Invalid signature"

    @given(
        body=body_st,
        current_secret=secret_st,
        previous_secret=secret_st,
        secret_arn=secret_arn_st,
        sig_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_previous_secret_rejected_with_sha256_prefix_after_grace_expires(
        self,
        body: str,
        current_secret: str,
        previous_secret: str,
        secret_arn: str,
        sig_header: str,
    ):
        """
        For any body, current secret, and previous secret, signing with
        the previous secret (sha256= prefixed) while graceUntil is in
        the past results in (False, "Invalid signature").

        **Validates: Requirement 5.3**
        """
        # Ensure current and previous secrets are different
        assume(current_secret != previous_secret)

        # Sign the body with the previous secret, using sha256= prefix
        hex_digest = hmac_mod.new(
            previous_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signature = f"sha256={hex_digest}"

        # graceUntil far in the past so the grace window has expired
        grace_until = "2020-01-01T00:00:00Z"

        # Mock Secrets Manager to return both current and previous secrets
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "current": {
                        "hmacSecret": current_secret,
                        "signatureHeader": sig_header,
                    },
                    "previous": {
                        "hmacSecret": previous_secret,
                        "signatureHeader": sig_header,
                    },
                    "graceUntil": grace_until,
                }
            )
        }

        headers = {sig_header: signature}

        # Act
        is_valid, error = _verify_hmac_signature(body, secret_arn, headers)

        # Assert
        assert is_valid is False, (
            f"Expected (False, 'Invalid signature') but got ({is_valid}, {error!r}) "
            f"for body={body!r}, previous_secret={previous_secret!r}, "
            f"graceUntil={grace_until}"
        )
        assert error == "Invalid signature"
