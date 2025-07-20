import { test, expect } from "../fixtures/auth.fixtures";

test.describe("Cognito E2E Authentication Tests", () => {
  test("should create test user and login successfully", async ({
    cognitoTestUser,
    authenticatedPage,
    baseURL,
  }) => {
    // The cognitoTestUser fixture has already created a user and the authenticatedPage has logged in
    console.log(`Test running with user: ${cognitoTestUser.username}`);
    console.log(`User pool ID: ${cognitoTestUser.userPoolId}`);
    console.log(`User pool client ID: ${cognitoTestUser.userPoolClientId}`);

    // Verify we're on the root page after successful login
    const expectedUrl = baseURL || "http://localhost:5173";
    await expect(authenticatedPage).toHaveURL(expectedUrl);

    // Add more assertions based on your application's behavior after login
    // For example, check for user-specific elements, navigation, etc.
  });

  test("should handle user authentication with fresh credentials", async ({
    cognitoTestUser,
    page,
    baseURL,
  }) => {
    // This test demonstrates manual login using the test user credentials
    const loginUrl = baseURL ? `${baseURL}/sign-in` : "/sign-in";
    await page.goto(loginUrl);

    // Fill in the login form with the dynamically created test user
    await page
      .getByRole("textbox", { name: "Email" })
      .fill(cognitoTestUser.username);
    await page
      .getByRole("textbox", { name: "Password" })
      .fill(cognitoTestUser.password);

    // Submit the form
    await page.getByRole("button", { name: "Sign in", exact: true }).click();

    // Wait for successful login - SPA redirects to root
    const rootUrl = baseURL || "http://localhost:5173";
    await page.waitForURL(rootUrl, { timeout: 15000 });

    // Verify successful authentication
    await expect(page).toHaveURL(rootUrl);
  });

  test("should provide unique test users for parallel execution", async ({
    cognitoTestUser,
  }) => {
    // Each test gets its own unique user, safe for parallel execution
    expect(cognitoTestUser.username).toMatch(
      /^mne-medialake\+e2etest-\d+-[a-f0-9]{8}@amazon\.com$/,
    );
    expect(cognitoTestUser.email).toMatch(
      /^mne-medialake\+e2etest-\d+-[a-f0-9]{8}@amazon\.com$/,
    );
    expect(cognitoTestUser.password.length).toBeGreaterThanOrEqual(8); // Dynamic length based on policy
    expect(cognitoTestUser.userPoolId).toBeTruthy();
    expect(cognitoTestUser.userPoolClientId).toBeTruthy();
  });

  test("should cleanup test user after test completion", async ({
    cognitoTestUser,
  }) => {
    // This test verifies that the fixture provides valid user data
    // The cleanup happens automatically in the fixture's finally block
    expect(cognitoTestUser.username).toBeTruthy();
    expect(cognitoTestUser.password).toBeTruthy();

    // The user will be automatically deleted after this test completes
    console.log(
      `Test user ${cognitoTestUser.username} will be cleaned up automatically`,
    );
  });
});

test.describe("Cognito User Management", () => {
  test("should work with authenticated context for multiple pages", async ({
    authenticatedContext,
    cognitoTestUser,
    baseURL,
  }) => {
    // Create a new page within the authenticated context
    const page = await authenticatedContext.newPage();

    // Navigate to the root - this should be accessible when authenticated
    const rootUrl = baseURL || "http://localhost:5173";
    await page.goto(rootUrl);

    // Verify we can access the authenticated root page
    await expect(page).toHaveURL(rootUrl);

    // You can create additional pages in the same context
    const secondPage = await authenticatedContext.newPage();
    await secondPage.goto(rootUrl);

    // Both pages should maintain authentication and access the root
    await expect(secondPage).toHaveURL(rootUrl);

    await page.close();
    await secondPage.close();
  });
});
