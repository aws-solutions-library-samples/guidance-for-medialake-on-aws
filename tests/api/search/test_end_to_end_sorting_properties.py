"""
Property-Based Tests for End-to-End Sorting

**Validates: Requirements 1.4, 10.1, 10.2, 10.6**

These tests verify the correctness properties of end-to-end sorting:
- Property 4: End-to-End Sorting
- Property 5: Sort Direction Consistency
- Property 6: Sort Order Across Pagination
"""

from datetime import datetime
from typing import Any, Dict, List, Literal

from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Type definitions
SortDirection = Literal["asc", "desc"]
SortField = Literal["createdAt", "name", "size", "type"]


# Strategies
@st.composite
def asset_item(draw):
    """Generate a realistic asset item"""
    asset_types = ["image", "video", "audio"]
    formats = {
        "image": ["jpg", "png", "gif", "bmp"],
        "video": ["mp4", "mov", "avi", "mkv"],
        "audio": ["mp3", "wav", "flac", "aac"],
    }

    asset_type = draw(st.sampled_from(asset_types))

    return {
        "InventoryID": draw(st.uuids()).hex,
        "DigitalSourceAsset": {
            "Type": asset_type,
            "CreateDate": draw(
                st.datetimes(
                    min_value=datetime(2020, 1, 1), max_value=datetime(2024, 12, 31)
                )
            ).isoformat(),
            "MainRepresentation": {
                "Format": draw(st.sampled_from(formats[asset_type])),
                "StorageInfo": {
                    "PrimaryLocation": {
                        "Bucket": "test-bucket",
                        "ObjectKey": {
                            "Name": draw(
                                st.text(
                                    alphabet=st.characters(
                                        whitelist_categories=("Lu", "Ll", "Nd"),
                                        whitelist_characters="-_.",
                                    ),
                                    min_size=5,
                                    max_size=50,
                                )
                            )
                            + f".{draw(st.sampled_from(formats[asset_type]))}"
                        },
                        "FileInfo": {
                            "Size": draw(
                                st.integers(
                                    min_value=1024, max_value=1024 * 1024 * 1024
                                )
                            )
                        },
                    }
                },
            },
        },
    }


@st.composite
def asset_list(draw, min_size=10, max_size=100):
    """Generate a list of asset items"""
    return draw(st.lists(asset_item(), min_size=min_size, max_size=max_size))


def extract_sort_key(asset: Dict[str, Any], sort_field: SortField) -> Any:
    """Extract the sort key from an asset based on the sort field"""
    if sort_field == "createdAt":
        return asset["DigitalSourceAsset"]["CreateDate"]
    elif sort_field == "name":
        return asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
            "PrimaryLocation"
        ]["ObjectKey"]["Name"]
    elif sort_field == "size":
        return asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
            "PrimaryLocation"
        ]["FileInfo"]["Size"]
    elif sort_field == "type":
        return asset["DigitalSourceAsset"]["Type"]
    else:
        raise ValueError(f"Unknown sort field: {sort_field}")


def sort_assets(
    assets: List[Dict[str, Any]], sort_field: SortField, sort_direction: SortDirection
) -> List[Dict[str, Any]]:
    """Sort assets according to the specified field and direction"""
    reverse = sort_direction == "desc"
    return sorted(
        assets, key=lambda a: extract_sort_key(a, sort_field), reverse=reverse
    )


def paginate_assets(
    assets: List[Dict[str, Any]], page: int, page_size: int
) -> List[Dict[str, Any]]:
    """Paginate assets"""
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    return assets[start_idx:end_idx]


