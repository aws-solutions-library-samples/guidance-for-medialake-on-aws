# Unit Test Patterns — Lambda Handlers

## API Gateway Handler Test

```python
# lambdas/api_handler/handler.py
import json
import os
import boto3
from typing import Any

_table = None

def get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource('dynamodb')
        _table = dynamodb.Table(os.environ['TABLE_NAME'])
    return _table

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        user_id = event['pathParameters']['userId']
        if not user_id:
            return {'statusCode': 400, 'body': json.dumps({'error': 'userId required'})}

        table = get_table()
        response = table.get_item(Key={'userId': user_id})

        if 'Item' not in response:
            return {'statusCode': 404, 'body': json.dumps({'error': 'User not found'})}

        return {'statusCode': 200, 'body': json.dumps(response['Item'])}
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
```

```python
# lambdas/api_handler/tests/conftest.py
import pytest
import boto3
from moto import mock_aws
from tests.factories import make_apigw_event, make_lambda_context

@pytest.fixture
def dynamodb_table(monkeypatch):
    """Create mock DynamoDB table and wire handler to it."""
    monkeypatch.setenv('TABLE_NAME', 'users')
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='users',
            KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST',
        )
        # Reset lazy-init so Moto intercepts
        import lambdas.api_handler.handler as handler_mod
        handler_mod._table = None
        yield table

@pytest.fixture
def context():
    return make_lambda_context()
```

```python
# lambdas/api_handler/tests/test_handler.py
import json
import pytest
from moto import mock_aws
from tests.factories import make_apigw_event
from lambdas.api_handler.handler import lambda_handler

@mock_aws
def test_returns_200_when_user_exists(dynamodb_table, context):
    """Happy path: user found in DynamoDB."""
    # Arrange
    dynamodb_table.put_item(Item={'userId': 'u123', 'name': 'Alice', 'email': 'alice@example.com'})
    event = make_apigw_event(path_params={'userId': 'u123'})

    # Act
    result = lambda_handler(event, context)

    # Assert
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['userId'] == 'u123'
    assert body['name'] == 'Alice'

@mock_aws
def test_returns_404_when_user_not_found(dynamodb_table, context):
    """No item in table for given userId."""
    event = make_apigw_event(path_params={'userId': 'nonexistent'})

    result = lambda_handler(event, context)

    assert result['statusCode'] == 404
    assert 'User not found' in json.loads(result['body'])['error']

@mock_aws
def test_returns_400_for_empty_user_id(dynamodb_table, context):
    """Empty userId should return 400, not query DynamoDB."""
    event = make_apigw_event(path_params={'userId': ''})

    result = lambda_handler(event, context)

    assert result['statusCode'] == 400

@pytest.mark.parametrize('user_id,expected_status', [
    ('u123', 200),
    ('nonexistent', 404),
    ('', 400),
])
@mock_aws
def test_handler_parametrized(dynamodb_table, context, user_id, expected_status):
    """Multiple scenarios via parametrize — insert only u123."""
    dynamodb_table.put_item(Item={'userId': 'u123', 'name': 'Test User'})
    event = make_apigw_event(path_params={'userId': user_id})

    result = lambda_handler(event, context)

    assert result['statusCode'] == expected_status
```

## SQS Worker with Partial Batch Failure

```python
# lambdas/event_worker/handler.py
import json
import boto3
import os
from typing import Any

s3 = boto3.client('s3')
eventbridge = boto3.client('events')

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    failures = []
    for record in event['Records']:
        try:
            message = json.loads(record['body'])
            file_key = message['fileKey']

            response = s3.get_object(Bucket=os.environ['MEDIA_BUCKET'], Key=file_key)
            content = response['Body'].read()

            eventbridge.put_events(Entries=[{
                'Source': 'media.processor',
                'DetailType': 'FileProcessed',
                'Detail': json.dumps({'fileKey': file_key, 'size': len(content)}),
            }])
        except Exception:
            failures.append({'itemIdentifier': record['messageId']})

    return {'batchItemFailures': failures}
```

```python
# lambdas/event_worker/tests/test_handler.py
import json
import pytest
import boto3
from moto import mock_aws
from tests.factories import make_sqs_event, make_lambda_context

@pytest.fixture
def s3_with_media(monkeypatch):
    monkeypatch.setenv('MEDIA_BUCKET', 'media-bucket')
    with mock_aws():
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='media-bucket')
        s3.put_object(Bucket='media-bucket', Key='valid.mp4', Body=b'video data')
        yield s3

@mock_aws
def test_processes_valid_messages(s3_with_media):
    from lambdas.event_worker.handler import lambda_handler
    event = make_sqs_event([{'fileKey': 'valid.mp4'}])

    result = lambda_handler(event, make_lambda_context())

    assert result['batchItemFailures'] == []

@mock_aws
def test_reports_partial_batch_failure(s3_with_media):
    """One valid file, one missing — only the missing one fails."""
    from lambdas.event_worker.handler import lambda_handler
    event = make_sqs_event([
        {'fileKey': 'valid.mp4'},
        {'fileKey': 'missing.mp4'},
    ])

    result = lambda_handler(event, make_lambda_context())

    assert len(result['batchItemFailures']) == 1
    assert result['batchItemFailures'][0]['itemIdentifier'] == 'msg-1'
```

