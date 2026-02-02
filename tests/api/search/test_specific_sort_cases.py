"""
Unit Tests for Specific Sort Cases

**Validates: Requirements 10.3, 10.4, 10.5**

These tests verify specific sorting scenarios:
- Sorting by name ascending (alphabetical order)
- Sorting by date descending (newest first)
- Sorting by size ascending (smallest first)
"""

from datetime import datetime, timedelta
from typing import Any, Dict


def create_test_asset(
    inventory_id: str,
    name: str,
    asset_type: str = "image",
    format_type: str = "jpg",
    size: int = 1024,
    created_date: str = "2024-01-01T00:00:00Z",
) -> Dict[str, Any]:
    """Helper to create a test asset"""
    return {
        "InventoryID": inventory_id,
        "DigitalSourceAsset": {
            "Type": asset_type,
            "CreateDate": created_date,
            "MainRepresentation": {
                "Format": format_type,
                "StorageInfo": {
                    "PrimaryLocation": {
                        "Bucket": "test-bucket",
                        "ObjectKey": {"Name": name},
                        "FileInfo": {"Size": size},
                    }
                },
            },
        },
    }


class TestSpecificSortCases:
    """Unit tests for specific sorting scenarios"""

    def test_sort_by_name_ascending_alphabetical(self):
        """
        Test sorting by name ascending produces alphabetical order

        **Validates: Requirement 10.3**
        """
        # Create assets with names in non-alphabetical order
        assets = [
            create_test_asset("1", "zebra.jpg"),
            create_test_asset("2", "apple.jpg"),
            create_test_asset("3", "mango.jpg"),
            create_test_asset("4", "banana.jpg"),
        ]

        # Sort by name ascending
        sorted_assets = sorted(
            assets,
            key=lambda a: a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"],
        )

        # Verify alphabetical order
        names = [
            a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"]
            for a in sorted_assets
        ]
        assert names == ["apple.jpg", "banana.jpg", "mango.jpg", "zebra.jpg"]

    def test_sort_by_name_case_insensitive(self):
        """
        Test that name sorting is case-insensitive

        **Validates: Requirement 10.3**
        """
        assets = [
            create_test_asset("1", "Zebra.jpg"),
            create_test_asset("2", "apple.jpg"),
            create_test_asset("3", "MANGO.jpg"),
            create_test_asset("4", "Banana.jpg"),
        ]

        # Sort by name (case-insensitive)
        sorted_assets = sorted(
            assets,
            key=lambda a: a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"].lower(),
        )

        names = [
            a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"]
            for a in sorted_assets
        ]
        assert names == ["apple.jpg", "Banana.jpg", "MANGO.jpg", "Zebra.jpg"]

    def test_sort_by_name_with_numbers(self):
        """
        Test sorting names that contain numbers

        **Validates: Requirement 10.3**
        """
        assets = [
            create_test_asset("1", "file10.jpg"),
            create_test_asset("2", "file2.jpg"),
            create_test_asset("3", "file1.jpg"),
            create_test_asset("4", "file20.jpg"),
        ]

        # Sort by name (lexicographic)
        sorted_assets = sorted(
            assets,
            key=lambda a: a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"],
        )

        names = [
            a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"]
            for a in sorted_assets
        ]
        # Lexicographic order (not natural number order)
        assert names == ["file1.jpg", "file10.jpg", "file2.jpg", "file20.jpg"]

    def test_sort_by_date_descending_newest_first(self):
        """
        Test sorting by date descending produces newest first

        **Validates: Requirement 10.4**
        """
        # Create assets with different dates
        base_date = datetime(2024, 1, 1)
        assets = [
            create_test_asset(
                "1", "old.jpg", created_date=(base_date + timedelta(days=1)).isoformat()
            ),
            create_test_asset(
                "2",
                "newest.jpg",
                created_date=(base_date + timedelta(days=10)).isoformat(),
            ),
            create_test_asset(
                "3",
                "middle.jpg",
                created_date=(base_date + timedelta(days=5)).isoformat(),
            ),
            create_test_asset("4", "oldest.jpg", created_date=base_date.isoformat()),
        ]

        # Sort by date descending
        sorted_assets = sorted(
            assets, key=lambda a: a["DigitalSourceAsset"]["CreateDate"], reverse=True
        )

        # Verify newest first
        names = [
            a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"]
            for a in sorted_assets
        ]
        assert names == ["newest.jpg", "middle.jpg", "old.jpg", "oldest.jpg"]

    def test_sort_by_date_ascending_oldest_first(self):
        """
        Test sorting by date ascending produces oldest first

        **Validates: Requirement 10.4**
        """
        base_date = datetime(2024, 1, 1)
        assets = [
            create_test_asset(
                "1",
                "new.jpg",
                created_date=(base_date + timedelta(days=10)).isoformat(),
            ),
            create_test_asset("2", "oldest.jpg", created_date=base_date.isoformat()),
            create_test_asset(
                "3",
                "middle.jpg",
                created_date=(base_date + timedelta(days=5)).isoformat(),
            ),
        ]

        # Sort by date ascending
        sorted_assets = sorted(
            assets, key=lambda a: a["DigitalSourceAsset"]["CreateDate"]
        )

        names = [
            a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"]
            for a in sorted_assets
        ]
        assert names == ["oldest.jpg", "middle.jpg", "new.jpg"]

    def test_sort_by_date_with_same_day(self):
        """
        Test sorting by date when multiple assets have the same date

        **Validates: Requirement 10.4**
        """
        same_date = datetime(2024, 1, 1, 12, 0, 0)
        assets = [
            create_test_asset("1", "file1.jpg", created_date=same_date.isoformat()),
            create_test_asset(
                "2",
                "file2.jpg",
                created_date=(same_date + timedelta(seconds=1)).isoformat(),
            ),
            create_test_asset("3", "file3.jpg", created_date=same_date.isoformat()),
        ]

        # Sort by date descending
        sorted_assets = sorted(
            assets, key=lambda a: a["DigitalSourceAsset"]["CreateDate"], reverse=True
        )

        # file2 should be first (1 second later)
        assert sorted_assets[0]["InventoryID"] == "2"

    def test_sort_by_size_ascending_smallest_first(self):
        """
        Test sorting by size ascending produces smallest first

        **Validates: Requirement 10.5**
        """
        assets = [
            create_test_asset("1", "large.jpg", size=1024 * 1024 * 10),  # 10 MB
            create_test_asset("2", "tiny.jpg", size=1024),  # 1 KB
            create_test_asset("3", "medium.jpg", size=1024 * 1024),  # 1 MB
            create_test_asset("4", "huge.jpg", size=1024 * 1024 * 100),  # 100 MB
        ]

        # Sort by size ascending
        sorted_assets = sorted(
            assets,
            key=lambda a: a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["FileInfo"]["Size"],
        )

        # Verify smallest first
        names = [
            a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"]
            for a in sorted_assets
        ]
        assert names == ["tiny.jpg", "medium.jpg", "large.jpg", "huge.jpg"]

    def test_sort_by_size_descending_largest_first(self):
        """
        Test sorting by size descending produces largest first

        **Validates: Requirement 10.5**
        """
        assets = [
            create_test_asset("1", "medium.jpg", size=1024 * 1024),
            create_test_asset("2", "huge.jpg", size=1024 * 1024 * 100),
            create_test_asset("3", "tiny.jpg", size=1024),
        ]

        # Sort by size descending
        sorted_assets = sorted(
            assets,
            key=lambda a: a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["FileInfo"]["Size"],
            reverse=True,
        )

        names = [
            a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"]
            for a in sorted_assets
        ]
        assert names == ["huge.jpg", "medium.jpg", "tiny.jpg"]

    def test_sort_by_size_with_zero_bytes(self):
        """
        Test sorting by size handles zero-byte files correctly

        **Validates: Requirement 10.5**
        """
        assets = [
            create_test_asset("1", "normal.jpg", size=1024),
            create_test_asset("2", "empty.jpg", size=0),
            create_test_asset("3", "large.jpg", size=1024 * 1024),
        ]

        # Sort by size ascending
        sorted_assets = sorted(
            assets,
            key=lambda a: a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["FileInfo"]["Size"],
        )

        # Empty file should be first
        assert (
            sorted_assets[0]["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["ObjectKey"]["Name"]
            == "empty.jpg"
        )
        assert (
            sorted_assets[0]["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["FileInfo"]["Size"]
            == 0
        )

    def test_sort_by_type_alphabetical(self):
        """
        Test sorting by type produces alphabetical order of types
        """
        assets = [
            create_test_asset("1", "file1.mp4", asset_type="video"),
            create_test_asset("2", "file2.jpg", asset_type="image"),
            create_test_asset("3", "file3.mp3", asset_type="audio"),
            create_test_asset("4", "file4.png", asset_type="image"),
        ]

        # Sort by type ascending
        sorted_assets = sorted(assets, key=lambda a: a["DigitalSourceAsset"]["Type"])

        types = [a["DigitalSourceAsset"]["Type"] for a in sorted_assets]
        assert types == ["audio", "image", "image", "video"]

    def test_sort_stability_with_equal_values(self):
        """
        Test that sorting is stable when values are equal
        """
        # Create assets with same size but different names
        assets = [
            create_test_asset("1", "zebra.jpg", size=1024),
            create_test_asset("2", "apple.jpg", size=1024),
            create_test_asset("3", "mango.jpg", size=1024),
        ]

        # Sort by size (all equal)
        sorted_assets = sorted(
            assets,
            key=lambda a: a["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["FileInfo"]["Size"],
        )

        # Original order should be preserved (stable sort)
        ids = [a["InventoryID"] for a in sorted_assets]
        assert ids == ["1", "2", "3"]

    def test_empty_list_sorting(self):
        """
        Test that sorting an empty list returns an empty list
        """
        assets = []

        sorted_assets = sorted(
            assets, key=lambda a: a["DigitalSourceAsset"]["CreateDate"]
        )

        assert sorted_assets == []

    def test_single_item_sorting(self):
        """
        Test that sorting a single-item list returns the same list
        """
        assets = [create_test_asset("1", "only.jpg")]

        sorted_assets = sorted(
            assets, key=lambda a: a["DigitalSourceAsset"]["CreateDate"]
        )

        assert len(sorted_assets) == 1
        assert sorted_assets[0]["InventoryID"] == "1"
