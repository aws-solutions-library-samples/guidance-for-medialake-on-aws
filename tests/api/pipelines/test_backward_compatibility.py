"""
Backward compatibility tests for pipeline Step Functions builder.

These tests verify that existing pipeline templates continue to generate
IDENTICAL state machine definitions. Any change to the generated output
will cause these tests to fail.

================================================================================
SNAPSHOT TESTING OVERVIEW
================================================================================

These tests use snapshot testing to ensure backward compatibility:

1. Each pipeline template in `pipeline_library/` has a corresponding snapshot
   file in `tests/api/pipelines/snapshots/`

2. When tests run, the generated state machine definition is compared
   byte-for-byte against the snapshot

3. If they differ, the test FAILS with a diff showing exactly what changed

================================================================================
WHEN TESTS FAIL
================================================================================

If these tests fail, it means the generated Step Function definition has changed.
This could be due to:

A) UNINTENTIONAL CHANGE (Bug):
   - You modified code in `lambdas/api/pipelines/post_pipelines/` and it
     accidentally changed the output for existing templates
   - FIX: Debug and fix your code to preserve backward compatibility

B) INTENTIONAL CHANGE to pipeline builder code:
   - You intentionally changed how state machines are generated
   - After verifying the new output is correct, update the snapshots:

     pytest tests/api/pipelines/test_backward_compatibility.py --update-snapshots

   - Review the updated snapshots in git diff before committing

C) INTENTIONAL CHANGE to a pipeline template:
   - You modified a template in `pipeline_library/`
   - After verifying the template change is correct, update its snapshot:

     pytest tests/api/pipelines/test_backward_compatibility.py --update-snapshots

   - Review the updated snapshot in git diff before committing

D) NEW PIPELINE TEMPLATE:
   - You added a new template to `pipeline_library/`
   - Run with --update-snapshots to create the initial snapshot:

     pytest tests/api/pipelines/test_backward_compatibility.py --update-snapshots

================================================================================
SNAPSHOT FILE LOCATION
================================================================================

Snapshots are stored in: tests/api/pipelines/snapshots/

Naming convention: {category}_{template_name}_snapshot.json
Example: Enrichment_External_Metadata_Enrichment_snapshot.json

================================================================================
COMMANDS
================================================================================

Run tests (compare against snapshots):
    pytest tests/api/pipelines/test_backward_compatibility.py -v

Update all snapshots:
    pytest tests/api/pipelines/test_backward_compatibility.py --update-snapshots

Update snapshot for a specific template:
    pytest tests/api/pipelines/test_backward_compatibility.py -k "External Metadata" --update-snapshots

================================================================================

Feature: custom-choice-branches
Task: 7 - Backward Compatibility Tests
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

# Paths
PIPELINE_LIBRARY_PATH = Path(__file__).parent.parent.parent.parent / "pipeline_library"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def get_all_template_paths():
    """Get all JSON template files from the pipeline library."""
    templates = []
    for json_file in PIPELINE_LIBRARY_PATH.rglob("*.json"):
        templates.append(json_file)
    return templates


def load_template(path: Path) -> dict:
    """Load a pipeline template from file."""
    with open(path, "r") as f:
        return json.load(f)


def get_snapshot_path(template_path: Path) -> Path:
    """Get the snapshot file path for a template."""
    # Create a safe filename from the template path
    relative_path = template_path.relative_to(PIPELINE_LIBRARY_PATH)
    safe_name = (
        str(relative_path).replace("/", "_").replace(" ", "_").replace(".json", "")
    )
    return SNAPSHOTS_DIR / f"{safe_name}_snapshot.json"


def load_snapshot(snapshot_path: Path) -> dict | None:
    """Load a snapshot file if it exists."""
    if snapshot_path.exists():
        with open(snapshot_path, "r") as f:
            return json.load(f)
    return None


def save_snapshot(snapshot_path: Path, definition: dict) -> None:
    """Save a state machine definition as a snapshot."""
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w") as f:
        json.dump(definition, f, indent=2, sort_keys=True)


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


def mock_yaml_side_effect(bucket, path):
    """Mock YAML template responses based on node type."""
    if "choice" in path:
        return {
            "node": {
                "integration": {"config": {"aws_stepfunction": {"step_name": "choice"}}}
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
                "integration": {"config": {"aws_stepfunction": {"step_name": "fail"}}}
            }
        }
    elif "wait" in path:
        return {
            "node": {
                "integration": {"config": {"aws_stepfunction": {"step_name": "wait"}}}
            }
        }
    elif "map" in path:
        return {
            "node": {
                "integration": {"config": {"aws_stepfunction": {"step_name": "map"}}}
            }
        }
    elif "trigger" in path:
        return {
            "node": {
                "integration": {"config": {"aws_stepfunction": {"step_name": "pass"}}}
            }
        }
    # Default to task for integration nodes
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


def build_state_machine(template_path: Path) -> dict:
    """Build a state machine definition from a template."""
    from builders import StateMachineBuilder

    template_data = load_template(template_path)
    pipeline = create_pipeline_from_template(template_data)

    # Create mock Lambda ARNs for all possible integration nodes
    lambda_arns = {}
    for node in template_data["configuration"]["nodes"]:
        if node["data"]["type"] == "INTEGRATION":
            config = node["data"]["configuration"]
            method = config.get("method", "")
            operation_id = config.get("operationId", "")
            node_id = node["data"]["nodeId"]
            key = f"{node_id}_{method}_{operation_id}"
            lambda_arns[key] = (
                f"arn:aws:lambda:us-east-1:123456789012:function:{node_id}"
            )

    builder = StateMachineBuilder(pipeline, lambda_arns, "test")
    return builder.build()


class TestBackwardCompatibilitySnapshots:
    """
    Snapshot-based backward compatibility tests.

    These tests compare generated state machine definitions against known-good
    baseline snapshots. If the output differs, the test fails - ensuring that
    changes to the pipeline builder don't accidentally break existing templates.
    """

    @pytest.mark.parametrize(
        "template_path", get_all_template_paths(), ids=lambda p: p.stem
    )
    @patch("state_definitions.read_yaml_from_s3")
    def test_template_matches_snapshot(self, mock_read_yaml, template_path, request):
        """
        Test that each template generates output identical to its snapshot.

        If --update-snapshots is passed, updates the snapshot instead of comparing.
        """
        mock_read_yaml.side_effect = mock_yaml_side_effect

        # Build the state machine
        definition = build_state_machine(template_path)

        # Normalize for comparison (sort keys for deterministic output)
        normalized_definition = json.loads(json.dumps(definition, sort_keys=True))

        snapshot_path = get_snapshot_path(template_path)

        # Check if we should update snapshots
        update_snapshots = request.config.getoption("--update-snapshots", default=False)

        if update_snapshots:
            save_snapshot(snapshot_path, normalized_definition)
            pytest.skip(f"Updated snapshot: {snapshot_path}")

        # Load and compare against snapshot
        expected = load_snapshot(snapshot_path)

        if expected is None:
            # No snapshot exists - save one and fail with instructions
            save_snapshot(snapshot_path, normalized_definition)
            pytest.fail(
                f"No snapshot found for {template_path.name}. "
                f"Created new snapshot at {snapshot_path}. "
                f"Review the snapshot and re-run the test."
            )

        # Compare the definitions
        if normalized_definition != expected:
            # Generate a diff for debugging
            import difflib

            expected_str = json.dumps(expected, indent=2, sort_keys=True)
            actual_str = json.dumps(normalized_definition, indent=2, sort_keys=True)
            diff = "\n".join(
                difflib.unified_diff(
                    expected_str.splitlines(),
                    actual_str.splitlines(),
                    fromfile="expected (snapshot)",
                    tofile="actual (generated)",
                    lineterm="",
                )
            )
            pytest.fail(
                f"\n"
                f"{'='*80}\n"
                f"BACKWARD COMPATIBILITY FAILURE: {template_path.name}\n"
                f"{'='*80}\n"
                f"\n"
                f"The generated state machine definition differs from the snapshot.\n"
                f"\n"
                f"WHAT TO DO:\n"
                f"\n"
                f"1. If this change is UNINTENTIONAL (bug):\n"
                f"   - Review your changes to lambdas/api/pipelines/post_pipelines/\n"
                f"   - Fix the code to preserve backward compatibility\n"
                f"\n"
                f"2. If this change is INTENTIONAL:\n"
                f"   - Verify the new output is correct\n"
                f"   - Update the snapshot by running:\n"
                f"     pytest {__file__} --update-snapshots\n"
                f"   - Review the snapshot changes in git diff before committing\n"
                f"\n"
                f"DIFF:\n"
                f"{diff}\n"
                f"\n"
                f"Snapshot file: {snapshot_path}\n"
                f"{'='*80}"
            )


class TestBackwardCompatibilityStructural:
    """
    Structural validation tests that don't require snapshots.

    These tests verify that generated state machines are structurally valid,
    regardless of the specific output.
    """

    @pytest.mark.parametrize(
        "template_path", get_all_template_paths(), ids=lambda p: p.stem
    )
    @patch("state_definitions.read_yaml_from_s3")
    def test_template_generates_valid_structure(self, mock_read_yaml, template_path):
        """
        Test that all templates generate structurally valid state machines.
        """
        mock_read_yaml.side_effect = mock_yaml_side_effect

        definition = build_state_machine(template_path)

        # Verify basic structure
        assert "StartAt" in definition, f"Missing StartAt in {template_path.name}"
        assert "States" in definition, f"Missing States in {template_path.name}"
        assert (
            len(definition["States"]) > 0
        ), f"No states generated for {template_path.name}"

        # Verify no placeholders remain
        definition_str = json.dumps(definition)
        assert (
            "__PLACEHOLDER__" not in definition_str
        ), f"Unresolved placeholder in {template_path.name}"

        # Verify StartAt points to an existing state
        assert (
            definition["StartAt"] in definition["States"]
        ), f"StartAt '{definition['StartAt']}' not in States for {template_path.name}"

        # Verify all Next references point to existing states
        for state_name, state_def in definition["States"].items():
            if "Next" in state_def:
                assert (
                    state_def["Next"] in definition["States"]
                ), f"State '{state_name}' has invalid Next '{state_def['Next']}' in {template_path.name}"

            # Check Choice branches
            if state_def.get("Type") == "Choice":
                for choice in state_def.get("Choices", []):
                    assert (
                        choice["Next"] in definition["States"]
                    ), f"Choice branch has invalid Next '{choice['Next']}' in {template_path.name}"
                if "Default" in state_def:
                    assert (
                        state_def["Default"] in definition["States"]
                    ), f"Choice Default has invalid target '{state_def['Default']}' in {template_path.name}"

    @patch("state_definitions.read_yaml_from_s3")
    def test_standard_choice_nodes_work_unchanged(self, mock_read_yaml):
        """
        Test that standard Choice nodes (with Variable/Condition parameters)
        continue to work as before.
        """
        from builders import StateMachineBuilder

        mock_read_yaml.side_effect = mock_yaml_side_effect

        # Create a pipeline with a standard Choice node
        trigger_node = MagicMock()
        trigger_node.id = "trigger_1"
        trigger_node.data = MagicMock()
        trigger_node.data.id = "trigger"
        trigger_node.data.type = "TRIGGER"
        trigger_node.data.label = "Trigger"
        trigger_node.data.configuration = {"method": "trigger"}
        trigger_node.data.outputTypes = [{"name": "any"}]

        choice_node = MagicMock()
        choice_node.id = "choice_1"
        choice_node.data = MagicMock()
        choice_node.data.id = "choice"
        choice_node.data.type = "FLOW"
        choice_node.data.label = "Check Status"
        choice_node.data.configuration = {
            "method": "choice",
            "parameters": {
                "Variable": "$.metadata.externalJobStatus",
                "Condition": "Completed",
            },
        }
        choice_node.data.outputTypes = [
            {"name": "Completed"},
            {"name": "In Progress"},
            {"name": "Fail"},
        ]

        success_node = MagicMock()
        success_node.id = "success_1"
        success_node.data = MagicMock()
        success_node.data.id = "success"
        success_node.data.type = "FLOW"
        success_node.data.label = "Success"
        success_node.data.configuration = {"method": "success"}
        success_node.data.outputTypes = []

        wait_node = MagicMock()
        wait_node.id = "wait_1"
        wait_node.data = MagicMock()
        wait_node.data.id = "wait"
        wait_node.data.type = "FLOW"
        wait_node.data.label = "Wait"
        wait_node.data.configuration = {
            "method": "wait",
            "parameters": {"Duration": 60},
        }
        wait_node.data.outputTypes = [{"name": "any"}]

        fail_node = MagicMock()
        fail_node.id = "fail_1"
        fail_node.data = MagicMock()
        fail_node.data.id = "fail"
        fail_node.data.type = "FLOW"
        fail_node.data.label = "Fail"
        fail_node.data.configuration = {
            "method": "fail",
            "parameters": {"Error": "Failed"},
        }
        fail_node.data.outputTypes = []

        nodes = [trigger_node, choice_node, success_node, wait_node, fail_node]

        edges = [
            {"source": "trigger_1", "target": "choice_1", "sourceHandle": "any"},
            {"source": "choice_1", "target": "success_1", "sourceHandle": "Completed"},
            {"source": "choice_1", "target": "wait_1", "sourceHandle": "In Progress"},
            {"source": "choice_1", "target": "fail_1", "sourceHandle": "Fail"},
        ]

        pipeline = MagicMock()
        pipeline.name = "Test Standard Choice"
        pipeline.configuration = MagicMock()
        pipeline.configuration.nodes = nodes
        pipeline.configuration.edges = edges
        pipeline.configuration.settings = MagicMock()
        pipeline.configuration.settings.retryAttempts = 3

        builder = StateMachineBuilder(pipeline, {}, "test")
        definition = builder.build()

        # Find the Choice state
        choice_state = None
        for state_def in definition["States"].values():
            if state_def.get("Type") == "Choice":
                choice_state = state_def
                break

        assert choice_state is not None
        assert len(choice_state["Choices"]) >= 1
        assert "Default" in choice_state

        # Verify no placeholders remain
        definition_str = json.dumps(definition)
        assert "__PLACEHOLDER__" not in definition_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
