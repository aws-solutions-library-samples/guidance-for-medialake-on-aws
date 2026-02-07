"""Integration tests for Dashboard API data isolation.

Property 7: Data Isolation
Validates: Requirements 6.2, 6.3

These tests require a deployed Dashboard API with two different test users.
"""

import os
from typing import Dict

import pytest
import requests

# Skip all tests if API endpoint is not configured
API_ENDPOINT = os.environ.get("DASHBOARD_API_ENDPOINT")
USER_A_TOKEN = os.environ.get("TEST_USER_A_TOKEN")
USER_B_TOKEN = os.environ.get("TEST_USER_B_TOKEN")

pytestmark = pytest.mark.skipif(
    not API_ENDPOINT or not USER_A_TOKEN or not USER_B_TOKEN,
    reason="DASHBOARD_API_ENDPOINT, TEST_USER_A_TOKEN, and TEST_USER_B_TOKEN required",
)


def get_headers_user_a() -> Dict[str, str]:
    """Get request headers for User A."""
    return {
        "Authorization": f"Bearer {USER_A_TOKEN}",
        "Content-Type": "application/json",
    }


def get_headers_user_b() -> Dict[str, str]:
    """Get request headers for User B."""
    return {
        "Authorization": f"Bearer {USER_B_TOKEN}",
        "Content-Type": "application/json",
    }


class TestDataIsolation:
    """Property 7: Data Isolation tests."""

    def test_user_a_cannot_see_user_b_layout(self):
        """Test that User A cannot access User B's layout."""
        # User B saves a unique layout
        unique_widget_id = "user-b-unique-widget"
        user_b_layout = {
            "widgets": [{"id": unique_widget_id, "type": "favorites", "config": {}}],
            "layouts": {
                "lg": [{"i": unique_widget_id, "x": 0, "y": 0, "w": 6, "h": 4}]
            },
        }

        save_response = requests.put(
            f"{API_ENDPOINT}/dashboard/layout",
            headers=get_headers_user_b(),
            json=user_b_layout,
        )
        assert save_response.status_code == 200

        # User A retrieves their layout
        get_response = requests.get(
            f"{API_ENDPOINT}/dashboard/layout", headers=get_headers_user_a()
        )

        assert get_response.status_code == 200
        user_a_layout = get_response.json()["data"]

        # User A should NOT see User B's unique widget
        widget_ids = [w["id"] for w in user_a_layout["widgets"]]
        assert unique_widget_id not in widget_ids

    def test_user_a_cannot_see_user_b_presets(self):
        """Test that User A cannot see User B's presets in listing."""
        preset_id = None

        try:
            # User B creates a preset
            create_response = requests.post(
                f"{API_ENDPOINT}/dashboard/presets",
                headers=get_headers_user_b(),
                json={"name": "User B Private Preset"},
            )

            if create_response.status_code == 201:
                preset_id = create_response.json()["data"]["presetId"]

            # User A lists their presets
            list_response = requests.get(
                f"{API_ENDPOINT}/dashboard/presets", headers=get_headers_user_a()
            )

            assert list_response.status_code == 200
            user_a_presets = list_response.json()["data"]

            # User A should NOT see User B's preset
            preset_ids = [p["presetId"] for p in user_a_presets]
            if preset_id:
                assert preset_id not in preset_ids

        finally:
            if preset_id:
                requests.delete(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers_user_b(),
                )

    def test_user_a_cannot_access_user_b_preset_directly(self):
        """Test that User A cannot access User B's preset by ID."""
        preset_id = None

        try:
            # User B creates a preset
            create_response = requests.post(
                f"{API_ENDPOINT}/dashboard/presets",
                headers=get_headers_user_b(),
                json={"name": "User B Secret Preset"},
            )

            if create_response.status_code == 201:
                preset_id = create_response.json()["data"]["presetId"]

                # User A tries to access User B's preset
                get_response = requests.get(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers_user_a(),
                )

                # Should return 404 (not found for this user) or 403 (forbidden)
                assert get_response.status_code in [403, 404]

        finally:
            if preset_id:
                requests.delete(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers_user_b(),
                )

    def test_user_a_cannot_delete_user_b_preset(self):
        """Test that User A cannot delete User B's preset."""
        preset_id = None

        try:
            # User B creates a preset
            create_response = requests.post(
                f"{API_ENDPOINT}/dashboard/presets",
                headers=get_headers_user_b(),
                json={"name": "User B Protected Preset"},
            )

            if create_response.status_code == 201:
                preset_id = create_response.json()["data"]["presetId"]

                # User A tries to delete User B's preset
                delete_response = requests.delete(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers_user_a(),
                )

                # Should return 404 (not found for this user) or 403 (forbidden)
                assert delete_response.status_code in [403, 404]

                # Verify preset still exists for User B
                verify_response = requests.get(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers_user_b(),
                )
                assert verify_response.status_code == 200

        finally:
            if preset_id:
                requests.delete(
                    f"{API_ENDPOINT}/dashboard/presets/{preset_id}",
                    headers=get_headers_user_b(),
                )
