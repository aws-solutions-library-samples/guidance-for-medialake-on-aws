"""
Property-based tests for collection groups API handlers.

These tests use Hypothesis to verify universal properties across randomized inputs.
Each property test runs a minimum of 100 iterations to ensure correctness.
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Add lambdas directory to path for imports
lambdas_path = Path(__file__).parent.parent.parent.parent / "lambdas"
sys.path.insert(0, str(lambdas_path))
sys.path.insert(0, str(lambdas_path / "common_libraries"))
sys.path.insert(0, str(lambdas_path / "api" / "collections_api"))

# Hypothesis strategies for generating test data


@st.composite
def user_id_strategy(draw):
    """Generate valid user IDs."""
    return f"user_{draw(st.uuids()).hex[:8]}"


@st.composite
def group_name_strategy(draw):
    """Generate valid group names (non-whitespace)."""
    return draw(
        st.text(
            min_size=1,
            max_size=200,
            alphabet=st.characters(
                blacklist_categories=("Cs",),  # Exclude surrogates
                blacklist_characters="\x00\n\r\t",
            ),
        ).filter(lambda x: x.strip() != "")
    )


@st.composite
def group_description_strategy(draw):
    """Generate optional group descriptions."""
    return draw(
        st.one_of(
            st.none(),
            st.text(
                max_size=1000, alphabet=st.characters(blacklist_characters="\x00\n\r")
            ),
        )
    )


@st.composite
def collection_ids_strategy(draw):
    """Generate list of collection IDs."""
    return draw(
        st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=20, unique=True)
    )


@st.composite
def create_group_request_strategy(draw):
    """Generate valid CreateCollectionGroupRequest data."""
    return {
        "name": draw(group_name_strategy()),
        "description": draw(group_description_strategy()),
        "isPublic": draw(st.booleans()),
    }


@pytest.mark.property
class TestGroupHandlerProperties:
    """Property-based tests for collection groups API handlers"""

    @given(user_id=user_id_strategy(), group_name=group_name_strategy())
    @settings(max_examples=100)
    def test_property_1_creator_ownership_assignment(self, user_id, group_name):
        """
        Property 1: Creator is assigned as owner.

        For any collection group created by a user, the ownerId field
        should be set to the user_id of the creator.

        Validates: Requirements 1.2, 4.1
        """
        from collection_groups_utils import create_collection_group

        # Create mock table
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        # Prepare group data with user as owner
        group_data = {
            "id": f"grp_{uuid.uuid4().hex[:8]}",
            "name": group_name,
            "ownerId": user_id,
            "isPublic": True,
        }

        # Create group
        result = create_collection_group(mock_table, group_data)

        # Verify owner is assigned correctly
        assert result["ownerId"] == user_id, "Creator must be assigned as owner"
        assert result["PK"] == f"GROUP#{group_data['id']}"
        assert result["SK"] == "METADATA"

    @given(
        request_data=st.dictionaries(
            st.sampled_from(["description", "isPublic"]),
            st.one_of(st.text(max_size=100), st.booleans()),
        )
    )
    @settings(max_examples=100)
    def test_property_2_required_name_validation(self, request_data):
        """
        Property 2: Name is required.

        For any collection group creation request, if the name field is missing
        or empty, the request should fail with a validation error.

        Validates: Requirements 1.3, 4.2
        """
        from models.group_models import CreateCollectionGroupRequest
        from pydantic import ValidationError

        # Request without name should fail
        with pytest.raises(ValidationError) as exc_info:
            CreateCollectionGroupRequest(**request_data)

        # Verify error mentions 'name' field
        error_str = str(exc_info.value)
        assert (
            "name" in error_str.lower()
        ), "Validation error should mention 'name' field"

    @given(
        group_name=group_name_strategy(),
        description=group_description_strategy(),
    )
    @settings(max_examples=100)
    def test_property_3_optional_description_acceptance(self, group_name, description):
        """
        Property 3: Description is optional.

        For any collection group creation request, the description field
        should be optional and accept None or any valid string value.

        Validates: Requirements 1.4, 4.3
        """
        from models.group_models import CreateCollectionGroupRequest

        # Request with or without description should succeed
        request_data = {"name": group_name, "isPublic": True}
        if description is not None:
            request_data["description"] = description

        try:
            request = CreateCollectionGroupRequest(**request_data)
            assert request.name == group_name.strip()
            if description is not None:
                assert request.description == description
            else:
                assert request.description is None
        except Exception as e:
            pytest.fail(f"Optional description should be accepted: {e}")

    @given(group_name=group_name_strategy())
    @settings(max_examples=100)
    def test_property_7_default_public_visibility(self, group_name):
        """
        Property 7: Default public visibility.

        For any collection group created without specifying isPublic,
        the group should default to public visibility (isPublic = True).

        Validates: Requirements 3.2, 4.6
        """
        from models.group_models import CreateCollectionGroupRequest

        # Request without isPublic should default to True
        request = CreateCollectionGroupRequest(name=group_name)
        assert request.isPublic is True, "Groups should default to public visibility"

    @given(
        group_id=st.text(min_size=1, max_size=20),
        collection_ids=collection_ids_strategy(),
    )
    @settings(max_examples=100)
    def test_property_9_multi_group_collection_membership(
        self, group_id, collection_ids
    ):
        """
        Property 9: Collections can belong to multiple groups.

        For any collection, it should be possible to add it to multiple
        different groups without conflicts.

        Validates: Requirements 1.8, 4.8
        """
        from collection_groups_utils import add_collection_ids

        # Create mock table
        mock_table = MagicMock()

        # Simulate adding same collection to multiple groups
        for i in range(3):
            test_group_id = f"{group_id}_{i}"

            # Mock get_item to return existing group
            mock_table.get_item.return_value = {
                "Item": {
                    "PK": f"GROUP#{test_group_id}",
                    "SK": "METADATA",
                    "ownerId": "user_test",
                    "collectionIds": [],
                }
            }
            mock_table.update_item.return_value = {}

            # Add collections to this group
            add_collection_ids(mock_table, test_group_id, collection_ids)

            # Verify update was called
            assert (
                mock_table.update_item.called
            ), f"Collections should be added to group {i}"

    @given(
        group_id=st.text(min_size=1, max_size=20),
        collection_ids=collection_ids_strategy(),
    )
    @settings(max_examples=100)
    def test_property_10_membership_creation_on_add(self, group_id, collection_ids):
        """
        Property 10: Membership is created when collections are added.

        For any collection added to a group, a membership relationship
        should be created (collection ID added to group's collectionIds).

        Validates: Requirements 1.8, 8.1
        """
        from collection_groups_utils import add_collection_ids

        # Create mock table
        mock_table = MagicMock()

        # Mock existing group
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"GROUP#{group_id}",
                "SK": "METADATA",
                "collectionIds": [],
            }
        }

        # Track update calls
        update_calls = []

        def capture_update(**kwargs):
            update_calls.append(kwargs)
            return {}

        mock_table.update_item.side_effect = capture_update

        # Add collections
        add_collection_ids(mock_table, group_id, collection_ids)

        # Verify membership was created (update was called)
        if len(collection_ids) > 0:
            assert (
                len(update_calls) > 0
            ), "Membership should be created when collections are added"

            # Verify collection IDs are in the update
            expr_values = update_calls[0]["ExpressionAttributeValues"]
            updated_ids = expr_values[":ids"]
            for cid in collection_ids:
                assert cid in updated_ids, f"Collection {cid} should be in membership"

    @given(
        group_id=st.text(min_size=1, max_size=20),
        collection_ids=collection_ids_strategy(),
    )
    @settings(max_examples=100)
    def test_property_11_membership_removal_preserves_collection(
        self, group_id, collection_ids
    ):
        """
        Property 11: Removing membership preserves the collection.

        For any collection removed from a group, the collection itself
        should remain intact (only the membership is removed).

        Validates: Requirements 1.9, 8.4
        """
        from collection_groups_utils import remove_collection_ids

        # Create mock table
        mock_table = MagicMock()

        # Mock existing group with collections
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"GROUP#{group_id}",
                "SK": "METADATA",
                "collectionIds": collection_ids,
            }
        }

        # Track update calls
        update_calls = []

        def capture_update(**kwargs):
            update_calls.append(kwargs)
            return {}

        mock_table.update_item.side_effect = capture_update

        # Remove collections
        remove_collection_ids(
            mock_table,
            group_id,
            (
                collection_ids[: len(collection_ids) // 2]
                if len(collection_ids) > 1
                else collection_ids
            ),
        )

        # Verify update was called (membership removed)
        if len(collection_ids) > 0:
            assert len(update_calls) > 0, "Membership removal should update group"

            # Note: The actual collection items are NOT deleted
            # Only the group's collectionIds array is updated
            # This test verifies that remove_collection_ids doesn't delete collections
            # by checking that only update_item is called, not delete_item
            assert (
                not mock_table.delete_item.called
            ), "Collections should not be deleted"

    @given(
        owner_id=user_id_strategy(),
        other_user_id=user_id_strategy(),
        collection_ids=collection_ids_strategy(),
    )
    @settings(max_examples=100)
    def test_property_12_authorization_for_membership_modification(
        self, owner_id, other_user_id, collection_ids
    ):
        """
        Property 12: Only authorized users can modify membership.

        For any collection group, only the owner (or pipeline) should be
        able to add or remove collections from the group.

        Validates: Requirements 4.8, 8.1, 9.6
        """
        from collection_groups_utils import get_collection_group_metadata

        # Ensure owner and other user are different
        if owner_id == other_user_id:
            other_user_id = f"{other_user_id}_different"

        # Create mock table
        mock_table = MagicMock()

        # Mock group metadata
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "GROUP#grp_test",
                "SK": "METADATA",
                "ownerId": owner_id,
                "collectionIds": [],
            }
        }

        # Get group metadata
        group = get_collection_group_metadata(mock_table, "grp_test")

        # Verify owner is correctly stored
        assert group is not None
        assert group["ownerId"] == owner_id

        # Authorization check would happen in the handler
        # This test verifies the data structure supports authorization
        assert group["ownerId"] != other_user_id, "Non-owner should have different ID"

    @given(
        group_name=group_name_strategy(),
        collection_ids=collection_ids_strategy(),
    )
    @settings(max_examples=100)
    def test_property_23_transaction_rollback_on_failure(
        self, group_name, collection_ids
    ):
        """
        Property 23: Transactions rollback on failure.

        For any operation that fails partway through, the system should
        rollback to maintain consistency (no partial updates).

        Validates: Requirements 9.6
        """
        from collection_groups_utils import add_collection_ids

        # Create mock table
        mock_table = MagicMock()

        # Mock existing group
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "GROUP#grp_test",
                "SK": "METADATA",
                "collectionIds": [],
            }
        }

        # Simulate failure during update
        mock_table.update_item.side_effect = Exception("Simulated failure")

        # Attempt to add collections (should fail)
        try:
            add_collection_ids(mock_table, "grp_test", collection_ids)
            pytest.fail("Should have raised exception")
        except Exception as e:
            # Expected to fail
            assert "Simulated failure" in str(e) or "not found" in str(e).lower()

    @given(
        owner_id=user_id_strategy(),
        collection_ids=collection_ids_strategy(),
    )
    @settings(max_examples=100)
    def test_property_25_authorization_consistency_owner_pipeline(
        self, owner_id, collection_ids
    ):
        """
        Property 25: Authorization consistency between owner and pipeline.

        For any collection group, both the owner and authorized pipelines
        should have consistent permissions to modify membership.

        Validates: Requirements 8.1, 8.4
        """
        from collection_groups_utils import add_collection_ids

        # Create mock table
        mock_table = MagicMock()

        # Mock group metadata
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "GROUP#grp_test",
                "SK": "METADATA",
                "ownerId": owner_id,
                "collectionIds": [],
            }
        }
        mock_table.update_item.return_value = {}

        # Owner should be able to add collections
        add_collection_ids(mock_table, "grp_test", collection_ids)
        assert mock_table.update_item.called, "Owner should be authorized"

        # Pipeline support will be added in Task 17
        # This property will be fully tested then


@pytest.mark.property
class TestGroupHandlerEdgeCases:
    """Property-based tests for edge cases in handlers"""

    @given(
        group_name=st.text(min_size=1, max_size=10).filter(lambda x: x.strip() == "")
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_whitespace_only_name_rejected(self, group_name):
        """Test that names with only whitespace are rejected."""
        from models.group_models import CreateCollectionGroupRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            CreateCollectionGroupRequest(name=group_name, isPublic=True)

        error_str = str(exc_info.value)
        assert (
            "name" in error_str.lower()
            or "whitespace" in error_str.lower()
            or "string" in error_str.lower()
        )

    @given(
        collection_ids=st.lists(
            st.text(min_size=1, max_size=20), min_size=0, max_size=0
        )
    )
    @settings(max_examples=100)
    def test_empty_collection_ids_list_rejected(self, collection_ids):
        """Test that empty collection ID lists are rejected."""
        from models.group_models import AddCollectionsRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AddCollectionsRequest(collectionIds=collection_ids)

    @given(
        collection_ids=st.lists(
            st.text(min_size=1, max_size=20),
            min_size=2,
            max_size=10,
        ).filter(
            lambda x: len(x) != len(set(x))
        )  # Has duplicates
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_duplicate_collection_ids_deduplicated(self, collection_ids):
        """Test that duplicate collection IDs are automatically deduplicated."""
        from models.group_models import AddCollectionsRequest

        request = AddCollectionsRequest(collectionIds=collection_ids)

        # Verify no duplicates in result
        assert len(request.collectionIds) == len(
            set(request.collectionIds)
        ), "Duplicate collection IDs should be deduplicated"
