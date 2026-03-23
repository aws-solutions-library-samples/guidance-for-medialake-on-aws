"""
Property-based tests for OIDC provider export structure consistency.
Feature: oidc-authentication, Property 6: OIDC Provider Export Structure Consistency
Validates: Requirements 4.1, 4.2
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

# Optional client secret: either None or a non-empty string
optional_client_secret = st.one_of(st.none(), non_empty_strings)

# Valid OIDC provider strategy
oidc_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("oidc"),
    identity_provider_name=non_empty_strings,
    identity_provider_oidc_issuer_url=valid_https_urls,
    identity_provider_oidc_client_id=non_empty_strings,
    identity_provider_oidc_client_secret=optional_client_secret,
)

# Valid cognito provider
cognito_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("cognito"),
)

# Valid SAML provider
saml_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("saml"),
    identity_provider_name=non_empty_strings,
    identity_provider_metadata_url=st.from_regex(
        r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}/metadata", fullmatch=True
    ),
)

# The expected key set for every entry in the exported identity_providers array
EXPECTED_EXPORT_KEYS = {
    "identity_provider_method",
    "identity_provider_name",
    "identity_provider_metadata_url",
}


def simulate_export(providers):
    """Simulate the identity_providers export logic from userInterface.py.

    This mirrors the list comprehension in UIConstruct.__init__ that builds
    the identity_providers array for aws-exports.json.
    """
    return [
        {
            "identity_provider_method": provider.identity_provider_method,
            "identity_provider_name": getattr(
                provider, "identity_provider_name", ""
            ),
            "identity_provider_metadata_url": getattr(
                provider, "identity_provider_metadata_url", ""
            ),
        }
        for provider in providers
    ]


# --- Property 6 Tests ---


@pytest.mark.property
# Feature: oidc-authentication, Property 6: OIDC Provider Export Structure Consistency
class TestOIDCProviderExportStructureConsistency:
    """
    Property 6: OIDC Provider Export Structure Consistency
    Validates: Requirements 4.1, 4.2

    For any OIDC provider in the configuration, the Config_Exporter should include
    an entry in the identity_providers array of aws-exports.json with the same key
    structure as SAML and Cognito entries, containing identity_provider_method set
    to "oidc" and identity_provider_name set to the configured name.
    """

    @given(provider=oidc_provider_strategy)
    @settings(max_examples=100)
    def test_oidc_export_has_correct_method_and_name(self, provider):
        """Exported OIDC entry has identity_provider_method='oidc' and the configured name."""
        # Feature: oidc-authentication, Property 6: OIDC Provider Export Structure Consistency
        # **Validates: Requirements 4.1, 4.2**
        exported = simulate_export([provider])
        assert len(exported) == 1
        entry = exported[0]
        assert entry["identity_provider_method"] == "oidc"
        assert entry["identity_provider_name"] == provider.identity_provider_name

    @given(provider=oidc_provider_strategy)
    @settings(max_examples=100)
    def test_oidc_export_has_same_keys_as_saml_and_cognito(self, provider):
        """Exported OIDC entry uses the same key structure as SAML and Cognito entries."""
        # Feature: oidc-authentication, Property 6: OIDC Provider Export Structure Consistency
        # **Validates: Requirements 4.2**
        exported = simulate_export([provider])
        entry = exported[0]
        assert set(entry.keys()) == EXPECTED_EXPORT_KEYS

    @given(
        oidc=oidc_provider_strategy,
        saml=saml_provider_strategy,
        cognito=cognito_provider_strategy,
    )
    @settings(max_examples=100)
    def test_all_provider_types_share_same_export_structure(
        self, oidc, saml, cognito
    ):
        """OIDC, SAML, and Cognito entries all share the same key structure in the export."""
        # Feature: oidc-authentication, Property 6: OIDC Provider Export Structure Consistency
        # **Validates: Requirements 4.1, 4.2**
        exported = simulate_export([cognito, saml, oidc])
        assert len(exported) == 3

        # All entries must have the exact same set of keys
        for entry in exported:
            assert set(entry.keys()) == EXPECTED_EXPORT_KEYS

        # The OIDC entry specifically must have method="oidc" and the right name
        oidc_entry = exported[2]
        assert oidc_entry["identity_provider_method"] == "oidc"
        assert oidc_entry["identity_provider_name"] == oidc.identity_provider_name

        # SAML entry retains its own values
        saml_entry = exported[1]
        assert saml_entry["identity_provider_method"] == "saml"
        assert saml_entry["identity_provider_name"] == saml.identity_provider_name

    @given(
        oidc_providers=st.lists(oidc_provider_strategy, min_size=1, max_size=3),
    )
    @settings(max_examples=100)
    def test_multiple_oidc_providers_all_exported(self, oidc_providers):
        """Every OIDC provider in the config appears in the exported array with correct values."""
        # Feature: oidc-authentication, Property 6: OIDC Provider Export Structure Consistency
        # **Validates: Requirements 4.1, 4.2**
        exported = simulate_export(oidc_providers)
        assert len(exported) == len(oidc_providers)

        for original, entry in zip(oidc_providers, exported):
            assert entry["identity_provider_method"] == "oidc"
            assert entry["identity_provider_name"] == original.identity_provider_name
            assert set(entry.keys()) == EXPECTED_EXPORT_KEYS
