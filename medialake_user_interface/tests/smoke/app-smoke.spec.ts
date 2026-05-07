/**
 * Comprehensive smoke test suite for the Media Lake application.
 *
 * Covers: authentication, dashboard, search, asset detail, collections,
 * pipelines, executions, and settings pages.
 *
 * Run with: npx playwright test tests/smoke/app-smoke.spec.ts
 */
import { test, expect } from "../fixtures/static-auth.fixtures";

test.describe("Authentication", () => {
  test("sign-in page renders correctly", async ({ page, baseURL }) => {
    await page.goto(baseURL ? `${baseURL}/sign-in` : "http://localhost:5173/sign-in");
    await expect(page.getByRole("heading", { name: "Welcome to Media Lake" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Email" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Password" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("unauthenticated user is redirected to sign-in", async ({ page, baseURL }) => {
    const root = baseURL || "http://localhost:5173";
    await page.goto(root);
    await expect(page).toHaveURL(/sign-in/);
  });

  test("successful login redirects to dashboard", async ({ authenticatedPage }) => {
    await expect(authenticatedPage).toHaveURL(/\/$/);
    // App shell is visible
    await expect(authenticatedPage.getByRole("button", { name: "Home" })).toBeVisible();
  });
});

test.describe("Dashboard", () => {
  test("renders widgets with data", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    // Dashboard heading
    await expect(page.getByRole("heading", { name: "Media Lake", level: 1 })).toBeVisible();

    // Recent Assets widget loads
    await expect(page.getByRole("heading", { name: "Recent Assets", exact: true })).toBeVisible({
      timeout: 15000,
    });

    // Favorites widget loads
    await expect(page.getByRole("heading", { name: "Favorites", exact: true })).toBeVisible({
      timeout: 15000,
    });

    // Widget controls are present
    await expect(page.getByRole("button", { name: "Add Widget" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reset to default layout" })).toBeVisible();
  });

  test("video players render in asset cards", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    // Wait for Recent Assets widget
    await expect(page.getByRole("heading", { name: "Recent Assets", exact: true })).toBeVisible({
      timeout: 15000,
    });

    // Video players should render (look for video player regions)
    const videoPlayers = page.getByRole("region", { name: "video player" });
    await expect(videoPlayers.first()).toBeVisible({ timeout: 20000 });

    // At least one video player should have controls
    const seekSliders = page.getByRole("slider", { name: "seek" });
    await expect(seekSliders.first()).toBeVisible({ timeout: 10000 });
  });

  test("asset cards show metadata", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    await expect(page.getByRole("heading", { name: "Recent Assets", exact: true })).toBeVisible({
      timeout: 15000,
    });

    // Asset cards should show file names
    const assetHeadings = page.locator("h4").filter({ hasText: /\.mp4|\.png|\.jpg/i });
    await expect(assetHeadings.first()).toBeVisible({ timeout: 15000 });

    // Format badges should be visible
    await expect(page.getByText("MP4").first()).toBeVisible({ timeout: 10000 });
  });

  test("favorite toggle buttons are present when assets load", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    await expect(page.getByRole("heading", { name: "Recent Assets", exact: true })).toBeVisible({
      timeout: 15000,
    });

    // Wait for asset cards to fully render
    await page.waitForTimeout(3000);
    const addFav = await page.getByRole("button", { name: "Add to favorites" }).count();
    const removeFav = await page.getByRole("button", { name: "Remove from favorites" }).count();
    expect(addFav + removeFav).toBeGreaterThan(0);
  });
});

test.describe("Search", () => {
  test("wildcard search returns results", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    // Type search query
    await page.getByRole("textbox", { name: /search/i }).fill("*");
    await page.getByRole("textbox", { name: /search/i }).press("Enter");

    // Should navigate to search page
    await expect(page).toHaveURL(/search/);

    // Results should load
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 15000 });
  });

  test("search results show card and table view toggles", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    await page.getByRole("textbox", { name: /search/i }).fill("*");
    await page.getByRole("textbox", { name: /search/i }).press("Enter");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 15000 });

    // View mode toggles
    await expect(page.getByRole("button", { name: "Card view" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Table view" })).toBeVisible();
  });

  test("table view renders correctly", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    await page.getByRole("textbox", { name: /search/i }).fill("*");
    await page.getByRole("textbox", { name: /search/i }).press("Enter");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 15000 });

    // Switch to table view
    await page.getByRole("button", { name: "Table view" }).click();

    // Table should render with rows
    await expect(page.getByRole("grid", { name: "Data table" })).toBeVisible({ timeout: 10000 });
  });

  test("search results have action buttons", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    await page.getByRole("textbox", { name: /search/i }).fill("*");
    await page.getByRole("textbox", { name: /search/i }).press("Enter");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 15000 });

    // Sort and Fields controls
    await expect(page.getByRole("button", { name: "Sort" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Fields" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Appearance" })).toBeVisible();
  });

  test("clear search works", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    await page.getByRole("textbox", { name: /search/i }).fill("*");
    await page.getByRole("textbox", { name: /search/i }).press("Enter");
    await expect(page).toHaveURL(/search/);

    // Clear search
    await page.getByRole("button", { name: "Clear search" }).click();
    const searchBox = page.getByRole("textbox", { name: /search/i });
    await expect(searchBox).toHaveValue("");
  });
});

