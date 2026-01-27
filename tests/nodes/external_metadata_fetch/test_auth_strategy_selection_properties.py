"""
Property-based tests for auth strategy factory selection.

These tests verify that the auth strategy factory correctly instantiates
the appropriate strategy class based on the auth_type configuration.

**Feature: external-metadata-enrichment, Property 13: Auth Strategy Selection**
**Validates: Requirements 4.4**
"""

import sys
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Mock aws_lambda_powertools before any imports that might trigger it
mock_powertools = MagicMock()
mock_powertools.Logger = MagicMock(return_value=MagicMock())
mock_powertools.Tracer = MagicMock(return_value=MagicMock())
mock_powertools.utilities = MagicMock()
mock_powertools.utilities.typing = MagicMock()
mock_powertools.utilities.typing.LambdaContext = MagicMock()
sys.modules["aws_lambda_powertools"] = mock_powertools
sys.modules["aws_lambda_powertools.utilities"] = mock_powertools.utilities
sys.modules["aws_lambda_powertools.utilities.typing"] = mock_powertools.utilities.typing

# Also mock lambda_middleware
sys.modules["lambda_middleware"] = MagicMock()

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.auth import (
    AUTH_STRATEGIES,
    AuthConfig,
    create_auth_strategy,
)
from nodes.external_metadata_fetch.auth.api_key import APIKeyStrategy
from nodes.external_metadata_fetch.auth.basic_auth import BasicAuthStrategy
from nodes.external_metadata_fetch.auth.oauth2_client_credentials import (
    OAuth2ClientCredentialsStrategy,
)

# Mapping of auth_type strings to expected class types
AUTH_TYPE_TO_CLASS = {
    "oauth2_client_credentials": OAuth2ClientCredentialsStrategy,
    "api_key": APIKeyStrategy,
    "basic_auth": BasicAuthStrategy,
}


@pytest.mark.unit
class TestAuthStrategySelectionProperty:
    """Property-based tests for auth strategy factory selection."""

    @given(
        auth_type=st.sampled_from(
            ["oauth2_client_credentials", "api_key", "basic_auth"]
        )
    )
    @settings(max_examples=100)
    def test_factory_returns_correct_strategy_class(self, auth_type: str):
        """
        Property 13: Auth Strategy Selection

        *For any* valid auth_type from the set of supported types, the
        create_auth_strategy() factory SHALL return an instance of the
        corresponding strategy class.

        **Validates: Requirements 4.4**

        This property ensures that:
        1. The factory correctly maps auth_type to strategy class
        2. The returned instance is of the expected type
        3. The strategy is properly initialized with the config
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/token",
            additional_config={},
        )
        expected_class = AUTH_TYPE_TO_CLASS[auth_type]

        # Act
        strategy = create_auth_strategy(auth_type, config)

        # Assert
        assert isinstance(strategy, expected_class), (
            f"Factory should return {expected_class.__name__} for auth_type '{auth_type}', "
            f"but got {type(strategy).__name__}"
        )

    @given(
        auth_type=st.sampled_from(
            ["oauth2_client_credentials", "api_key", "basic_auth"]
        )
    )
    @settings(max_examples=100)
    def test_strategy_name_matches_auth_type(self, auth_type: str):
        """
        Property 13 (extended): Strategy name matches auth_type.

        *For any* valid auth_type, the instantiated strategy's get_strategy_name()
        method SHALL return the same auth_type string used to create it.

        **Validates: Requirements 4.4**

        This property ensures consistency between the factory selection
        and the strategy's self-identification.
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/token",
            additional_config={},
        )

        # Act
        strategy = create_auth_strategy(auth_type, config)
        strategy_name = strategy.get_strategy_name()

        # Assert
        assert strategy_name == auth_type, (
            f"Strategy's get_strategy_name() should return '{auth_type}', "
            f"but got '{strategy_name}'"
        )

    @given(
        auth_type=st.sampled_from(
            ["oauth2_client_credentials", "api_key", "basic_auth"]
        )
    )
    @settings(max_examples=100)
    def test_strategy_receives_config(self, auth_type: str):
        """
        Property 13 (extended): Strategy receives configuration.

        *For any* valid auth_type, the instantiated strategy SHALL have
        access to the AuthConfig passed to the factory.

        **Validates: Requirements 4.4**

        This property ensures that configuration is properly passed
        through the factory to the strategy instance.
        """
        # Arrange
        test_endpoint = "https://auth.example.com/token"
        test_additional_config = {"timeout_seconds": 60}
        config = AuthConfig(
            auth_endpoint_url=test_endpoint,
            additional_config=test_additional_config,
        )

        # Act
        strategy = create_auth_strategy(auth_type, config)

        # Assert
        assert (
            strategy.config is config
        ), "Strategy should receive the exact config object passed to factory"
        assert (
            strategy.config.auth_endpoint_url == test_endpoint
        ), f"Strategy config should have auth_endpoint_url '{test_endpoint}'"

    @given(
        invalid_auth_type=st.text(min_size=1).filter(lambda x: x not in AUTH_STRATEGIES)
    )
    @settings(max_examples=100)
    def test_factory_raises_for_invalid_auth_type(self, invalid_auth_type: str):
        """
        Property 13 (error case): Factory raises ValueError for invalid auth_type.

        *For any* string that is not a valid auth_type, the create_auth_strategy()
        factory SHALL raise a ValueError with a descriptive message.

        **Validates: Requirements 4.4**

        This property ensures proper error handling for invalid inputs.
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/token",
            additional_config={},
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_auth_strategy(invalid_auth_type, config)

        # Verify error message is descriptive
        error_message = str(exc_info.value)
        assert (
            invalid_auth_type in error_message
        ), f"Error message should mention the invalid auth_type '{invalid_auth_type}'"
        assert (
            "Available types" in error_message or "available" in error_message.lower()
        ), "Error message should mention available auth types"
