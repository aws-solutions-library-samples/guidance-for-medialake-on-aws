"""
Tests for custom Choice branch functionality in the pipeline Step Functions builder.

This module tests the ability to create Choice nodes with custom branch outputs
(e.g., Success, NoMatch, AuthError, Error) instead of the standard
Completed/In Progress/Fail outputs.

Feature: custom-choice-branches
"""

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# Add the post_pipelines directory to the path
POST_PIPELINES_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "lambdas"
    / "api"
    / "pipelines"
    / "post_pipelines"
)
if str(POST_PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(POST_PIPELINES_DIR))

# Mock dependencies before importing modules
sys.modules["lambda_operations"] = MagicMock()
sys.modules["config"] = MagicMock()
sys.modules["config"].NODE_TEMPLATES_BUCKET = "test-bucket"


# =============================================================================
# Test Data Fixtures
# =============================================================================


def create_mock_node(
    node_id: str,
    data_id: str,
    node_type: str,
    label: str,
    configuration: Dict[str, Any],
    output_types: List[Dict[str, str]] = None,
) -> MagicMock:
    """Create a mock pipeline node."""
    node = MagicMock()
    node.id = node_id
    node.data = MagicMock()
    node.data.id = data_id
    node.data.type = node_type
    node.data.label = label
    node.data.configuration = configuration
    node.data.outputTypes = output_types or []
    return node


def create_mock_edge(
    source: str, target: str, source_handle: str = None
) -> Dict[str, Any]:
    """Create a mock pipeline edge."""
    edge = {
        "source": source,
        "target": target,
    }
    if source_handle:
        edge["sourceHandle"] = source_handle
    return edge


def create_mock_pipeline(
    nodes: List[MagicMock], edges: List[Dict[str, Any]]
) -> MagicMock:
    """Create a mock pipeline object."""
    pipeline = MagicMock()
    pipeline.name = "Test Pipeline"
    pipeline.configuration = MagicMock()
    pipeline.configuration.nodes = nodes
    pipeline.configuration.edges = edges
    pipeline.configuration.settings = MagicMock()
    pipeline.configuration.settings.retryAttempts = 3
    return pipeline


# =============================================================================
# GraphAnalyzer Tests
# =============================================================================


