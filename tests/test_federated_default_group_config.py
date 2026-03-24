"""
Property-based tests for federated user default group configuration validation.
Feature: federated-user-default-group, Property 1: Valid Default Group Acceptance
Validates: Requirements 1.1, 1.2, 1.4
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from config import IdentityProviderConfig


# --- Strategies ---

# Non-empty strings for valid field values
non_empty_strings = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())

# Valid HTTPS URLs for OIDC issuer
valid_https_urls = st.from_regex(
    r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}", fullmatch=True
)

# Valid SAML metadata URLs
valid_saml_metadata_urls = st.from_regex(
    r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}/metadata", fullmatch=True
)

# Valid default group values (including None)
valid_default_groups = st.sampled_from(
    [None, "editors", "read-only", "superAdministrators"]
)

# Strategy for valid OIDC configs with random default group assignment
oidc_with_default_group = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("oidc"),
    identity_provider_name=non_empty_strings,
    identity_provider_oidc_issuer_url=valid_https_urls,
    identity_provider_oidc_client_id=non_empty_strings,
    identity_provider_default_group_assignment=valid_default_groups,
)

# Strategy for valid SAML configs with random default group assignment
saml_with_default_group = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("saml"),
    identity_provider_name=non_empty_strings,
    identity_provider_metadata_url=valid_saml_metadata_urls,
    identity_provider_default_group_assignment=valid_default_groups,
)


# --- Property 1 Tests ---


@pytest.mark.property
# Feature: federated-user-default-group, Property 1: Valid Default Group Acceptance
class TestValidDefaultGroupAcceptance:
    """
    Property 1: Valid Default Group Acceptance
    **Validates: Requirements 1.1, 1.2, 1.4**

    For any identity provider configuration with identity_provider_method set to
    "oidc" or "saml", the Config_Validator should accept the configuration when
    identity_provider_default_group_assignment is either None or one of
    ["editors", "read-only", "superAdministrators"].
    """

    @given(config=oidc_with_default_group)
    @settings(max_examples=100)
    def test_oidc_accepts_valid_default_group(self, config):
        """OIDC configs accept valid default group assignments (including None)."""
        # Feature: federated-user-default-group, Property 1: Valid Default Group Acceptance
        # **Validates: Requirements 1.1, 1.2, 1.4**
        assert config.identity_provider_method == "oidc"
        assert config.identity_provider_default_group_assignment in (
            None,
            "editors",
            "read-only",
            "superAdministrators",
        )

    @given(config=saml_with_default_group)
    @settings(max_examples=100)
    def test_saml_accepts_valid_default_group(self, config):
        """SAML configs accept valid default group assignments (including None)."""
        # Feature: federated-user-default-group, Property 1: Valid Default Group Acceptance
        # **Validates: Requirements 1.1, 1.2, 1.4**
        assert config.identity_provider_method == "saml"
        assert config.identity_provider_default_group_assignment in (
            None,
            "editors",
            "read-only",
            "superAdministrators",
        )


# --- Strategies for Property 2 ---

VALID_GROUPS = ["editors", "read-only", "superAdministrators"]

# Strings that are NOT valid default groups
invalid_default_groups = st.text(min_size=1).filter(lambda s: s not in VALID_GROUPS)

# Strategy for OIDC configs with invalid default group assignment
oidc_with_invalid_default_group = st.fixed_dictionaries(
    {
        "identity_provider_method": st.just("oidc"),
        "identity_provider_name": non_empty_strings,
        "identity_provider_oidc_issuer_url": valid_https_urls,
        "identity_provider_oidc_client_id": non_empty_strings,
        "identity_provider_default_group_assignment": invalid_default_groups,
    }
)

# Strategy for SAML configs with invalid default group assignment
saml_with_invalid_default_group = st.fixed_dictionaries(
    {
        "identity_provider_method": st.just("saml"),
        "identity_provider_name": non_empty_strings,
        "identity_provider_metadata_url": valid_saml_metadata_urls,
        "identity_provider_default_group_assignment": invalid_default_groups,
    }
)


# --- Property 2 Tests ---


@pytest.mark.property
# Feature: federated-user-default-group, Property 2: Invalid Default Group Rejection
class TestInvalidDefaultGroupRejection:
    """
    Property 2: Invalid Default Group Rejection
    **Validates: Requirements 1.2, 1.3**

    For any identity provider configuration with identity_provider_method set to
    "oidc" or "saml", and for any string value for
    identity_provider_default_group_assignment that is not one of
    ["editors", "read-only", "superAdministrators"], the Config_Validator should
    raise a validation error whose message identifies the invalid group name and
    lists the valid options.
    """

    @given(data=oidc_with_invalid_default_group)
    @settings(max_examples=100)
    def test_oidc_rejects_invalid_default_group(self, data):
        """OIDC configs reject invalid default group assignments with descriptive error."""
        # Feature: federated-user-default-group, Property 2: Invalid Default Group Rejection
        # **Validates: Requirements 1.2, 1.3**
        invalid_value = data["identity_provider_default_group_assignment"]
        with pytest.raises(ValidationError) as exc_info:
            IdentityProviderConfig(**data)
        error_message = str(exc_info.value)
        assert invalid_value in error_message
        for group in VALID_GROUPS:
            assert group in error_message

    @given(data=saml_with_invalid_default_group)
    @settings(max_examples=100)
    def test_saml_rejects_invalid_default_group(self, data):
        """SAML configs reject invalid default group assignments with descriptive error."""
        # Feature: federated-user-default-group, Property 2: Invalid Default Group Rejection
        # **Validates: Requirements 1.2, 1.3**
        invalid_value = data["identity_provider_default_group_assignment"]
        with pytest.raises(ValidationError) as exc_info:
            IdentityProviderConfig(**data)
        error_message = str(exc_info.value)
        assert invalid_value in error_message
        for group in VALID_GROUPS:
            assert group in error_message


# --- Strategies for Property 3 ---

# Any value for default group assignment (None or arbitrary text)
any_default_group = st.one_of(st.none(), st.text())

# Strategy for cognito configs with any default group assignment value
cognito_with_any_default_group = st.fixed_dictionaries(
    {
        "identity_provider_method": st.just("cognito"),
        "identity_provider_default_group_assignment": any_default_group,
    }
)


# --- Property 3 Tests ---


@pytest.mark.property
# Feature: federated-user-default-group, Property 3: Cognito Provider Ignores Default Group
class TestCognitoProviderIgnoresDefaultGroup:
    """
    Property 3: Cognito Provider Ignores Default Group
    **Validates: Requirements 1.5**

    For any identity provider configuration with identity_provider_method set to
    "cognito", the Config_Validator should accept the configuration regardless of
    the value of identity_provider_default_group_assignment (including invalid
    group names and None).
    """

    @given(data=cognito_with_any_default_group)
    @settings(max_examples=100)
    def test_cognito_accepts_any_default_group(self, data):
        """Cognito configs accept any default group assignment value without error."""
        # Feature: federated-user-default-group, Property 3: Cognito Provider Ignores Default Group
        # **Validates: Requirements 1.5**
        config = IdentityProviderConfig(**data)
        assert config.identity_provider_method == "cognito"
        assert config.identity_provider_default_group_assignment == data["identity_provider_default_group_assignment"]


# --- Strategies for Property 4 ---

# Valid default groups (non-None only, since we want to test round-trip of set values)
valid_default_groups_non_none = st.sampled_from(
    ["editors", "read-only", "superAdministrators"]
)

# Strategy for valid OIDC configs with default group assignment set
oidc_with_set_default_group = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("oidc"),
    identity_provider_name=non_empty_strings,
    identity_provider_oidc_issuer_url=valid_https_urls,
    identity_provider_oidc_client_id=non_empty_strings,
    identity_provider_default_group_assignment=valid_default_groups_non_none,
)

# Strategy for valid SAML configs with default group assignment set
saml_with_set_default_group = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("saml"),
    identity_provider_name=non_empty_strings,
    identity_provider_metadata_url=valid_saml_metadata_urls,
    identity_provider_default_group_assignment=valid_default_groups_non_none,
)

# Combined strategy for any valid config with default group set
valid_config_with_default_group = st.one_of(
    oidc_with_set_default_group, saml_with_set_default_group
)


# --- Property 4 Tests ---


@pytest.mark.property
# Feature: federated-user-default-group, Property 4: Default Group Configuration Round-Trip
class TestDefaultGroupConfigurationRoundTrip:
    """
    Property 4: Default Group Configuration Round-Trip
    **Validates: Requirements 1.6**

    For any valid identity provider configuration containing
    identity_provider_default_group_assignment, serializing to JSON and
    deserializing back should produce an equivalent configuration object
    preserving the field value.
    """

    @given(config=valid_config_with_default_group)
    @settings(max_examples=100)
    def test_round_trip_preserves_default_group(self, config):
        """Serializing and deserializing a valid config preserves the default group assignment."""
        # Feature: federated-user-default-group, Property 4: Default Group Configuration Round-Trip
        # **Validates: Requirements 1.6**
        json_str = config.model_dump_json()
        restored = IdentityProviderConfig.model_validate_json(json_str)
        assert restored.identity_provider_default_group_assignment == config.identity_provider_default_group_assignment

    @given(config=valid_config_with_default_group)
    @settings(max_examples=100)
    def test_round_trip_preserves_all_fields(self, config):
        """Serializing and deserializing a valid config preserves all field values."""
        # Feature: federated-user-default-group, Property 4: Default Group Configuration Round-Trip
        # **Validates: Requirements 1.6**
        json_str = config.model_dump_json()
        restored = IdentityProviderConfig.model_validate_json(json_str)
        assert restored == config
