---
name: python-lambda-testing
description: Python Lambda and CDK testing rules with Pytest, Moto, aws-cdk-lib.assertions, syrupy snapshots, and real-AWS integration testing. Covers unit testing Lambda handlers (API Gateway, SQS, EventBridge, S3 triggers), CDK infrastructure assertions, integration tests against real AWS accounts, and E2E critical path validation. Use this skill whenever writing Python tests for Lambda functions, reviewing Lambda test quality, setting up Pytest fixtures for AWS mocking, creating Moto-based unit tests, testing CDK stacks with Template assertions, debugging flaky AWS integration tests, or designing CI/CD test pipelines for serverless Python apps. Also trigger when someone asks about Moto vs LocalStack, testing event-driven architectures, Lambda Powertools testing patterns, DynamoDB mocking, Step Functions testing, CDK snapshot tests with syrupy, parametrized Lambda tests, or coverage thresholds for serverless projects. Trigger even for questions about testing a single Lambda handler — the patterns here apply.
---

# Python Lambda & CDK Testing Rules

## Test Stack

| Layer          | Tool                                          | Purpose                                          |
| -------------- | --------------------------------------------- | ------------------------------------------------ |
| Unit (Lambda)  | Pytest + Moto (`mock_aws`)                    | Handler logic with in-process AWS mocking        |
| Unit (CDK)     | Pytest + `aws_cdk.assertions`                 | CloudFormation template validation               |
| Snapshot (CDK) | syrupy                                        | Drift detection for synthesized templates        |
| Integration    | Pytest + real AWS (test account)              | Deployed Lambda + real service interactions      |
| E2E            | Pytest + real AWS                             | Critical multi-service user journeys             |
| Coverage       | pytest-cov (v8)                               | Statement, branch, function, line                |
| Time           | freezegun or time-machine                     | Deterministic timestamp testing                  |
| Retry          | tenacity                                      | Retry logic for eventually-consistent assertions |
| Events         | Powertools event factories or custom builders | Typed Lambda event generation                    |

### What We Don't Use

- **LocalStack** — Requires Docker, has IAM emulation gaps, adds infrastructure complexity. Moto covers 95%+ of unit-test needs in-process.
- **SAM Local** — Heavyweight for unit tests; use Moto instead. Reserve real AWS for integration layer.
- **unittest** — Pytest is the standard. No `unittest.TestCase` subclasses.
- **Snapshot tests as sole CDK validation** — Snapshots detect drift but don't assert intent. Pair with targeted `has_resource_properties` assertions.
- **`time.sleep` in unit tests** — Never. Use Moto's synchronous behavior. Reserve waits for integration tests only, with retry/backoff.

## Testing Pyramid

Target distribution across all Lambda + CDK code:

- **70% Unit tests** — Lambda handler logic + CDK infrastructure assertions
- **20% Integration tests** — Real AWS services in test account
- **10% E2E tests** — Critical multi-service journeys (5-10 tests max)

Speed targets: Unit <5s, CDK <10s, Integration <2min, E2E <5min.

## Quick Reference: Pytest Markers

```ini
# pytest.ini or pyproject.toml [tool.pytest.ini_options]
markers =
    unit: Unit tests (fast, Moto, no real AWS)
    cdk: CDK infrastructure assertion tests
    integration: Integration tests (real AWS, needs credentials)
    e2e: End-to-end tests (full deployed flows)
```

Run selectively: `pytest -m unit`, `pytest -m "not e2e"`, `pytest -m integration`.

## Module-Level Client Initialization (Critical Pattern)

Lambda handlers commonly initialize boto3 clients at module level for connection reuse. This creates a testing challenge because the client binds before `mock_aws` activates.

**Pattern A — Lazy initialization (preferred):**

```python
# handler.py
import boto3
import os

_table = None

def get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource('dynamodb')
        _table = dynamodb.Table(os.environ['TABLE_NAME'])
    return _table

def lambda_handler(event, context):
    table = get_table()
    # ... use table
```

```python
# test_handler.py
from moto import mock_aws

@mock_aws
def test_handler(monkeypatch):
    monkeypatch.setenv('TABLE_NAME', 'users')
    # Reset lazy init so Moto intercepts
    import handler
    handler._table = None
    # Create the mock table, invoke handler...
```

**Pattern B — Re-import inside mock context:**

```python
@mock_aws
def test_handler():
    # Create mock resources first
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    dynamodb.create_table(TableName='users', ...)

    # Import handler AFTER mock_aws is active
    from importlib import reload
    import handler
    reload(handler)

    result = handler.lambda_handler(event, context)
```

**Pattern C — Dependency injection (cleanest, most testable):**

```python
# handler.py
def lambda_handler(event, context, table=None):
    if table is None:
        table = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
    # ... use table
```

Choose Pattern A for existing codebases, Pattern C for new code. Avoid Pattern B unless refactoring isn't feasible.

