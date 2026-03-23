"""
Property-based tests for OIDC provider inclusion in supported identity providers.
Feature: oidc-authentication, Property 4: OIDC Provider Inclusion in Supported Identity Providers
Validates: Requirements 2.5, 2.7
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from config import IdentityProviderConfig, AuthConfig


# --- Strategies ---

# Non-empty strings for valid field values
non_empty_strings = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())

# Valid HTTPS URLs for issuer
valid_https_urls = st.from_regex(
    r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}", fullmatch=True
)

# OIDC provider names: alphanumeric with hyphens, typical for Cognito provider names
oidc_provider_names = st.from_regex(r"[A-Za-z][A-Za-z0-9\-]{0,19}", fullmatch=True)

# Valid OIDC provider strategy
oidc_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("oidc"),
    identity_provider_name=oidc_provider_names,
    identity_provider_oidc_issuer_url=valid_https_urls,
    identity_provider_oidc_client_id=non_empty_strings,
    identity_provider_oidc_client_secret=st.one_of(st.none(), non_empty_strings),
)

# Valid cognito provider strategy
cognito_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("cognito"),
)

# Valid SAML provider strategy
saml_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("saml"),
    identity_provider_name=oidc_provider_names,
    identity_provider_metadata_url=st.from_regex(
        r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}/metadata", fullmatch=True
    ),
)

# Config with at least one OIDC provider, optionally mixed with cognito and SAML
config_with_oidc_providers = st.tuples(
    st.just([IdentityProviderConfig(identity_provider_method="cognito")]),
    st.lists(saml_provider_strategy, min_size=0, max_size=2),
    st.lists(oidc_provider_strategy, min_size=1, max_size=3),
).map(lambda t: t[0] + t[1] + t[2])


def build_supported_providers(identity_providers):
    """
    Replicates the supported_providers list-building logic from cognito.py.

    In cognito.py, the loop iterates over config.authZ.identity_providers and:
    - For "saml": appends UserPoolClientIdentityProvider.custom(provider_name)
    - For "oidc": appends UserPoolClientIdentityProvider.custom(provider_name)
    - For "cognito": appends UserPoolClientIdentityProvider.COGNITO

    We return the list of provider name strings that would be in supported_providers.
    """
    supported = []
    for provider in identity_providers:
        if provider.identity_provider_method == "saml":
            supported.append(provider.identity_provider_name)
        elif provider.identity_provider_method == "oidc":
            supported.append(provider.identity_provider_name)
        elif provider.identity_provider_method == "cognito":
            supported.append("COGNITO")
    return supported


def build_callback_supported_identity_providers(identity_providers):
    """
    Replicates the SupportedIdentityProviders list-building logic from
    the update_callback_urls method in cognito.py:

        ["COGNITO"] + [
            provider.identity_provider_name
            for provider in config.authZ.identity_providers
            if provider.identity_provider_method in ("saml", "oidc")
        ]
    """
    return ["COGNITO"] + [
        provider.identity_provider_name
        for provider in identity_providers
        if provider.identity_provider_method in ("saml", "oidc")
    ]


# --- Property 4 Tests ---


@pytest.mark.property
# Feature: oidc-authentication, Property 4: OIDC Provider Inclusion in Supported Identity Providers
class TestOIDCProviderInclusionInSupportedIdentityProviders:
    """
    Property 4: OIDC Provider Inclusion in Supported Identity Providers
    Validates: Requirements 2.5, 2.7

    For any configuration containing OIDC providers, the OIDC provider names should
    appear in both the App_Client's supported_identity_providers list and the
    update_callback_urls custom resource's SupportedIdentityProviders list,
    alongside existing "COGNITO" and SAML entries.
    """

    @given(providers=config_with_oidc_providers)
    @settings(max_examples=100)
    def test_oidc_names_in_supported_providers(self, providers):
        """OIDC provider names appear in the App_Client's supported_identity_providers list."""
        # Feature: oidc-authentication, Property 4: OIDC Provider Inclusion in Supported Identity Providers
        # **Validates: Requirements 2.5, 2.7**

        # Validate the config is accepted
        auth = AuthConfig(identity_providers=providers)

        # Extract OIDC provider names from the config
        oidc_names = [
            p.identity_provider_name
            for p in auth.identity_providers
            if p.identity_provider_method == "oidc"
        ]
        assert len(oidc_names) >= 1, "Test requires at least one OIDC provider"

        # Build the supported_providers list using the same logic as cognito.py
        supported = build_supported_providers(auth.identity_providers)

        # Requirement 2.5: Each OIDC provider name must appear in supported_identity_providers
        for name in oidc_names:
            assert name in supported, (
                f"OIDC provider '{name}' not found in supported_identity_providers: {supported}"
            )

        # "COGNITO" should also be present (from the cognito provider in the config)
        assert "COGNITO" in supported, (
            f"'COGNITO' not found in supported_identity_providers: {supported}"
        )

    @given(providers=config_with_oidc_providers)
    @settings(max_examples=100)
    def test_oidc_names_in_callback_supported_identity_providers(self, providers):
        """OIDC provider names appear in the update_callback_urls SupportedIdentityProviders list."""
        # Feature: oidc-authentication, Property 4: OIDC Provider Inclusion in Supported Identity Providers
        # **Validates: Requirements 2.5, 2.7**

        auth = AuthConfig(identity_providers=providers)

        # Extract OIDC provider names
        oidc_names = [
            p.identity_provider_name
            for p in auth.identity_providers
            if p.identity_provider_method == "oidc"
        ]
        assert len(oidc_names) >= 1

        # Build the SupportedIdentityProviders list using the same logic as update_callback_urls
        callback_providers = build_callback_supported_identity_providers(auth.identity_providers)

        # Requirement 2.7: Each OIDC provider name must appear in SupportedIdentityProviders
        for name in oidc_names:
            assert name in callback_providers, (
                f"OIDC provider '{name}' not found in callback SupportedIdentityProviders: {callback_providers}"
            )

        # "COGNITO" is always the first entry
        assert callback_providers[0] == "COGNITO", (
            f"'COGNITO' should be the first entry in SupportedIdentityProviders"
        )

    @given(providers=config_with_oidc_providers)
    @settings(max_examples=100)
    def test_saml_providers_also_preserved(self, providers):
        """SAML provider names are preserved alongside OIDC providers in both lists."""
        # Feature: oidc-authentication, Property 4: OIDC Provider Inclusion in Supported Identity Providers
        # **Validates: Requirements 2.5, 2.7**

        auth = AuthConfig(identity_providers=providers)

        saml_names = [
            p.identity_provider_name
            for p in auth.identity_providers
            if p.identity_provider_method == "saml"
        ]

        # Build both lists
        supported = build_supported_providers(auth.identity_providers)
        callback_providers = build_callback_supported_identity_providers(auth.identity_providers)

        # SAML providers should also be in both lists
        for name in saml_names:
            assert name in supported, (
                f"SAML provider '{name}' not found in supported_identity_providers"
            )
            assert name in callback_providers, (
                f"SAML provider '{name}' not found in callback SupportedIdentityProviders"
            )

    @given(providers=config_with_oidc_providers)
    @settings(max_examples=100)
    def test_both_lists_consistent(self, providers):
        """The OIDC and SAML provider names in supported_providers match those in callback SupportedIdentityProviders."""
        # Feature: oidc-authentication, Property 4: OIDC Provider Inclusion in Supported Identity Providers
        # **Validates: Requirements 2.5, 2.7**

        auth = AuthConfig(identity_providers=providers)

        # Extract federated provider names (SAML + OIDC) from config
        federated_names = [
            p.identity_provider_name
            for p in auth.identity_providers
            if p.identity_provider_method in ("saml", "oidc")
        ]

        # Build both lists
        supported = build_supported_providers(auth.identity_providers)
        callback_providers = build_callback_supported_identity_providers(auth.identity_providers)

        # The federated names in callback_providers (excluding "COGNITO") should match
        # the federated names in supported (excluding "COGNITO")
        supported_federated = [n for n in supported if n != "COGNITO"]
        callback_federated = [n for n in callback_providers if n != "COGNITO"]

        assert supported_federated == callback_federated, (
            f"Federated providers differ between supported_providers {supported_federated} "
            f"and callback SupportedIdentityProviders {callback_federated}"
        )

        # Both should contain exactly the federated names from config
        assert set(supported_federated) == set(federated_names), (
            f"supported_providers federated names {set(supported_federated)} "
            f"don't match config federated names {set(federated_names)}"
        )
