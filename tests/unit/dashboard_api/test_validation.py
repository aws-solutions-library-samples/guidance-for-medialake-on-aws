"""Unit tests for dashboard layout validation utilities.

Property 3: Layout Validation
Validates: Requirements 2.2, 2.3, 2.4
"""

import sys
from pathlib import Path

# Add the dashboard_api to the path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent / "lambdas" / "api" / "dashboard_api"
    ),
)

from dashboard_defaults import WIDGET_CONSTRAINTS
from dashboard_validation import (
    MAX_CONFIG_SIZE_BYTES,
    MAX_LAYOUT_SIZE_BYTES,
    MAX_WIDGETS,
    validate_config_size,
    validate_layout,
    validate_layout_size,
    validate_widget_configs,
    validate_widget_count,
    validate_widget_sizes,
)


class TestValidateWidgetCount:
    """Tests for validate_widget_count function."""

    def test_valid_widget_count(self):
        """Test that valid widget counts pass validation."""
        widgets = [{"id": f"widget-{i}", "type": "favorites"} for i in range(10)]
        result = validate_widget_count(widgets)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_max_widget_count(self):
        """Test that exactly MAX_WIDGETS passes validation."""
        widgets = [
            {"id": f"widget-{i}", "type": "favorites"} for i in range(MAX_WIDGETS)
        ]
        result = validate_widget_count(widgets)
        assert result.is_valid is True

    def test_exceeds_max_widget_count(self):
        """Test that exceeding MAX_WIDGETS fails validation."""
        widgets = [
            {"id": f"widget-{i}", "type": "favorites"} for i in range(MAX_WIDGETS + 1)
        ]
        result = validate_widget_count(widgets)
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "widgets" in result.errors[0].field
        assert str(MAX_WIDGETS) in result.errors[0].message

    def test_empty_widgets(self):
        """Test that empty widget list passes validation."""
        result = validate_widget_count([])
        assert result.is_valid is True


class TestValidateWidgetSizes:
    """Tests for validate_widget_sizes function."""

    def test_valid_widget_sizes(self):
        """Test that valid widget sizes pass validation."""
        widgets = [{"id": "fav-1", "type": "favorites"}]
        layouts = {"lg": [{"i": "fav-1", "x": 0, "y": 0, "w": 6, "h": 4}]}
        result = validate_widget_sizes(widgets, layouts)
        assert result.is_valid is True

    def test_widget_width_below_minimum(self):
        """Test that width below minimum fails validation."""
        widgets = [{"id": "fav-1", "type": "favorites"}]
        min_w = WIDGET_CONSTRAINTS["favorites"]["minSize"]["w"]
        layouts = {"lg": [{"i": "fav-1", "x": 0, "y": 0, "w": min_w - 1, "h": 4}]}
        result = validate_widget_sizes(widgets, layouts)
        assert result.is_valid is False
        assert any("below minimum" in e.message for e in result.errors)

    def test_widget_width_above_maximum(self):
        """Test that width above maximum fails validation."""
        widgets = [{"id": "fav-1", "type": "favorites"}]
        max_w = WIDGET_CONSTRAINTS["favorites"]["maxSize"]["w"]
        layouts = {"lg": [{"i": "fav-1", "x": 0, "y": 0, "w": max_w + 1, "h": 4}]}
        result = validate_widget_sizes(widgets, layouts)
        assert result.is_valid is False
        assert any("exceeds maximum" in e.message for e in result.errors)

    def test_widget_height_below_minimum(self):
        """Test that height below minimum fails validation."""
        widgets = [{"id": "fav-1", "type": "favorites"}]
        min_h = WIDGET_CONSTRAINTS["favorites"]["minSize"]["h"]
        layouts = {"lg": [{"i": "fav-1", "x": 0, "y": 0, "w": 6, "h": min_h - 1}]}
        result = validate_widget_sizes(widgets, layouts)
        assert result.is_valid is False

    def test_unknown_widget_type_passes(self):
        """Test that unknown widget types are skipped (not validated)."""
        widgets = [{"id": "unknown-1", "type": "unknown-type"}]
        layouts = {"lg": [{"i": "unknown-1", "x": 0, "y": 0, "w": 100, "h": 100}]}
        result = validate_widget_sizes(widgets, layouts)
        assert result.is_valid is True


