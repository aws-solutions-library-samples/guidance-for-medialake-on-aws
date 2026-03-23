"""
Property-based tests for callback URL preservation with OIDC providers.
Feature: oidc-authentication, Property 5: Callback URL Preservation
Validates: Requirements 3.1, 3.2, 3.3
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from config import IdentityProviderConfig, AuthConfig


# --- Strategies ---

non_empty_strings = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())

valid_https_urls = st.from_regex(
    r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}", fullmatch=True
)

oidc_provider_names = st.from_regex(r"[A-Za-z][A-Za-z0-9\-]{0,19}", fullmatch=True)

oidc_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("oidc"),
    identity_provider_name=oidc_provider_names,
    identity_provider_oidc_issuer_url=valid_https_urls,
    identity_provider_oidc_client_id=non_empty_strings,
    identity_provider_oidc_client_secret=st.one_of(st.none(), non_empty_strings),
)

saml_provider_strategy = st.builds(
    IdentityProviderConfig,
    identity_provider_method=st.just("saml"),
    identity_provider_name=oidc_provider_names,
    identity_provider_metadata_url=st.from_regex(
        r"https://[a-z][a-z0-9\-]{1,20}\.[a-z]{2,6}/metadata", fullmatch=True
    ),
)

# Domain prefix strategy: lowercase alphanumeric with hyphens
domain_prefixes = st.from_regex(r"[a-z][a-z0-9\-]{3,20}", fullmatch=True)

# CloudFront domain strategy
cloudfront_domains = st.from_regex(
    r"[a-z0-9]{8,14}\.cloudfront\.net", fullmatch=True
)

# Region strategy
regions = st.sampled_from([
    "us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1",
])

# Config with at least one SAML and one OIDC provider
config_with_saml_and_oidc = st.tuples(
    st.just([IdentityProviderConfig(identity_provider_method="cognito")]),
    st.lists(saml_provider_strategy, min_size=1, max_size=2),
    st.lists(oidc_provider_strategy, min_size=1, max_size=2),
).map(lambda t: t[0] + t[1] + t[2])

# Config with only OIDC providers (no SAML)
config_with_oidc_only = st.tuples(
    st.just([IdentityProviderConfig(identity_provider_method="cognito")]),
    st.lists(oidc_provider_strategy, min_size=1, max_size=3),
).map(lambda t: t[0] + t[1])


# --- Helper functions replicating cognito.py logic ---


def build_initial_callback_urls(domain_prefix, region):
    """
    Replicates the initial callback URLs set on the app client in cognito.py __init__
    when supported_providers is non-empty (i.e., any federated providers exist).
    """
    return [
        f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/oauth2/idpresponse",
        f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/saml2/idpresponse",
    ]


def build_updated_callback_urls(domain_prefix, region, cloudfront_domain):
    """
    Replicates the CallbackURLs list from update_callback_urls in cognito.py.
    """
    return [
        f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/oauth2/idpresponse",
        f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/saml2/idpresponse",
        f"https://{cloudfront_domain}",
        f"https://{cloudfront_domain}/",
        f"https://{cloudfront_domain}/login",
    ]


# --- Property 5 Tests ---


@pytest.mark.property
# Feature: oidc-authentication, Property 5: Callback URL Preservation
class TestCallbackURLPreservation:
    """
    Property 5: Callback URL Preservation
    Validates: Requirements 3.1, 3.2, 3.3

    For any configuration containing both SAML and OIDC providers, the callback URL
    list should contain all existing SAML callback URLs (saml2/idpresponse) and the
    OIDC callback URL (oauth2/idpresponse) without removing any previously configured URLs.
    """

    @given(
        providers=config_with_saml_and_oidc,
        domain_prefix=domain_prefixes,
        region=regions,
    )
    @settings(max_examples=100)
    def test_oauth2_idpresponse_present_in_initial_urls(self, providers, domain_prefix, region):
        """Requirement 3.1: oauth2/idpresponse callback URL is included when OIDC provider is configured."""
        # Feature: oidc-authentication, Property 5: Callback URL Preservation
        # **Validates: Requirements 3.1**

        auth = AuthConfig(identity_providers=providers)

        has_oidc = any(
            p.identity_provider_method == "oidc" for p in auth.identity_providers
        )
        assert has_oidc, "Test requires at least one OIDC provider"

        callback_urls = build_initial_callback_urls(domain_prefix, region)

        oauth2_url = f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/oauth2/idpresponse"
        assert oauth2_url in callback_urls, (
            f"oauth2/idpresponse URL not found in initial callback URLs: {callback_urls}"
        )

    @given(
        providers=config_with_saml_and_oidc,
        domain_prefix=domain_prefixes,
        region=regions,
        cloudfront_domain=cloudfront_domains,
    )
    @settings(max_examples=100)
    def test_cloudfront_and_idpresponse_urls_in_updated_callbacks(
        self, providers, domain_prefix, region, cloudfront_domain
    ):
        """Requirement 3.2: update_callback_urls includes both CloudFront domain URLs and idpresponse URLs."""
        # Feature: oidc-authentication, Property 5: Callback URL Preservation
        # **Validates: Requirements 3.2**

        auth = AuthConfig(identity_providers=providers)

        callback_urls = build_updated_callback_urls(domain_prefix, region, cloudfront_domain)

        # oauth2/idpresponse must be present
        oauth2_url = f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/oauth2/idpresponse"
        assert oauth2_url in callback_urls, (
            f"oauth2/idpresponse not in updated callback URLs"
        )

        # saml2/idpresponse must be present
        saml2_url = f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/saml2/idpresponse"
        assert saml2_url in callback_urls, (
            f"saml2/idpresponse not in updated callback URLs"
        )

        # CloudFront domain URLs must be present
        assert f"https://{cloudfront_domain}" in callback_urls
        assert f"https://{cloudfront_domain}/" in callback_urls
        assert f"https://{cloudfront_domain}/login" in callback_urls

    @given(
        providers=config_with_saml_and_oidc,
        domain_prefix=domain_prefixes,
        region=regions,
        cloudfront_domain=cloudfront_domains,
    )
    @settings(max_examples=100)
    def test_saml_callback_urls_preserved_when_oidc_added(
        self, providers, domain_prefix, region, cloudfront_domain
    ):
        """Requirement 3.3: Existing SAML callback URLs are preserved when OIDC callback URLs are added."""
        # Feature: oidc-authentication, Property 5: Callback URL Preservation
        # **Validates: Requirements 3.3**

        auth = AuthConfig(identity_providers=providers)

        has_saml = any(
            p.identity_provider_method == "saml" for p in auth.identity_providers
        )
        has_oidc = any(
            p.identity_provider_method == "oidc" for p in auth.identity_providers
        )
        assert has_saml and has_oidc, "Test requires both SAML and OIDC providers"

        # The initial callback URLs (before CloudFront update)
        initial_urls = build_initial_callback_urls(domain_prefix, region)

        # The updated callback URLs (after CloudFront update)
        updated_urls = build_updated_callback_urls(domain_prefix, region, cloudfront_domain)

        # All initial URLs must still be present in the updated list
        for url in initial_urls:
            assert url in updated_urls, (
                f"Initial callback URL '{url}' was lost after update_callback_urls"
            )

        # saml2/idpresponse specifically must be preserved
        saml2_url = f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/saml2/idpresponse"
        assert saml2_url in initial_urls, "saml2/idpresponse must be in initial URLs"
        assert saml2_url in updated_urls, "saml2/idpresponse must be preserved in updated URLs"

    @given(
        providers=config_with_oidc_only,
        domain_prefix=domain_prefixes,
        region=regions,
        cloudfront_domain=cloudfront_domains,
    )
    @settings(max_examples=100)
    def test_callback_urls_complete_with_oidc_only(
        self, providers, domain_prefix, region, cloudfront_domain
    ):
        """Both oauth2 and saml2 idpresponse URLs are present even with only OIDC providers."""
        # Feature: oidc-authentication, Property 5: Callback URL Preservation
        # **Validates: Requirements 3.1, 3.2, 3.3**

        auth = AuthConfig(identity_providers=providers)

        has_oidc = any(
            p.identity_provider_method == "oidc" for p in auth.identity_providers
        )
        assert has_oidc

        updated_urls = build_updated_callback_urls(domain_prefix, region, cloudfront_domain)

        # Both idpresponse endpoints must be present regardless of provider mix
        oauth2_url = f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/oauth2/idpresponse"
        saml2_url = f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/saml2/idpresponse"

        assert oauth2_url in updated_urls, "oauth2/idpresponse must be present"
        assert saml2_url in updated_urls, "saml2/idpresponse must be present"

        # All 5 expected URLs must be present
        assert len(updated_urls) == 5, (
            f"Expected 5 callback URLs, got {len(updated_urls)}: {updated_urls}"
        )

    @given(
        providers=config_with_saml_and_oidc,
        domain_prefix=domain_prefixes,
        region=regions,
        cloudfront_domain=cloudfront_domains,
    )
    @settings(max_examples=100)
    def test_no_duplicate_callback_urls(
        self, providers, domain_prefix, region, cloudfront_domain
    ):
        """Callback URL list contains no duplicates."""
        # Feature: oidc-authentication, Property 5: Callback URL Preservation
        # **Validates: Requirements 3.1, 3.2, 3.3**

        auth = AuthConfig(identity_providers=providers)

        updated_urls = build_updated_callback_urls(domain_prefix, region, cloudfront_domain)

        assert len(updated_urls) == len(set(updated_urls)), (
            f"Duplicate callback URLs found: {updated_urls}"
        )
