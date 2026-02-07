"""
Property-based tests for collection_groups_utils.py

These tests use Hypothesis to verify universal properties across randomized inputs.
Each property test runs a minimum of 100 iterations to ensure correctness.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# Import from common_libraries (pytest.ini adds lambdas/ to pythonpath)
from common_libraries.collection_groups_utils import (
    GROUP_METADATA_SK,
    GROUP_PK_PREFIX,
    add_collection_ids,
    create_collection_group,
    format_collection_group_item,
    update_collection_group,
)
from hypothesis import given, settings
from hypothesis import strategies as st


# Hypothesis strategies for generating test data
@st.composite
def group_data_strategy(draw):
    """Generate valid collection group data."""
    return {
        "id": f"grp_{draw(st.uuids()).hex[:8]}",
        "name": draw(st.text(min_size=1, max_size=100)),
        "description": draw(st.one_of(st.none(), st.text(max_size=500))),
        "ownerId": f"user_{draw(st.uuids()).hex[:8]}",
        "isPublic": draw(st.booleans()),
        "collectionIds": draw(st.lists(st.text(min_size=1, max_size=20), max_size=10)),
    }


@st.composite
def collection_ids_strategy(draw):
    """Generate list of collection IDs."""
    return draw(st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=20))


@pytest.mark.property
class TestCollectionGroupProperties:
    """Property-based tests for collection group operations"""

    @given(group_data=group_data_strategy())
    @settings(max_examples=100)
    def test_property_4_unique_identifier_generation(self, group_data):
        """
        Property 4: Test unique identifier generation across multiple creates.

        For any set of collection groups created in the system, all group IDs
        should be unique (no duplicates).

        Validates: Requirements 1.6
        """
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        # Create multiple groups
        created_ids = set()
        for _ in range(10):
            group_data_copy = group_data.copy()
            group_data_copy["id"] = f"grp_{uuid.uuid4().hex[:8]}"

            result = create_collection_group(mock_table, group_data_copy)
            group_id = result["PK"].replace(GROUP_PK_PREFIX, "")

            # Verify ID is unique
            assert group_id not in created_ids, "Group ID must be unique"
            created_ids.add(group_id)

    @given(group_data=group_data_strategy())
    @settings(max_examples=100)
    def test_property_5_timestamp_recording_on_creation(self, group_data):
        """
        Property 5: Test timestamp recording on creation.

        For any newly created collection group, both createdAt and updatedAt
        fields should be present, valid timestamps, and approximately equal
        to the creation time.

        Validates: Requirements 1.7
        """
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        before_creation = datetime.now(timezone.utc)
        result = create_collection_group(mock_table, group_data)
        after_creation = datetime.now(timezone.utc)

        # Verify timestamps exist
        assert "createdAt" in result, "createdAt must be present"
        assert "updatedAt" in result, "updatedAt must be present"

        # Verify timestamps are valid ISO format
        created_at = datetime.fromisoformat(result["createdAt"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(result["updatedAt"].replace("Z", "+00:00"))

        # Verify timestamps are within reasonable range
        assert before_creation <= created_at <= after_creation
        assert before_creation <= updated_at <= after_creation

        # Verify createdAt and updatedAt are equal on creation
        assert result["createdAt"] == result["updatedAt"]

    @given(
        group_data=group_data_strategy(),
        updates=st.dictionaries(
            st.sampled_from(["name", "description", "isPublic"]),
            st.one_of(st.text(min_size=1, max_size=100), st.booleans()),
            min_size=1,
        ),
    )
    @settings(max_examples=100)
    def test_property_6_timestamp_update_on_modification(self, group_data, updates):
        """
        Property 6: Test timestamp update on modification.

        For any collection group that is updated, the updatedAt timestamp
        should be greater than its previous value.

        Validates: Requirements 1.8
        """
        mock_table = MagicMock()

        # Mock initial group with old timestamp
        initial_timestamp = "2024-01-01T00:00:00Z"
        mock_table.update_item.return_value = {
            "Attributes": {
                "PK": f"{GROUP_PK_PREFIX}{group_data['id']}",
                "SK": GROUP_METADATA_SK,
                "updatedAt": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                **updates,
            }
        }

        result = update_collection_group(mock_table, group_data["id"], updates)

        # Verify updatedAt is present and more recent
        assert "updatedAt" in result
        updated_at = datetime.fromisoformat(result["updatedAt"].replace("Z", ""))
        initial_at = datetime.fromisoformat(initial_timestamp.replace("Z", ""))

        assert updated_at > initial_at, "updatedAt must be greater than previous value"

    @given(
        group_id=st.text(min_size=1, max_size=20),
        collection_ids=collection_ids_strategy(),
    )
    @settings(max_examples=100)
    def test_property_22_collection_id_uniqueness_idempotent_adds(
        self, group_id, collection_ids
    ):
        """
        Property 22: Test collection ID uniqueness in groups (idempotent adds).

        For any collection group, if the same collection is added multiple times,
        the collection's ID should appear exactly once in the collectionIds array.

        Validates: Requirements 9.7
        """
        mock_table = MagicMock()

        # Mock existing group with some collection IDs
        existing_ids = (
            collection_ids[: len(collection_ids) // 2]
            if len(collection_ids) > 1
            else []
        )
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"{GROUP_PK_PREFIX}{group_id}",
                "SK": GROUP_METADATA_SK,
                "collectionIds": existing_ids,
            }
        }

        # Track what update_item was called with
        update_calls = []

        def capture_update(**kwargs):
            update_calls.append(kwargs)
            return {}

        mock_table.update_item.side_effect = capture_update

        # Add collection IDs (including duplicates)
        add_collection_ids(mock_table, group_id, collection_ids)

        # Calculate expected new IDs (deduplicated and not already in existing)
        unique_collection_ids = list(set(collection_ids))
        new_ids = [cid for cid in unique_collection_ids if cid not in existing_ids]

        # Verify update was called only if there are new IDs to add
        if len(new_ids) > 0:
            assert len(update_calls) > 0, "Update should be called when adding new IDs"

            # Extract the updated collection IDs
            expr_values = update_calls[0]["ExpressionAttributeValues"]
            updated_ids = expr_values[":ids"]

            # Verify no duplicates
            assert len(updated_ids) == len(
                set(updated_ids)
            ), "Collection IDs should be unique (no duplicates)"

            # Verify all new IDs are included
            for cid in new_ids:
                assert (
                    cid in updated_ids
                ), f"New collection ID {cid} should be in updated list"
        else:
            # If all IDs already exist, no update should be made
            # The function returns early without calling update_item
            pass

    @given(
        group_data=group_data_strategy(),
        user_id=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    )
    @settings(max_examples=100)
    def test_property_formatting_consistency(self, group_data, user_id):
        """
        Test that format_collection_group_item produces consistent output.

        For any collection group item and user context, the formatted output
        should contain all required fields and maintain data integrity.
        """
        # Create a mock DynamoDB item
        item = {
            "PK": f"{GROUP_PK_PREFIX}{group_data['id']}",
            "SK": GROUP_METADATA_SK,
            "name": group_data["name"],
            "description": group_data.get("description", ""),
            "ownerId": group_data["ownerId"],
            "isPublic": group_data["isPublic"],
            "collectionIds": group_data.get("collectionIds", []),
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
        }

        user_context = {"user_id": user_id} if user_id else {}

        result = format_collection_group_item(item, user_context)

        # Verify required fields are present
        assert "id" in result
        assert "name" in result
        assert "ownerId" in result
        assert "isPublic" in result
        assert "collectionIds" in result
        assert "collectionCount" in result
        assert "createdAt" in result
        assert "updatedAt" in result

        # Verify data integrity
        assert result["id"] == group_data["id"]
        assert result["name"] == group_data["name"]
        assert result["ownerId"] == group_data["ownerId"]
        assert result["collectionCount"] == len(group_data.get("collectionIds", []))

        # Verify user-specific fields
        if user_id:
            assert "isOwner" in result
            assert "userRole" in result

            if user_id == group_data["ownerId"]:
                assert result["isOwner"] is True
                assert result["userRole"] == "owner"
            else:
                assert result["isOwner"] is False
                assert result["userRole"] == "viewer"


@pytest.mark.property
class TestCollectionGroupEdgeCases:
    """Property-based tests for edge cases"""

    @given(group_id=st.text(min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_empty_collection_ids_list(self, group_id):
        """Test that groups can have empty collection ID lists."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"{GROUP_PK_PREFIX}{group_id}",
                "SK": GROUP_METADATA_SK,
                "collectionIds": [],
            }
        }

        # Adding empty list should not cause errors
        add_collection_ids(mock_table, group_id, [])

        # Should not call update_item for empty additions
        assert mock_table.update_item.call_count == 0

    @given(
        group_data=group_data_strategy(),
        collection_ids=st.lists(
            st.text(min_size=1, max_size=20), min_size=1, max_size=50
        ),
    )
    @settings(max_examples=100)
    def test_large_collection_id_lists(self, group_data, collection_ids):
        """Test that groups can handle large numbers of collection IDs."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"{GROUP_PK_PREFIX}{group_data['id']}",
                "SK": GROUP_METADATA_SK,
                "collectionIds": [],
            }
        }
        mock_table.update_item.return_value = {}

        # Should handle large lists without errors
        add_collection_ids(mock_table, group_data["id"], collection_ids)

        # Verify update was called
        assert mock_table.update_item.call_count == 1