test.describe("Asset Detail", () => {
  test("video detail page loads with player and metadata", async ({ authenticatedPage }) => {
    test.setTimeout(90000);
    const page = authenticatedPage;

    // Navigate directly to search results page
    await page.goto("/search?q=*&semantic=false");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 20000 });

    // Use the "Asset Detail" button approach — force-click to bypass hover requirement
    const firstCard = page.locator("[data-testid^='asset-card-']").first();
    const detailBtn = firstCard.getByRole("button", { name: "Asset Detail" });
    await detailBtn.click({ force: true });

    // Should navigate to a detail page
    await expect(page).toHaveURL(/\/(videos|images|audio)\//, { timeout: 15000 });

    // Video player should be present (use first() since search page cards may still be in DOM)
    await expect(page.getByRole("region", { name: "video player" }).first()).toBeVisible({
      timeout: 15000,
    });

    // Metadata tabs should be visible
    await expect(page.getByRole("tab", { name: "Summary" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Technical Metadata" })).toBeVisible();
  });

  test("metadata tabs are navigable", async ({ authenticatedPage }) => {
    test.setTimeout(90000);
    const page = authenticatedPage;

    // Navigate directly to search results
    await page.goto("/search?q=*&semantic=false");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 20000 });

    const firstCard = page.locator("[data-testid^='asset-card-']").first();
    await firstCard.getByRole("button", { name: "Asset Detail" }).click({ force: true });
    await expect(page).toHaveURL(/\/(videos|images|audio)\//, { timeout: 15000 });

    // Summary tab should be selected by default
    await expect(page.getByRole("tab", { name: "Summary", selected: true })).toBeVisible();

    // Click Technical Metadata tab
    await page.getByRole("tab", { name: "Technical Metadata" }).click();
    await expect(
      page.getByRole("tab", { name: "Technical Metadata", selected: true })
    ).toBeVisible();

    // Click Descriptive tab
    await page.getByRole("tab", { name: "Descriptive" }).click();
    await expect(page.getByRole("tab", { name: "Descriptive", selected: true })).toBeVisible();
  });

  test("breadcrumb navigation works", async ({ authenticatedPage }) => {
    test.setTimeout(90000);
    const page = authenticatedPage;

    await page.getByRole("textbox", { name: /search/i }).fill("*");
    await page.getByRole("textbox", { name: /search/i }).press("Enter");
    await page.goto("/search?q=*&semantic=false");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 20000 });

    const firstCard = page.locator("[data-testid^='asset-card-']").first();
    await firstCard.getByRole("button", { name: "Asset Detail" }).click({ force: true });
    await expect(page).toHaveURL(/\/(videos|images|audio)\//, { timeout: 15000 });
    // Breadcrumb should show search context
    await expect(page.getByText(/Search/)).toBeVisible();

    // History button should be present
    await expect(page.getByRole("button", { name: "show history" })).toBeVisible();
  });
});