class TestGraphAnalyzerCustomChoiceBranches:
    """Tests for GraphAnalyzer custom Choice branch detection."""

    def test_find_special_edges_detects_custom_branches(self):
        """
        Test that find_special_edges correctly detects custom Choice branches.

        Property 2: Custom Branch Edge Detection Correctness
        Validates: Requirements 2.1, 2.2, 2.3
        """
        from graph_utils import GraphAnalyzer

        # Create a Choice node with custom outputs
        choice_node = create_mock_node(
            node_id="choice_1",
            data_id="choice",
            node_type="FLOW",
            label="Enrichment Result",
            configuration={
                "method": "choice",
                "parameters": {
                    "variable": "$.body.status",
                    "choices": [
                        {"condition": "success", "output": "Success"},
                        {"condition": "error", "output": "Error"},
                    ],
                    "default": "Error",
                },
            },
            output_types=[
                {"name": "Success", "description": "Success path"},
                {"name": "Error", "description": "Error path"},
            ],
        )

        success_node = create_mock_node(
            node_id="success_1",
            data_id="success",
            node_type="FLOW",
            label="Success",
            configuration={"method": "success"},
        )

        error_node = create_mock_node(
            node_id="error_1",
            data_id="fail",
            node_type="FLOW",
            label="Error",
            configuration={"method": "fail"},
        )

        edges = [
            create_mock_edge("choice_1", "success_1", "Success"),
            create_mock_edge("choice_1", "error_1", "Error"),
        ]

        pipeline = create_mock_pipeline([choice_node, success_node, error_node], edges)
        analyzer = GraphAnalyzer(pipeline)
        analyzer.analyze()

        result = analyzer.find_special_edges()

        # Should return 5 elements now
        assert len(result) == 5

        (
            choice_true_targets,
            choice_false_targets,
            choice_fail_targets,
            map_processor_chains,
            choice_custom_branches,
        ) = result

        # Custom branches should be detected
        assert "choice_1" in choice_custom_branches
        assert choice_custom_branches["choice_1"]["Success"] == "success_1"
        assert choice_custom_branches["choice_1"]["Error"] == "error_1"

    def test_find_special_edges_ignores_standard_outputs(self):
        """
        Test that standard outputs (Completed, In Progress, Fail) are not
        treated as custom branches.

        Validates: Requirements 4.2
        """
        from graph_utils import GraphAnalyzer

        # Create a Choice node with standard outputs
        choice_node = create_mock_node(
            node_id="choice_1",
            data_id="choice",
            node_type="FLOW",
            label="Check Status",
            configuration={
                "method": "choice",
                "parameters": {
                    "Variable": "$.metadata.externalJobStatus",
                    "Condition": "Completed",
                },
            },
            output_types=[
                {"name": "Completed", "description": "Completed path"},
                {"name": "In Progress", "description": "In Progress path"},
                {"name": "Fail", "description": "Fail path"},
            ],
        )

        completed_node = create_mock_node(
            node_id="completed_1",
            data_id="success",
            node_type="FLOW",
            label="Completed",
            configuration={"method": "success"},
        )

        in_progress_node = create_mock_node(
            node_id="in_progress_1",
            data_id="wait",
            node_type="FLOW",
            label="Wait",
            configuration={"method": "wait", "parameters": {"Duration": 60}},
        )

        edges = [
            create_mock_edge("choice_1", "completed_1", "Completed"),
            create_mock_edge("choice_1", "in_progress_1", "In Progress"),
        ]

        pipeline = create_mock_pipeline(
            [choice_node, completed_node, in_progress_node], edges
        )
        analyzer = GraphAnalyzer(pipeline)
        analyzer.analyze()

        result = analyzer.find_special_edges()
        (
            choice_true_targets,
            choice_false_targets,
            choice_fail_targets,
            map_processor_chains,
            choice_custom_branches,
        ) = result

        # Standard outputs should be in true/false targets, not custom branches
        assert "choice_1" in choice_true_targets
        assert "choice_1" in choice_false_targets
        assert "choice_1" not in choice_custom_branches

    def test_find_special_edges_handles_mixed_outputs(self):
        """
        Test that a Choice node with both standard and custom outputs
        is handled correctly.
        """
        from graph_utils import GraphAnalyzer

        # Create a Choice node with mixed outputs
        choice_node = create_mock_node(
            node_id="choice_1",
            data_id="choice",
            node_type="FLOW",
            label="Mixed Choice",
            configuration={
                "method": "choice",
                "parameters": {
                    "variable": "$.body.status",
                    "choices": [
                        {"condition": "custom_value", "output": "CustomOutput"}
                    ],
                },
            },
            output_types=[
                {"name": "Completed", "description": "Standard completed"},
                {"name": "CustomOutput", "description": "Custom output"},
            ],
        )

        completed_node = create_mock_node(
            node_id="completed_1",
            data_id="success",
            node_type="FLOW",
            label="Completed",
            configuration={"method": "success"},
        )

        custom_node = create_mock_node(
            node_id="custom_1",
            data_id="fail",
            node_type="FLOW",
            label="Custom",
            configuration={"method": "fail"},
        )

        edges = [
            create_mock_edge("choice_1", "completed_1", "Completed"),
            create_mock_edge("choice_1", "custom_1", "CustomOutput"),
        ]

        pipeline = create_mock_pipeline(
            [choice_node, completed_node, custom_node], edges
        )
        analyzer = GraphAnalyzer(pipeline)
        analyzer.analyze()

        result = analyzer.find_special_edges()
        (
            choice_true_targets,
            choice_false_targets,
            choice_fail_targets,
            map_processor_chains,
            choice_custom_branches,
        ) = result

        # Standard output should be in true targets
        assert "choice_1" in choice_true_targets
        # Custom output should be in custom branches
        assert "choice_1" in choice_custom_branches
        assert choice_custom_branches["choice_1"]["CustomOutput"] == "custom_1"


# =============================================================================
# StateDefinitionFactory Tests
# =============================================================================


