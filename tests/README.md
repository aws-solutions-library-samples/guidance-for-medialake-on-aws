# MediaLake Lambda Tests

This directory contains unit and integration tests for MediaLake Lambda functions.

## Directory Structure

```
tests/
├── README.md              # This file
├── conftest.py            # Shared fixtures and AWS mocks
├── __init__.py
└── common_libraries/      # Tests for lambdas/common_libraries/
    ├── __init__.py
    └── test_collections_utils.py
```

The test directory structure mirrors the `lambdas/` source directory. To find tests for a specific file:

- Source: `lambdas/common_libraries/collections_utils.py`
- Tests: `tests/common_libraries/test_collections_utils.py`

## Prerequisites

Ensure you have the development dependencies installed:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

### Run all tests

```bash
pytest
```

### Run tests for a specific module

```bash
pytest tests/common_libraries/
```

### Run a specific test file

```bash
pytest tests/common_libraries/test_collections_utils.py
```

### Run a specific test class or function

```bash
# Run a specific test class
pytest tests/common_libraries/test_collections_utils.py::TestGetCollectionItemCount

# Run a specific test function
pytest tests/common_libraries/test_collections_utils.py::TestGetCollectionItemCount::test_count_empty_collection
```

### Run tests by marker

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Useful pytest options

```bash
# Verbose output (shows each test name)
pytest -v

# Show print statements and logs
pytest -s

# Stop on first failure
pytest -x

# Run last failed tests only
pytest --lf

# Show local variables in tracebacks
pytest -l

# Run tests matching a keyword
pytest -k "pagination"
```

## Writing Tests

### Test file naming

- Test files must be named `test_*.py`
- Test classes must be named `Test*`
- Test functions must be named `test_*`

### Using fixtures

The `conftest.py` file provides shared fixtures that are automatically available to all tests:

```python
def test_example(mock_dynamodb_table, mock_client_error):
    # mock_dynamodb_table is a fresh MagicMock for each test
    mock_dynamodb_table.query.return_value = {"Count": 5}

    # mock_client_error is the MockClientError class for creating errors
    error = mock_client_error(
        {"Error": {"Code": "InternalServerError", "Message": "Test"}},
        "Query"
    )
    mock_dynamodb_table.query.side_effect = error
```

### Available fixtures

| Fixture               | Description                                                |
| --------------------- | ---------------------------------------------------------- |
| `mock_dynamodb_table` | A fresh `MagicMock` representing a DynamoDB table resource |
| `mock_client_error`   | The `MockClientError` class for simulating AWS errors      |
| `aws_mocks`           | Dictionary with `logger`, `tracer`, `metrics` mock objects |

### Test markers

Use markers to categorize tests:

```python
import pytest

@pytest.mark.unit
class TestMyFunction:
    def test_something(self):
        pass

@pytest.mark.integration
def test_with_real_aws():
    pass

@pytest.mark.slow
def test_large_dataset():
    pass
```

### Importing Lambda code

The `conftest.py` automatically adds `lambdas/` to the Python path, so you can import directly:

```python
from common_libraries.collections_utils import get_collection_item_count
from api.collections_api.handlers.collections_ID_get import lambda_handler
```

## How Fixtures Work

Fixtures have **function scope by default**, meaning each test gets a fresh instance. This prevents state from leaking between tests.

```python
@pytest.fixture  # scope="function" is the default
def mock_dynamodb_table():
    return MagicMock()  # New instance for each test
```

The AWS mocks in `conftest.py` are set up at module load time because they need to be in place before any Lambda code is imported. This is safe because:

1. They replace AWS SDK modules we never want in tests
2. The actual test fixtures are still function-scoped

## Adding Tests for New Modules

1. Create a directory matching the source structure:

   ```bash
   mkdir -p tests/api/collections_api/handlers
   touch tests/api/collections_api/__init__.py
   touch tests/api/collections_api/handlers/__init__.py
   ```

2. Create the test file:

   ```bash
   touch tests/api/collections_api/handlers/test_collections_ID_get.py
   ```

3. Write tests using the shared fixtures:

   ```python
   import pytest
   from api.collections_api.handlers.collections_ID_get import lambda_handler

   @pytest.mark.unit
   class TestCollectionsIDGet:
       def test_returns_collection(self, mock_dynamodb_table):
           # Test implementation
           pass
   ```

## Configuration

Test configuration is in `pytest.ini` at the project root:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
norecursedirs = .git .venv node_modules cdk.out dist __pycache__
```