class TestValidateLayoutSize:
    """Tests for validate_layout_size function."""

    def test_valid_layout_size(self):
        """Test that normal layout size passes validation."""
        widgets = [{"id": "fav-1", "type": "favorites", "config": {}}]
        layouts = {"lg": [{"i": "fav-1", "x": 0, "y": 0, "w": 6, "h": 4}]}
        result = validate_layout_size(widgets, layouts)
        assert result.is_valid is True

    def test_exceeds_max_layout_size(self):
        """Test that exceeding max layout size fails validation."""
        # Create a large layout that exceeds 32KB
        large_config = {"data": "x" * (MAX_LAYOUT_SIZE_BYTES + 1000)}
        widgets = [{"id": "fav-1", "type": "favorites", "config": large_config}]
        layouts = {"lg": [{"i": "fav-1", "x": 0, "y": 0, "w": 6, "h": 4}]}
        result = validate_layout_size(widgets, layouts)
        assert result.is_valid is False
        assert any("exceeds maximum" in e.message for e in result.errors)


class TestValidateConfigSize:
    """Tests for validate_config_size function."""

    def test_valid_config_size(self):
        """Test that normal config size passes validation."""
        widgets = [{"id": "fav-1", "type": "favorites", "config": {"key": "value"}}]
        result = validate_config_size(widgets)
        assert result.is_valid is True

    def test_exceeds_max_config_size(self):
        """Test that exceeding max config size fails validation."""
        large_config = {"data": "x" * (MAX_CONFIG_SIZE_BYTES + 100)}
        widgets = [{"id": "fav-1", "type": "favorites", "config": large_config}]
        result = validate_config_size(widgets)
        assert result.is_valid is False
        assert any("config" in e.field.lower() for e in result.errors)

    def test_empty_config_passes(self):
        """Test that empty config passes validation."""
        widgets = [{"id": "fav-1", "type": "favorites", "config": {}}]
        result = validate_config_size(widgets)
        assert result.is_valid is True

    def test_no_config_passes(self):
        """Test that missing config passes validation."""
        widgets = [{"id": "fav-1", "type": "favorites"}]
        result = validate_config_size(widgets)
        assert result.is_valid is True


