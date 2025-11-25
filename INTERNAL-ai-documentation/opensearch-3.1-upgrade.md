# OpenSearch 3.1 Version Upgrade

## Overview

Updated the MediaLake CDK infrastructure to use OpenSearch version 3.1 instead of the previous version 2.15.

## Changes Made

### File: `medialake_constructs/shared_constructs/opensearch_managed_cluster.py`

#### Change 1: Updated Default Engine Version (Line 25)

**Before:**

```python
engine_version: str = "OpenSearch_2.15"
```

**After:**

```python
engine_version: opensearch.EngineVersion = opensearch.EngineVersion.OPENSEARCH_3_1
```

**Rationale:**

- Changed from string-based version to using the proper AWS CDK `EngineVersion` enum constant
- Updated to OpenSearch 3.1 as requested
- Changed type annotation from `str` to `opensearch.EngineVersion` for type safety

#### Change 2: Updated CfnDomain Engine Version Parameter (Line 267)

**Before:**

```python
engine_version=props.engine_version,
```

**After:**

```python
engine_version=props.engine_version.version,
```

**Rationale:**

- `CfnDomain` expects a string value for `engine_version`
- The `EngineVersion` object has a `.version` property that returns the string representation
- This ensures compatibility with the CloudFormation resource

## Impact Analysis

### Affected Stacks

The following stacks instantiate `OpenSearchCluster` and will automatically use the new version:

1. **BaseInfrastructureStack** (`medialake_stacks/base_infrastructure.py`)
2. **SharedSearchStack** (`medialake_stacks/shared_search_stack.py`)

Both stacks use the default `engine_version` parameter, so no changes were needed in these files.

## Testing Recommendations

1. **Deployment Test**: Deploy the CDK stack to a test environment to verify the OpenSearch 3.1 cluster provisions correctly
2. **Compatibility Check**: Verify that all Lambda functions and applications that interact with OpenSearch are compatible with version 3.1
3. **Index Migration**: If upgrading an existing cluster, ensure proper index migration procedures are followed
4. **API Compatibility**: Test all OpenSearch API calls to ensure they work with version 3.1

## Rollback Plan

If issues arise, revert the changes by:

1. Change `opensearch.EngineVersion.OPENSEARCH_3_1` back to `opensearch.EngineVersion.OPENSEARCH_2_15`
2. Redeploy the CDK stack

## Additional Notes

- OpenSearch 3.1 may include breaking changes or new features compared to 2.15
- Review the [OpenSearch 3.1 release notes](https://opensearch.org/docs/latest/version-history/) for detailed changes
- Consider updating any OpenSearch client libraries in Lambda functions to versions compatible with OpenSearch 3.1
