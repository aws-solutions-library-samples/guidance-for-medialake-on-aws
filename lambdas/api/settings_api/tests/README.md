# Settings API Lambda Tests

Comprehensive test suite for the Settings API Lambda function using pytest and moto3 for AWS service mocking.

## Test Coverage

### Collection Types Endpoints

#### GET /settings/collection-types

- ✅ List empty collection types
- ✅ List collection types with data
- ✅ Filter by active status (`filter[active]`)
- ✅ Cursor-based pagination
- ✅ Public read access (no admin required for GET)

#### POST /settings/collection-types

- ✅ Create collection type successfully
- ✅ Validation: missing required fields (name, color, icon)
- ✅ Validation: invalid hex color format
- ✅ Validation: invalid icon name
- ✅ Validation: name length constraints
- ✅ Admin-only access (403 for non-admins)
- ✅ Optional fields (description, isActive)
- ✅ DynamoDB persistence verification

#### PUT /settings/collection-types/{id}

- ✅ Update collection type successfully
- ✅ 404 for non-existent types
- ✅ 403 for system types (cannot update)
- ✅ Validation errors
- ✅ Admin-only access
- ✅ DynamoDB update verification

#### DELETE /settings/collection-types/{id}

- ✅ Delete unused collection type
- ✅ 409 conflict when type is in use
- ✅ 403 for system types (cannot delete)
- ✅ 404 for non-existent types
- ✅ Admin-only access
- ✅ DynamoDB deletion verification

#### POST /settings/collection-types/{id}/migrate

- ✅ Migrate collections between types
- ✅ 404 for non-existent source/target types
- ✅ 400 for inactive target types
- ✅ 400 for missing target type ID
- ✅ Admin-only access
- ✅ Zero collections migration (edge case)
- ✅ DynamoDB batch update verification

## Running Tests

### Install Dependencies

```bash
cd lambdas/api/settings_api
pip install -r requirements-test.txt
```

### Run All Tests

```bash
pytest
```

### Run with Coverage Report

```bash
pytest --cov=. --cov-report=html
```

Then open `htmlcov/index.html` to view detailed coverage report.

### Run Specific Test File

```bash
pytest tests/test_collection_types_get_post.py
pytest tests/test_collection_types_mutations.py
```

### Run Specific Test Class

```bash
pytest tests/test_collection_types_get_post.py::TestGetCollectionTypes
```

### Run Specific Test

```bash
pytest tests/test_collection_types_get_post.py::TestGetCollectionTypes::test_get_collection_types_empty
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Only Failed Tests

```bash
pytest --lf
```

## Test Architecture

### Fixtures (`conftest.py`)

- **`aws_credentials`**: Mock AWS credentials for moto
- **`dynamodb_table`**: Mock DynamoDB table with proper schema
- **`admin_event`**: API Gateway event with admin user (superAdministrators group)
- **`non_admin_event`**: API Gateway event with non-admin user (editors group)
- **`lambda_context`**: Mock Lambda context
- **`sample_collection_type`**: Sample collection type data
- **`seed_types_helper`**: Helper to seed multiple collection types
- **`seed_collections_helper`**: Helper to seed collections

### Mocking Strategy

All tests use **moto3** to mock AWS services:

- DynamoDB tables are created in-memory for each test
- No real AWS resources are created
- Tests are isolated and can run in parallel
- Fast execution (no network calls)

### Test Isolation

Each test:

1. Gets a fresh DynamoDB table
2. Seeds only the data it needs
3. Cleans up automatically via fixtures
4. Can run independently

## Coverage Goals

- **Target**: 80%+ code coverage
- **Current**: Run `pytest --cov` to check
- **Focus areas**:
  - All handler functions
  - Validation logic
  - Permission checks
  - Error handling
  - DynamoDB operations

## Continuous Integration

These tests can be integrated into CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Run Settings API Tests
  run: |
    cd lambdas/api/settings_api
    pip install -r requirements-test.txt
    pytest --cov --cov-fail-under=80
```

## Future Test Additions

As new features are added to `/settings/*`:

1. Create new test files in `tests/`
2. Add fixtures to `conftest.py` if needed
3. Follow existing patterns for consistency
4. Maintain 80%+ coverage
