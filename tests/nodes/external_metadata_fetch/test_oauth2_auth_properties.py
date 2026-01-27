"""
Property-based tests for OAuth2 Client Credentials authentication strategy.

These tests verify that the OAuth2 authentication strategy correctly formats
authorization headers for API calls.

**Feature: external-metadata-enrichment, Property 14: Token Usage in API Calls**
**Validates: Requirements 6.3**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from nodes.external_metadata_fetch.auth.base import AuthConfig, AuthResult

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.auth.oauth2_client_credentials import (
    OAuth2ClientCredentialsStrategy,
)


@pytest.mark.unit
class TestOAuth2AuthHeaderProperty:
    """Property-based tests for OAuth2 auth header formatting."""

    @given(token=st.text(min_size=1))
    @settings(max_examples=100)
    def test_bearer_token_header_format(self, token: str):
        """
        Property 14: Token Usage in API Calls

        *For any* non-empty access token, the get_auth_header() method SHALL return
        a dictionary with an "Authorization" key containing "Bearer <token>".

        **Validates: Requirements 6.3**

        This property ensures that:
        1. The Authorization header is always present
        2. The header value follows the "Bearer <token>" format
        3. The token is included exactly as provided (no modification)
        """
        # Arrange
        config = AuthConfig(auth_endpoint_url="https://auth.example.com/token")
        strategy = OAuth2ClientCredentialsStrategy(config)
        auth_result = AuthResult(
            success=True,
            access_token=token,
            token_type="Bearer",
        )

        # Act
        headers = strategy.get_auth_header(auth_result)

        # Assert
        assert "Authorization" in headers, "Authorization header must be present"
        assert (
            headers["Authorization"] == f"Bearer {token}"
        ), f"Authorization header must be 'Bearer <token>', got: {headers['Authorization']}"

    @given(
        token=st.text(min_size=1),
        token_type=st.sampled_from(["Bearer", "bearer", "BEARER", "Token", "JWT"]),
    )
    @settings(max_examples=100)
    def test_custom_token_type_header_format(self, token: str, token_type: str):
        """
        Property 14 (extended): Token type is respected in header format.

        *For any* non-empty access token and any token type, the get_auth_header()
        method SHALL return a dictionary with an "Authorization" key containing
        "<token_type> <token>".

        **Validates: Requirements 6.3**

        This property ensures that custom token types from OAuth2 responses
        are correctly used in the Authorization header.
        """
        # Arrange
        config = AuthConfig(auth_endpoint_url="https://auth.example.com/token")
        strategy = OAuth2ClientCredentialsStrategy(config)
        auth_result = AuthResult(
            success=True,
            access_token=token,
            token_type=token_type,
        )

        # Act
        headers = strategy.get_auth_header(auth_result)

        # Assert
        assert "Authorization" in headers, "Authorization header must be present"
        expected_header = f"{token_type} {token}"
        assert (
            headers["Authorization"] == expected_header
        ), f"Authorization header must be '{expected_header}', got: {headers['Authorization']}"

    @given(token=st.text(min_size=1))
    @settings(max_examples=100)
    def test_default_bearer_token_type_when_none(self, token: str):
        """
        Property 14 (edge case): Default to Bearer when token_type is None.

        *For any* non-empty access token with None token_type, the get_auth_header()
        method SHALL default to "Bearer" token type.

        **Validates: Requirements 6.3**
        """
        # Arrange
        config = AuthConfig(auth_endpoint_url="https://auth.example.com/token")
        strategy = OAuth2ClientCredentialsStrategy(config)
        auth_result = AuthResult(
            success=True,
            access_token=token,
            token_type=None,  # type: ignore - testing None handling
        )

        # Act
        headers = strategy.get_auth_header(auth_result)

        # Assert
        assert "Authorization" in headers, "Authorization header must be present"
        assert (
            headers["Authorization"] == f"Bearer {token}"
        ), f"Authorization header must default to 'Bearer <token>' when token_type is None"
