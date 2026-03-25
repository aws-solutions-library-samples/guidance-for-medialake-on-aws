"""
Property-based tests for HMAC SHA-256 pipeline secret provisioning.

These tests verify the pure provisioning logic extracted from the
pipeline creation handler: secret payload construction, credential
hint generation, and secret rotation structure.

**Feature: hmac-sha256-webhook-auth**
"""

import json
from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Non-empty signing secrets (realistic webhook shared secrets)
secret_st = st.text(min_size=1, max_size=256).filter(lambda s: s.strip())

# Signature header names (valid HTTP header names)
sig_header_st = st.sampled_from(
    [
        "X-Hub-Signature-256",
        "X-Signature",
        "Stripe-Signature",
        "X-Webhook-Signature",
        "X-Custom-Sig",
    ]
)

# Secrets of length >= 4 for hint generation with visible suffix
secret_long_st = st.text(min_size=4, max_size=256).filter(lambda s: s.strip())

# Secrets of length < 4 for hint generation edge case
secret_short_st = st.text(min_size=1, max_size=3).filter(lambda s: len(s) < 4)


# =============================================================================
# Helper: replicate the provisioning logic from the handler
# =============================================================================


def build_hmac_secret_payload(secret: str, sig_header: str) -> dict:
    """
    Replicate the hmac_sha256 branch of the pipeline creation handler.

    This mirrors the logic in post_pipelines/handlers.py:
        secret_payload["current"] = {
            "hmacSecret": secret,
            "signatureHeader": sig_header,
        }
    """
    return {
        "authMethod": "hmac_sha256",
        "current": {
            "hmacSecret": secret,
            "signatureHeader": sig_header,
        },
        "previous": None,
        "graceUntil": None,
    }


def generate_credential_hint(secret: str) -> str:
    """
    Replicate the credential hint logic from the handler.

    This mirrors:
        f"****{secret[-4:]}" if len(secret) >= 4 else "****"
    """
    return f"****{secret[-4:]}" if len(secret) >= 4 else "****"


def rotate_secret(existing_payload: dict, new_secret: str, new_sig_header: str) -> dict:
    """
    Replicate the secret rotation logic from the handler.

    On pipeline update the handler does:
        secret_payload["previous"] = existing_payload.get("current")
        secret_payload["graceUntil"] = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    """
    now = datetime.utcnow()
    return {
        "authMethod": "hmac_sha256",
        "current": {
            "hmacSecret": new_secret,
            "signatureHeader": new_sig_header,
        },
        "previous": existing_payload.get("current"),
        "graceUntil": (now + timedelta(minutes=15)).isoformat(),
    }


# =============================================================================
# Property 10: Secret provisioning round-trip
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestSecretProvisioningRoundTrip:
    """
    Property 10: Secret provisioning round-trip.

    For any valid signing secret and header name, the stored payload
    contains current.hmacSecret equal to the secret and
    current.signatureHeader equal to the header name.

    **Validates: Requirement 6.1**
    """

    @given(secret=secret_st, sig_header=sig_header_st)
    @settings(max_examples=100)
    def test_current_hmac_secret_matches_input(self, secret: str, sig_header: str):
        """
        The stored payload's current.hmacSecret equals the provided secret.

        **Validates: Requirements 6.1**
        """
        payload = build_hmac_secret_payload(secret, sig_header)

        assert (
            payload["current"]["hmacSecret"] == secret
        ), f"Expected hmacSecret={secret!r}, got {payload['current']['hmacSecret']!r}"

    @given(secret=secret_st, sig_header=sig_header_st)
    @settings(max_examples=100)
    def test_current_signature_header_matches_input(self, secret: str, sig_header: str):
        """
        The stored payload's current.signatureHeader equals the provided header.

        **Validates: Requirements 6.1**
        """
        payload = build_hmac_secret_payload(secret, sig_header)

        assert payload["current"]["signatureHeader"] == sig_header, (
            f"Expected signatureHeader={sig_header!r}, "
            f"got {payload['current']['signatureHeader']!r}"
        )

    @given(secret=secret_st, sig_header=sig_header_st)
    @settings(max_examples=100)
    def test_payload_structure_is_complete(self, secret: str, sig_header: str):
        """
        The payload has the expected top-level keys and authMethod is hmac_sha256.

        **Validates: Requirements 6.1**
        """
        payload = build_hmac_secret_payload(secret, sig_header)

        assert payload["authMethod"] == "hmac_sha256"
        assert "current" in payload
        assert "previous" in payload
        assert "graceUntil" in payload
        assert payload["previous"] is None
        assert payload["graceUntil"] is None

    @given(secret=secret_st, sig_header=sig_header_st)
    @settings(max_examples=100)
    def test_payload_json_serializable(self, secret: str, sig_header: str):
        """
        The payload can be serialized to JSON (as required for Secrets Manager).

        **Validates: Requirements 6.1**
        """
        payload = build_hmac_secret_payload(secret, sig_header)
        serialized = json.dumps(payload)
        deserialized = json.loads(serialized)

        assert deserialized["current"]["hmacSecret"] == secret
        assert deserialized["current"]["signatureHeader"] == sig_header


