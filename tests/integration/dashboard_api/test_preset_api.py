"""Integration tests for Dashboard Preset API.

Property 4: Preset Round Trip
Property 5: Preset Listing Completeness
Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6

These tests require a deployed Dashboard API or LocalStack environment.
"""

import os
from typing import Dict

import pytest
import requests

# Skip all tests if API endpoint is not configured
API_ENDPOINT = os.environ.get("DASHBOARD_API_ENDPOINT")
AUTH_TOKEN = os.environ.get("TEST_AUTH_TOKEN")

pytestmark = pytest.mark.skipif(
    not API_ENDPOINT or not AUTH_TOKEN,
    reason="DASHBOARD_API_ENDPOINT and TEST_AUTH_TOKEN environment variables required",
)


def get_headers() -> Dict[str, str]:
    """Get request headers with authorization."""
    return {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
    }


class TestPresetAPI:
    """Integration tests for preset endpoints."""

    def test_list_presets_returns_array(self):
        """Test that GET /dashboard/presets returns an array."""
        response = requests.get(
            f"{API_ENDPOINT}/dashboard/presets", headers=get_headers()
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_create_preset_round_trip(self):
        """Test Property 4: Preset Round Trip - create and retrieve preset."""
        # Create a preset
        create_request = {
            "name": "Test Preset",
            "description": "Integration test preset",
        }

        create_response = requests.post(
            f"{API_ENDPOINT}/dashboard/presets",
            headers=get_headers(),
            json=create_request,
        )

        assert create_response.status_code == 201
        create_data = create_response.json()

        assert create_data["success"] is True
        preset_id = create_data["data"]["presetId"]
        assert create_data["data"]["name"] == "Test Preset"

        # Retrieve the preset
        get_response = requests.get(
            f"{API_ENDPOINT}/dashboard/presets/{preset_id}", headers=get_headers()
        )

        assert get_response.status_code == 200
        get_data = get_response.json()

        # Property 4: Verify round trip equivalence
        assert get_data["data"]["name"] == "Test Preset"
        assert get_data["data"]["description"] == "Integration test preset"

        # Cleanup - delete the preset
        delete_response = requests.delete(
            f"{API_ENDPOINT}/dashboard/presets/{preset_id}", headers=get_headers()
        )
        assert delete_response.status_code == 204

    def test_preset_listing_completeness(self):
        """Test Property 5: All created presets appear in listing."""
        created_preset_ids = []

        try:
            # Create multiple presets
            for i in range(3):
                create_response = requests.post(
                    f"{API_ENDPOINT}/dashboard/presets",
                    headers=get_headers(),
                    json={"name": f"Completeness Test {i}", "description": f"Test {i}"},
                )

                if create_response.status_code == 201:
                    preset_id = create_response.json()["data"]["presetId"]
                    created_preset_ids.append(preset_id)

            # List all presets
            list_response = requests.get(
                f"{API_ENDPOINT}/dashboard/presets", headers=get_headers()
            )

            assert list_response.status_code == 200
            presets = list_response.json()["data"]

            # Property 5: All created presets should be in the list
            listed_ids = {p["presetId"] for p in presets}
            for preset_id in created_preset_ids:
                assert (
                    preset_id in listed_ids
                ), f"Preset {preset_id} not found in listing"

        finally:
            # Cleanup
            for preset_id in created_preset_ids:
                requests.delete(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers(),
                )

    def test_apply_preset_updates_layout(self):
        """Test that applying a preset updates the active layout."""
        preset_id = None

        try:
            # Create a preset
            create_response = requests.post(
                f"{API_ENDPOINT}/dashboard/presets",
                headers=get_headers(),
                json={"name": "Apply Test Preset"},
            )

            assert create_response.status_code == 201
            preset_id = create_response.json()["data"]["presetId"]

            # Apply the preset
            apply_response = requests.post(
                f"{API_ENDPOINT}/dashboard/presets/{preset_id}/apply",
                headers=get_headers(),
            )

            assert apply_response.status_code == 200
            apply_data = apply_response.json()

            assert apply_data["success"] is True
            assert "layoutVersion" in apply_data["data"]
            assert "widgets" in apply_data["data"]
            assert "layouts" in apply_data["data"]

        finally:
            if preset_id:
                requests.delete(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers(),
                )

    def test_update_preset(self):
        """Test that PUT /dashboard/presets/{id} updates preset."""
        preset_id = None

        try:
            # Create a preset
            create_response = requests.post(
                f"{API_ENDPOINT}/dashboard/presets",
                headers=get_headers(),
                json={"name": "Original Name", "description": "Original description"},
            )

            assert create_response.status_code == 201
            preset_id = create_response.json()["data"]["presetId"]

            # Update the preset
            update_response = requests.put(
                f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                headers=get_headers(),
                json={"name": "Updated Name", "description": "Updated description"},
            )

            assert update_response.status_code == 200
            update_data = update_response.json()

            assert update_data["data"]["name"] == "Updated Name"
            assert update_data["data"]["description"] == "Updated description"

        finally:
            if preset_id:
                requests.delete(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers(),
                )

    def test_delete_preset(self):
        """Test that DELETE /dashboard/presets/{id} removes preset."""
        # Create a preset
        create_response = requests.post(
            f"{API_ENDPOINT}/dashboard/presets",
            headers=get_headers(),
            json={"name": "Delete Test Preset"},
        )

        assert create_response.status_code == 201
        preset_id = create_response.json()["data"]["presetId"]

        # Delete the preset
        delete_response = requests.delete(
            f"{API_ENDPOINT}/dashboard/presets/{preset_id}", headers=get_headers()
        )

        assert delete_response.status_code == 204

        # Verify it's gone
        get_response = requests.get(
            f"{API_ENDPOINT}/dashboard/presets/{preset_id}", headers=get_headers()
        )

        assert get_response.status_code == 404

    def test_get_nonexistent_preset_returns_404(self):
        """Test that GET /dashboard/presets/{id} returns 404 for nonexistent preset."""
        response = requests.get(
            f"{API_ENDPOINT}/dashboard/presets/nonexistent-preset-id",
            headers=get_headers(),
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "PRESET_NOT_FOUND"