class TestValidateLayout:
    """Tests for validate_layout aggregate function."""

    def test_valid_layout_passes_all_validations(self):
        """Test that a valid layout passes all validations."""
        widgets = [
            {"id": "fav-1", "type": "favorites", "config": {}},
            {"id": "coll-1", "type": "collections", "config": {}},
        ]
        layouts = {
            "lg": [
                {"i": "fav-1", "x": 0, "y": 0, "w": 6, "h": 4},
                {"i": "coll-1", "x": 6, "y": 0, "w": 6, "h": 4},
            ]
        }
        result = validate_layout(widgets, layouts)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are aggregated."""
        # Too many widgets AND invalid size
        widgets = [
            {"id": f"w-{i}", "type": "favorites"} for i in range(MAX_WIDGETS + 1)
        ]
        layouts = {
            "lg": [{"i": "w-0", "x": 0, "y": 0, "w": 1, "h": 1}]  # Below min size
        }
        result = validate_layout(widgets, layouts)
        assert result.is_valid is False
        assert len(result.errors) >= 2  # At least widget count and size errors


class TestValidateWidgetConfigs:
    """Tests for validate_widget_configs function."""

    def test_valid_collections_widget_config(self):
        """Test that valid collections widget config passes validation."""
        widgets = [
            {
                "id": "coll-1",
                "type": "collections",
                "config": {
                    "viewType": "all",
                    "sorting": {"sortBy": "name", "sortOrder": "asc"},
                },
            }
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_collections_widget_missing_config(self):
        """Test that collections widget without config fails validation."""
        widgets = [{"id": "coll-1", "type": "collections"}]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        assert any("requires a config object" in e.message for e in result.errors)

    def test_collections_widget_empty_config(self):
        """Test that collections widget with empty config fails validation."""
        widgets = [{"id": "coll-1", "type": "collections", "config": {}}]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        # Should have errors for missing viewType and sorting
        assert len(result.errors) >= 2

    def test_collections_widget_invalid_view_type(self):
        """Test that invalid viewType fails validation."""
        widgets = [
            {
                "id": "coll-1",
                "type": "collections",
                "config": {
                    "viewType": "invalid-view",
                    "sorting": {"sortBy": "name", "sortOrder": "asc"},
                },
            }
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        assert any("Invalid viewType" in e.message for e in result.errors)

    def test_collections_widget_missing_view_type(self):
        """Test that missing viewType fails validation."""
        widgets = [
            {
                "id": "coll-1",
                "type": "collections",
                "config": {"sorting": {"sortBy": "name", "sortOrder": "asc"}},
            }
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        assert any("viewType" in e.field for e in result.errors)

    def test_collections_widget_invalid_sort_by(self):
        """Test that invalid sortBy fails validation."""
        widgets = [
            {
                "id": "coll-1",
                "type": "collections",
                "config": {
                    "viewType": "all",
                    "sorting": {"sortBy": "invalid-field", "sortOrder": "asc"},
                },
            }
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        assert any("Invalid sortBy" in e.message for e in result.errors)

    def test_collections_widget_invalid_sort_order(self):
        """Test that invalid sortOrder fails validation."""
        widgets = [
            {
                "id": "coll-1",
                "type": "collections",
                "config": {
                    "viewType": "all",
                    "sorting": {"sortBy": "name", "sortOrder": "invalid-order"},
                },
            }
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        assert any("Invalid sortOrder" in e.message for e in result.errors)

    def test_collections_widget_missing_sorting(self):
        """Test that missing sorting object fails validation."""
        widgets = [
            {"id": "coll-1", "type": "collections", "config": {"viewType": "all"}}
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        assert any("sorting" in e.field for e in result.errors)

    def test_collections_widget_invalid_sorting_type(self):
        """Test that non-object sorting fails validation."""
        widgets = [
            {
                "id": "coll-1",
                "type": "collections",
                "config": {"viewType": "all", "sorting": "not-an-object"},
            }
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        assert any("must be an object" in e.message for e in result.errors)

    def test_collections_widget_all_view_types(self):
        """Test that all valid view types pass validation."""
        view_types = [
            "all",
            "public",
            "private",
            "my-collections",
            "shared-with-me",
            "my-shared",
        ]

        for view_type in view_types:
            widgets = [
                {
                    "id": "coll-1",
                    "type": "collections",
                    "config": {
                        "viewType": view_type,
                        "sorting": {"sortBy": "name", "sortOrder": "asc"},
                    },
                }
            ]
            result = validate_widget_configs(widgets)
            assert result.is_valid is True, f"View type '{view_type}' should be valid"

    def test_collections_widget_all_sort_by_options(self):
        """Test that all valid sortBy options pass validation."""
        sort_by_options = ["name", "createdAt", "updatedAt"]

        for sort_by in sort_by_options:
            widgets = [
                {
                    "id": "coll-1",
                    "type": "collections",
                    "config": {
                        "viewType": "all",
                        "sorting": {"sortBy": sort_by, "sortOrder": "asc"},
                    },
                }
            ]
            result = validate_widget_configs(widgets)
            assert result.is_valid is True, f"sortBy '{sort_by}' should be valid"

    def test_collections_widget_all_sort_orders(self):
        """Test that all valid sortOrder options pass validation."""
        sort_orders = ["asc", "desc"]

        for sort_order in sort_orders:
            widgets = [
                {
                    "id": "coll-1",
                    "type": "collections",
                    "config": {
                        "viewType": "all",
                        "sorting": {"sortBy": "name", "sortOrder": sort_order},
                    },
                }
            ]
            result = validate_widget_configs(widgets)
            assert result.is_valid is True, f"sortOrder '{sort_order}' should be valid"

    def test_non_collections_widgets_not_validated(self):
        """Test that non-collections widgets are not validated for config."""
        # Favorites and recent-assets don't require config
        widgets = [
            {"id": "fav-1", "type": "favorites"},
            {"id": "recent-1", "type": "recent-assets"},
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is True

    def test_multiple_collections_widgets_validated_independently(self):
        """Test that multiple collections widgets are validated independently."""
        widgets = [
            {
                "id": "coll-1",
                "type": "collections",
                "config": {
                    "viewType": "all",
                    "sorting": {"sortBy": "name", "sortOrder": "asc"},
                },
            },
            {
                "id": "coll-2",
                "type": "collections",
                "config": {
                    "viewType": "public",
                    "sorting": {"sortBy": "createdAt", "sortOrder": "desc"},
                },
            },
            {"id": "coll-3", "type": "collections"},  # Invalid - missing config
        ]
        result = validate_widget_configs(widgets)
        assert result.is_valid is False
        # Should only have error for coll-3
        assert len(result.errors) == 1
        assert "coll-3" in result.errors[0].field
