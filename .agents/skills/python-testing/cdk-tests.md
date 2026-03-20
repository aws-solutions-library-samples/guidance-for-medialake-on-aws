# CDK Infrastructure Test Patterns

## Template Assertion Basics

Every CDK test follows the same structure: instantiate a stack, synthesize a template, assert properties.

```python
import aws_cdk as cdk
from aws_cdk.assertions import Template, Match, Capture
from cdk.stacks.api_stack import ApiStack

def test_lambda_runtime_and_memory():
    """Validate Lambda is configured with expected runtime and resources."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    template.has_resource_properties('AWS::Lambda::Function', {
        'Runtime': 'python3.12',
        'MemorySize': 512,
        'Timeout': 30,
    })
```

## Match Helpers

| Matcher                      | Purpose                    | Example                           |
| ---------------------------- | -------------------------- | --------------------------------- |
| `Match.any_value()`          | Property exists, any value | Runtime is set (don't care which) |
| `Match.object_like({})`      | Partial object match       | IAM statement has Effect: Allow   |
| `Match.array_with([])`       | Array contains these items | Policy has specific actions       |
| `Match.string_like_regexp()` | Regex match on strings     | ARN matches pattern               |
| `Match.not_(matcher)`        | Negation                   | Resource does NOT have property   |
| `Match.absent()`             | Property must not exist    | No VPC config on Lambda           |

## Capture for Cross-Resource Validation

`Capture` extracts values from the template so you can assert relationships between resources. This is essential for verifying wiring — that a Lambda's environment variable actually references the correct DynamoDB table.

```python
def test_lambda_env_var_references_correct_table():
    """Lambda TABLE_NAME env var matches the actual DynamoDB table."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    # Capture the table name from the DynamoDB resource
    table_name_capture = Capture()
    template.has_resource_properties('AWS::DynamoDB::Table', {
        'TableName': table_name_capture,
    })

    # Verify Lambda env var uses the same table name
    template.has_resource_properties('AWS::Lambda::Function', {
        'Environment': {
            'Variables': {
                'TABLE_NAME': table_name_capture.as_string(),
            }
        }
    })
```

```python
def test_lambda_iam_policy_targets_correct_table_arn():
    """IAM policy Resource field points to the DynamoDB table ARN."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    # Capture the table's logical ID to build expected ARN reference
    table_capture = Capture()
    template.has_resource_properties('AWS::IAM::Policy', {
        'PolicyDocument': {
            'Statement': Match.array_with([
                Match.object_like({
                    'Action': Match.array_with(['dynamodb:GetItem']),
                    'Effect': 'Allow',
                    'Resource': table_capture,
                })
            ])
        }
    })
    # The captured value should be a Fn::GetAtt reference to the table
    captured = table_capture.as_object()
    assert 'Fn::GetAtt' in captured or 'Fn::Join' in captured
```

## IAM Policy Validation (Critical)

Always assert least-privilege. Never allow `*` actions in production stacks.

```python
def test_lambda_has_least_privilege_dynamodb_access():
    """Lambda should have GetItem and Query only, not wildcard."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    template.has_resource_properties('AWS::IAM::Policy', {
        'PolicyDocument': {
            'Statement': Match.array_with([
                Match.object_like({
                    'Action': ['dynamodb:GetItem', 'dynamodb:Query'],
                    'Effect': 'Allow',
                })
            ])
        }
    })

def test_no_wildcard_iam_actions():
    """No IAM statement should use Action: '*'."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    # Get all IAM policies and check none have wildcard actions
    policies = template.find_resources('AWS::IAM::Policy')
    for logical_id, policy in policies.items():
        statements = policy['Properties']['PolicyDocument']['Statement']
        for stmt in statements:
            action = stmt.get('Action', [])
            if isinstance(action, str):
                assert action != '*', f'{logical_id} has wildcard action'
            else:
                assert '*' not in action, f'{logical_id} has wildcard action'
```

## API Gateway Integration

```python
def test_api_gateway_lambda_proxy_integration():
    """API Gateway uses HTTP proxy integration with correct payload version."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    template.resource_count_is('AWS::ApiGatewayV2::Api', 1)
    template.has_resource_properties('AWS::ApiGatewayV2::Integration', {
        'IntegrationType': 'AWS_PROXY',
        'PayloadFormatVersion': '2.0',
    })

def test_api_gateway_has_cors_configured():
    """API Gateway has CORS enabled for allowed origins."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    template.has_resource_properties('AWS::ApiGatewayV2::Api', {
        'CorsConfiguration': {
            'AllowMethods': Match.array_with(['GET', 'POST']),
            'AllowOrigins': Match.any_value(),
        }
    })
```

## Environment Variables

```python
def test_lambda_receives_required_env_vars():
    """Lambda has all required environment variables."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    template.has_resource_properties('AWS::Lambda::Function', {
        'Environment': {
            'Variables': {
                'TABLE_NAME': Match.any_value(),
                'LOG_LEVEL': Match.any_value(),
                'POWERTOOLS_SERVICE_NAME': Match.any_value(),
            }
        }
    })
```

## Cross-Stack References

```python
def test_worker_stack_receives_table_from_api_stack():
    """Worker stack's Lambda env var references the table from API stack."""
    app = cdk.App()
    api_stack = ApiStack(app, 'ApiStack')
    worker_stack = WorkerStack(app, 'WorkerStack', api_table=api_stack.table)
    template = Template.from_stack(worker_stack)

    template.has_resource_properties('AWS::Lambda::Function', {
        'Environment': {
            'Variables': {
                'TABLE_NAME': Match.any_value(),  # Will be an ImportValue or Ref
            }
        }
    })
```

## Resource Counts

Useful for preventing accidental resource creation (e.g., an extra Lambda or queue):

```python
def test_stack_creates_expected_resource_counts():
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    template.resource_count_is('AWS::Lambda::Function', 2)
    template.resource_count_is('AWS::DynamoDB::Table', 1)
    template.resource_count_is('AWS::SQS::Queue', 1)  # includes DLQ
```

## Step Functions State Machine Testing

```python
def test_step_functions_state_machine_definition():
    """Validate state machine has expected states and transitions."""
    app = cdk.App()
    stack = WorkflowStack(app, 'WorkflowStack')
    template = Template.from_stack(stack)

    # Assert state machine exists
    template.resource_count_is('AWS::StepFunctions::StateMachine', 1)

    # Capture the definition to inspect states
    definition_capture = Capture()
    template.has_resource_properties('AWS::StepFunctions::StateMachine', {
        'DefinitionString': definition_capture,
    })

    # If using DefinitionString (JSON), parse and validate
    import json
    # Note: CDK often uses Fn::Join for the definition string,
    # so for complex validations, snapshot testing may be more practical

def test_step_functions_has_error_handling():
    """State machine includes Catch/Retry on task states."""
    app = cdk.App()
    stack = WorkflowStack(app, 'WorkflowStack')
    template = Template.from_stack(stack)

    # Validate the state machine role has Lambda invoke permissions
    template.has_resource_properties('AWS::IAM::Policy', {
        'PolicyDocument': {
            'Statement': Match.array_with([
                Match.object_like({
                    'Action': 'lambda:InvokeFunction',
                    'Effect': 'Allow',
                })
            ])
        }
    })
```

## Snapshot Testing with syrupy

Snapshots catch unintended changes in the full CloudFormation template. Use alongside targeted assertions — snapshots detect drift, assertions document intent.

```python
# cdk/tests/test_api_stack_snapshot.py
import aws_cdk as cdk
from cdk.stacks.api_stack import ApiStack

def test_api_stack_matches_snapshot(snapshot):
    """Detect unintended infrastructure changes."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = app.synth().get_stack_by_name('TestApiStack').template

    assert template == snapshot
```

**First run:** `pytest --snapshot-update` creates the baseline.
**Subsequent runs:** Fails if template changed. Review the diff, then update: `pytest --snapshot-update`.

**When to update vs investigate:**

- CDK version bump changed logical IDs → Update snapshot
- New resource appeared unexpectedly → Investigate
- IAM policy changed → Investigate carefully

Install: `pip install syrupy`.

## Multi-Account / Cross-Account Permissions

```python
def test_cross_account_invoke_permission():
    """Lambda allows invocation from trusted account."""
    app = cdk.App()
    stack = CrossAccountStack(app, 'XAccount', trusted_account='111122223333')
    template = Template.from_stack(stack)

    template.has_resource_properties('AWS::Lambda::Permission', {
        'Principal': '111122223333',
        'Action': 'lambda:InvokeFunction',
    })
```

## Lambda Layer Testing (CDK)

```python
def test_lambda_uses_shared_layer():
    """Lambda function includes the shared utilities layer."""
    app = cdk.App()
    stack = ApiStack(app, 'TestApiStack')
    template = Template.from_stack(stack)

    template.has_resource_properties('AWS::Lambda::Function', {
        'Layers': Match.array_with([Match.any_value()]),
    })

    # Verify layer exists
    template.resource_count_is('AWS::Lambda::LayerVersion', 1)
```

## Anti-Patterns

- **Asserting only resource existence** — `template.resource_count_is('AWS::Lambda::Function', 1)` alone is insufficient. Assert properties too.
- **Ignoring IAM in tests** — Permission errors are the #1 cause of Lambda failures in production. Always validate IAM policies.
- **Over-relying on snapshots** — Teams blindly update snapshots. Pair with targeted assertions that fail with meaningful messages.
- **Hardcoding stack names in tests** — Use `'TestApiStack'` in tests; the real stack name comes from CDK context/env.
- **Not testing context-dependent behavior** — If your stack uses `cdk.App(context={'environment': 'prod'})`, test both `prod` and `test` contexts.
