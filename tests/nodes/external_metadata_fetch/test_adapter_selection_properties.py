"""
Property-based tests for adapter factory selection.

These tests verify that the adapter factory correctly instantiates
the appropriate adapter class based on the adapter_type configuration.

**Feature: external-metadata-enrichment, Property 12: Adapter Selection**
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
from nodes.external_metadata_fetch.adapters import (
    ADAPTERS,
    AdapterConfig,
    create_adapter,
)
from nodes.external_metadata_fetch.adapters.generic_rest import GenericRestAdapter
from nodes.external_metadata_fetch.auth import (
    AuthConfig,
    create_auth_strategy,
)

# Mapping of adapter_type strings to expected class types
ADAPTER_TYPE_TO_CLASS = {
    "generic_rest": GenericRestAdapter,
}


@pytest.mark.unit
class TestAdapterSelectionProperty:
    """Property-based tests for adapter factory selection."""

    @given(adapter_type=st.sampled_from(["generic_rest"]))
    @settings(max_examples=100)
    def test_factory_returns_correct_adapter_class(self, adapter_type: str):
        """
        Property 12: Adapter Selection

        *For any* valid adapter_type from the set of supported types, the
        create_adapter() factory SHALL return an instance of the
        corresponding adapter class.

        **Validates: Requirements 4.4**

        This property ensures that:
        1. The factory correctly maps adapter_type to adapter class
        2. The returned instance is of the expected type
        3. The adapter is properly initialized with the config and auth strategy
        """
        # Arrange
        auth_config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/token",
            additional_config={},
        )
        auth_strategy = create_auth_strategy("api_key", auth_config)

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/assets",
            additional_config={},
        )
        expected_class = ADAPTER_TYPE_TO_CLASS[adapter_type]

        # Act
        adapter = create_adapter(adapter_type, adapter_config, auth_strategy)

        # Assert
        assert isinstance(adapter, expected_class), (
            f"Factory should return {expected_class.__name__} for adapter_type '{adapter_type}', "
            f"but got {type(adapter).__name__}"
        )

    @given(adapter_type=st.sampled_from(["generic_rest"]))
    @settings(max_examples=100)
    def test_adapter_name_matches_expected_name(self, adapter_type: str):
        """
        Property 12 (extended): Adapter name is consistent.

        *For any* valid adapter_type, the instantiated adapter's get_adapter_name()
        method SHALL return a consistent name for source attribution.

        **Validates: Requirements 4.4**

        This property ensures consistency in adapter identification
        for source attribution purposes.
        """
        # Arrange
        auth_config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/token",
            additional_config={},
        )
        auth_strategy = create_auth_strategy("api_key", auth_config)

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/assets",
            additional_config={},
        )

        # Act
        adapter = create_adapter(adapter_type, adapter_config, auth_strategy)
        adapter_name = adapter.get_adapter_name()

        # Assert
        # The adapter name should be a non-empty string
        assert isinstance(adapter_name, str), (
            f"Adapter's get_adapter_name() should return a string, "
            f"but got {type(adapter_name).__name__}"
        )
        assert (
            len(adapter_name) > 0
        ), "Adapter's get_adapter_name() should return a non-empty string"

    @given(adapter_type=st.sampled_from(["generic_rest"]))
    @settings(max_examples=100)
    def test_adapter_receives_config_and_auth_strategy(self, adapter_type: str):
        """
        Property 12 (extended): Adapter receives configuration and auth strategy.

        *For any* valid adapter_type, the instantiated adapter SHALL have
        access to the AdapterConfig and AuthStrategy passed to the factory.

        **Validates: Requirements 4.4**

        This property ensures that configuration and auth strategy are properly
        passed through the factory to the adapter instance.
        """
        # Arrange
        test_endpoint = "https://api.example.com/assets"
        test_additional_config = {"timeout_seconds": 60}

        auth_config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/token",
            additional_config={},
        )
        auth_strategy = create_auth_strategy("api_key", auth_config)

        adapter_config = AdapterConfig(
            metadata_endpoint=test_endpoint,
            additional_config=test_additional_config,
        )

        # Act
        adapter = create_adapter(adapter_type, adapter_config, auth_strategy)

        # Assert
        assert (
            adapter.config is adapter_config
        ), "Adapter should receive the exact config object passed to factory"
        assert (
            adapter.config.metadata_endpoint == test_endpoint
        ), f"Adapter config should have metadata_endpoint '{test_endpoint}'"
        assert (
            adapter.auth_strategy is auth_strategy
        ), "Adapter should receive the exact auth_strategy object passed to factory"

    @given(invalid_adapter_type=st.text(min_size=1).filter(lambda x: x not in ADAPTERS))
    @settings(max_examples=100)
    def test_factory_raises_for_invalid_adapter_type(self, invalid_adapter_type: str):
        """
        Property 12 (error case): Factory raises ValueError for invalid adapter_type.

        *For any* string that is not a valid adapter_type, the create_adapter()
        factory SHALL raise a ValueError with a descriptive message.

        **Validates: Requirements 4.4**

        This property ensures proper error handling for invalid inputs.
        """
        # Arrange
        auth_config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/token",
            additional_config={},
        )
        auth_strategy = create_auth_strategy("api_key", auth_config)

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/assets",
            additional_config={},
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_adapter(invalid_adapter_type, adapter_config, auth_strategy)

        # Verify error message is descriptive
        error_message = str(exc_info.value)
        assert (
            invalid_adapter_type in error_message
        ), f"Error message should mention the invalid adapter_type '{invalid_adapter_type}'"
        assert (
            "Available types" in error_message or "available" in error_message.lower()
        ), "Error message should mention available adapter types"

    @given(adapter_type=st.sampled_from(["generic_rest"]))
    @settings(max_examples=100)
    def test_adapter_full_source_name_includes_auth_strategy(self, adapter_type: str):
        """
        Property 12 (extended): Full source name includes auth strategy.

        *For any* valid adapter_type, the instantiated adapter's get_full_source_name()
        method SHALL return a string that includes both the adapter name and
        the auth strategy name.

        **Validates: Requirements 4.4**

        This property ensures proper source attribution that identifies
        both the adapter and authentication method used.
        """
        # Arrange
        auth_config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/token",
            additional_config={},
        )
        auth_strategy = create_auth_strategy("api_key", auth_config)

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/assets",
            additional_config={},
        )

        # Act
        adapter = create_adapter(adapter_type, adapter_config, auth_strategy)
        full_source_name = adapter.get_full_source_name()

        # Assert
        adapter_name = adapter.get_adapter_name()
        auth_strategy_name = auth_strategy.get_strategy_name()

        assert (
            adapter_name in full_source_name
        ), f"Full source name should include adapter name '{adapter_name}'"
        assert (
            auth_strategy_name in full_source_name
        ), f"Full source name should include auth strategy name '{auth_strategy_name}'"
        # Verify the format is "adapter:auth_strategy"
        assert full_source_name == f"{adapter_name}:{auth_strategy_name}", (
            f"Full source name should be '{adapter_name}:{auth_strategy_name}', "
            f"but got '{full_source_name}'"
        )
