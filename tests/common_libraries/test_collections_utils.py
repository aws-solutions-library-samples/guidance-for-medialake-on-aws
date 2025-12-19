"""
Unit tests for collections_utils.py - specifically the get_collection_item_count function.

These tests verify that the get_collection_item_count function correctly counts
items in a collection by querying DynamoDB for both ASSET# and ITEM# SK prefixes.
"""

import pytest

# Import from common_libraries (pytest.ini adds lambdas/ to pythonpath)
from common_libraries.collections_utils import (
    ASSET_SK_PREFIX,
    COLLECTION_PK_PREFIX,
    ITEM_SK_PREFIX,
    _count_items_with_prefix,
    get_collection_item_count,
)


@pytest.mark.unit
class TestGetCollectionItemCount:
    """Tests for get_collection_item_count function"""

    def test_count_empty_collection(self, mock_dynamodb_table):
        """Returns 0 for collection with no items."""
        # Arrange
        mock_dynamodb_table.query.return_value = {"Count": 0}
        collection_pk = f"{COLLECTION_PK_PREFIX}test-collection-123"

        # Act
        result = get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert
        assert result == 0

    def test_count_queries_both_prefixes(self, mock_dynamodb_table):
        """Verifies that the function queries for both ASSET# and ITEM# SK prefixes."""
        # Arrange
        mock_dynamodb_table.query.return_value = {"Count": 0}
        collection_pk = f"{COLLECTION_PK_PREFIX}test-collection-prefixes"

        # Act
        get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert - verify query was called exactly twice (once for ASSET#, once for ITEM#)
        assert mock_dynamodb_table.query.call_count == 2

    def test_count_single_asset_item(self, mock_dynamodb_table):
        """Returns 1 for collection with one ASSET# item."""
        # Arrange
        mock_dynamodb_table.query.side_effect = [
            {"Count": 1},  # ASSET# query
            {"Count": 0},  # ITEM# query
        ]
        collection_pk = f"{COLLECTION_PK_PREFIX}test-collection-456"

        # Act
        result = get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert
        assert result == 1

    def test_count_single_item_item(self, mock_dynamodb_table):
        """Returns 1 for collection with one ITEM# item."""
        # Arrange
        mock_dynamodb_table.query.side_effect = [
            {"Count": 0},  # ASSET# query
            {"Count": 1},  # ITEM# query
        ]
        collection_pk = f"{COLLECTION_PK_PREFIX}test-collection-789"

        # Act
        result = get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert
        assert result == 1

    def test_count_multiple_items(self, mock_dynamodb_table):
        """Returns correct count for collection with multiple items."""
        # Arrange
        mock_dynamodb_table.query.side_effect = [
            {"Count": 5},  # ASSET# query
            {"Count": 3},  # ITEM# query
        ]
        collection_pk = f"{COLLECTION_PK_PREFIX}test-collection-multi"

        # Act
        result = get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert
        assert result == 8

    def test_count_mixed_prefixes(self, mock_dynamodb_table):
        """Returns correct count for collection with both ASSET# and ITEM# prefixes."""
        # Arrange
        mock_dynamodb_table.query.side_effect = [
            {"Count": 10},  # ASSET# query
            {"Count": 15},  # ITEM# query
        ]
        collection_pk = f"{COLLECTION_PK_PREFIX}test-collection-mixed"

        # Act
        result = get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert
        assert result == 25

    def test_count_pagination(self, mock_dynamodb_table):
        """Returns correct count when results exceed 1MB (requires pagination)."""
        # Arrange
        mock_dynamodb_table.query.side_effect = [
            {"Count": 500, "LastEvaluatedKey": {"PK": "COLL#test", "SK": "ASSET#500"}},
            {"Count": 300},  # Second ASSET# page
            {"Count": 200},  # ITEM# query
        ]
        collection_pk = f"{COLLECTION_PK_PREFIX}test-collection-large"

        # Act
        result = get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert
        assert result == 1000  # 500 + 300 + 200
        assert mock_dynamodb_table.query.call_count == 3

    def test_count_dynamodb_error(self, mock_dynamodb_table, mock_client_error):
        """Returns -1 when DynamoDB query fails."""
        # Arrange
        error_response = {
            "Error": {"Code": "InternalServerError", "Message": "Test error"}
        }
        mock_dynamodb_table.query.side_effect = mock_client_error(
            error_response, "Query"
        )
        collection_pk = f"{COLLECTION_PK_PREFIX}test-collection-error"

        # Act
        result = get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert
        assert result == -1

    def test_count_nonexistent_collection(self, mock_dynamodb_table):
        """Returns 0 for collection ID with no items."""
        # Arrange
        mock_dynamodb_table.query.return_value = {"Count": 0}
        collection_pk = f"{COLLECTION_PK_PREFIX}nonexistent-collection-xyz"

        # Act
        result = get_collection_item_count(mock_dynamodb_table, collection_pk)

        # Assert
        assert result == 0


@pytest.mark.unit
class TestCountItemsWithPrefix:
    """Tests for the internal _count_items_with_prefix helper function"""

    def test_count_with_prefix_success(self, mock_dynamodb_table):
        """Returns correct count for items with specific prefix."""
        # Arrange
        mock_dynamodb_table.query.return_value = {"Count": 42}
        pk_value = f"{COLLECTION_PK_PREFIX}test-collection"
        sk_prefix = ASSET_SK_PREFIX

        # Act
        result = _count_items_with_prefix(mock_dynamodb_table, pk_value, sk_prefix)

        # Assert
        assert result == 42

    def test_count_with_prefix_pagination(self, mock_dynamodb_table):
        """Handles pagination correctly when counting items."""
        # Arrange
        mock_dynamodb_table.query.side_effect = [
            {"Count": 100, "LastEvaluatedKey": {"PK": "test", "SK": "test"}},
            {"Count": 50, "LastEvaluatedKey": {"PK": "test2", "SK": "test2"}},
            {"Count": 25},  # No LastEvaluatedKey means end of pagination
        ]
        pk_value = f"{COLLECTION_PK_PREFIX}test-collection"
        sk_prefix = ITEM_SK_PREFIX

        # Act
        result = _count_items_with_prefix(mock_dynamodb_table, pk_value, sk_prefix)

        # Assert
        assert result == 175  # 100 + 50 + 25
        assert mock_dynamodb_table.query.call_count == 3

    def test_count_with_prefix_error(self, mock_dynamodb_table, mock_client_error):
        """Returns -1 when DynamoDB query fails."""
        # Arrange
        error_response = {
            "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
        }
        mock_dynamodb_table.query.side_effect = mock_client_error(
            error_response, "Query"
        )
        pk_value = f"{COLLECTION_PK_PREFIX}test-collection"
        sk_prefix = ASSET_SK_PREFIX

        # Act
        result = _count_items_with_prefix(mock_dynamodb_table, pk_value, sk_prefix)

        # Assert
        assert result == -1