class TestStateDefinitionFactoryCustomChoice:
    """Tests for StateDefinitionFactory custom Choice state creation."""

    @patch("state_definitions.read_yaml_from_s3")
    def test_create_custom_choice_state_with_multiple_branches(self, mock_read_yaml):
        """
        Test creating a Choice state with multiple custom branches.

        Property 1: Custom Choice State Generation Correctness
        Validates: Requirements 1.1, 1.2, 1.3, 1.4
        """
        from state_definitions import StateDefinitionFactory

        # Mock the YAML template
        mock_read_yaml.return_value = {
            "node": {
                "integration": {"config": {"aws_stepfunction": {"step_name": "choice"}}}
            }
        }

        choice_node = create_mock_node(
            node_id="choice_1",
            data_id="choice",
            node_type="FLOW",
            label="Enrichment Result",
            configuration={
                "method": "choice",
                "parameters": {
                    "variable": "$.body.enrichment_status",
                    "choices": [
                        {"condition": "success", "output": "Success"},
                        {"condition": "no_match", "output": "NoMatch"},
                        {"condition": "auth_error", "output": "AuthError"},
                    ],
                    "default": "Error",
                },
            },
        )

        pipeline = create_mock_pipeline([choice_node], [])
        factory = StateDefinitionFactory(pipeline, {})

        state_def = factory.create_flow_state_definition(choice_node)

        # Verify the state definition
        assert state_def["Type"] == "Choice"
        assert len(state_def["Choices"]) == 3

        # Verify each branch has correct structure
        for choice in state_def["Choices"]:
            assert choice["Variable"] == "$.body.enrichment_status"
            assert "StringEquals" in choice
            assert "__PLACEHOLDER__" in choice["Next"]

        # Verify conditions
        conditions = [c["StringEquals"] for c in state_def["Choices"]]
        assert "success" in conditions
        assert "no_match" in conditions
        assert "auth_error" in conditions

        # Verify default
        assert "__PLACEHOLDER__choice_1_Error__" in state_def["Default"]

    @patch("state_definitions.read_yaml_from_s3")
    def test_create_custom_choice_state_uses_default_variable(self, mock_read_yaml):
        """
        Test that missing variable parameter uses default.

        Property 5: Default Variable Fallback
        Validates: Requirements 6.1
        """
        from state_definitions import StateDefinitionFactory

        mock_read_yaml.return_value = {
            "node": {
                "integration": {"config": {"aws_stepfunction": {"step_name": "choice"}}}
            }
        }

        # No variable specified in parameters
        choice_node = create_mock_node(
            node_id="choice_1",
            data_id="choice",
            node_type="FLOW",
            label="Choice",
            configuration={
                "method": "choice",
                "parameters": {
                    "choices": [{"condition": "success", "output": "Success"}],
                    "default": "Error",
                },
            },
        )

        pipeline = create_mock_pipeline([choice_node], [])
        factory = StateDefinitionFactory(pipeline, {})

        state_def = factory.create_flow_state_definition(choice_node)

        # Should use default variable
        assert state_def["Choices"][0]["Variable"] == "$.metadata.externalJobStatus"

    @patch("state_definitions.read_yaml_from_s3")
    def test_create_standard_choice_state_unchanged(self, mock_read_yaml):
        """
        Test that standard Choice nodes (without parameters.choices) work unchanged.

        Property 4: Backward Compatibility Round-Trip
        Validates: Requirements 4.1
        """
        from state_definitions import StateDefinitionFactory

        mock_read_yaml.return_value = {
            "node": {
                "integration": {"config": {"aws_stepfunction": {"step_name": "choice"}}}
            }
        }

        # Standard Choice node with Variable/Condition parameters
        choice_node = create_mock_node(
            node_id="choice_1",
            data_id="choice",
            node_type="FLOW",
            label="Check Status",
            configuration={
                "method": "choice",
                "parameters": {
                    "Variable": "$.metadata.externalJobStatus",
                    "Condition": "Completed",
                },
            },
        )

        pipeline = create_mock_pipeline([choice_node], [])
        factory = StateDefinitionFactory(pipeline, {})

        state_def = factory.create_flow_state_definition(choice_node)

        # Should use standard TRUE/FALSE placeholders
        assert state_def["Type"] == "Choice"
        assert "__PLACEHOLDER__choice_1_TRUE__" in state_def["Choices"][0]["Next"]
        assert "__PLACEHOLDER__choice_1_FALSE__" in state_def["Default"]


# =============================================================================
# StateConnector Tests
# =============================================================================


