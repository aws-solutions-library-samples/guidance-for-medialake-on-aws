# Integration & E2E Test Patterns

## Why Real AWS (Not LocalStack/SAM)

- **100% parity** — No emulation gaps. DynamoDB consistency, IAM evaluation, EventBridge delivery all behave exactly as production.
- **IAM validation** — LocalStack's IAM enforcement is incomplete. Real AWS catches permission errors that mocks hide.
- **No tooling overhead** — No Docker, no LocalStack containers, no SAM CLI. Just a test AWS account and CDK.
- **CI/CD native** — Deploy ephemeral stacks, run tests, tear down. CDK handles everything.

**Trade-offs:** Slower (seconds not milliseconds), requires credentials, small cost (mitigated by ephemeral stacks and resource tagging).

## Integration Test Fixtures

```python
# integration_tests/conftest.py
import pytest
import boto3
import os

@pytest.fixture(scope='session')
def aws_region():
    return os.environ.get('AWS_REGION', 'us-east-1')

@pytest.fixture(scope='session')
def api_url():
    """API Gateway URL from CDK stack output."""
    url = os.environ.get('API_GATEWAY_URL')
    assert url, 'API_GATEWAY_URL env var required — export from CDK stack outputs'
    return url

@pytest.fixture(scope='session')
def table_name():
    return os.environ.get('DYNAMODB_TABLE_NAME', 'users-test')

@pytest.fixture
def dynamodb_client(aws_region):
    return boto3.client('dynamodb', region_name=aws_region)

@pytest.fixture
def cleanup_items(dynamodb_client, table_name):
    """Collect test item keys for cleanup after each test."""
    keys_to_delete = []
    yield keys_to_delete
    for key in keys_to_delete:
        dynamodb_client.delete_item(TableName=table_name, Key=key)
```

## Retry Pattern for Eventually-Consistent Reads

Never use bare `time.sleep()`. Use `tenacity` for exponential backoff with clear stop conditions.

```python
# integration_tests/helpers/retry.py
from tenacity import retry, stop_after_delay, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_delay(30),           # Give up after 30 seconds
    wait=wait_exponential(min=1, max=8), # 1s, 2s, 4s, 8s...
    retry=retry_if_exception_type(AssertionError),
)
def assert_item_exists(dynamodb_client, table_name, key):
    """Retry until DynamoDB item appears (eventually consistent)."""
    response = dynamodb_client.get_item(TableName=table_name, Key=key)
    assert 'Item' in response, f'Item {key} not yet in {table_name}'
    return response['Item']

@retry(
    stop=stop_after_delay(30),
    wait=wait_exponential(min=1, max=8),
    retry=retry_if_exception_type(AssertionError),
)
def assert_sqs_message_received(sqs_client, queue_url, expected_key, expected_value):
    """Retry until expected message appears in SQS queue."""
    import json
    response = sqs_client.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=5,
    )
    messages = response.get('Messages', [])
    assert messages, 'No messages received yet'
    for msg in messages:
        body = json.loads(msg['Body'])
        if body.get(expected_key) == expected_value:
            sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=msg['ReceiptHandle'])
            return body
    raise AssertionError(f'No message with {expected_key}={expected_value}')
```

## API Gateway → Lambda → DynamoDB Integration

```python
# integration_tests/test_api_integration.py
import requests
import pytest
from integration_tests.helpers.retry import assert_item_exists

@pytest.mark.integration
def test_create_and_retrieve_user(api_url, table_name, cleanup_items, dynamodb_client):
    """Full API round-trip: POST creates, GET retrieves."""
    user_id = 'integ-test-user-001'
    cleanup_items.append({'userId': {'S': user_id}})

    # Create
    resp = requests.post(f'{api_url}/users', json={
        'userId': user_id, 'name': 'Integration User', 'email': 'integ@example.com',
    })
    assert resp.status_code == 201

    # Retrieve
    resp = requests.get(f'{api_url}/users/{user_id}')
    assert resp.status_code == 200
    data = resp.json()
    assert data['userId'] == user_id
    assert data['name'] == 'Integration User'

@pytest.mark.integration
def test_get_nonexistent_user_returns_404(api_url):
    resp = requests.get(f'{api_url}/users/does-not-exist-999')
    assert resp.status_code == 404
```

## SQS → Lambda → EventBridge Integration

```python
# integration_tests/test_event_worker_integration.py
import json
import pytest
import boto3
from integration_tests.helpers.retry import assert_sqs_message_received

@pytest.fixture(scope='session')
def sqs_client(aws_region):
    return boto3.client('sqs', region_name=aws_region)

@pytest.fixture(scope='session')
def input_queue_url():
    return os.environ['INPUT_QUEUE_URL']

@pytest.fixture(scope='session')
def test_consumer_queue_url():
    """SQS queue subscribed to the EventBridge rule for test verification."""
    return os.environ['TEST_CONSUMER_QUEUE_URL']

@pytest.mark.integration
def test_sqs_to_lambda_to_eventbridge(sqs_client, input_queue_url, test_consumer_queue_url):
    """Send SQS message → Lambda processes → EventBridge event arrives at test consumer."""
    # Send
    message = {'fileKey': 'integration-test.mp4', 'userId': 'user123'}
    sqs_client.send_message(QueueUrl=input_queue_url, MessageBody=json.dumps(message))

    # Verify EventBridge event arrived (via test consumer queue)
    event_body = assert_sqs_message_received(
        sqs_client, test_consumer_queue_url,
        expected_key='fileKey', expected_value='integration-test.mp4',
    )
    assert event_body['fileKey'] == 'integration-test.mp4'
```