test.describe("Collections", () => {
  test("collections page loads with tabs", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Collections" }).click();
    await expect(page).toHaveURL(/collections/);

    // Page heading
    await expect(page.getByRole("heading", { name: "Collections", level: 4 })).toBeVisible();

    // Tabs
    await expect(page.getByRole("button", { name: "All Collections" })).toBeVisible();
    await expect(page.getByRole("button", { name: "My Collections" })).toBeVisible();

    // Create button
    await expect(page.getByRole("button", { name: "Create Collection" }).first()).toBeVisible();

    // Search box
    await expect(page.getByRole("textbox", { name: /search collections/i })).toBeVisible();
  });

  test("create collection button is clickable", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Collections" }).click();
    await expect(page).toHaveURL(/collections/);

    // Create Collection button should be present and enabled
    const createBtn = page.getByRole("button", { name: "Create Collection" }).first();
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toBeEnabled();
  });
});

test.describe("Pipelines", () => {
  test("pipelines page loads with table", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Pipelines" }).click();
    await expect(page).toHaveURL(/pipelines/);

    // Page heading
    await expect(page.getByRole("heading", { name: "Pipelines", level: 4 })).toBeVisible();

    // Add button
    await expect(page.getByText("Add New Pipeline")).toBeVisible();

    // Data table
    await expect(page.getByRole("grid", { name: "Data table" })).toBeVisible({ timeout: 10000 });

    // Table columns
    await expect(page.getByText("Name", { exact: false }).first()).toBeVisible();
    await expect(page.getByText("Status", { exact: false }).first()).toBeVisible();
  });

  test("pipeline search works", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Pipelines" }).click();
    await expect(page).toHaveURL(/pipelines/);

    // Search box should be present
    const searchBox = page.getByRole("textbox", { name: /search pipelines/i });
    await expect(searchBox).toBeVisible();
  });
});

test.describe("Pipeline Executions", () => {
  test("executions page loads", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Pipeline Executions" }).click();
    await expect(page).toHaveURL(/executions/);
  });
});

test.describe("Settings", () => {
  test("settings navigation shows sub-pages", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Settings" }).click();

    // Sub-navigation items should appear
    await expect(page.getByRole("button", { name: "Connectors" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Users and Groups" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Permissions" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Integrations" })).toBeVisible();
    await expect(page.getByRole("button", { name: "System Settings" })).toBeVisible();
  });

  test("system settings page loads with tabs", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "System Settings" }).click();
    await expect(page).toHaveURL(/settings\/system/);

    // Page heading
    await expect(page.getByRole("heading", { name: "System Settings" })).toBeVisible();

    // Tabs
    await expect(page.getByRole("tab", { name: "Search", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "API Keys" })).toBeVisible();

    // Search tab content — semantic search settings
    await expect(page.getByText("Semantic Search Enabled")).toBeVisible({ timeout: 10000 });
  });

  test("system settings API Keys tab loads", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "System Settings" }).click();
    await expect(page).toHaveURL(/settings\/system/);

    // Switch to API Keys tab
    await page.getByRole("tab", { name: "API Keys" }).click();
    await expect(page.getByRole("tab", { name: "API Keys", selected: true })).toBeVisible();
  });

  test("integrations page loads", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Integrations" }).click();
    await expect(page).toHaveURL(/settings\/integrations/);

    await expect(page.getByRole("heading", { name: "Integrations" })).toBeVisible();
    await expect(page.getByText("Add Integration")).toBeVisible();
  });

  test("users and groups page loads", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Users and Groups" }).click();
    await expect(page).toHaveURL(/settings\/users/);
  });

  test("permissions page loads", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Permissions" }).click();
    await expect(page).toHaveURL(/settings\/permissions/);
  });

  test("connectors page loads", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Connectors" }).click();
    await expect(page).toHaveURL(/settings\/connectors/);
  });
});

