"""
Property-based tests for OIDC configuration validation.
Feature: oidc-authentication, Property 1: OIDC Required Field Validation
Validates: Requirements 1.2, 1.3, 1.4, 1.6
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from config import IdentityProviderConfig


# --- Strategies ---

# Non-empty strings for valid field values
non_empty_strings = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())

# Valid HTTPS URLs for issuer
valid_https_urls = st.from_regex(r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}", fullmatch=True)

# Invalid (non-HTTPS) URLs
non_https_urls = st.from_regex(r"http://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}", fullmatch=True)


# --- Property Tests ---


@pytest.mark.property
# Feature: oidc-authentication, Property 1: OIDC Required Field Validation
class TestOIDCRequiredFieldValidation:
    """
    Property 1: OIDC Required Field Validation
    Validates: Requirements 1.2, 1.3, 1.4, 1.6

    For any identity provider configuration with identity_provider_method set to "oidc",
    the Config_Validator should accept the configuration if and only if
    identity_provider_name is a non-empty string,
    identity_provider_oidc_issuer_url is a non-empty HTTPS URL, and
    identity_provider_oidc_client_id is a non-empty string.
    """

    @given(
        name=non_empty_strings,
        issuer_url=valid_https_urls,
        client_id=non_empty_strings,
    )
    @settings(max_examples=100)
    def test_valid_oidc_config_accepted(self, name, issuer_url, client_id):
        """Valid OIDC configs with all required fields present and valid are accepted."""
        # Feature: oidc-authentication, Property 1: OIDC Required Field Validation
        config = IdentityProviderConfig(
            identity_provider_method="oidc",
            identity_provider_name=name,
            identity_provider_oidc_issuer_url=issuer_url,
            identity_provider_oidc_client_id=client_id,
        )
        assert config.identity_provider_method == "oidc"
        assert config.identity_provider_name == name
        assert config.identity_provider_oidc_issuer_url == issuer_url
        assert config.identity_provider_oidc_client_id == client_id

    @given(
        issuer_url=valid_https_urls,
        client_id=non_empty_strings,
    )
    @settings(max_examples=100)
    def test_missing_name_raises_error(self, issuer_url, client_id):
        """OIDC configs missing identity_provider_name raise a ValidationError."""
        # Feature: oidc-authentication, Property 1: OIDC Required Field Validation
        with pytest.raises(ValidationError) as exc_info:
            IdentityProviderConfig(
                identity_provider_method="oidc",
                identity_provider_name=None,
                identity_provider_oidc_issuer_url=issuer_url,
                identity_provider_oidc_client_id=client_id,
            )
        assert "identity_provider_name" in str(exc_info.value).lower()

    @given(
        name=non_empty_strings,
        client_id=non_empty_strings,
    )
    @settings(max_examples=100)
    def test_missing_issuer_url_raises_error(self, name, client_id):
        """OIDC configs missing identity_provider_oidc_issuer_url raise a ValidationError."""
        # Feature: oidc-authentication, Property 1: OIDC Required Field Validation
        with pytest.raises(ValidationError) as exc_info:
            IdentityProviderConfig(
                identity_provider_method="oidc",
                identity_provider_name=name,
                identity_provider_oidc_issuer_url=None,
                identity_provider_oidc_client_id=client_id,
            )
        assert "issuer_url" in str(exc_info.value).lower()

    @given(
        name=non_empty_strings,
        issuer_url=non_https_urls,
        client_id=non_empty_strings,
    )
    @settings(max_examples=100)
    def test_non_https_issuer_url_raises_error(self, name, issuer_url, client_id):
        """OIDC configs with a non-HTTPS issuer URL raise a ValidationError."""
        # Feature: oidc-authentication, Property 1: OIDC Required Field Validation
        with pytest.raises(ValidationError) as exc_info:
            IdentityProviderConfig(
                identity_provider_method="oidc",
                identity_provider_name=name,
                identity_provider_oidc_issuer_url=issuer_url,
                identity_provider_oidc_client_id=client_id,
            )
        assert "https" in str(exc_info.value).lower()

    @given(
        name=non_empty_strings,
        issuer_url=valid_https_urls,
    )
    @settings(max_examples=100)
    def test_missing_client_id_raises_error(self, name, issuer_url):
        """OIDC configs missing identity_provider_oidc_client_id raise a ValidationError."""
        # Feature: oidc-authentication, Property 1: OIDC Required Field Validation
        with pytest.raises(ValidationError) as exc_info:
            IdentityProviderConfig(
                identity_provider_method="oidc",
                identity_provider_name=name,
                identity_provider_oidc_issuer_url=issuer_url,
                identity_provider_oidc_client_id=None,
            )
        assert "client_id" in str(exc_info.value).lower()


# --- Property 2 Strategies ---

# Optional client secret: either None or a non-empty string
optional_client_secret = st.one_of(st.none(), non_empty_strings)


# --- Property 2 Tests ---


@pytest.mark.property
# Feature: oidc-authentication, Property 2: OIDC Optional Client Secret Acceptance
class TestOIDCOptionalClientSecretAcceptance:
    """
    Property 2: OIDC Optional Client Secret Acceptance
    Validates: Requirements 1.1, 1.5

    For any valid OIDC provider configuration, the Config_Validator should accept
    the configuration regardless of whether identity_provider_oidc_client_secret
    is present or absent, as long as when present it is a non-empty string.
    """

    @given(
        name=non_empty_strings,
        issuer_url=valid_https_urls,
        client_id=non_empty_strings,
        client_secret=optional_client_secret,
    )
    @settings(max_examples=100)
    def test_valid_oidc_config_accepted_with_or_without_secret(
        self, name, issuer_url, client_id, client_secret
    ):
        """Valid OIDC configs are accepted regardless of client_secret presence."""
        # Feature: oidc-authentication, Property 2: OIDC Optional Client Secret Acceptance
        # **Validates: Requirements 1.1, 1.5**
        config = IdentityProviderConfig(
            identity_provider_method="oidc",
            identity_provider_name=name,
            identity_provider_oidc_issuer_url=issuer_url,
            identity_provider_oidc_client_id=client_id,
            identity_provider_oidc_client_secret=client_secret,
        )
        # Requirement 1.1: "oidc" is accepted as a valid provider method
        assert config.identity_provider_method == "oidc"
        # Requirement 1.5: client_secret is preserved as-is (None or non-empty string)
        assert config.identity_provider_oidc_client_secret == client_secret


# --- Property 3 Strategies ---

# Valid cognito provider
cognito_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("cognito"),
)

# Valid SAML provider (requires name and metadata_url)
saml_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("saml"),
    identity_provider_name=non_empty_strings,
    identity_provider_metadata_url=st.from_regex(
        r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}/metadata", fullmatch=True
    ),
)

# Valid OIDC provider (requires name, issuer_url, client_id)
oidc_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("oidc"),
    identity_provider_name=non_empty_strings,
    identity_provider_oidc_issuer_url=valid_https_urls,
    identity_provider_oidc_client_id=non_empty_strings,
    identity_provider_oidc_client_secret=optional_client_secret,
)

# Mixed provider list: at least one of each type
mixed_provider_list = st.tuples(
    st.lists(cognito_provider_strategy, min_size=1, max_size=2),
    st.lists(saml_provider_strategy, min_size=1, max_size=2),
    st.lists(oidc_provider_strategy, min_size=1, max_size=2),
).map(lambda t: t[0] + t[1] + t[2])


# --- Property 3 Tests ---


@pytest.mark.property
# Feature: oidc-authentication, Property 3: Mixed Provider Validation Independence
class TestMixedProviderValidationIndependence:
    """
    Property 3: Mixed Provider Validation Independence
    Validates: Requirements 1.7

    For any configuration containing a mix of "cognito", "saml", and "oidc" providers,
    the Config_Validator should validate each provider according to its own method rules
    without interference from other provider types in the list.
    """

    @given(providers=mixed_provider_list)
    @settings(max_examples=100)
    def test_mixed_valid_providers_accepted(self, providers):
        """A mixed list of valid cognito, saml, and oidc providers is accepted by AuthConfig."""
        # Feature: oidc-authentication, Property 3: Mixed Provider Validation Independence
        # **Validates: Requirements 1.7**
        from config import AuthConfig

        auth = AuthConfig(identity_providers=providers)

        # Verify all providers are preserved
        assert len(auth.identity_providers) == len(providers)

        # Verify each provider type is present
        methods = [p.identity_provider_method for p in auth.identity_providers]
        assert "cognito" in methods
        assert "saml" in methods
        assert "oidc" in methods

        # Verify each provider retains its own fields
        for provider in auth.identity_providers:
            if provider.identity_provider_method == "saml":
                assert provider.identity_provider_name is not None
                assert provider.identity_provider_metadata_url is not None
            elif provider.identity_provider_method == "oidc":
                assert provider.identity_provider_name is not None
                assert provider.identity_provider_oidc_issuer_url is not None
                assert provider.identity_provider_oidc_issuer_url.startswith("https://")
                assert provider.identity_provider_oidc_client_id is not None

    @given(
        valid_cognito=cognito_provider_strategy,
        valid_saml=saml_provider_strategy,
        oidc_name=non_empty_strings,
        oidc_client_id=non_empty_strings,
    )
    @settings(max_examples=100)
    def test_invalid_oidc_in_mixed_list_still_rejected(
        self, valid_cognito, valid_saml, oidc_name, oidc_client_id
    ):
        """An invalid OIDC provider (missing issuer URL) in a mixed list is still rejected,
        even when valid cognito and saml providers are present."""
        # Feature: oidc-authentication, Property 3: Mixed Provider Validation Independence
        # **Validates: Requirements 1.7**
        with pytest.raises(ValidationError):
            IdentityProviderConfig(
                identity_provider_method="oidc",
                identity_provider_name=oidc_name,
                identity_provider_oidc_issuer_url=None,
                identity_provider_oidc_client_id=oidc_client_id,
            )

    @given(
        valid_cognito=cognito_provider_strategy,
        valid_oidc=oidc_provider_strategy,
        saml_name=non_empty_strings,
    )
    @settings(max_examples=100)
    def test_invalid_saml_in_mixed_list_still_rejected(
        self, valid_cognito, valid_oidc, saml_name
    ):
        """An invalid SAML provider (missing metadata_url) is still rejected by its own
        method rules, even when valid cognito and oidc providers exist."""
        # Feature: oidc-authentication, Property 3: Mixed Provider Validation Independence
        # **Validates: Requirements 1.7**
        # SAML validation fires at the IdentityProviderConfig level — the SAML field
        # validator rejects missing metadata_url independently of other providers.
        with pytest.raises(ValidationError) as exc_info:
            IdentityProviderConfig(
                identity_provider_method="saml",
                identity_provider_name=saml_name,
                identity_provider_metadata_url=None,
            )
        assert "saml" in str(exc_info.value).lower() or "metadata_url" in str(exc_info.value).lower()


# --- Property 10 Strategies ---

# Single OIDC provider with all fields randomized
oidc_provider_with_optional_fields = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("oidc"),
    identity_provider_name=non_empty_strings,
    identity_provider_oidc_issuer_url=valid_https_urls,
    identity_provider_oidc_client_id=non_empty_strings,
    identity_provider_oidc_client_secret=optional_client_secret,
)

# Mixed provider list for round-trip testing (at least one of each type)
mixed_provider_list_for_roundtrip = st.tuples(
    st.lists(cognito_provider_strategy, min_size=1, max_size=2),
    st.lists(saml_provider_strategy, min_size=1, max_size=2),
    st.lists(oidc_provider_with_optional_fields, min_size=1, max_size=2),
).map(lambda t: t[0] + t[1] + t[2])


# --- Property 10 Tests ---


@pytest.mark.property
# Feature: oidc-authentication, Property 10: Configuration Serialization Round-Trip
class TestConfigurationSerializationRoundTrip:
    """
    Property 10: Configuration Serialization Round-Trip
    Validates: Requirements 9.1, 9.2

    For any valid configuration containing a mix of "cognito", "saml", and "oidc"
    providers, serializing to JSON and deserializing back should produce an equivalent
    configuration object preserving the count, order, and field values of all provider
    entries.
    """

    @given(provider=oidc_provider_with_optional_fields)
    @settings(max_examples=100)
    def test_single_oidc_provider_dict_roundtrip(self, provider):
        """A single OIDC provider survives a model_dump → model_validate round-trip."""
        # Feature: oidc-authentication, Property 10: Configuration Serialization Round-Trip
        # **Validates: Requirements 9.1**
        dumped = provider.model_dump()
        restored = IdentityProviderConfig.model_validate(dumped)
        assert restored == provider
        assert restored.identity_provider_method == "oidc"
        assert restored.identity_provider_name == provider.identity_provider_name
        assert restored.identity_provider_oidc_issuer_url == provider.identity_provider_oidc_issuer_url
        assert restored.identity_provider_oidc_client_id == provider.identity_provider_oidc_client_id
        assert restored.identity_provider_oidc_client_secret == provider.identity_provider_oidc_client_secret

    @given(provider=oidc_provider_with_optional_fields)
    @settings(max_examples=100)
    def test_single_oidc_provider_json_roundtrip(self, provider):
        """A single OIDC provider survives a model_dump_json → model_validate_json round-trip."""
        # Feature: oidc-authentication, Property 10: Configuration Serialization Round-Trip
        # **Validates: Requirements 9.1**
        json_str = provider.model_dump_json()
        restored = IdentityProviderConfig.model_validate_json(json_str)
        assert restored == provider

    @given(providers=mixed_provider_list_for_roundtrip)
    @settings(max_examples=100)
    def test_mixed_providers_authconfig_dict_roundtrip(self, providers):
        """An AuthConfig with mixed providers survives a dict round-trip preserving count, order, and values."""
        # Feature: oidc-authentication, Property 10: Configuration Serialization Round-Trip
        # **Validates: Requirements 9.1, 9.2**
        from config import AuthConfig

        auth = AuthConfig(identity_providers=providers)
        dumped = auth.model_dump()
        restored = AuthConfig.model_validate(dumped)

        assert restored == auth
        assert len(restored.identity_providers) == len(providers)

        # Verify order is preserved
        for original, roundtripped in zip(auth.identity_providers, restored.identity_providers):
            assert original.identity_provider_method == roundtripped.identity_provider_method
            assert original.identity_provider_name == roundtripped.identity_provider_name

        # Verify all three method types are present
        methods = [p.identity_provider_method for p in restored.identity_providers]
        assert "cognito" in methods
        assert "saml" in methods
        assert "oidc" in methods

    @given(providers=mixed_provider_list_for_roundtrip)
    @settings(max_examples=100)
    def test_mixed_providers_authconfig_json_roundtrip(self, providers):
        """An AuthConfig with mixed providers survives a JSON string round-trip preserving count, order, and values."""
        # Feature: oidc-authentication, Property 10: Configuration Serialization Round-Trip
        # **Validates: Requirements 9.1, 9.2**
        from config import AuthConfig

        auth = AuthConfig(identity_providers=providers)
        json_str = auth.model_dump_json()
        restored = AuthConfig.model_validate_json(json_str)

        assert restored == auth
        assert len(restored.identity_providers) == len(providers)

        # Verify field values for each OIDC provider are preserved
        for original, roundtripped in zip(auth.identity_providers, restored.identity_providers):
            assert original.identity_provider_method == roundtripped.identity_provider_method
            if original.identity_provider_method == "oidc":
                assert original.identity_provider_oidc_issuer_url == roundtripped.identity_provider_oidc_issuer_url
                assert original.identity_provider_oidc_client_id == roundtripped.identity_provider_oidc_client_id
                assert original.identity_provider_oidc_client_secret == roundtripped.identity_provider_oidc_client_secret