## E2E Test: Full Media Upload Flow

```python
# e2e_tests/test_media_upload_flow.py
import requests
import pytest
from integration_tests.helpers.retry import assert_item_exists

@pytest.mark.e2e
def test_upload_process_and_verify_metadata(api_url, dynamodb_client):
    """E2E: presign → upload → Lambda processes → DynamoDB updated."""
    # Step 1: Get presigned upload URL
    presign = requests.post(f'{api_url}/media/presign', json={'fileName': 'e2e-test.mp4'})
    assert presign.status_code == 200
    upload_url = presign.json()['uploadUrl']
    media_id = presign.json()['mediaId']

    # Step 2: Upload file
    with open('e2e_tests/fixtures/sample.mp4', 'rb') as f:
        requests.put(upload_url, data=f)

    # Step 3: Wait for async processing, verify metadata
    item = assert_item_exists(
        dynamodb_client, 'media-metadata',
        key={'mediaId': {'S': media_id}},
    )
    assert item['status']['S'] == 'processed'
```

## Running Integration Tests

### Deploy and Test

```bash
# Deploy ephemeral test stack
cdk deploy TestStack-${CI_COMMIT_SHORT_SHA} \
  --context environment=test \
  --require-approval never \
  --tags Environment=test Branch=${CI_COMMIT_REF_NAME}

# Export CDK stack outputs
STACK_NAME="TestStack-${CI_COMMIT_SHORT_SHA}"
export API_GATEWAY_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)
export DYNAMODB_TABLE_NAME=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='TableName'].OutputValue" \
  --output text)

# Run integration tests
pytest -m integration -v

# Cleanup
cdk destroy $STACK_NAME --force
```

### Environment Variable Management

Use `pytest-env` in `pyproject.toml` for default values (overridden by real exports in CI):

```toml
[tool.pytest-env]
AWS_DEFAULT_REGION = "us-east-1"
LOG_LEVEL = "DEBUG"
```

## CI/CD Pipeline (GitLab CI)

```yaml
stages:
  - test
  - deploy-test
  - integration
  - e2e
  - cleanup

unit-and-cdk-tests:
  stage: test
  script:
    - pip install -r requirements-test.txt
    - pytest -m "unit or cdk" -v --cov=lambdas --cov=cdk --cov-fail-under=80
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'

deploy-test-stack:
  stage: deploy-test
  script:
    - cdk deploy TestStack-${CI_COMMIT_SHORT_SHA}
      --context environment=test
      --require-approval never
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

integration-tests:
  stage: integration
  script:
    - export API_GATEWAY_URL=$(aws cloudformation describe-stacks ...)
    - export DYNAMODB_TABLE_NAME=$(aws cloudformation describe-stacks ...)
    - pytest -m integration -v
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

e2e-tests:
  stage: e2e
  script:
    - pytest -m e2e -v
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'

cleanup-test-stack:
  stage: cleanup
  script:
    - cdk destroy TestStack-${CI_COMMIT_SHORT_SHA} --force
  when: always
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
```

## CI/CD Pipeline (GitHub Actions)

```yaml
name: Lambda Test Pipeline

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "0 2 * * *" # Nightly E2E

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-test.txt
      - run: pytest -m "unit or cdk" -v --cov --cov-fail-under=80

  integration-tests:
    if: github.ref == 'refs/heads/main'
    needs: unit-tests
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_TEST_ROLE_ARN }}
          aws-region: us-east-1
      - run: |
          cdk deploy TestStack-${{ github.sha }} --require-approval never
          export API_GATEWAY_URL=$(aws cloudformation describe-stacks ...)
          pytest -m integration -v
      - if: always()
        run: cdk destroy TestStack-${{ github.sha }} --force

  e2e-tests:
    if: github.event_name == 'schedule'
    needs: integration-tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest -m e2e -v
```

## Test Resource Tagging

Tag all test resources for cost tracking and orphan cleanup:

```python
# cdk/stacks/test_stack.py
cdk.Tags.of(self).add('Environment', 'test')
cdk.Tags.of(self).add('Branch', os.environ.get('CI_COMMIT_REF_NAME', 'local'))
cdk.Tags.of(self).add('CreatedBy', 'integration-tests')
```

Run a weekly cleanup script to delete stacks with `Environment=test` older than 24 hours.

## Anti-Patterns

- **`time.sleep(10)` without retry** — Async operations have variable latency. Use tenacity with exponential backoff.
- **No cleanup fixtures** — Orphaned test data pollutes the test account and costs money. Always clean up.
- **Testing against shared dev account** — Use a dedicated test account. Multiple developers running integration tests simultaneously causes flaky failures.
- **Hardcoded queue URLs and table names** — Export from CDK stack outputs. Hardcoded values break when stacks are redeployed.
- **No resource tagging** — Without tags, orphaned test stacks are invisible. Tag everything.
- **Running integration tests on every commit** — Too slow. Run unit tests on every commit, integration on main branch only.
