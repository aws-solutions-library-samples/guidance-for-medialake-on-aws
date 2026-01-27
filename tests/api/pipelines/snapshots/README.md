# Pipeline State Machine Snapshots

This directory contains snapshot files for backward compatibility testing of the
pipeline Step Functions builder.

## Purpose

Each JSON file represents the expected state machine definition that should be
generated from a pipeline template in `pipeline_library/`. These snapshots ensure
that changes to the pipeline builder code don't accidentally break existing templates.

## How It Works

1. Tests in `test_backward_compatibility.py` load each pipeline template
2. The `StateMachineBuilder` generates a state machine definition
3. The generated output is compared against the snapshot file
4. If they differ, the test fails with a detailed diff

## When Tests Fail

See the docstring in `test_backward_compatibility.py` for detailed guidance on
handling test failures.

**Quick reference:**

- **Unintentional change**: Fix your code to preserve backward compatibility
- **Intentional change**: Update snapshots with `pytest test_backward_compatibility.py --update-snapshots`

## Updating Snapshots

```bash
# Update all snapshots
pytest tests/api/pipelines/test_backward_compatibility.py --update-snapshots

# Update snapshot for a specific template
pytest tests/api/pipelines/test_backward_compatibility.py -k "External Metadata" --update-snapshots
```

## File Naming Convention

`{category}_{template_name}_snapshot.json`

Examples:

- `Default_Pipelines_Default_Video_Pipeline_snapshot.json`
- `Enrichment_External_Metadata_Enrichment_snapshot.json`
- `Semantic_Search_TwelveLabs_API_OpenSearch_TwelveLabs_API_Video_Embedding_to_OpenSearch_snapshot.json`

## Important Notes

- **Always review snapshot changes** in `git diff` before committing
- **Never blindly update snapshots** - understand why the output changed
- **Snapshots should be committed** to version control alongside code changes