test.describe("Navigation & App Shell", () => {
  test("sidebar navigation works for all main pages", async ({ authenticatedPage }) => {
    test.setTimeout(60000);
    const page = authenticatedPage;

    // Home
    await page.getByRole("button", { name: "Home" }).click();
    await expect(page).toHaveURL(/\/$/);

    // Assets
    await page.getByRole("button", { name: "Assets" }).click();
    await expect(page).toHaveURL(/assets/);
    await expect(page.getByRole("heading", { name: "Assets", level: 4 })).toBeVisible();

    // Collections
    await page.getByRole("button", { name: "Collections" }).click();
    await expect(page).toHaveURL(/collections/);

    // Pipelines
    await page.getByRole("button", { name: "Pipelines" }).click();
    await expect(page).toHaveURL(/pipelines/);

    // Pipeline Executions
    await page.getByRole("button", { name: "Pipeline Executions" }).click();
    await expect(page).toHaveURL(/executions/);

    // Back to Home
    await page.getByRole("button", { name: "Home" }).click();
    await expect(page).toHaveURL(/\/$/);
  });

  test("theme toggle is present", async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    // Theme toggle buttons should be in the sidebar
    await expect(page.getByText("Theme")).toBeVisible();
  });

  test("notification bell is present", async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await expect(page.getByRole("button", { name: "notifications" })).toBeVisible();
  });

  test("search bar is always visible in app shell", async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await expect(page.getByRole("textbox", { name: /search/i })).toBeVisible();

    // Navigate to different pages — search bar should persist
    await page.getByRole("button", { name: "Collections" }).click();
    await expect(page.getByRole("textbox", { name: /search/i })).toBeVisible();

    await page.getByRole("button", { name: "Pipelines" }).click();
    await expect(page.getByRole("textbox", { name: /search/i })).toBeVisible();
  });

  test("semantic search toggle is present", async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await expect(page.getByRole("switch", { name: /semantic search/i })).toBeVisible();
  });
});

test.describe("Assets Page", () => {
  test("assets page loads with connector selection", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    await page.getByRole("button", { name: "Assets" }).click();
    await expect(page).toHaveURL(/assets/);

    await expect(page.getByRole("heading", { name: "Assets", level: 4 })).toBeVisible();
    await expect(page.getByText("Browse and manage your media assets")).toBeVisible();

    // Connector section should be visible
    await expect(page.getByText("Connectors")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Performance", () => {
  test("dashboard loads within acceptable time", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    const start = Date.now();

    // Reload to measure fresh load
    await page.reload({ waitUntil: "domcontentloaded" });

    // Wait for the main widget to render
    await expect(page.getByRole("heading", { name: "Recent Assets", exact: true })).toBeVisible({
      timeout: 15000,
    });

    const loadTime = Date.now() - start;

    // Dashboard should load within 10 seconds (generous for cold API calls)
    expect(loadTime).toBeLessThan(10000);
  });

  test("no failed API calls on dashboard load", async ({ authenticatedPage }) => {
    test.setTimeout(30000);
    const page = authenticatedPage;

    const failedRequests: string[] = [];
    page.on("requestfailed", (request) => {
      const url = request.url();
      // Ignore aborted requests (expected during React re-renders)
      if (request.failure()?.errorText !== "net::ERR_ABORTED") {
        failedRequests.push(url);
      }
    });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(5000);

    // Filter out non-API failures (e.g., favicon, analytics)
    const apiFailures = failedRequests.filter(
      (url) => url.includes("/v1/") || url.includes("cloudfront.net")
    );
    expect(apiFailures).toHaveLength(0);
  });
});