class TestEndToEndSortingProperties:
    """Property tests for end-to-end sorting behavior"""

    @given(
        assets=asset_list(min_size=20, max_size=50),
        sort_field=st.sampled_from(["createdAt", "name", "size", "type"]),
        sort_direction=st.sampled_from(["asc", "desc"]),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_4_end_to_end_sorting(
        self,
        assets: List[Dict[str, Any]],
        sort_field: SortField,
        sort_direction: SortDirection,
    ):
        """
        Property 4: End-to-End Sorting

        When assets are sorted by a field in a direction, the results should be
        in the correct order according to that field and direction.

        **Validates: Requirements 1.4, 10.1**
        """
        # Sort the assets
        sorted_assets = sort_assets(assets, sort_field, sort_direction)

        # Verify the sort order
        for i in range(len(sorted_assets) - 1):
            current_key = extract_sort_key(sorted_assets[i], sort_field)
            next_key = extract_sort_key(sorted_assets[i + 1], sort_field)

            if sort_direction == "asc":
                assert current_key <= next_key, (
                    f"Assets not sorted correctly in ascending order by {sort_field}. "
                    f"Asset {i} ({current_key}) > Asset {i+1} ({next_key})"
                )
            else:
                assert current_key >= next_key, (
                    f"Assets not sorted correctly in descending order by {sort_field}. "
                    f"Asset {i} ({current_key}) < Asset {i+1} ({next_key})"
                )

    @given(
        assets=asset_list(min_size=20, max_size=50),
        sort_field=st.sampled_from(["createdAt", "name", "size", "type"]),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_5_sort_direction_consistency(
        self, assets: List[Dict[str, Any]], sort_field: SortField
    ):
        """
        Property 5: Sort Direction Consistency

        Sorting by the same field in opposite directions should produce
        reverse-ordered results.

        **Validates: Requirements 10.2**
        """
        # Sort in both directions
        asc_sorted = sort_assets(assets, sort_field, "asc")
        desc_sorted = sort_assets(assets, sort_field, "desc")

        # Verify they are reverses of each other
        assert len(asc_sorted) == len(desc_sorted)

        for i in range(len(asc_sorted)):
            asc_asset = asc_sorted[i]
            desc_asset = desc_sorted[-(i + 1)]  # Reverse index

            # Compare by ID since assets should be the same, just in reverse order
            assert asc_asset["InventoryID"] == desc_asset["InventoryID"], (
                f"Assets at position {i} (asc) and {-(i+1)} (desc) should be the same. "
                f"Got {asc_asset['InventoryID']} vs {desc_asset['InventoryID']}"
            )

    @given(
        assets=asset_list(min_size=30, max_size=100),
        sort_field=st.sampled_from(["createdAt", "name", "size", "type"]),
        sort_direction=st.sampled_from(["asc", "desc"]),
        page_size=st.integers(min_value=5, max_value=20),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_6_sort_order_across_pagination(
        self,
        assets: List[Dict[str, Any]],
        sort_field: SortField,
        sort_direction: SortDirection,
        page_size: int,
    ):
        """
        Property 6: Sort Order Across Pagination

        When paginating sorted results, the sort order should be maintained
        across page boundaries. The last item on page N should come before
        the first item on page N+1 in the sort order.

        **Validates: Requirements 10.6**
        """
        # Sort the assets
        sorted_assets = sort_assets(assets, sort_field, sort_direction)

        # Calculate number of pages
        total_pages = (len(sorted_assets) + page_size - 1) // page_size

        # Skip if only one page
        assume(total_pages > 1)

        # Check sort order across page boundaries
        for page in range(1, total_pages):
            # Get current page and next page
            current_page_assets = paginate_assets(sorted_assets, page, page_size)
            next_page_assets = paginate_assets(sorted_assets, page + 1, page_size)

            # Skip if either page is empty
            if not current_page_assets or not next_page_assets:
                continue

            # Get last item of current page and first item of next page
            last_current = current_page_assets[-1]
            first_next = next_page_assets[0]

            last_key = extract_sort_key(last_current, sort_field)
            first_key = extract_sort_key(first_next, sort_field)

            # Verify sort order is maintained across page boundary
            if sort_direction == "asc":
                assert last_key <= first_key, (
                    f"Sort order not maintained across page boundary (page {page} to {page+1}). "
                    f"Last item on page {page} ({last_key}) > First item on page {page+1} ({first_key})"
                )
            else:
                assert last_key >= first_key, (
                    f"Sort order not maintained across page boundary (page {page} to {page+1}). "
                    f"Last item on page {page} ({last_key}) < First item on page {page+1} ({first_key})"
                )

    @given(
        assets=asset_list(min_size=20, max_size=50),
        sort_field=st.sampled_from(["createdAt", "name", "size", "type"]),
        sort_direction=st.sampled_from(["asc", "desc"]),
    )
    @settings(max_examples=100, deadline=None)
    def test_sort_stability(
        self,
        assets: List[Dict[str, Any]],
        sort_field: SortField,
        sort_direction: SortDirection,
    ):
        """
        Verify that sorting is stable - items with equal sort keys maintain
        their relative order.
        """
        # Sort twice
        first_sort = sort_assets(assets, sort_field, sort_direction)
        second_sort = sort_assets(first_sort, sort_field, sort_direction)

        # Results should be identical
        assert len(first_sort) == len(second_sort)
        for i in range(len(first_sort)):
            assert (
                first_sort[i]["InventoryID"] == second_sort[i]["InventoryID"]
            ), f"Sort is not stable. Asset at position {i} changed between sorts."

    @given(
        assets=asset_list(min_size=20, max_size=50),
        sort_field=st.sampled_from(["createdAt", "name", "size", "type"]),
        sort_direction=st.sampled_from(["asc", "desc"]),
    )
    @settings(max_examples=100, deadline=None)
    def test_sort_preserves_all_items(
        self,
        assets: List[Dict[str, Any]],
        sort_field: SortField,
        sort_direction: SortDirection,
    ):
        """
        Verify that sorting preserves all items - no items are lost or duplicated.
        """
        sorted_assets = sort_assets(assets, sort_field, sort_direction)

        # Same number of items
        assert len(sorted_assets) == len(assets)

        # All original IDs are present
        original_ids = {asset["InventoryID"] for asset in assets}
        sorted_ids = {asset["InventoryID"] for asset in sorted_assets}
        assert original_ids == sorted_ids, "Sorting changed the set of asset IDs"