## Event Factories

Raw dict fixtures break when event schemas change. Use typed factory functions.

```python
# tests/factories.py
from typing import Any

def make_apigw_event(
    method: str = 'GET',
    path: str = '/',
    path_params: dict | None = None,
    body: dict | None = None,
    headers: dict | None = None,
    query_params: dict | None = None,
) -> dict[str, Any]:
    """Build API Gateway v2 HTTP event."""
    import json
    return {
        'requestContext': {
            'http': {'method': method, 'path': path},
            'requestId': 'test-request-id',
        },
        'pathParameters': path_params or {},
        'queryStringParameters': query_params or {},
        'headers': {'content-type': 'application/json', **(headers or {})},
        'body': json.dumps(body) if body else None,
        'isBase64Encoded': False,
    }

def make_sqs_event(messages: list[dict]) -> dict[str, Any]:
    """Build SQS batch event."""
    import json
    return {
        'Records': [
            {
                'messageId': f'msg-{i}',
                'body': json.dumps(msg),
                'receiptHandle': f'receipt-{i}',
                'attributes': {'ApproximateReceiveCount': '1'},
                'messageAttributes': {},
            }
            for i, msg in enumerate(messages)
        ]
    }

def make_s3_event(bucket: str, key: str, event_name: str = 'ObjectCreated:Put') -> dict[str, Any]:
    """Build S3 notification event."""
    return {
        'Records': [{
            'eventSource': 'aws:s3',
            'eventName': event_name,
            's3': {
                'bucket': {'name': bucket},
                'object': {'key': key, 'size': 1024},
            },
        }]
    }

def make_eventbridge_event(source: str, detail_type: str, detail: dict) -> dict[str, Any]:
    """Build EventBridge event."""
    import json
    return {
        'source': source,
        'detail-type': detail_type,
        'detail': detail,
        'id': 'test-event-id',
        'region': 'us-east-1',
        'account': '123456789012',
    }

def make_lambda_context(
    function_name: str = 'test-function',
    memory_mb: int = 128,
    timeout: int = 30,
) -> Any:
    """Build mock Lambda context."""
    class LambdaContext:
        pass
    ctx = LambdaContext()
    ctx.function_name = function_name
    ctx.memory_limit_in_mb = memory_mb
    ctx.invoked_function_arn = f'arn:aws:lambda:us-east-1:123456789012:function:{function_name}'
    ctx.aws_request_id = 'test-request-id'
    ctx.get_remaining_time_in_millis = lambda: timeout * 1000
    return ctx
```

Usage: `event = make_apigw_event(path_params={'userId': 'u123'}, method='GET')`.

## Shared Fixtures (conftest.py)

```python
# tests/conftest.py
import pytest
import boto3
import os
from moto import mock_aws

@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Set mock AWS credentials for all tests."""
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_SECURITY_TOKEN', 'testing')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')

@pytest.fixture
def dynamodb_table():
    """Create and yield a mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='users',
            KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'pk', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST',
        )
        yield table

@pytest.fixture
def s3_bucket():
    """Create and yield a mock S3 bucket."""
    with mock_aws():
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='test-bucket')
        yield 'test-bucket'

@pytest.fixture
def sqs_queue():
    """Create and yield a mock SQS queue URL."""
    with mock_aws():
        sqs = boto3.client('sqs', region_name='us-east-1')
        result = sqs.create_queue(QueueName='test-queue')
        yield result['QueueUrl']
```

Use `monkeypatch.setenv` (not `os.environ`) — it auto-reverts after each test.

## Unit Test Patterns (Lambda Handlers)

→ For complete unit test examples including API Gateway, SQS, EventBridge, S3 trigger, error handling, partial batch failure, and DynamoDB throttling patterns, read `references/unit-tests.md`.

Key principles:

- **Arrange-Act-Assert** in every test. Clear separation, one behavior per test.
- **Descriptive names**: `test_handler_returns_404_when_user_not_found`, not `test_handler_2`.
- **Parametrize** repeated scenarios with `@pytest.mark.parametrize`.
- **Mock only I/O boundaries** — use Moto for AWS, `requests-mock` for HTTP, real code for business logic.
- **Test error paths**: throttling, timeouts, malformed input, missing permissions.
- **Freeze time** with `freezegun` when testing TTLs, timestamps, or expiry logic.

## CDK Infrastructure Tests

→ For complete CDK assertion patterns including `Template.has_resource_properties`, `Match`, `Capture`, cross-stack references, snapshot testing with syrupy, and Step Functions state machine validation, read `references/cdk-tests.md`.

Key principles:

