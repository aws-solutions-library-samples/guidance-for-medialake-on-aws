# MediaLake Playwright Tests

This directory contains end-to-end tests for the MediaLake application using Playwright.

## Test Structure

- `tests/` - Contains all test files
  - `basic.spec.ts` - Basic tests that don't require a web server
  - `example.spec.ts` - Example tests with both basic and web-dependent tests
  - `api.spec.ts` - API tests with both mock and real API tests
  - `ui.spec.ts` - UI tests with both mock and real UI tests

## Running Tests

You can run the tests using the following commands:

```bash
# Run all tests
npx playwright test

# Run a specific test file
npx playwright test tests/basic.spec.ts

# Run tests with UI mode
npx playwright test --ui

# Run tests with debug mode
npx playwright test --debug
```

## Test Categories

The tests are organized into two categories:

1. **Tests that don't require a web server** - These tests run without any external dependencies and are always enabled.
2. **Tests that require a web server** - These tests are skipped by default and need to be enabled manually when the web server is running.

To enable the web server dependent tests:

1. Start the web server: `npm run dev`
2. Remove the `.skip()` from the test descriptions in the test files
3. Run the tests

## Configuration

The Playwright configuration is in `playwright.config.ts`. The web server configuration is commented out by default to allow running tests without a web server.

To enable the web server configuration:

1. Uncomment the `webServer` section in `playwright.config.ts`
2. Uncomment the `baseURL` line in the `use` section
3. Update the command and URL if needed

## Adding New Tests

When adding new tests, follow these guidelines:

1. For tests that don't require a web server, add them to the appropriate test description without `.skip()`
2. For tests that require a web server, add them to a test description with `.skip()` to prevent them from running by default
3. Add clear comments to indicate the dependencies of the test
4. Use descriptive test names that indicate what is being tested 