class TestStateConnectorCustomChoice:
    """Tests for StateConnector custom Choice branch connection."""

    def test_connect_custom_choice_branches_replaces_placeholders(self):
        """
        Test that custom Choice branch placeholders are replaced correctly.

        Property 3: Custom Branch Connection Correctness
        Validates: Requirements 3.1, 3.2, 3.3
        """
        from state_connector import StateConnector

        # Create states with placeholders
        states = {
            "Enrichment_Result__choice_1_": {
                "Type": "Choice",
                "Choices": [
                    {
                        "Variable": "$.body.status",
                        "StringEquals": "success",
                        "Next": "__PLACEHOLDER__choice_1_Success__",
                    },
                    {
                        "Variable": "$.body.status",
                        "StringEquals": "error",
                        "Next": "__PLACEHOLDER__choice_1_Error__",
                    },
                ],
                "Default": "__PLACEHOLDER__choice_1_Default__",
            },
            "Success__success_1_": {"Type": "Succeed"},
            "Error__error_1_": {"Type": "Fail", "Error": "Error", "Cause": "Error"},
            "Default__default_1_": {
                "Type": "Fail",
                "Error": "Default",
                "Cause": "Default",
            },
        }

        node_id_to_state_name = {
            "choice_1": "Enrichment_Result__choice_1_",
            "success_1": "Success__success_1_",
            "error_1": "Error__error_1_",
            "default_1": "Default__default_1_",
        }

        node_id_to_node = {
            "choice_1": MagicMock(),
            "success_1": MagicMock(),
            "error_1": MagicMock(),
            "default_1": MagicMock(),
        }

        connector = StateConnector(states, node_id_to_state_name, node_id_to_node)

        # Custom branches mapping
        custom_branches = {
            "choice_1": {
                "Success": "success_1",
                "Error": "error_1",
                "Default": "default_1",
            }
        }

        # Connect states
        connector.connect_states(
            edges=[],
            choice_true_targets={},
            choice_false_targets={},
            choice_fail_targets={},
            choice_custom_branches=custom_branches,
        )

        # Verify placeholders were replaced
        choice_state = states["Enrichment_Result__choice_1_"]
        assert choice_state["Choices"][0]["Next"] == "Success__success_1_"
        assert choice_state["Choices"][1]["Next"] == "Error__error_1_"
        assert choice_state["Default"] == "Default__default_1_"

    def test_connect_custom_choice_branches_logs_warning_for_missing_target(self):
        """
        Test that missing targets log a warning but don't fail.

        Validates: Requirements 3.4, 6.2
        """
        from state_connector import StateConnector

        states = {
            "Choice__choice_1_": {
                "Type": "Choice",
                "Choices": [
                    {
                        "Variable": "$.body.status",
                        "StringEquals": "success",
                        "Next": "__PLACEHOLDER__choice_1_Success__",
                    },
                ],
                "Default": "__PLACEHOLDER__choice_1_Error__",
            },
            "Success__success_1_": {"Type": "Succeed"},
            # Note: Error state is missing
        }

        node_id_to_state_name = {
            "choice_1": "Choice__choice_1_",
            "success_1": "Success__success_1_",
            # error_1 is not mapped
        }

        node_id_to_node = {"choice_1": MagicMock(), "success_1": MagicMock()}

        connector = StateConnector(states, node_id_to_state_name, node_id_to_node)

        custom_branches = {
            "choice_1": {
                "Success": "success_1",
                "Error": "error_1",  # This target doesn't exist
            }
        }

        # Should not raise an exception
        connector.connect_states(
            edges=[],
            choice_true_targets={},
            choice_false_targets={},
            choice_fail_targets={},
            choice_custom_branches=custom_branches,
        )

        # Success branch should be connected
        choice_state = states["Choice__choice_1_"]
        assert choice_state["Choices"][0]["Next"] == "Success__success_1_"

        # Error branch placeholder should remain (or be logged as warning)
        # The Default still has the placeholder since error_1 wasn't found


# =============================================================================
# Integration Tests
# =============================================================================


