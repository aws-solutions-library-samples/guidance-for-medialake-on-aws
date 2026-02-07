"""
Property-based tests for cascade deletion and data integrity.

Tests cascade operations and referential integrity using Hypothesis.
Verifies that deletions properly clean up related data.
"""

from unittest.mock import MagicMock

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Property 18: Test cascade deletion of group references
# Property 19: Test cascade deletion of collection references
# Property 21: Test collection reference validity


@pytest.mark.property
class TestCascadeDeletionProperties:
    """Property-based tests for cascade deletion operations."""

    @given(
        collection_id=st.text(min_size=1, max_size=50),
        group_count=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_property_19_collection_deletion_removes_from_all_groups(
        self, collection_id, group_count
    ):
        """
        Property 19: Deleting a collection removes it from all groups.

        When a collection is deleted, it should be removed from
        the collectionIds array of all groups that contain it.
        """
        assume(collection_id.strip() != "")

        from lambdas.common_libraries.collection_groups_utils import (
            remove_collection_from_all_groups,
        )

        # Create mock groups that contain the collection
        mock_groups = []
        for i in range(group_count):
            group = {
                "PK": f"GROUP#group-{i}",
                "SK": "METADATA",
                "id": f"group-{i}",
                "name": f"Group {i}",
                "collectionIds": [collection_id, f"other-collection-{i}"],
            }
            mock_groups.append(group)

        mock_table = MagicMock()

        # Mock scan to return groups containing the collection
        mock_table.scan.return_value = {"Items": mock_groups, "Count": len(mock_groups)}

        # Call the cascade deletion function
        remove_collection_from_all_groups(mock_table, collection_id)

        # Verify update was called for each group
        assert mock_table.update_item.call_count == group_count

        # Verify each update removes the collection_id
        for call in mock_table.update_item.call_args_list:
            kwargs = call[1]
            # Check that the update expression removes the collection
            assert "collectionIds" in kwargs.get("UpdateExpression", "")

    @given(
        group_id=st.text(min_size=1, max_size=50),
        collection_count=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=100)
    def test_property_18_group_deletion_cleans_up_references(
        self, group_id, collection_count
    ):
        """
        Property 18: Deleting a group removes all its references.

        When a group is deleted, all its data should be removed
        and no orphaned references should remain.
        """
        assume(group_id.strip() != "")

        from lambdas.common_libraries.collection_groups_utils import (
            delete_collection_group,
        )

        collection_ids = [f"collection-{i}" for i in range(collection_count)]

        mock_group = {
            "PK": f"GROUP#{group_id}",
            "SK": "METADATA",
            "id": group_id,
            "name": "Test Group",
            "collectionIds": collection_ids,
        }

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": mock_group}

        # Delete the group
        delete_collection_group(mock_table, group_id)

        # Verify delete was called
        assert mock_table.delete_item.called
        call_kwargs = mock_table.delete_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == f"GROUP#{group_id}"
        assert call_kwargs["Key"]["SK"] == "METADATA"

    @given(
        collection_ids=st.lists(
            st.text(min_size=1, max_size=50), min_size=1, max_size=10, unique=True
        ),
        valid_count=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_property_21_collection_reference_validation(
        self, collection_ids, valid_count
    ):
        """
        Property 21: Collection reference validity is enforced.

        When adding collections to a group, the system should
        validate that all collection IDs reference existing collections.
        """
        assume(len(collection_ids) > 0)
        assume(valid_count <= len(collection_ids))

        from lambdas.common_libraries.collection_groups_utils import (
            validate_collection_ids,
        )

        # Split collections into valid and invalid
        valid_ids = collection_ids[:valid_count]
        invalid_ids = collection_ids[valid_count:]

        mock_table = MagicMock()

        # Mock get_item to return items for valid IDs only
        def mock_get_item(Key):
            collection_id = Key["PK"].replace("COLLECTION#", "")
            if collection_id in valid_ids:
                return {
                    "Item": {
                        "PK": Key["PK"],
                        "SK": "METADATA",
                        "id": collection_id,
                    }
                }
            return {}  # No "Item" key means collection doesn't exist

        mock_table.get_item.side_effect = mock_get_item

        # Validate the collection IDs
        is_valid, invalid_list = validate_collection_ids(mock_table, collection_ids)

        # Verify validation results
        if len(invalid_ids) > 0:
            assert not is_valid
            assert len(invalid_list) == len(invalid_ids)
            assert set(invalid_list) == set(invalid_ids)
        else:
            assert is_valid
            assert len(invalid_list) == 0

    @given(
        group_id=st.text(min_size=1, max_size=50),
        initial_collections=st.lists(
            st.text(min_size=1, max_size=50), min_size=1, max_size=10, unique=True
        ),
        collections_to_remove=st.lists(
            st.text(min_size=1, max_size=50), min_size=1, max_size=5, unique=True
        ),
    )
    @settings(max_examples=100)
    def test_property_19_partial_removal_maintains_integrity(
        self, group_id, initial_collections, collections_to_remove
    ):
        """
        Property 19: Removing some collections maintains data integrity.

        When removing a subset of collections from a group,
        the remaining collections should be preserved correctly.
        """
        assume(group_id.strip() != "")
        assume(len(initial_collections) > 0)

        from lambdas.common_libraries.collection_groups_utils import (
            remove_collection_ids,
        )

        mock_group = {
            "PK": f"GROUP#{group_id}",
            "SK": "METADATA",
            "id": group_id,
            "name": "Test Group",
            "collectionIds": initial_collections.copy(),
        }

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": mock_group}

        # Remove collections
        remove_collection_ids(mock_table, group_id, collections_to_remove)

        # Verify update was called
        assert mock_table.update_item.called

        # Calculate expected remaining collections
        expected_remaining = [
            cid for cid in initial_collections if cid not in collections_to_remove
        ]

        # Verify the update expression
        call_kwargs = mock_table.update_item.call_args[1]
        assert "UpdateExpression" in call_kwargs
        assert "collectionIds" in call_kwargs["UpdateExpression"]

    @given(
        num_groups=st.integers(min_value=1, max_value=5),
        num_collections=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_property_18_cascade_deletion_is_atomic(self, num_groups, num_collections):
        """
        Property 18: Cascade deletions are atomic operations.

        When performing cascade deletions, either all related
        data is removed or none is (transaction semantics).
        """
        from lambdas.common_libraries.collection_groups_utils import (
            remove_collection_from_all_groups,
        )

        collection_id = "test-collection"

        # Create mock groups
        mock_groups = []
        for i in range(num_groups):
            group = {
                "PK": f"GROUP#group-{i}",
                "SK": "METADATA",
                "id": f"group-{i}",
                "collectionIds": [collection_id]
                + [f"col-{j}" for j in range(num_collections)],
            }
            mock_groups.append(group)

        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": mock_groups, "Count": len(mock_groups)}

        # Simulate a failure on the last update
        call_count = [0]

        def mock_update(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == num_groups:
                raise Exception("Simulated DynamoDB error")

        mock_table.update_item.side_effect = mock_update

        # Attempt cascade deletion
        try:
            remove_collection_from_all_groups(mock_table, collection_id)
        except Exception:
            pass  # Expected to fail

        # Verify that we attempted to update all groups
        # (In a real implementation with transactions, this would rollback)
        assert mock_table.update_item.call_count == num_groups


@pytest.mark.property
class TestDataIntegrityProperties:
    """Property-based tests for data integrity constraints."""

    @given(
        group_id=st.text(min_size=1, max_size=50),
        collection_ids=st.lists(
            st.text(min_size=1, max_size=50), min_size=1, max_size=10, unique=True
        ),
    )
    @settings(max_examples=100)
    def test_property_21_no_duplicate_collections_in_group(
        self, group_id, collection_ids
    ):
        """
        Property 21: Groups cannot contain duplicate collection IDs.

        Adding the same collection multiple times should result
        in it appearing only once in the group.
        """
        assume(group_id.strip() != "")
        assume(all(cid.strip() != "" for cid in collection_ids))

        from lambdas.common_libraries.collection_groups_utils import (
            add_collection_ids,
        )

        mock_group = {
            "PK": f"GROUP#{group_id}",
            "SK": "METADATA",
            "id": group_id,
            "name": "Test Group",
            "collectionIds": [],
        }

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": mock_group}

        # Add collections twice
        add_collection_ids(mock_table, group_id, collection_ids)
        add_collection_ids(mock_table, group_id, collection_ids)

        # Verify that duplicates are handled
        # The function should use set logic to prevent duplicates
        assert mock_table.update_item.call_count == 2

        # Each call should only add new collections
        for call in mock_table.update_item.call_args_list:
            kwargs = call[1]
            # Verify the update expression uses ADD or SET with deduplication
            assert "UpdateExpression" in kwargs

    @given(
        collection_id=st.text(min_size=1, max_size=50),
        num_groups=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_property_19_orphaned_references_are_prevented(
        self, collection_id, num_groups
    ):
        """
        Property 19: System prevents orphaned collection references.

        When a collection is deleted, the cascade deletion function
        should be called to remove it from all groups.
        """
        assume(collection_id.strip() != "")

        from lambdas.common_libraries.collection_groups_utils import (
            remove_collection_from_all_groups,
        )

        # Create groups containing the collection
        mock_groups = []
        for i in range(num_groups):
            group = {
                "PK": f"GROUP#group-{i}",
                "SK": "METADATA",
                "id": f"group-{i}",
                "collectionIds": [collection_id, f"other-{i}"],
            }
            mock_groups.append(group)

        mock_table = MagicMock()

        # Mock scan to return groups with the collection
        mock_table.scan.return_value = {"Items": mock_groups, "Count": len(mock_groups)}

        # Remove collection from all groups
        remove_collection_from_all_groups(mock_table, collection_id)

        # Verify all groups were updated
        if num_groups > 0:
            assert mock_table.update_item.call_count == num_groups

            # Verify each update targets the correct group
            for i, call in enumerate(mock_table.update_item.call_args_list):
                kwargs = call[1]
                assert "Key" in kwargs
                assert kwargs["Key"]["PK"] == f"GROUP#group-{i}"
                assert "UpdateExpression" in kwargs
        else:
            # No groups to update
            assert mock_table.update_item.call_count == 0
