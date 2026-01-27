"""
Integration test for External Metadata Enrichment pipeline template.

This test loads the actual template file and verifies that the pipeline builder
generates a valid Step Function with all 4 end states.

Feature: custom-choice-branches
Task: 6 - Integration Test with External Metadata Enrichment Template
"""

import json
import sys
from pathlib import Path
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

# Path to the template file
TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "pipeline_library"
    / "Enrichment"
    / "External Metadata Enrichment.json"
)


def load_template():
    """Load the External Metadata Enrichment template."""
    with open(TEMPLATE_PATH, "r") as f:
        return json.load(f)


def create_pipeline_from_template(template_data: dict) -> MagicMock:
    """Create a mock pipeline object from template data."""
    pipeline = MagicMock()
    pipeline.name = template_data["name"]
    pipeline.configuration = MagicMock()

    # Convert nodes to mock objects
    nodes = []
    for node_data in template_data["configuration"]["nodes"]:
        node = MagicMock()
        node.id = node_data["id"]
        node.data = MagicMock()
        node.data.id = node_data["data"]["nodeId"]
        node.data.type = node_data["data"]["type"]
        node.data.label = node_data["data"]["label"]
        node.data.configuration = node_data["data"]["configuration"]
        node.data.outputTypes = node_data["data"].get("outputTypes", [])
        nodes.append(node)

    pipeline.configuration.nodes = nodes
    pipeline.configuration.edges = template_data["configuration"]["edges"]
    pipeline.configuration.settings = MagicMock()
    pipeline.configuration.settings.retryAttempts = template_data["configuration"][
        "settings"
    ].get("retryAttempts", 3)

    return pipeline


class TestExternalMetadataEnrichmentIntegration:
    """Integration tests using the actual External Metadata Enrichment template."""

    @patch("state_definitions.read_yaml_from_s3")
    def test_template_generates_valid_state_machine(self, mock_read_yaml):
        """
        Test that the actual External Metadata Enrichment template generates
        a valid state machine with all 4 end states.
        """
        from builders import StateMachineBuilder

        # Mock YAML templates based on node type
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
            elif "trigger" in path:
                return {
                    "node": {
                        "integration": {
                            "config": {"aws_stepfunction": {"step_name": "pass"}}
                        }
                    }
                }
            elif "external_metadata_fetch" in path:
                return {
                    "node": {
                        "integration": {
                            "config": {
                                "aws_stepfunction": {
                                    "step_name": "task",
                                    "resource_type": "lambda",
                                }
                            }
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

        # Load the actual template
        template_data = load_template()
        pipeline = create_pipeline_from_template(template_data)

        # Mock Lambda ARNs
        lambda_arns = {
            "external_metadata_fetch_fetch_metadata_fetchExternalMetadata": (
                "arn:aws:lambda:us-east-1:123456789012:function:external-metadata-fetch"
            )
        }

        # Build the state machine
        builder = StateMachineBuilder(pipeline, lambda_arns, "test")
        definition = builder.build()

        # Verify the state machine structure
        assert "StartAt" in definition
        assert "States" in definition

        states = definition["States"]

        # Print states for debugging
        print(f"\nGenerated states: {list(states.keys())}")
        for name, state in states.items():
            print(f"  {name}: Type={state.get('Type')}")

        # Find the Choice state
        choice_state = None
        choice_state_name = None
        for state_name, state_def in states.items():
            if state_def.get("Type") == "Choice":
                choice_state = state_def
                choice_state_name = state_name
                break

        assert (
            choice_state is not None
        ), "Choice state not found in generated state machine"
        print(f"\nChoice state '{choice_state_name}':")
        print(f"  Choices: {len(choice_state.get('Choices', []))}")
        for i, choice in enumerate(choice_state.get("Choices", [])):
            print(f"    [{i}] {choice.get('StringEquals')} -> {choice.get('Next')}")
        print(f"  Default: {choice_state.get('Default')}")

        # Verify Choice state has correct structure
        assert "Choices" in choice_state
        assert len(choice_state["Choices"]) == 3  # success, no_match, auth_error
        assert "Default" in choice_state  # Error is default

        # Verify all branches point to existing states (no placeholders)
        for choice in choice_state["Choices"]:
            next_state = choice["Next"]
            assert (
                "__PLACEHOLDER__" not in next_state
            ), f"Placeholder not replaced: {next_state}"
            assert (
                next_state in states
            ), f"Branch target '{next_state}' not found in states"

        default_state = choice_state["Default"]
        assert (
            "__PLACEHOLDER__" not in default_state
        ), f"Default placeholder not replaced: {default_state}"
        assert (
            default_state in states
        ), f"Default target '{default_state}' not found in states"

        # Verify the conditions match the template
        conditions = {c["StringEquals"]: c["Next"] for c in choice_state["Choices"]}
        assert "success" in conditions
        assert "no_match" in conditions
        assert "auth_error" in conditions

        # Verify end states exist and have correct types
        end_state_count = 0
        for state_name, state_def in states.items():
            if state_def.get("Type") == "Succeed":
                end_state_count += 1
            elif state_def.get("Type") == "Fail":
                end_state_count += 1

        # Should have 4 end states: 1 Succeed + 3 Fail
        assert (
            end_state_count >= 4
        ), f"Expected at least 4 end states, found {end_state_count}"

    @patch("state_definitions.read_yaml_from_s3")
    def test_template_choice_variable_is_correct(self, mock_read_yaml):
        """
        Test that the Choice state uses the correct variable from the template.
        """
        from builders import StateMachineBuilder

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

        template_data = load_template()
        pipeline = create_pipeline_from_template(template_data)

        lambda_arns = {
            "external_metadata_fetch_fetch_metadata_fetchExternalMetadata": (
                "arn:aws:lambda:us-east-1:123456789012:function:test"
            )
        }

        builder = StateMachineBuilder(pipeline, lambda_arns, "test")
        definition = builder.build()

        # Find the Choice state
        choice_state = None
        for state_def in definition["States"].values():
            if state_def.get("Type") == "Choice":
                choice_state = state_def
                break

        assert choice_state is not None

        # Verify the variable matches the template
        # Template specifies: "variable": "$.payload.data.body.enrichment_status"
        for choice in choice_state["Choices"]:
            assert choice["Variable"] == "$.payload.data.body.enrichment_status"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
