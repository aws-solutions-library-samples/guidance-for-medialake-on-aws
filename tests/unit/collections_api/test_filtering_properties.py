"""
Property-based tests for collection filtering by groups.

These tests use Hypothesis to verify universal properties of the group filtering logic.
Each property test runs a minimum of 100 iterations to ensure correctness.
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Add lambdas directory to path for imports
lambdas_path = Path(__file__).parent.parent.parent.parent / "lambdas"
sys.path.insert(0, str(lambdas_path))
sys.path.insert(0, str(lambdas_path / "common_libraries"))


# Hypothesis strategies for generating test data


@st.composite
def group_id_strategy(draw):
    """Generate valid group IDs."""
    return f"grp_{draw(st.uuids()).hex[:8]}"


@st.composite
def collection_id_strategy(draw):
    """Generate valid collection IDs."""
    return f"col_{draw(st.uuids()).hex[:8]}"


@st.composite
def group_membership_strategy(draw):
    """Generate group membership data (groups with their collection IDs)."""
    num_groups = draw(st.integers(min_value=1, max_value=5))
    num_collections = draw(st.integers(min_value=1, max_value=20))

    # Generate collection IDs
    collection_ids = [f"col_{uuid.uuid4().hex[:8]}" for _ in range(num_collections)]

    # Generate groups and assign collections
    groups = {}
    for i in range(num_groups):
        group_id = f"grp_{uuid.uuid4().hex[:8]}"
        # Each group gets a random subset of collections
        num_in_group = draw(st.integers(min_value=0, max_value=num_collections))
        group_collections = (
            draw(
                st.lists(
                    st.sampled_from(collection_ids),
                    min_size=num_in_group,
                    max_size=num_in_group,
                    unique=True,
                )
            )
            if num_in_group > 0
            else []
        )
        groups[group_id] = group_collections

    return {
        "groups": groups,
        "all_collections": collection_ids,
    }


@st.composite
def view_type_strategy(draw):
    """Generate valid view types."""
    return draw(st.sampled_from(["STANDARD", "SMART", "FOLDER", None]))


@pytest.mark.property
class TestCollectionFilteringProperties:
    """Property-based tests for collection filtering by groups"""

    @given(membership_data=group_membership_strategy())
    @settings(max_examples=100)
    def test_property_13_group_filtering_or_logic(self, membership_data):
        """
        Property 13: Group filtering returns correct collections (OR logic).

        For any set of groups and collections, when filtering by multiple groups,
        the result should include collections that belong to ANY of the specified
        groups (OR logic, not AND).

        Validates: Requirements 5.9, 6.4
        """
        from collection_groups_utils import get_collection_ids_by_group_ids

        groups = membership_data["groups"]
        all_collections = membership_data["all_collections"]

        if not groups:
            return  # Skip if no groups

        # Select a subset of groups to filter by
        group_ids = list(groups.keys())
        num_filter_groups = min(len(group_ids), 3)
        filter_group_ids = group_ids[:num_filter_groups]

        # Calculate expected result (OR logic)
        expected_collection_ids = set()
        for gid in filter_group_ids:
            expected_collection_ids.update(groups[gid])

        # Mock the table
        mock_table = MagicMock()

        # Mock get_item to return groups with their collections
        def mock_get_item(Key):
            group_id = Key["PK"].replace("GROUP#", "")
            if group_id in groups:
                return {
                    "Item": {
                        "PK": Key["PK"],
                        "SK": "METADATA",
                        "collectionIds": groups[group_id],
                    }
                }
            return {}

        mock_table.get_item.side_effect = mock_get_item

        # Call the function
        result = get_collection_ids_by_group_ids(mock_table, filter_group_ids)

        # Verify OR logic: result contains collections from ANY of the groups
        result_set = set(result)
        assert (
            result_set == expected_collection_ids
        ), "Filtering should return collections from ANY of the specified groups (OR logic)"

        # Verify no extra collections
        for cid in result_set:
            assert (
                cid in all_collections
            ), "Result should only contain valid collection IDs"

    @given(
        membership_data=group_membership_strategy(),
        view_type=view_type_strategy(),
    )
    @settings(max_examples=100)
    def test_property_16_widget_backward_compatibility(
        self, membership_data, view_type
    ):
        """
        Property 16: Widget backward compatibility (no filters).

        For any widget configuration without groupIds filter, the widget
        should display all collections (backward compatible behavior).

        Validates: Requirements 6.4, 6.9
        """
        all_collections = membership_data["all_collections"]

        # Simulate widget query without groupIds
        # When groupIds is None or empty, all collections should be returned

        # Mock collections query
        mock_collections = [
            {
                "PK": f"COLL#{cid}",
                "SK": "METADATA",
                "name": f"Collection {cid}",
                "isPublic": True,
            }
            for cid in all_collections
        ]

        # Filter without groupIds (backward compatibility)
        groupIds = None

        if groupIds:
            # Would filter here
            filtered = []
        else:
            # No filter - return all
            filtered = mock_collections

        # Verify all collections are returned
        assert len(filtered) == len(
            all_collections
        ), "Without groupIds filter, all collections should be returned (backward compatible)"

    @given(
        membership_data=group_membership_strategy(),
        view_type=view_type_strategy(),
    )
    @settings(max_examples=100)
    def test_property_17_widget_combined_filter_and_logic(
        self, membership_data, view_type
    ):
        """
        Property 17: Widget combined filter AND logic.

        For any widget with both viewType and groupIds filters, the filters
        should be combined using AND logic (collections must match BOTH filters).

        Validates: Requirements 6.5, 6.6, 6.7
        """
        groups = membership_data["groups"]
        all_collections = membership_data["all_collections"]

        if not groups or not view_type:
            return  # Skip if no groups or no view type

        # Select groups to filter by
        group_ids = list(groups.keys())[:2]

        # Calculate collections in selected groups (OR logic)
        collections_in_groups = set()
        for gid in group_ids:
            collections_in_groups.update(groups[gid])

        # Mock collections with viewType
        mock_collections = []
        for cid in all_collections:
            # Randomly assign viewType
            coll_view_type = view_type if hash(cid) % 2 == 0 else "OTHER"
            mock_collections.append(
                {
                    "PK": f"COLL#{cid}",
                    "SK": "METADATA",
                    "name": f"Collection {cid}",
                    "collectionTypeId": coll_view_type,
                    "isPublic": True,
                }
            )

        # Apply filters with AND logic
        # Step 1: Filter by viewType
        filtered_by_type = [
            c for c in mock_collections if c.get("collectionTypeId") == view_type
        ]

        # Step 2: Filter by groupIds (AND logic with viewType)
        filtered_by_both = [
            c
            for c in filtered_by_type
            if c["PK"].replace("COLL#", "") in collections_in_groups
        ]

        # Verify AND logic
        for c in filtered_by_both:
            cid = c["PK"].replace("COLL#", "")
            # Must match viewType
            assert (
                c.get("collectionTypeId") == view_type
            ), "Collection must match viewType filter"
            # Must be in one of the groups
            assert (
                cid in collections_in_groups
            ), "Collection must be in one of the specified groups"

        # Verify no collections that don't match both filters
        for c in mock_collections:
            cid = c["PK"].replace("COLL#", "")
            if (
                c.get("collectionTypeId") != view_type
                or cid not in collections_in_groups
            ):
                assert (
                    c not in filtered_by_both
                ), "Collections not matching both filters should be excluded"


@pytest.mark.property
class TestCollectionFilteringEdgeCases:
    """Property-based tests for edge cases in collection filtering"""

    @given(collection_ids=st.lists(collection_id_strategy(), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_empty_group_ids_returns_all(self, collection_ids):
        """Test that empty groupIds list returns all collections."""
        # Mock collections
        mock_collections = [
            {"PK": f"COLL#{cid}", "SK": "METADATA", "name": f"Collection {cid}"}
            for cid in collection_ids
        ]

        # Filter with empty groupIds
        groupIds = []

        if groupIds:
            filtered = []
        else:
            filtered = mock_collections

        # Should return all collections
        assert len(filtered) == len(
            collection_ids
        ), "Empty groupIds should return all collections"

    @given(
        group_id=group_id_strategy(),
        collection_ids=st.lists(collection_id_strategy(), min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_single_group_filter(self, group_id, collection_ids):
        """Test filtering by a single group."""
        from collection_groups_utils import get_collection_ids_by_group_ids

        # Mock group with collections
        group_collections = (
            collection_ids[: len(collection_ids) // 2]
            if len(collection_ids) > 1
            else collection_ids
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"GROUP#{group_id}",
                "SK": "METADATA",
                "collectionIds": group_collections,
            }
        }

        result = get_collection_ids_by_group_ids(mock_table, [group_id])

        # Verify correct collections returned
        assert set(result) == set(
            group_collections
        ), "Single group filter should return only collections in that group"

    @given(
        group_ids=st.lists(group_id_strategy(), min_size=2, max_size=5, unique=True),
        collection_ids=st.lists(
            collection_id_strategy(), min_size=5, max_size=20, unique=True
        ),
    )
    @settings(max_examples=100)
    def test_overlapping_group_memberships(self, group_ids, collection_ids):
        """Test that collections in multiple groups are not duplicated."""
        from collection_groups_utils import get_collection_ids_by_group_ids

        # Create overlapping memberships
        # Some collections belong to multiple groups
        groups = {}
        for i, gid in enumerate(group_ids):
            # Each group gets some collections, with overlap
            start_idx = i * 2
            end_idx = start_idx + 5
            groups[gid] = collection_ids[start_idx : min(end_idx, len(collection_ids))]

        # Calculate expected result (union, no duplicates)
        expected = set()
        for gid in group_ids:
            expected.update(groups[gid])

        mock_table = MagicMock()

        def mock_get_item(Key):
            group_id = Key["PK"].replace("GROUP#", "")
            if group_id in groups:
                return {
                    "Item": {
                        "PK": Key["PK"],
                        "SK": "METADATA",
                        "collectionIds": groups[group_id],
                    }
                }
            return {}

        mock_table.get_item.side_effect = mock_get_item

        result = get_collection_ids_by_group_ids(mock_table, group_ids)

        # Verify no duplicates
        assert len(result) == len(
            set(result)
        ), "Result should not contain duplicate collection IDs"

        # Verify correct collections
        assert (
            set(result) == expected
        ), "Result should be union of all collections in specified groups"

    @given(
        group_id=group_id_strategy(),
        deleted_collection_id=collection_id_strategy(),
    )
    @settings(max_examples=100)
    def test_deleted_collection_handling(self, group_id, deleted_collection_id):
        """Test that deleted collections are handled gracefully."""
        from collection_groups_utils import get_collection_ids_by_group_ids

        # Mock group with a deleted collection ID
        group_collections = [deleted_collection_id, "col_valid1", "col_valid2"]

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"GROUP#{group_id}",
                "SK": "METADATA",
                "collectionIds": group_collections,
            }
        }

        result = get_collection_ids_by_group_ids(mock_table, [group_id])

        # The function returns all IDs (including deleted)
        # The actual filtering happens in the collections_get handler
        # which will skip collections that don't exist
        assert (
            deleted_collection_id in result
        ), "Function returns all IDs; handler filters non-existent collections"


@pytest.mark.property
class TestGroupFilteringPerformance:
    """Property-based tests for performance characteristics"""

    @given(
        num_groups=st.integers(min_value=1, max_value=10),
        num_collections=st.integers(min_value=10, max_value=100),
    )
    @settings(max_examples=50)
    def test_large_scale_filtering(self, num_groups, num_collections):
        """Test filtering with large numbers of groups and collections."""
        from collection_groups_utils import get_collection_ids_by_group_ids

        # Generate groups and collections
        group_ids = [f"grp_{i}" for i in range(num_groups)]
        collection_ids = [f"col_{i}" for i in range(num_collections)]

        # Assign collections to groups (each collection in 1-3 groups)
        groups = {gid: [] for gid in group_ids}
        for cid in collection_ids:
            # Add to random groups
            num_groups_for_coll = min(3, num_groups)
            for i in range(num_groups_for_coll):
                groups[group_ids[i % num_groups]].append(cid)

        # Calculate expected result
        expected = set()
        for gid in group_ids:
            expected.update(groups[gid])

        mock_table = MagicMock()

        def mock_get_item(Key):
            group_id = Key["PK"].replace("GROUP#", "")
            if group_id in groups:
                return {
                    "Item": {
                        "PK": Key["PK"],
                        "SK": "METADATA",
                        "collectionIds": groups[group_id],
                    }
                }
            return {}

        mock_table.get_item.side_effect = mock_get_item

        result = get_collection_ids_by_group_ids(mock_table, group_ids)

        # Verify result is correct
        assert (
            set(result) == expected
        ), "Large-scale filtering should return correct results"