- **Assert intent, not just existence** — Don't just check a Lambda exists; verify its runtime, memory, timeout, and environment variables.
- **Use `Capture` for cross-resource validation** — Extract a DynamoDB table ARN via `Capture`, then verify it appears in the Lambda's IAM policy.
- **IAM is critical** — Always assert least-privilege policies. Check that `dynamodb:GetItem` is granted, not `dynamodb:*`.
- **Snapshot + targeted assertions** — Snapshots catch unintended drift; targeted assertions document requirements. Use both.
- **Test cross-stack wiring** — When Stack B imports from Stack A, verify the exported value flows correctly.

## Integration Tests (Real AWS)

→ For complete integration test patterns including API Gateway → Lambda → DynamoDB flows, SQS → Lambda → EventBridge verification, retry/backoff for eventually-consistent reads, cleanup fixtures, and CI/CD environment variable setup, read `references/integration-tests.md`.

Key principles:

- **Use a dedicated test AWS account** — Never test against production.
- **Deploy ephemeral stacks** — `cdk deploy TestStack-${BRANCH}`, run tests, `cdk destroy`.
- **Export CDK outputs as env vars** — `API_GATEWAY_URL`, `TABLE_NAME`, etc.
- **Retry eventually-consistent reads** — Use `tenacity` with exponential backoff, not `time.sleep`.
- **Clean up test data** — Fixtures yield a collector list; teardown deletes all items.
- **Tag test resources** — `Environment: test`, `Branch: feature-xyz` for cost tracking and orphan cleanup.

## CI/CD Pipeline Integration

Five-stage pipeline, fail-fast ordering:

1. **Unit + CDK tests** (every commit/MR) — `pytest -m "unit or cdk" --cov --cov-fail-under=80`
2. **Deploy test stack** (main branch) — `cdk deploy TestStack --require-approval never`
3. **Integration tests** (main branch) — Export stack outputs, `pytest -m integration`
4. **E2E tests** (nightly/pre-prod) — `pytest -m e2e`
5. **Cleanup** (always) — `cdk destroy TestStack --force`

→ For complete CI/CD YAML examples (GitLab CI and GitHub Actions), read `references/integration-tests.md`.

## Coverage Policy

| Scope                  | Threshold    | Enforcement                               |
| ---------------------- | ------------ | ----------------------------------------- |
| Lambda handler code    | 80%          | `--cov-fail-under=80` in CI               |
| Business logic modules | 90%          | Per-module coverage                       |
| CDK stacks             | 70%          | Separate coverage run                     |
| Integration tests      | No threshold | Coverage not meaningful for deployed code |

Run: `pytest --cov=lambdas --cov-report=term-missing --cov-report=html`.

## Dependencies

```txt
# requirements-test.txt
pytest>=8.0
pytest-cov>=4.1
pytest-mock>=3.12
pytest-env>=1.1
moto[all]>=5.0
requests-mock>=1.11
boto3>=1.34
syrupy>=4.6
freezegun>=1.4
tenacity>=8.2
```

## Directory Structure

```
project/
├── lambdas/
│   ├── api_handler/
│   │   ├── handler.py
│   │   ├── business_logic.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── conftest.py
│   │       ├── test_handler.py
│   │       └── test_business_logic.py
│   ├── event_worker/
│   │   ├── handler.py
│   │   └── tests/
│   │       └── test_handler.py
│   └── shared/               # Lambda Layer code
│       ├── utils.py
│       └── tests/
│           └── test_utils.py
├── cdk/
│   ├── stacks/
│   │   ├── api_stack.py
│   │   ├── worker_stack.py
│   │   └── database_stack.py
│   └── tests/
│       ├── conftest.py
│       ├── test_api_stack.py
│       └── snapshots/
├── integration_tests/
│   ├── conftest.py
│   ├── test_api_integration.py
│   └── helpers/
│       ├── aws_clients.py
│       └── retry.py
├── e2e_tests/
│   └── test_media_upload_flow.py
├── tests/
│   ├── conftest.py           # Root-level shared fixtures
│   └── factories.py          # Event factory functions
├── pytest.ini
└── requirements-test.txt
```

Tests mirror source structure. Co-locate unit tests with handler code. Shared fixtures in root `tests/conftest.py`.

## Reference Files

Read these when you need deeper guidance on a specific area:

| File                              | When to Read                                                                                                                                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `references/unit-tests.md`        | Moto-based Lambda handler tests (API Gateway, SQS, EventBridge, S3, partial batch failures, error handling, DynamoDB throttling, Powertools integration, freezegun time mocking, parametrized patterns) |
| `references/cdk-tests.md`         | CDK Template assertions, Match/Capture patterns, IAM policy validation, cross-stack references, snapshot testing with syrupy, Step Functions state machine testing, Lambda Layer testing                |
| `references/integration-tests.md` | Real-AWS integration tests, API Gateway → Lambda → DynamoDB flows, SQS → EventBridge verification, tenacity retry patterns, cleanup fixtures, CI/CD pipeline YAML, environment variable management      |
