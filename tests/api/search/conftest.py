"""
Pytest configuration for search API tests.

This conftest provides additional mocks specific to the search API,
particularly for aws_lambda_powertools.event_handler which is used
in the search Lambda function.
"""

import sys
from unittest.mock import MagicMock


def pytest_configure(config):
    """Configure pytest with additional mocks for search tests."""
    # Mock aws_lambda_powertools.event_handler
    if "aws_lambda_powertools.event_handler" not in sys.modules:
        mock_event_handler = MagicMock()
        mock_event_handler.APIGatewayRestResolver = MagicMock
        mock_event_handler.api_gateway = MagicMock()
        mock_event_handler.api_gateway.CORSConfig = MagicMock
        sys.modules["aws_lambda_powertools.event_handler"] = mock_event_handler
        sys.modules["aws_lambda_powertools.event_handler.api_gateway"] = (
            mock_event_handler.api_gateway
        )

    # Mock aws_lambda_powertools.logging
    if "aws_lambda_powertools.logging" not in sys.modules:
        mock_logging = MagicMock()
        mock_logging.correlation_paths = MagicMock()
        sys.modules["aws_lambda_powertools.logging"] = mock_logging

    # Mock aws_lambda_powertools.utilities.typing
    if "aws_lambda_powertools.utilities.typing" not in sys.modules:
        mock_typing = MagicMock()
        mock_typing.LambdaContext = MagicMock
        sys.modules["aws_lambda_powertools.utilities"] = MagicMock()
        sys.modules["aws_lambda_powertools.utilities.typing"] = mock_typing

    # Mock opensearchpy
    if "opensearchpy" not in sys.modules:
        mock_opensearch = MagicMock()
        mock_opensearch.OpenSearch = MagicMock
        mock_opensearch.NotFoundError = type("NotFoundError", (Exception,), {})
        mock_opensearch.RequestError = type("RequestError", (Exception,), {})
        mock_opensearch.RequestsAWSV4SignerAuth = MagicMock
        mock_opensearch.RequestsHttpConnection = MagicMock
        sys.modules["opensearchpy"] = mock_opensearch

    # Mock search_utils
    if "search_utils" not in sys.modules:
        mock_search_utils = MagicMock()
        mock_search_utils.parse_search_query = MagicMock(return_value={})
        sys.modules["search_utils"] = mock_search_utils

    # Mock unified_search_orchestrator
    if "unified_search_orchestrator" not in sys.modules:
        mock_orchestrator = MagicMock()
        mock_orchestrator.UnifiedSearchOrchestrator = MagicMock
        sys.modules["unified_search_orchestrator"] = mock_orchestrator

    # Mock url_utils
    if "url_utils" not in sys.modules:
        mock_url_utils = MagicMock()
        mock_url_utils.generate_cloudfront_url = MagicMock(
            return_value="https://example.com/test.jpg"
        )
        mock_url_utils.generate_cloudfront_urls_batch = MagicMock(return_value=[])
        sys.modules["url_utils"] = mock_url_utils
