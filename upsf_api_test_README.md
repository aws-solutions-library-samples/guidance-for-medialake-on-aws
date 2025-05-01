# UPSF API Testing

This directory contains files for testing the User Profile, Settings, and Favorites (UPSF) API endpoints.

## Files

- `upsf_api_test_plan.md`: A comprehensive test plan outlining all test cases for the UPSF API endpoints.
- `test_upsf_api.py`: A Python script that executes the test cases outlined in the test plan.

## Prerequisites

Before running the tests, you need to:

1. Deploy the UPSF API to the development environment:
   ```
   cdk deploy medialake-users-groups-roles-stack
   ```

2. Have a valid Cognito user for testing.

3. Install the required Python packages:
   ```
   pip install boto3 requests
   ```

4. Configure AWS credentials with appropriate permissions.

## Configuration

Edit the `test_upsf_api.py` file and update the following configuration variables:

```python
# Configuration
API_ENDPOINT = "https://api.dev.medialake.example.com"  # Replace with your API Gateway endpoint
USER_POOL_ID = "us-west-2_abcdefghi"  # Replace with your Cognito User Pool ID
CLIENT_ID = "1234567890abcdefghijklmno"  # Replace with your Cognito App Client ID
USERNAME = "test@example.com"  # Replace with your test user email
PASSWORD = "TestPassword123!"  # Replace with your test user password

# DynamoDB configuration
REGION = "us-west-2"  # Replace with your AWS region
USER_TABLE_NAME = "medialake-user-dev"  # Replace with your actual user table name
```

## Running the Tests

To run the tests, simply execute the Python script:

```
python test_upsf_api.py
```

The script will:
1. Authenticate with Cognito to get an ID token
2. Execute all the test cases outlined in the test plan
3. Print a summary of the test results

## Test Cases

The script tests the following endpoints:

### User Profile Endpoints
- GET /users/profile
- PUT /users/profile

### User Settings Endpoints
- GET /users/settings
- GET /users/settings?namespace={namespace}
- PUT /users/settings/{namespace}/{key}

### User Favorites Endpoints
- POST /users/favorites
- GET /users/favorites
- GET /users/favorites?itemType={itemType}
- DELETE /users/favorites/{itemType}/{itemId}

For each endpoint, the script tests both valid and invalid inputs, and verifies the responses and DynamoDB interactions.

## Interpreting Results

After running the tests, the script will print a summary of the results:

```
=== Test Summary ===
Total tests: X
Passed: Y
Failed: Z
Success rate: XX.XX%
```

If any tests fail, the script will also print details of the failed tests:

```
=== Failed Tests ===
❌ Test Name: Reason for failure
```

Use this information to identify and fix any issues with the UPSF API endpoints.