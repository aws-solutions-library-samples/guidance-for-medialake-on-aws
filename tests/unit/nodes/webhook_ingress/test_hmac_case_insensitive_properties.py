"""
Property-based tests for case-insensitive header lookup in HMAC verification.

These tests verify that for any configured signature header name and any
case variation of that header name in the request headers, the ingress
finds and uses the signature value for HMAC verification.

**Feature: hmac-sha256-webhook-auth, Property 4: Case-insensitive header lookup**
**Validates: Requirement 4.3**
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

# Strategy for non-empty request body strings
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


@st.composite
def random_case_variation(draw, header_st=sig_header_st):
    """Generate a header name and a random case variation of it.

    For each character in the header name, randomly choose upper or lower case.
    This ensures the variation differs in case but is equivalent under
    case-insensitive comparison.
    """
    original = draw(header_st)
    # For each character, randomly pick upper or lower
    varied_chars = []
    for ch in original:
        if draw(st.booleans()):
            varied_chars.append(ch.upper())
        else:
            varied_chars.append(ch.lower())
    varied = "".join(varied_chars)
    return original, varied


# =============================================================================
# Property Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestHmacCaseInsensitiveHeaderProperty:
    """
    Property 4: Case-insensitive header lookup.

    For any configured header name and any case variation in request
    headers, the ingress finds and uses the signature value.

    **Validates: Requirement 4.3**
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
        header_pair=random_case_variation(),
    )
    @settings(max_examples=100)
    def test_case_varied_header_is_found(
        self,
        body: str,
        secret: str,
        secret_arn: str,
        header_pair: tuple,
    ):
        """
        For any configured header name and a random case variation of
        that name used as the request header key, _verify_hmac_signature
        finds the signature and returns (True, None).

        **Validates: Requirement 4.3**
        """
        configured_header, varied_header = header_pair

        # Compute valid HMAC signature
        expected_sig = hmac_mod.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Mock Secrets Manager — configured header is the "canonical" name
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "current": {
                        "hmacSecret": secret,
                        "signatureHeader": configured_header,
                    },
                    "previous": {},
                    "graceUntil": None,
                }
            )
        }

        # Place the signature under the case-varied header key
        headers = {varied_header: expected_sig}

        # Act
        is_valid, error = _verify_hmac_signature(body, secret_arn, headers)

        # Assert
        assert is_valid is True, (
            f"Expected (True, None) but got ({is_valid}, {error!r}) "
            f"for configured_header={configured_header!r}, "
            f"varied_header={varied_header!r}"
        )
        assert error is None
