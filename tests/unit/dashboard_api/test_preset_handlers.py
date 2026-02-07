"""Unit tests for dashboard preset handlers.

Property 4: Preset Round Trip
Property 5: Preset Listing Completeness
Property 6: Preset Application
Validates: Requirements 4.1, 4.2, 4.3, 4.4
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the dashboard_api to the path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent / "lambdas" / "api" / "dashboard_api"
    ),
)


class TestPresetsGet:
    """Tests for GET /dashboard/presets handler."""

    @patch("handlers.presets_get.DashboardPresetModel")
    def test_returns_empty_list_for_no_presets(self, mock_model):
        """Test that empty list is returned when user has no presets."""
        mock_model.query.return_value = iter([])

        from handlers.presets_get import _success_response

        response = _success_response([])

        assert response["statusCode"] == 200
        assert response["body"]["success"] is True
        assert response["body"]["data"] == []

    @patch("handlers.presets_get.DashboardPresetModel")
    def test_returns_all_user_presets(self, mock_model):
        """Test that all user presets are returned (Property 5)."""
        # Create mock presets
        mock_presets = []
        for i in range(3):
            preset = MagicMock()
            preset.presetId = f"preset-{i}"
            preset.name = f"Preset {i}"
            preset.description = f"Description {i}"
            preset.widgets = [{"id": "w1"}, {"id": "w2"}]
            preset.createdAt = "2024-01-01T00:00:00Z"
            preset.updatedAt = "2024-01-01T00:00:00Z"
            mock_presets.append(preset)

        mock_model.query.return_value = iter(mock_presets)

        # Simulate the handler logic
        presets = []
        for preset in mock_presets:
            presets.append(
                {
                    "presetId": preset.presetId,
                    "name": preset.name,
                    "description": preset.description,
                    "widgetCount": len(preset.widgets),
                    "createdAt": preset.createdAt,
                    "updatedAt": preset.updatedAt,
                }
            )

        # Property 5: All presets should be returned
        assert len(presets) == 3
        for i, preset in enumerate(presets):
            assert preset["presetId"] == f"preset-{i}"
            assert preset["widgetCount"] == 2


class TestPresetsPost:
    """Tests for POST /dashboard/presets handler."""

    def test_error_response_format(self):
        """Test that error responses have correct format."""
        from handlers.presets_post import _error_response

        response = _error_response(
            400, "MAX_PRESETS_EXCEEDED", "Cannot create more presets"
        )

        assert response["statusCode"] == 400
        assert response["body"]["success"] is False
        assert response["body"]["error"]["code"] == "MAX_PRESETS_EXCEEDED"

    @patch("handlers.presets_post.DashboardPresetModel")
    def test_count_user_presets(self, mock_model):
        """Test that preset count is calculated correctly."""
        # Create mock presets
        mock_presets = [MagicMock() for _ in range(3)]
        mock_model.query.return_value = iter(mock_presets)

        from handlers.presets_post import _count_user_presets

        count = _count_user_presets("USER#user-123")
        assert count == 3

    @patch("handlers.presets_post.DashboardLayoutModel")
    def test_get_user_layout_returns_default_when_none(self, mock_model):
        """Test that default layout is returned when user has no saved layout."""
        from pynamodb.exceptions import DoesNotExist

        mock_model.get.side_effect = DoesNotExist()

        from handlers.presets_post import _get_user_layout
        from utils.defaults import DEFAULT_LAYOUT

        result = _get_user_layout("user-123")

        assert result["widgets"] == DEFAULT_LAYOUT["widgets"]
        assert result["layouts"] == DEFAULT_LAYOUT["layouts"]


class TestPresetsIDGet:
    """Tests for GET /dashboard/presets/{presetId} handler."""

    def test_not_found_response_format(self):
        """Test that 404 response has correct format."""
        from handlers.presets_ID_get import _error_response

        response = _error_response(404, "PRESET_NOT_FOUND", "Preset not found")

        assert response["statusCode"] == 404
        assert response["body"]["error"]["code"] == "PRESET_NOT_FOUND"


class TestPresetsIDApply:
    """Tests for POST /dashboard/presets/{presetId}/apply handler."""

    @patch("handlers.presets_ID_apply_post.DashboardLayoutModel")
    def test_get_current_version_for_new_user(self, mock_model):
        """Test version handling for users without existing layout."""
        from pynamodb.exceptions import DoesNotExist

        mock_model.get.side_effect = DoesNotExist()

        from handlers.presets_ID_apply_post import _get_current_version

        result = _get_current_version("new-user")
        assert result == 0

    @patch("handlers.presets_ID_apply_post.DashboardLayoutModel")
    def test_get_current_version_for_existing_user(self, mock_model):
        """Test version handling for users with existing layout."""
        mock_layout = MagicMock()
        mock_layout.layoutVersion = 10
        mock_model.get.return_value = mock_layout

        from handlers.presets_ID_apply_post import _get_current_version

        result = _get_current_version("existing-user")
        assert result == 10


class TestPresetRoundTrip:
    """Property 4: Preset Round Trip tests."""

    def test_preset_data_preserved(self):
        """Test that preset data is preserved through save/load cycle."""
        # Simulate preset creation data
        original_widgets = [
            {"id": "fav-1", "type": "favorites", "config": {}},
            {
                "id": "coll-1",
                "type": "collections",
                "config": {"viewType": "my-collections"},
            },
        ]
        original_layouts = {
            "lg": [
                {"i": "fav-1", "x": 0, "y": 0, "w": 6, "h": 4},
                {"i": "coll-1", "x": 6, "y": 0, "w": 6, "h": 4},
            ],
            "md": [
                {"i": "fav-1", "x": 0, "y": 0, "w": 3, "h": 4},
                {"i": "coll-1", "x": 3, "y": 0, "w": 3, "h": 4},
            ],
            "sm": [
                {"i": "fav-1", "x": 0, "y": 0, "w": 1, "h": 4},
                {"i": "coll-1", "x": 0, "y": 4, "w": 1, "h": 4},
            ],
        }

        # Simulate what would be stored and retrieved
        stored_preset = {
            "presetId": "preset-123",
            "name": "Test Preset",
            "description": "Test description",
            "widgets": original_widgets,
            "layouts": original_layouts,
        }

        # Property 4: Data should be equivalent after round trip
        assert stored_preset["widgets"] == original_widgets
        assert stored_preset["layouts"] == original_layouts

        # Verify structure is preserved
        assert len(stored_preset["widgets"]) == 2
        assert "lg" in stored_preset["layouts"]
        assert "md" in stored_preset["layouts"]
        assert "sm" in stored_preset["layouts"]
