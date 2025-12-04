# CloudFormation Export Dependency Fix

## Problem Description

### Error Message

```
MediaLakeUserInterface: ROLLBACK_IN_PROGRESS | AWS::CloudFormation::Stack | MediaLakeUserInterface
No export named MediaLakeApiGatewayDeployment-StageName found. Rollback requested by user.
```

### Root Cause

The deployment was failing due to a **circular dependency timing issue** between CloudFormation stacks:

1. `MediaLakeUserInterface` stack (created first in [`app.py:121`](app.py:121)) attempted to import the API Gateway stage name using `Fn.import_value("MediaLakeApiGatewayDeployment-StageName")`
2. `MediaLakeApiGatewayDeployment` stack (created later in [`app.py:606`](app.py:606)) exported this value via CloudFormation export
3. CloudFormation evaluates `Fn.import_value()` calls during stack creation, not after dependencies are resolved
4. The export didn't exist when the UI stack tried to reference it, causing immediate deployment failure

Even though explicit dependencies were defined in [`app.py:617`](app.py:617), CloudFormation couldn't resolve the import timing issue because the export was created by a stack that hadn't been deployed yet.

## Solution Implemented

Replaced CloudFormation exports with **SSM Parameter Store** for cross-stack communication. This breaks the circular dependency because SSM parameters can be read at runtime rather than during stack synthesis.

### Changes Made

#### 1. Modified [`api_gateway_deployment_stack.py`](medialake_stacks/api_gateway_deployment_stack.py)

**Added imports:**

```python
from aws_cdk import aws_ssm as ssm
from config import config
```

**Replaced CloudFormation export with SSM Parameter:**

```python
# Store the stage name in SSM Parameter Store instead of CloudFormation export
# This avoids circular dependency issues with stacks that need the stage name
stage_name_param = ssm.StringParameter(
    self,
    "ApiGatewayStageNameParameter",
    parameter_name=f"/medialake/{config.environment}/api-gateway-stage-name",
    string_value=self.api_deployment.stage.stage_name,
    description="API Gateway deployment stage name for MediaLake",
)

# Export the SSM parameter name as CloudFormation output for reference
cdk.CfnOutput(
    self,
    "ApiGatewayStageNameParameterName",
    value=stage_name_param.parameter_name,
    description="SSM parameter name containing the API Gateway stage name",
)
```

#### 2. Modified [`user_interface_stack.py`](medialake_stacks/user_interface_stack.py)

**Changed from CloudFormation import to SSM Parameter lookup:**

```python
# Import API Gateway REST API ID from CloudFormation export
api_gateway_rest_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")

# Read API Gateway stage name from SSM Parameter Store instead of CloudFormation export
# This avoids circular dependency issues since the deployment stack is created after this stack
api_gateway_stage_param = ssm.StringParameter.from_string_parameter_name(
    self,
    "ApiGatewayStageNameParameter",
    string_parameter_name=f"/medialake/{config.environment}/api-gateway-stage-name",
)
api_gateway_stage = api_gateway_stage_param.string_value
```

## Benefits of This Approach

1. **Breaks Circular Dependencies**: SSM parameters are read at runtime, not during stack synthesis
2. **Maintains Loose Coupling**: Stacks can be deployed independently without strict ordering requirements
3. **Better Scalability**: SSM Parameter Store is designed for cross-stack and cross-region parameter sharing
4. **Consistent Pattern**: Aligns with existing SSM parameter usage in the codebase (e.g., WAF ACL ARN, CloudFront distribution domain)

## SSM Parameter Details

- **Parameter Name**: `/medialake/{environment}/api-gateway-stage-name`
- **Type**: String
- **Value**: API Gateway deployment stage name (e.g., "prod", "dev")
- **Description**: "API Gateway deployment stage name for MediaLake"

## Deployment Order

With this fix, the deployment order remains:

1. `MediaLakeApiGatewayCore` - Creates the API Gateway
2. `MediaLakeUserInterface` - Can now deploy without waiting for deployment stack
3. `MediaLakeApiGatewayDeployment` - Writes stage name to SSM Parameter

The UI stack will read the SSM parameter at runtime, allowing it to deploy even if the deployment stack hasn't created the parameter yet (though the parameter must exist before the UI stack's resources that use it are invoked).

## Testing Recommendations

1. **Clean Deployment**: Test a fresh deployment to ensure all stacks deploy successfully
2. **Update Deployment**: Test updating existing stacks to verify the SSM parameter approach works
3. **Parameter Verification**: Confirm the SSM parameter is created with correct value:
   ```bash
   aws ssm get-parameter --name "/medialake/{environment}/api-gateway-stage-name"
   ```

## Alternative Solutions Considered

1. **Reorder Stack Creation**: Deploy `ApiGatewayDeployment` before `UserInterface`

   - Rejected: Would require significant refactoring of dependency chain

2. **Hardcoded Stage Name**: Use a fixed stage name value

   - Rejected: Reduces flexibility and doesn't follow infrastructure-as-code best practices

3. **Direct Stack References**: Pass stage name directly between stacks
   - Rejected: Creates tight coupling and circular dependency issues

## Related Files

- [`medialake_stacks/api_gateway_deployment_stack.py`](medialake_stacks/api_gateway_deployment_stack.py)
- [`medialake_stacks/user_interface_stack.py`](medialake_stacks/user_interface_stack.py)
- [`app.py`](app.py)

## Date

2025-11-12