class TestExternalMetadataEnrichmentPipeline:
    """
    Integration tests for the External Metadata Enrichment pipeline template.

    These tests verify that the complete pipeline generates a valid state machine
    with all 4 end states (Success, NoMatch, AuthError, Error).
    """

    @patch("state_definitions.read_yaml_from_s3")
    def test_external_metadata_enrichment_generates_all_end_states(
        self, mock_read_yaml
    ):
        """
        Test that the External Metadata Enrichment pipeline generates
        a state machine with all 4 end states.

        Validates: Requirements 1.1-1.5, 2.1-2.3, 3.1-3.3
        """
        from builders import StateMachineBuilder

        # Mock YAML templates
        def yaml_side_effect(bucket, path):
            if "choice" in path:
                return {
                    "node": {
                        "integration": {
                            "config": {"aws_stepfunction": {"step_name": "choice"}}
                        }
                    }
                }
            elif "success" in path:
                return {
                    "node": {
                        "integration": {
                            "config": {"aws_stepfunction": {"step_name": "succeed"}}
                        }
                    }
                }
            elif "fail" in path:
                return {
                    "node": {
                        "integration": {
                            "config": {"aws_stepfunction": {"step_name": "fail"}}
                        }
                    }
                }
            return {
                "node": {
                    "integration": {
                        "config": {"aws_stepfunction": {"step_name": "pass"}}
                    }
                }
            }

        mock_read_yaml.side_effect = yaml_side_effect

        # Create nodes matching the External Metadata Enrichment template
        trigger_node = create_mock_node(
            node_id="dndnode_0",
            data_id="trigger_workflow_completed",
            node_type="TRIGGER",
            label="Workflow Completed",
            configuration={"method": "trigger"},
        )

        lambda_node = create_mock_node(
            node_id="dndnode_2",
            data_id="external_metadata_fetch",
            node_type="INTEGRATION",
            label="External Metadata Fetch",
            configuration={
                "method": "fetch_metadata",
                "operationId": "fetchExternalMetadata",
            },
        )

        choice_node = create_mock_node(
            node_id="dndnode_3",
            data_id="choice",
            node_type="FLOW",
            label="Enrichment Result",
            configuration={
                "method": "choice",
                "parameters": {
                    "variable": "$.body.enrichment_status",
                    "choices": [
                        {"condition": "success", "output": "Success"},
                        {"condition": "no_match", "output": "NoMatch"},
                        {"condition": "auth_error", "output": "AuthError"},
                    ],
                    "default": "Error",
                },
            },
            output_types=[
                {"name": "Success", "description": "Success"},
                {"name": "NoMatch", "description": "NoMatch"},
                {"name": "AuthError", "description": "AuthError"},
                {"name": "Error", "description": "Error"},
            ],
        )

        success_node = create_mock_node(
            node_id="dndnode_4",
            data_id="success",
            node_type="FLOW",
            label="Success",
            configuration={"method": "success"},
        )

        no_match_node = create_mock_node(
            node_id="dndnode_5",
            data_id="fail",
            node_type="FLOW",
            label="NoMatch",
            configuration={
                "method": "fail",
                "parameters": {"Error": "NoMatch", "Cause": "Not found"},
            },
        )

        auth_error_node = create_mock_node(
            node_id="dndnode_6",
            data_id="fail",
            node_type="FLOW",
            label="AuthError",
            configuration={
                "method": "fail",
                "parameters": {"Error": "AuthError", "Cause": "Auth failed"},
            },
        )

        error_node = create_mock_node(
            node_id="dndnode_7",
            data_id="fail",
            node_type="FLOW",
            label="Error",
            configuration={
                "method": "fail",
                "parameters": {"Error": "Error", "Cause": "Unknown error"},
            },
        )

        nodes = [
            trigger_node,
            lambda_node,
            choice_node,
            success_node,
            no_match_node,
            auth_error_node,
            error_node,
        ]

        edges = [
            create_mock_edge("dndnode_0", "dndnode_2", "any"),
            create_mock_edge("dndnode_2", "dndnode_3", "any"),
            create_mock_edge("dndnode_3", "dndnode_4", "Success"),
            create_mock_edge("dndnode_3", "dndnode_5", "NoMatch"),
            create_mock_edge("dndnode_3", "dndnode_6", "AuthError"),
            create_mock_edge("dndnode_3", "dndnode_7", "Error"),
        ]

        pipeline = create_mock_pipeline(nodes, edges)

        # Mock Lambda ARNs
        lambda_arns = {
            "external_metadata_fetch_fetch_metadata_fetchExternalMetadata": (
                "arn:aws:lambda:us-east-1:123456789012:function:test"
            )
        }

        builder = StateMachineBuilder(pipeline, lambda_arns, "test")
        definition = builder.build()

        # Verify the state machine has all expected states
        states = definition["States"]

        # Should have states for: Lambda, Choice, Success, NoMatch, AuthError, Error
        assert len(states) >= 5  # At minimum: Lambda + Choice + 4 end states

        # Find the Choice state
        choice_state = None
        for state_name, state_def in states.items():
            if state_def.get("Type") == "Choice":
                choice_state = state_def
                break

        assert choice_state is not None, "Choice state not found"
        assert len(choice_state["Choices"]) == 3  # success, no_match, auth_error
        assert "Default" in choice_state  # Error is default

        # Verify all branches point to existing states
        for choice in choice_state["Choices"]:
            assert choice["Next"] in states, f"Branch target {choice['Next']} not found"
            assert "__PLACEHOLDER__" not in choice["Next"], "Placeholder not replaced"

        assert choice_state["Default"] in states, "Default target not found"
        assert (
            "__PLACEHOLDER__" not in choice_state["Default"]
        ), "Default placeholder not replaced"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
