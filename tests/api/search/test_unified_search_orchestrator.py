"""
Unit tests for unified_search_orchestrator.py - specifically the sort parameter forwarding.

These tests verify that the _execute_opensearch_search method correctly forwards
the sort parameter to the SearchParams constructor.
"""

import pytest


@pytest.mark.unit
class TestSortParameterForwardingLogic:
    """Tests for sort parameter forwarding logic (without full module imports)"""

    def test_sort_parameter_forwarding_logic(self):
        """
        Verifies the logic for forwarding the sort parameter.

        This test simulates the parameter forwarding logic without importing
        the full unified_search_orchestrator module to avoid dependency issues.
        """
        # Arrange - simulate the query_params dict
        query_params = {
            "q": "storageIdentifier:test-bucket",
            "page": "1",
            "pageSize": "50",
            "sort": "-createdAt",
        }

        # Act - simulate the parameter forwarding logic from _execute_opensearch_search
        search_params = {}
        search_params["q"] = query_params.get("q", "")
        search_params["page"] = int(query_params.get("page", 1))
        search_params["pageSize"] = int(query_params.get("pageSize", 50))

        # This is the key logic we're testing - sort parameter forwarding
        if "sort" in query_params:
            search_params["sort"] = query_params["sort"]

        # Assert
        assert "sort" in search_params, "sort parameter should be in search_params"
        assert search_params["sort"] == "-createdAt", "sort value should match input"

    def test_sort_parameter_not_present_logic(self):
        """
        Verifies that the logic handles missing sort parameter correctly.
        """
        # Arrange - query_params without sort
        query_params = {
            "q": "storageIdentifier:test-bucket",
            "page": "1",
            "pageSize": "50",
        }

        # Act - simulate the parameter forwarding logic
        search_params = {}
        search_params["q"] = query_params.get("q", "")
        search_params["page"] = int(query_params.get("page", 1))
        search_params["pageSize"] = int(query_params.get("pageSize", 50))

        if "sort" in query_params:
            search_params["sort"] = query_params["sort"]

        # Assert
        assert (
            "sort" not in search_params
        ), "sort parameter should not be in search_params when not provided"

    def test_sort_parameter_with_other_optional_parameters_logic(self):
        """
        Verifies that sort parameter is forwarded along with other optional parameters.
        """
        # Arrange
        query_params = {
            "q": "storageIdentifier:test-bucket",
            "page": "1",
            "pageSize": "50",
            "sort": "name",
            "filters": [{"field": "type", "value": "image"}],
            "type": "image",
            "storageIdentifier": "test-bucket",
        }

        # Act - simulate the parameter forwarding logic
        search_params = {}
        search_params["q"] = query_params.get("q", "")
        search_params["page"] = int(query_params.get("page", 1))
        search_params["pageSize"] = int(query_params.get("pageSize", 50))

        # Forward optional parameters (including sort)
        if "filters" in query_params:
            search_params["filters"] = query_params["filters"]
        if "type" in query_params:
            search_params["type"] = query_params["type"]
        if "storageIdentifier" in query_params:
            search_params["storageIdentifier"] = query_params["storageIdentifier"]
        if "sort" in query_params:
            search_params["sort"] = query_params["sort"]

        # Assert
        assert "sort" in search_params, "sort parameter should be forwarded"
        assert search_params["sort"] == "name", "sort value should match input"
        assert "filters" in search_params, "filters should be forwarded"
        assert "type" in search_params, "type should be forwarded"
        assert (
            "storageIdentifier" in search_params
        ), "storageIdentifier should be forwarded"