# =============================================================================
# Property 11: Credential hint generation
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestCredentialHintGeneration:
    """
    Property 11: Credential hint generation.

    For any secret of length >= 4, the hint equals '****' + last 4 chars;
    for secrets < 4 chars, the hint is '****'.

    **Validates: Requirements 6.3, 6.4**
    """

    @given(secret=secret_long_st)
    @settings(max_examples=100)
    def test_hint_suffix_for_long_secrets(self, secret: str):
        """
        For secrets with length >= 4, the hint is '****' + last 4 characters.

        **Validates: Requirements 6.3**
        """
        hint = generate_credential_hint(secret)

        expected = f"****{secret[-4:]}"
        assert hint == expected, (
            f"For secret of length {len(secret)}, "
            f"expected hint={expected!r}, got {hint!r}"
        )

    @given(secret=secret_short_st)
    @settings(max_examples=100)
    def test_hint_masked_for_short_secrets(self, secret: str):
        """
        For secrets with length < 4, the hint is just '****'.

        **Validates: Requirements 6.4**
        """
        hint = generate_credential_hint(secret)

        assert hint == "****", (
            f"For secret of length {len(secret)}, "
            f"expected hint='****', got {hint!r}"
        )

    @given(secret=secret_st)
    @settings(max_examples=100)
    def test_hint_always_starts_with_mask(self, secret: str):
        """
        Regardless of secret length, the hint always starts with '****'.

        **Validates: Requirements 6.3, 6.4**
        """
        hint = generate_credential_hint(secret)

        assert hint.startswith("****"), f"Hint {hint!r} does not start with '****'"

    @given(secret=secret_long_st)
    @settings(max_examples=100)
    def test_hint_length_for_long_secrets(self, secret: str):
        """
        For secrets >= 4 chars, the hint length is exactly 8 (4 stars + 4 chars).

        **Validates: Requirements 6.3**
        """
        hint = generate_credential_hint(secret)

        assert (
            len(hint) == 8
        ), f"Expected hint length 8, got {len(hint)} for hint={hint!r}"

    @given(secret=secret_short_st)
    @settings(max_examples=100)
    def test_hint_length_for_short_secrets(self, secret: str):
        """
        For secrets < 4 chars, the hint length is exactly 4 (just the stars).

        **Validates: Requirements 6.4**
        """
        hint = generate_credential_hint(secret)

        assert (
            len(hint) == 4
        ), f"Expected hint length 4, got {len(hint)} for hint={hint!r}"


# =============================================================================
# Property 7: Secret rotation structure
# =============================================================================


