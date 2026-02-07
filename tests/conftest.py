"""
Shared pytest fixtures and configuration for MediaLake Lambda tests.

This conftest.py provides common fixtures and mocks that can be reused
across all test modules. It handles the mocking of AWS dependencies
that are commonly needed when testing Lambda functions.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Path Setup - Add lambdas directory to Python path
# =============================================================================

# Get the project root directory (parent of tests/)
PROJECT_ROOT = Path(__file__).parent.parent
LAMBDAS_DIR = PROJECT_ROOT / "lambdas"

# Add lambdas directory to sys.path for imports
if str(LAMBDAS_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDAS_DIR))


# =============================================================================
# Mock ClientError for DynamoDB error handling tests
# =============================================================================


class MockClientError(Exception):
    """
    Mock ClientError for testing DynamoDB and other AWS service error handling.

    This class mimics the behavior of botocore.exceptions.ClientError
    without requiring the actual botocore library.
    """

    def __init__(self, error_response: dict, operation_name: str):
        self.response = error_response
        self.operation_name = operation_name
        error_code = error_response.get("Error", {}).get("Code", "Unknown")
        error_message = error_response.get("Error", {}).get("Message", "Unknown")
        super().__init__(
            f"An error occurred ({error_code}) when calling the "
            f"{operation_name} operation: {error_message}"
        )


# =============================================================================
# AWS Lambda Powertools Mocks
# =============================================================================


def _setup_aws_mocks():
    """Set up mocks for AWS dependencies before importing Lambda modules."""
    mock_logger = MagicMock()
    mock_tracer = MagicMock()
    mock_metrics = MagicMock()

    # Create mock decorators that return the function unchanged
    mock_tracer.capture_method = lambda f: f

    # Mock aws_lambda_powertools
    sys.modules["aws_lambda_powertools"] = MagicMock()
    sys.modules["aws_lambda_powertools"].Logger = MagicMock(return_value=mock_logger)
    sys.modules["aws_lambda_powertools"].Tracer = MagicMock(return_value=mock_tracer)
    sys.modules["aws_lambda_powertools"].Metrics = MagicMock(return_value=mock_metrics)
    sys.modules["aws_lambda_powertools.metrics"] = MagicMock()

    # Mock boto3
    sys.modules["boto3"] = MagicMock()
    sys.modules["boto3.dynamodb"] = MagicMock()
    sys.modules["boto3.dynamodb.conditions"] = MagicMock()

    # Mock botocore with our MockClientError
    mock_botocore = MagicMock()
    mock_botocore_exceptions = MagicMock()
    mock_botocore_exceptions.ClientError = MockClientError
    sys.modules["botocore"] = mock_botocore
    sys.modules["botocore.exceptions"] = mock_botocore_exceptions

    # Mock pynamodb
    mock_pynamodb = MagicMock()
    mock_pynamodb_models = MagicMock()
    mock_pynamodb_attributes = MagicMock()
    mock_pynamodb_indexes = MagicMock()
    mock_pynamodb_exceptions = MagicMock()

    # Create DoesNotExist exception class
    class DoesNotExist(Exception):
        pass

    # Create PutError exception class
    class PutError(Exception):
        pass

    mock_pynamodb_exceptions.DoesNotExist = DoesNotExist
    mock_pynamodb_exceptions.PutError = PutError

    sys.modules["pynamodb"] = mock_pynamodb
    sys.modules["pynamodb.models"] = mock_pynamodb_models
    sys.modules["pynamodb.attributes"] = mock_pynamodb_attributes
    sys.modules["pynamodb.indexes"] = mock_pynamodb_indexes
    sys.modules["pynamodb.exceptions"] = mock_pynamodb_exceptions

    return {
        "logger": mock_logger,
        "tracer": mock_tracer,
        "metrics": mock_metrics,
    }


# Set up mocks at module load time (before any Lambda modules are imported)
_aws_mocks = _setup_aws_mocks()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_dynamodb_table():
    """
    Provides a mock DynamoDB table resource for testing.

    Usage:
        def test_something(mock_dynamodb_table):
            mock_dynamodb_table.query.return_value = {"Count": 5}
            # ... test code ...
    """
    return MagicMock()


@pytest.fixture
def mock_client_error():
    """
    Provides the MockClientError class for creating DynamoDB errors in tests.

    Usage:
        def test_error_handling(mock_dynamodb_table, mock_client_error):
            error = mock_client_error(
                {"Error": {"Code": "InternalServerError", "Message": "Test"}},
                "Query"
            )
            mock_dynamodb_table.query.side_effect = error
    """
    return MockClientError


@pytest.fixture
def aws_mocks():
    """
    Provides access to the AWS mock objects (logger, tracer, metrics).

    Usage:
        def test_logging(aws_mocks):
            # ... test code ...
            aws_mocks["logger"].info.assert_called_once()
    """
    return _aws_mocks
