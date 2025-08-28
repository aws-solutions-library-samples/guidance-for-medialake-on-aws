# Playwright Fixtures for MediaLake E2E Testing

This directory contains Playwright fixtures for end-to-end testing of the MediaLake application.

## Cognito Fixture (`cognito.fixtures.ts`)

The Cognito fixture automatically manages AWS Cognito test users for E2E authentication testing.

### Features

- **Automatic User Discovery**: Finds the MediaLake user pool and client automatically
- **Dynamic User Creation**: Creates unique test users for each test run
- **Secure Password Generation**: Generates random passwords meeting Cognito requirements
- **Parallel Test Support**: Each test worker gets unique users to avoid conflicts
- **Automatic Cleanup**: Deletes test users after test completion
- **AWS Profile Support**: Uses AWS CLI with configurable profiles

### Prerequisites

1. **AWS CLI**: Must be installed and configured
2. **AWS Profile**: Set up with appropriate Cognito permissions
3. **Environment Variables** (optional):
   - `AWS_PROFILE`: AWS profile name (defaults to `medialake-dev4`)
   - `AWS_REGION`: AWS region (defaults to `us-east-1`)

### Required AWS Permissions

Your AWS profile needs the following Cognito permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cognito-idp:ListUserPools",
        "cognito-idp:ListUserPoolClients",
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminSetUserPassword",
        "cognito-idp:AdminDeleteUser"
      ],
      "Resource": "*"
    }
  ]
}
```

### Usage

#### Basic Usage

```typescript
import { test, expect } from "../fixtures/cognito.fixtures";

test("my test", async ({ cognitoTestUser }) => {
  console.log(`Username: ${cognitoTestUser.username}`);
  console.log(`Password: ${cognitoTestUser.password}`);
  console.log(`Email: ${cognitoTestUser.email}`);
  console.log(`User Pool ID: ${cognitoTestUser.userPoolId}`);
  console.log(`Client ID: ${cognitoTestUser.userPoolClientId}`);
});
```

#### With Authentication

```typescript
import { test, expect } from "../fixtures/auth.fixtures";

test("authenticated test", async ({ authenticatedPage, cognitoTestUser }) => {
  // Page is already logged in with the test user
  await expect(authenticatedPage).toHaveURL(/.*dashboard.*/);
});
```

#### Manual Login

```typescript
import { test, expect } from "../fixtures/cognito.fixtures";

test("manual login", async ({ page, cognitoTestUser }) => {
  await page.goto("/sign-in");
  await page.fill('[name="email"]', cognitoTestUser.username);
  await page.fill('[name="password"]', cognitoTestUser.password);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard");
});
```

### Running Tests

#### With Default Profile

```bash
npx playwright test tests/auth/cognito-e2e.spec.ts
```

#### With Custom Profile

```bash
AWS_PROFILE=my-profile npx playwright test tests/auth/cognito-e2e.spec.ts
```

#### With Custom Region

```bash
AWS_REGION=us-west-2 npx playwright test tests/auth/cognito-e2e.spec.ts
```

## Auth Fixture (`auth.fixtures.ts`)

Extends the Cognito fixture to provide pre-authenticated pages and contexts.

### Features

- **Pre-authenticated Pages**: Pages that are already logged in
- **Authenticated Contexts**: Browser contexts with authentication
- **Automatic Login**: Handles the login flow automatically

### Usage

```typescript
import { test, expect } from "../fixtures/auth.fixtures";

test("test with authenticated page", async ({ authenticatedPage }) => {
  // Page is already logged in
  await authenticatedPage.goto("/protected-route");
  // Test protected functionality
});

test("test with authenticated context", async ({ authenticatedContext }) => {
  const page = await authenticatedContext.newPage();
  await page.goto("/dashboard");
  // Multiple pages can share the same authenticated context
});
```

## S3 Fixture (`s3.fixtures.ts`)

Manages S3 buckets for testing file upload functionality.

### Features

- **Temporary Buckets**: Creates unique S3 buckets for each test
- **Automatic Cleanup**: Deletes buckets and contents after tests
- **Parallel Safe**: Each test worker gets unique bucket names

## Troubleshooting

### Common Issues

1. **AWS CLI Not Found**

   ```
   Error: aws command not found
   ```

   Solution: Install AWS CLI and ensure it's in your PATH

2. **Invalid Profile**

   ```
   Error: The config profile (profile-name) could not be found
   ```

   Solution: Check your AWS profile configuration with `aws configure list-profiles`

3. **Insufficient Permissions**

   ```
   Error: User is not authorized to perform: cognito-idp:ListUserPools
   ```

   Solution: Add the required Cognito permissions to your AWS profile

4. **User Pool Not Found**
   ```
   Error: No MediaLake user pool found
   ```
   Solution: Ensure your AWS profile has access to the correct account/region

### Debug Mode

Enable verbose logging by setting the DEBUG environment variable:

```bash
DEBUG=1 npx playwright test tests/auth/cognito-e2e.spec.ts
```

### Manual Cleanup

If tests fail and leave test users behind, you can clean them up manually:

```bash
# List users with e2etest prefix
aws cognito-idp list-users --user-pool-id YOUR_POOL_ID --filter "username ^= \"e2etest\""

# Delete specific user
aws cognito-idp admin-delete-user --user-pool-id YOUR_POOL_ID --username e2etest-0-12345678
```
