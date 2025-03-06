# MediaLake Playwright Tests

This directory contains end-to-end tests for the MediaLake application using Playwright.

## Test Structure

- `tests/` - Contains all test files
  - `deployment.spec.ts` - Tests for CDK deployment validation
  - `api.spec.ts` - Tests for API functionality
  - `ui.spec.ts` - Tests for UI functionality
  - `cdk-outputs.spec.ts` - Tests for CDK stack outputs and resources
- `fixtures/` - Contains test fixtures
  - `auth-fixture.ts` - Authentication fixture for tests
- `utils/` - Contains utility functions
  - `auth.ts` - Authentication utilities
  - `api.ts` - API utilities

## Environment Variables

The tests use the following environment variables:

- `BASE_URL` - The base URL of the application (default: http://localhost:3000)
- `API_URL` - The base URL of the API (default: https://api.example.com)
- `TEST_USERNAME` - The username to use for authentication (default: test@example.com)
- `TEST_PASSWORD` - The password to use for authentication (default: Password123!)
- `AWS_REGION` - The AWS region to use (default: us-east-1)
- `API_ENDPOINT` - The API Gateway endpoint from CDK outputs

## Running Tests

You can run the tests using the following npm scripts:

```bash
# Run all tests
npm run test:e2e

# Run tests with UI mode
npm run test:e2e:ui

# Run specific test suites
npm run test:e2e:deployment
npm run test:e2e:api
npm run test:e2e:ui-tests
npm run test:e2e:cdk-outputs
```

## Customizing Tests

To customize the tests for your specific environment:

1. Update the environment variables to match your deployment
2. Adjust the selectors in the UI tests to match your application's structure
3. Update the API endpoints in the API tests to match your API's structure
4. Update the stack names in the deployment tests to match your CDK stack names

## CI/CD Integration

These tests can be integrated into your CI/CD pipeline by setting the appropriate environment variables and running the tests in headless mode:

```bash
# Example CI/CD command
CI=true npm run test:e2e
```

## Debugging Tests

To debug tests, you can use the UI mode:

```bash
npm run test:e2e:ui
```

This will open the Playwright UI, which allows you to:
- See test execution in real-time
- View screenshots and videos of test runs
- Inspect the DOM during test execution
- Step through tests 