## S3 Trigger Handler

```python
@mock_aws
def test_s3_trigger_processes_uploaded_file(monkeypatch):
    """Lambda triggered by S3 ObjectCreated event."""
    monkeypatch.setenv('OUTPUT_BUCKET', 'processed-bucket')
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='uploads')
    s3.create_bucket(Bucket='processed-bucket')
    s3.put_object(Bucket='uploads', Key='raw/video.mp4', Body=b'raw content')

    from tests.factories import make_s3_event, make_lambda_context
    event = make_s3_event(bucket='uploads', key='raw/video.mp4')

    from lambdas.s3_processor.handler import lambda_handler
    result = lambda_handler(event, make_lambda_context())

    assert result['statusCode'] == 200
    # Verify output was written
    output = s3.get_object(Bucket='processed-bucket', Key='raw/video.mp4')
    assert output['Body'].read() is not None
```

## Error Handling Patterns

### DynamoDB Throttling with Retry

```python
@mock_aws
def test_handles_dynamodb_throttling(dynamodb_table, context, mocker):
    """Handler retries on ProvisionedThroughputExceededException."""
    from botocore.exceptions import ClientError

    throttle_error = ClientError(
        {'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'Rate exceeded'}},
        'GetItem',
    )
    mocker.patch.object(
        dynamodb_table, 'get_item',
        side_effect=[throttle_error, {'Item': {'userId': 'u123', 'name': 'Alice'}}],
    )
    event = make_apigw_event(path_params={'userId': 'u123'})

    result = lambda_handler(event, context)

    assert result['statusCode'] == 200
```

### Malformed Input

```python
def test_handles_missing_path_parameters(context):
    """Event with no pathParameters key should return 500, not crash."""
    event = {'headers': {}}

    result = lambda_handler(event, context)

    assert result['statusCode'] == 500
    assert 'error' in json.loads(result['body'])
```

## Time-Dependent Logic with freezegun

```python
from freezegun import freeze_time
import time

@freeze_time('2026-01-15 12:00:00')
@mock_aws
def test_sets_ttl_30_days_from_now(dynamodb_table, context):
    """Verify DynamoDB TTL is set 30 days in the future."""
    event = make_apigw_event(method='POST', body={'userId': 'u123', 'name': 'Alice'})

    lambda_handler(event, context)

    item = dynamodb_table.get_item(Key={'userId': 'u123'})['Item']
    expected_ttl = int(time.time()) + (30 * 86400)
    assert item['ttl'] == expected_ttl
```

## Testing with Powertools

If your handler uses `@event_source`, `@idempotent`, or Powertools Logger/Tracer:

```python
# Handler using Powertools event parsing
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2

def lambda_handler(event: dict, context: LambdaContext) -> dict:
    api_event = APIGatewayProxyEventV2(event)
    user_id = api_event.path_parameters.get('userId')
    # ...
```

```python
# Test: Powertools-compatible events work with the same factories
def test_powertools_event_parsing():
    event = make_apigw_event(path_params={'userId': 'u123'})

    result = lambda_handler(event, make_lambda_context())

    assert result['statusCode'] == 200
```

For idempotency testing, mock the persistence layer:

```python
@mock_aws
def test_idempotent_handler_returns_cached_result(dynamodb_table, mocker):
    """Second invocation with same idempotency key returns cached response."""
    # Create the idempotency table Moto mock
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    dynamodb.create_table(
        TableName='idempotency-table',
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    # Invoke twice with same payload — second should be cached
    event = make_apigw_event(body={'userId': 'u123', 'action': 'create'})
    result1 = lambda_handler(event, make_lambda_context())
    result2 = lambda_handler(event, make_lambda_context())
    assert result1 == result2
```

## Testing Lambda Layers

Layer code lives in `lambdas/shared/` and is tested independently. The key challenge is import paths — in Lambda runtime, layers are on `PYTHONPATH`, but locally they're not.

```python
# lambdas/shared/utils.py
def sanitize_filename(name: str) -> str:
    return name.replace(' ', '_').lower()
```

```python
# lambdas/shared/tests/test_utils.py
from lambdas.shared.utils import sanitize_filename

def test_sanitize_filename_replaces_spaces():
    assert sanitize_filename('My File Name.mp4') == 'my_file_name.mp4'
```

In `pyproject.toml` or `setup.cfg`, add the layer path to the test `PYTHONPATH` so imports resolve:

```toml
[tool.pytest.ini_options]
pythonpath = ["lambdas/shared"]
```

## Anti-Patterns

- **Testing boto3 itself** — Don't assert that `dynamodb.put_item` writes an item. Moto guarantees that. Test your handler's logic around the call.
- **Mocking everything** — If you mock the handler's internal function, you're testing the mock, not the code. Mock at I/O boundaries only.
- **Hardcoded regions in handler code** — Use `os.environ['AWS_REGION']` or `AWS_DEFAULT_REGION`. Moto needs region consistency.
- **Sharing state between tests** — Each test gets its own Moto context via `with mock_aws()`. Never share a DynamoDB table fixture across tests that mutate it without `function` scope.
- **Testing private functions** — Test through the handler's public interface. If a private function needs its own tests, it probably belongs in a separate module.
