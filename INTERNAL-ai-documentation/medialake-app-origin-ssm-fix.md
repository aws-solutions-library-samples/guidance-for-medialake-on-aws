# MEDIALAKE_APP_ORIGIN SSM Parameter Fix

## Problem Description

After fixing the CloudFormation export dependency issue by reordering stacks, a new problem emerged: the `MEDIALAKE_APP_ORIGIN` environment variable in the S3 connector Lambda (`medialake_connectors_s3_post_dev`) was not populated correctly.

### Root Cause

When we reordered the stacks to fix the SSM parameter issue for the API Gateway stage name:

1. `MediaLakeStack` (containing API Gateway and connectors) was moved to deploy BEFORE `UserInterfaceStack`
2. `MediaLakeStack` was created with empty `cloudfront_domain=""` parameter in [`app.py:566`](app.py:566)
3. This empty value propagated through:
   - [`api_gateway_stack.py:235`](medialake_stacks/api_gateway_stack.py:235) → `ConnectorsConstruct`
   - [`api_gateway_connectors.py:458`](medialake_constructs/api_gateway/api_gateway_connectors.py:458) → `origin_host` became empty string
   - [`api_gateway_connectors.py:489`](medialake_constructs/api_gateway/api_gateway_connectors.py:489) → `MEDIALAKE_APP_ORIGIN="https://"` (empty domain)

## Solution Implemented

Implemented a runtime SSM Parameter lookup pattern for the CloudFront domain, similar to the stage name fix.

### Changes Made

#### 1. Modified [`api_gateway_connectors.py`](medialake_constructs/api_gateway/api_gateway_connectors.py)

**Removed hardcoded MEDIALAKE_APP_ORIGIN from environment variables:**

```python
# Before (lines 455-492):
origin_host = props.ui_origin_host if props.ui_origin_host else props.cloudfront_domain
env_vars = {
    # ...
    "MEDIALAKE_APP_ORIGIN": f"https://{origin_host}",
    # ...
}

# After:
env_vars = {
    # ...
    # SSM Parameter name for CloudFront domain (read at runtime by Lambda)
    "CLOUDFRONT_DOMAIN_SSM_PARAM": f"/medialake/{config.environment}/cloudfront-distribution-domain",
    # ...
}
```

**Added SSM read permissions:**

```python
# Grant SSM read permission for CloudFront domain parameter
connector_s3_post_lambda.function.add_to_role_policy(
    iam.PolicyStatement(
        actions=["ssm:GetParameter"],
        resources=[
            f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/medialake/{config.environment}/cloudfront-distribution-domain"
        ],
    )
)
```

#### 2. Modified [`lambdas/api/connectors/s3/post_s3/index.py`](lambdas/api/connectors/s3/post_s3/index.py)

**Updated CORS origin retrieval logic (lines 906-928):**

```python
# Before:
medialake_origin_env = os.environ.get("MEDIALAKE_APP_ORIGIN", "*")

# After:
# Get MediaLake application origin from SSM Parameter Store
# This is read at runtime to avoid deployment order issues with CloudFront domain
ssm_param_name = os.environ.get("CLOUDFRONT_DOMAIN_SSM_PARAM")

if ssm_param_name:
    try:
        ssm_client = boto3.client("ssm", region_name=region)
        param_response = ssm_client.get_parameter(Name=ssm_param_name)
        cloudfront_domain = param_response["Parameter"]["Value"]
        medialake_origin_env = f"https://{cloudfront_domain}"
        logger.info(f"Retrieved CloudFront domain from SSM: {cloudfront_domain}")
    except Exception as e:
        logger.warning(f"Failed to read CloudFront domain from SSM ({ssm_param_name}): {str(e)}, falling back to wildcard")
        medialake_origin_env = "*"
else:
    # Fallback to environment variable if SSM parameter name not provided
    medialake_origin_env = os.environ.get("MEDIALAKE_APP_ORIGIN", "*")
    logger.info(f"Using MEDIALAKE_APP_ORIGIN from environment: {medialake_origin_env}")
```

## Benefits

1. **Decouples Stack Dependencies**: Connector Lambda no longer requires CloudFront domain at deployment time
2. **Runtime Flexibility**: CloudFront domain is fetched dynamically when creating connectors
3. **Graceful Fallback**: Falls back to wildcard `*` if SSM parameter is unavailable
4. **Consistent Pattern**: Aligns with the stage name SSM parameter approach
5. **Maintains Security**: Still restricts CORS to specific CloudFront domain in production

## SSM Parameter Details

- **Parameter Name**: `/medialake/{environment}/cloudfront-distribution-domain`
- **Created By**: `UserInterfaceStack` at [`user_interface_stack.py:146-152`](medialake_stacks/user_interface_stack.py:146-152)
- **Value**: CloudFront distribution domain (e.g., `d1234567890abc.cloudfront.net`)
- **Read By**: S3 connector POST Lambda at runtime when creating connectors

## Deployment Flow

1. **MediaLakeStack** deploys (with empty cloudfront_domain)
   - Creates connector Lambda with `CLOUDFRONT_DOMAIN_SSM_PARAM` environment variable
   - Grants SSM read permissions to Lambda

2. **ApiGatewayDeployment** deploys
   - Creates SSM parameter for API Gateway stage name

3. **UserInterfaceStack** deploys
   - Creates CloudFront distribution
   - Writes CloudFront domain to SSM parameter

4. **Runtime** (when user creates connector)
   - Connector Lambda reads CloudFront domain from SSM
   - Configures CORS with correct origin

## Testing Recommendations

1. **Verify SSM Parameter**: Confirm the CloudFront domain parameter exists:

   ```bash
   aws ssm get-parameter --name "/medialake/dev/cloudfront-distribution-domain"
   ```

2. **Test Connector Creation**: Create a new S3 connector with uploads enabled and verify:
   - Lambda logs show successful SSM parameter retrieval
   - CORS configuration uses CloudFront domain, not wildcard
   - Uploads work from the MediaLake UI

3. **Verify Lambda Permissions**: Check that the connector Lambda has SSM read permissions:
   ```bash
   aws lambda get-policy --function-name medialake_connectors_s3_post_dev
   ```

## Related Files

- [`medialake_constructs/api_gateway/api_gateway_connectors.py`](medialake_constructs/api_gateway/api_gateway_connectors.py)
- [`lambdas/api/connectors/s3/post_s3/index.py`](lambdas/api/connectors/s3/post_s3/index.py)
- [`medialake_stacks/user_interface_stack.py`](medialake_stacks/user_interface_stack.py)
- [`app.py`](app.py)

## Related Issues

This fix complements the CloudFormation export dependency fix documented in [`cloudformation-export-dependency-fix.md`](INTERNAL-ai-documentation/cloudformation-export-dependency-fix.md).

## Date

2025-11-12