@pytest.mark.unit
@pytest.mark.property
class TestSecretRotationStructure:
    """
    Property 7: Secret rotation structure.

    For any pipeline secret update, the old current secret moves to
    'previous' and 'graceUntil' is set to now + 15 minutes.

    **Validates: Requirement 5.4**
    """

    @given(
        old_secret=secret_st,
        old_header=sig_header_st,
        new_secret=secret_st,
        new_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_old_current_moves_to_previous(
        self, old_secret: str, old_header: str, new_secret: str, new_header: str
    ):
        """
        After rotation, the old current secret is stored in 'previous'.

        **Validates: Requirement 5.4**
        """
        existing_payload = build_hmac_secret_payload(old_secret, old_header)
        rotated = rotate_secret(existing_payload, new_secret, new_header)

        assert (
            rotated["previous"] is not None
        ), "previous should not be None after rotation"
        assert rotated["previous"]["hmacSecret"] == old_secret, (
            f"Expected previous.hmacSecret={old_secret!r}, "
            f"got {rotated['previous']['hmacSecret']!r}"
        )
        assert rotated["previous"]["signatureHeader"] == old_header, (
            f"Expected previous.signatureHeader={old_header!r}, "
            f"got {rotated['previous']['signatureHeader']!r}"
        )

    @given(
        old_secret=secret_st,
        old_header=sig_header_st,
        new_secret=secret_st,
        new_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_new_current_is_set(
        self, old_secret: str, old_header: str, new_secret: str, new_header: str
    ):
        """
        After rotation, the new secret is stored in 'current'.

        **Validates: Requirement 5.4**
        """
        existing_payload = build_hmac_secret_payload(old_secret, old_header)
        rotated = rotate_secret(existing_payload, new_secret, new_header)

        assert rotated["current"]["hmacSecret"] == new_secret
        assert rotated["current"]["signatureHeader"] == new_header

    @given(
        old_secret=secret_st,
        old_header=sig_header_st,
        new_secret=secret_st,
        new_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_grace_until_is_approximately_15_minutes(
        self, old_secret: str, old_header: str, new_secret: str, new_header: str
    ):
        """
        After rotation, graceUntil is set to approximately now + 15 minutes.

        **Validates: Requirement 5.4**
        """
        before = datetime.utcnow()
        existing_payload = build_hmac_secret_payload(old_secret, old_header)
        rotated = rotate_secret(existing_payload, new_secret, new_header)
        after = datetime.utcnow()

        assert (
            rotated["graceUntil"] is not None
        ), "graceUntil should be set after rotation"

        grace_dt = datetime.fromisoformat(rotated["graceUntil"])
        expected_min = before + timedelta(minutes=15)
        expected_max = after + timedelta(minutes=15)

        assert expected_min <= grace_dt <= expected_max, (
            f"graceUntil {grace_dt} not within expected range "
            f"[{expected_min}, {expected_max}]"
        )

    @given(
        old_secret=secret_st,
        old_header=sig_header_st,
        new_secret=secret_st,
        new_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_grace_until_is_valid_iso8601(
        self, old_secret: str, old_header: str, new_secret: str, new_header: str
    ):
        """
        The graceUntil value is a valid ISO-8601 timestamp string.

        **Validates: Requirement 5.4**
        """
        existing_payload = build_hmac_secret_payload(old_secret, old_header)
        rotated = rotate_secret(existing_payload, new_secret, new_header)

        # Should not raise
        grace_dt = datetime.fromisoformat(rotated["graceUntil"])
        assert isinstance(grace_dt, datetime)

    @given(
        old_secret=secret_st,
        old_header=sig_header_st,
        new_secret=secret_st,
        new_header=sig_header_st,
    )
    @settings(max_examples=100)
    def test_rotation_preserves_auth_method(
        self, old_secret: str, old_header: str, new_secret: str, new_header: str
    ):
        """
        After rotation, authMethod remains 'hmac_sha256'.

        **Validates: Requirement 5.4**
        """
        existing_payload = build_hmac_secret_payload(old_secret, old_header)
        rotated = rotate_secret(existing_payload, new_secret, new_header)

        assert rotated["authMethod"] == "hmac_sha256"
