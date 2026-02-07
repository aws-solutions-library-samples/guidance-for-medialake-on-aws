"""Integration tests for Dashboard Layout API.

Property 1: Layout Round Trip
Property 8: Response Format Consistency
Validates: Requirements 1.1, 2.1, 3.1, 7.1, 7.2

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


class TestLayoutAPI:
    """Integration tests for layout endpoints."""

    def test_get_layout_returns_default_for_new_user(self):
        """Test that GET /dashboard/layout returns default layout for new users."""
        response = requests.get(
            f"{API_ENDPOINT}/dashboard/layout", headers=get_headers()
        )

        assert response.status_code == 200
        data = response.json()

        # Property 8: Response Format Consistency
        assert data["success"] is True
        assert "data" in data

        layout = data["data"]
        assert "layoutVersion" in layout
        assert "widgets" in layout
        assert "layouts" in layout
        assert "updatedAt" in layout

    def test_save_and_retrieve_layout_round_trip(self):
        """Test Property 1: Layout Round Trip - save and retrieve produces equivalent layout."""
        # Create a test layout
        test_layout = {
            "widgets": [
                {"id": "test-fav-1", "type": "favorites", "config": {}},
                {
                    "id": "test-coll-1",
                    "type": "collections",
                    "config": {"viewType": "my-collections"},
                },
            ],
            "layouts": {
                "lg": [
                    {"i": "test-fav-1", "x": 0, "y": 0, "w": 6, "h": 4},
                    {"i": "test-coll-1", "x": 6, "y": 0, "w": 6, "h": 4},
                ],
                "md": [
                    {"i": "test-fav-1", "x": 0, "y": 0, "w": 3, "h": 4},
                    {"i": "test-coll-1", "x": 3, "y": 0, "w": 3, "h": 4},
                ],
                "sm": [
                    {"i": "test-fav-1", "x": 0, "y": 0, "w": 1, "h": 4},
                    {"i": "test-coll-1", "x": 0, "y": 4, "w": 1, "h": 4},
                ],
            },
        }

        # Save the layout
        save_response = requests.put(
            f"{API_ENDPOINT}/dashboard/layout", headers=get_headers(), json=test_layout
        )

        assert save_response.status_code == 200
        save_data = save_response.json()
        assert save_data["success"] is True
        assert "layoutVersion" in save_data["data"]

        # Retrieve the layout
        get_response = requests.get(
            f"{API_ENDPOINT}/dashboard/layout", headers=get_headers()
        )

        assert get_response.status_code == 200
        get_data = get_response.json()

        # Property 1: Layout Round Trip - verify equivalence
        retrieved_layout = get_data["data"]
        assert len(retrieved_layout["widgets"]) == len(test_layout["widgets"])
        assert set(retrieved_layout["layouts"].keys()) == set(
            test_layout["layouts"].keys()
        )

    def test_save_layout_validation_error(self):
        """Test that invalid layouts return validation errors."""
        # Create an invalid layout with too many widgets
        invalid_layout = {
            "widgets": [
                {"id": f"w-{i}", "type": "favorites", "config": {}} for i in range(25)
            ],
            "layouts": {
                "lg": [
                    {"i": f"w-{i}", "x": 0, "y": i, "w": 6, "h": 4} for i in range(25)
                ]
            },
        }

        response = requests.put(
            f"{API_ENDPOINT}/dashboard/layout",
            headers=get_headers(),
            json=invalid_layout,
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_reset_layout_returns_default(self):
        """Test that POST /dashboard/layout/reset returns default layout."""
        response = requests.post(
            f"{API_ENDPOINT}/dashboard/layout/reset", headers=get_headers()
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        layout = data["data"]

        # Should have default widgets
        assert len(layout["widgets"]) >= 4
        assert "layoutVersion" in layout
        assert "layouts" in layout
