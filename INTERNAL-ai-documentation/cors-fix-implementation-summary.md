# CORS Fix Implementation Summary

## Overview

Successfully implemented the CORS policy fix to use the CloudFront distribution domain instead of wildcard `*` for the `AllowedOrigins` configuration. This ensures uploads are only allowed from the MediaLake application's CloudFront domain.

## Implementation Approach

Used **Option 3: Environment Variable from CDK** - Pass CloudFront domain directly as an environment variable from the UserInterfaceStack to the connector Lambda via CDK props.

## Changes Implemented

### 1. medialake_stacks/user_interface_stack.py

**Changes:**

- Added `CfnOutput` to export the CloudFront distribution domain with export name `{resource_prefix}-{environment}-cloudfront-domain`
- Added class property `self.cloudfront_domain` to store the CloudFront distribution domain name for cross-stack references
- This makes the CloudFront domain available to other stacks that need it

**Location:** After line 268, before the "Add the initial user to the administrators group" section

### 2. medialake_stacks/api_gateway_stack.py

**Changes:**

- Updated `ApiGatewayStackProps` dataclass to include `cloudfront_domain: str` field
- Passed `cloudfront_domain=props.cloudfront_domain` to the `ConnectorsConstruct` initialization
- Removed unused variables and commented code to fix linter warnings

**Key lines:**

- Line 76: Added `cloudfront_domain` field to props dataclass
- Line 236: Passed cloudfront_domain to ConnectorsConstruct

### 3. medialake_constructs/api_gateway/api_gateway_connectors.py

**Changes:**

- Updated `ConnectorsProps` dataclass to include `cloudfront_domain: str` field with documentation
- Removed the old logic that tried to read `MEDIALAKE_APP_ORIGIN` from config or defaulted to `'*'`
- Updated environment variable configuration to use `f"https://{props.cloudfront_domain}"` for `MEDIALAKE_APP_ORIGIN`
- Added explanatory comment about CORS origin usage

**Key lines:**

- Line 73: Added `cloudfront_domain` field to props dataclass
- Lines 462-464: Set `MEDIALAKE_APP_ORIGIN` environment variable using CloudFront domain with `https://` protocol

### 4. app.py

**Changes:**

- Restructured stack creation order to create `UserInterfaceStack` BEFORE `MediaLakeStack`
- Added `cloudfront_domain: str` field to `MediaLakeStackProps` dataclass
- Passed `cloudfront_domain=user_interface_stack.cloudfront_domain` when creating `MediaLakeStack`
- Added dependency: `medialake_stack.add_dependency(user_interface_stack)`
- Added dependency: `api_gateway_deployment_stack.add_dependency(user_interface_stack)`
- Moved UserInterfaceStack creation to line 121 (after api_gateway_core_stack, before authorization_stack)

**New stack creation order:**

1. base_infrastructure
2. cognito_stack
3. api_gateway_core_stack
4. **user_interface_stack** (moved earlier)
5. authorization_stack
6. medialake_stack (depends on user_interface_stack for CloudFront domain)
7. api_gateway_deployment_stack (depends on both)

### 5. medialake_constructs/userInterface.py

**Changes:**

- Updated SSM parameter name to include environment: `/medialake/{environment}/cloudfront-distribution-domain`
- This allows multiple environments (dev, staging, prod) to have separate CloudFront domains in the same account
- Matches the pattern used in `url_utils.py`
- Added explanatory comments about the SSM parameter being optional (primary method is via stack properties)

**Location:** Line 675

### 6. lambdas/api/connectors/s3/post_s3/index.py

**No changes needed** - The Lambda code already correctly handles the `MEDIALAKE_APP_ORIGIN` environment variable:

- Line 899: Reads the environment variable with fallback to `*`
- Line 906: Sets `AllowedOrigins` to `[medialake_origin]`
- The Lambda is already correctly implemented; the fix is purely in the CDK configuration

## Flow Diagram

```
CDK Synthesis Time:
  UserInterfaceStack (created)
    └─> Creates CloudFront distribution
    └─> Exports cloudfront_domain property

  MediaLakeStack (created with cloudfront_domain prop)
    └─> ApiGatewayStack
        └─> ConnectorsConstruct
            └─> Connector POST Lambda
                └─> Environment variable: MEDIALAKE_APP_ORIGIN=https://{cloudfront_domain}

Deployment Time:
  1. UserInterfaceStack deployed → CloudFront domain available
  2. MediaLakeStack deployed → Lambda has correct environment variable
  3. ApiGatewayDeploymentStack deployed → API fully configured

Runtime (User Creates Connector):
  Connector POST Lambda executes
    └─> Reads MEDIALAKE_APP_ORIGIN=https://d1234.cloudfront.net
    └─> Creates CORS rule with AllowedOrigins: [https://d1234.cloudfront.net]
    └─> Applies CORS rule to S3 bucket
    └─> Result: Uploads only allowed from CloudFront domain
```

## Benefits

1. **Security**: CORS policy is restricted to the specific CloudFront domain, not wildcard `*`
2. **No Runtime Overhead**: CloudFront domain is set at deployment time, no SSM calls at runtime
3. **Maintainable**: Clean dependency flow through CDK props
4. **Multi-Environment Support**: SSM parameter includes environment name for clean separation
5. **Follows CDK Best Practices**: Uses stack properties and dependencies correctly

## Testing Recommendations

1. **Deployment Test**: Deploy the stacks and verify correct order
2. **Environment Variable Test**: Check that connector Lambda has correct `MEDIALAKE_APP_ORIGIN` value
3. **CORS Test**: Create a connector and verify S3 bucket CORS rules use CloudFront domain
4. **Upload Test**: Test file uploads from the UI work correctly
5. **Security Test**: Verify uploads from other origins are blocked

## Rollback Plan

If issues arise, the change can be rolled back by:

1. Reverting the CDK changes in all modified files
2. Setting `MEDIALAKE_APP_ORIGIN` back to `*` temporarily
3. Re-deploying the stacks

## Notes

- No changes to Lambda code were required
- The fix is entirely in the CDK infrastructure configuration
- Existing connectors will need to be recreated or have their CORS rules updated manually
- The SSM parameter is optional and maintained for backward compatibility
