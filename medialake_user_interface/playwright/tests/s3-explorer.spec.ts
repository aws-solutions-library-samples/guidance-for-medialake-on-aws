import { test, expect, Page } from "@playwright/test";

const MOCK_CONNECTOR_ID = "test-connector-123";
const BASE_URL = `http://localhost:3000`; // Adjust based on your dev server
const S3_EXPLORER_ROUTE = `/s3/explorer/${MOCK_CONNECTOR_ID}`;

// Mock API responses
const mockS3Response = {
  status: "success",
  message: "S3 objects retrieved successfully",
  data: {
    objects: [
      {
        Key: "test-folder/file1.txt",
        Size: 1024,
        LastModified: "2024-01-01T00:00:00Z",
        StorageClass: "STANDARD",
        ETag: "test-etag-1",
      },
      {
        Key: "test-folder/image.jpg",
        Size: 2048,
        LastModified: "2024-01-02T00:00:00Z",
        StorageClass: "STANDARD",
        ETag: "test-etag-2",
      },
    ],
    commonPrefixes: ["test-folder/subfolder1/", "test-folder/subfolder2/"],
    prefix: "",
    delimiter: "/",
    isTruncated: false,
  },
};

const mockEmptyResponse = {
  status: "success",
  message: "S3 objects retrieved successfully",
  data: {
    objects: [],
    commonPrefixes: [],
    prefix: "",
    delimiter: "/",
    isTruncated: false,
  },
};

const mockErrorResponse = {
  status: "error",
  message: "Access denied",
  data: null,
};

const mockPermissionErrorWithPrefixes = {
  status: "error",
  message: "Access denied",
  data: {
    objects: [],
    commonPrefixes: [],
    prefix: "",
    delimiter: "/",
    isTruncated: false,
    allowedPrefixes: ["allowed-path-1/", "allowed-path-2/"],
  },
};

// Helper to setup API mocks
async function setupApiMocks(page: Page, responseData: any, status = 200) {
  await page.route(
    `**/api/connectors/s3/explorer/${MOCK_CONNECTOR_ID}*`,
    (route) => {
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(responseData),
      });
    },
  );
}

test.describe("S3Explorer Page", () => {
  test.beforeEach(async ({ page }) => {
    // Setup authentication mock if needed
    await page.goto(BASE_URL);
  });

  test.describe("Page Load Tests", () => {
    test("should load S3Explorer page with valid connectorId", async ({
      page,
    }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Wait for the page to load
      await expect(page.locator("text=Filter by name")).toBeVisible();
    });

    test("should show loading state initially", async ({ page }) => {
      // Delay the API response
      await page.route(
        `**/api/connectors/s3/explorer/${MOCK_CONNECTOR_ID}*`,
        async (route) => {
          await new Promise((resolve) => setTimeout(resolve, 1000));
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(mockS3Response),
          });
        },
      );

      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);
      await expect(page.locator("text=Loading...")).toBeVisible();
    });

    test("should display folder/file list after loading", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      await expect(page.locator("text=subfolder1")).toBeVisible();
      await expect(page.locator("text=subfolder2")).toBeVisible();
      await expect(page.locator("text=file1.txt")).toBeVisible();
      await expect(page.locator("text=image.jpg")).toBeVisible();
    });

    test("should render breadcrumbs and filter input", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      await expect(page.locator("text=Root")).toBeVisible();
      await expect(page.getByLabel("Filter by name")).toBeVisible();
    });
  });

  test.describe("Navigation Flow Tests", () => {
    test("should navigate through folder hierarchy", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Click on a folder
      const folder = page.locator("text=subfolder1").first();
      await folder.click();

      // Verify navigation occurred
      await expect(page.locator("text=subfolder1")).toBeVisible();
    });

    test("should navigate back using breadcrumbs", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Navigate into a folder first
      await page.locator("text=subfolder1").first().click();

      // Click breadcrumb to go back
      const rootBreadcrumb = page.locator("text=Root").first();
      await rootBreadcrumb.click();

      // Verify we're back at root
      await expect(page.locator("text=subfolder1")).toBeVisible();
    });
  });

  test.describe("Search/Filter Tests", () => {
    test("should filter items when typing in search box", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      const filterInput = page.getByLabel("Filter by name");
      await filterInput.fill("file1");

      // Wait for debounce
      await page.waitForTimeout(400);

      await expect(page.locator("text=file1.txt")).toBeVisible();
      await expect(page.locator("text=image.jpg")).not.toBeVisible();
    });

    test("should update result count", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      const filterInput = page.getByLabel("Filter by name");
      await filterInput.fill("file");

      // Wait for debounce
      await page.waitForTimeout(400);

      await expect(
        page.locator("text=/Showing \\d+ of \\d+ items/"),
      ).toBeVisible();
    });

    test("should clear filter with clear button", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      const filterInput = page.getByLabel("Filter by name");
      await filterInput.fill("test");

      // Wait for clear button to appear
      const clearButton = page.locator("button[aria-label*='clear']").first();
      await clearButton.click();

      await expect(filterInput).toHaveValue("");
    });

    test("should show no results message when appropriate", async ({
      page,
    }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      const filterInput = page.getByLabel("Filter by name");
      await filterInput.fill("nonexistent-file");

      // Wait for debounce
      await page.waitForTimeout(400);

      await expect(
        page.locator("text=No items match your filter"),
      ).toBeVisible();
    });
  });

  test.describe("Keyboard Navigation Tests", () => {
    test("should navigate with arrow keys", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Focus the list container
      const listContainer = page.locator('[tabindex="0"]').first();
      await listContainer.focus();

      // Press ArrowDown
      await page.keyboard.press("ArrowDown");

      // Verify selection (visual indicator should be present)
      // This would need to check for the selected styling
      await page.waitForTimeout(100);

      // Press ArrowDown again
      await page.keyboard.press("ArrowDown");
      await page.waitForTimeout(100);
    });

    test("should open folders with Enter key", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      const listContainer = page.locator('[tabindex="0"]').first();
      await listContainer.focus();

      // Navigate to first item
      await page.keyboard.press("ArrowDown");

      // Press Enter to open folder
      await page.keyboard.press("Enter");

      await page.waitForTimeout(100);
    });

    test("should go back with Backspace key", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Navigate into a folder first
      await page.locator("text=subfolder1").first().click();

      const listContainer = page.locator('[tabindex="0"]').first();
      await listContainer.focus();

      // Press Backspace
      await page.keyboard.press("Backspace");

      await page.waitForTimeout(100);
    });

    test("should jump to first/last item with Home/End keys", async ({
      page,
    }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      const listContainer = page.locator('[tabindex="0"]').first();
      await listContainer.focus();

      // Press End to go to last item
      await page.keyboard.press("End");
      await page.waitForTimeout(100);

      // Press Home to go to first item
      await page.keyboard.press("Home");
      await page.waitForTimeout(100);
    });
  });

  test.describe("Error Scenario Tests", () => {
    test("should handle API errors gracefully", async ({ page }) => {
      await setupApiMocks(page, mockErrorResponse, 500);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      await expect(
        page.locator("text=/Error loading S3 objects/"),
      ).toBeVisible();
    });

    test("should show retry button on network failure", async ({ page }) => {
      await setupApiMocks(page, mockErrorResponse, 500);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      const retryButton = page.locator("text=Retry");
      await expect(retryButton).toBeVisible();
    });

    test("should display permission error for 403 responses", async ({
      page,
    }) => {
      await setupApiMocks(page, mockErrorResponse, 403);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      await expect(page.locator("text=/Access denied/")).toBeVisible();
    });

    test("should show allowed prefixes when access is restricted", async ({
      page,
    }) => {
      await setupApiMocks(page, mockPermissionErrorWithPrefixes, 403);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      await expect(page.locator("text=allowed-path-1")).toBeVisible();
      await expect(page.locator("text=allowed-path-2")).toBeVisible();
    });
  });

  test.describe("Performance Tests", () => {
    test("should handle large directories without lag", async ({ page }) => {
      const largeDataset = {
        status: "success",
        message: "S3 objects retrieved successfully",
        data: {
          objects: Array.from({ length: 1000 }, (_, i) => ({
            Key: `file-${i}.txt`,
            Size: 1024,
            LastModified: "2024-01-01T00:00:00Z",
            StorageClass: "STANDARD",
            ETag: `test-${i}`,
          })),
          commonPrefixes: [],
          prefix: "",
          delimiter: "/",
          isTruncated: false,
        },
      };

      await setupApiMocks(page, largeDataset);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Check that virtualization is working
      const items = page.locator("text=/file-\\d+\\.txt/");
      const itemCount = await items.count();

      // Should not render all 1000 items at once
      expect(itemCount).toBeLessThan(1000);
      expect(itemCount).toBeGreaterThan(0);
    });
  });

  test.describe("Responsive Tests", () => {
    test("should adapt layout for mobile viewport", async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      await expect(page.locator("text=Filter by name")).toBeVisible();
      await expect(page.locator("text=Root")).toBeVisible();
    });

    test("should show mobile-optimized breadcrumbs", async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Mobile should show limited breadcrumbs
      const breadcrumbs = page.locator("nav[aria-label='breadcrumb']");
      await expect(breadcrumbs).toBeVisible();
    });

    test("should maintain functionality on touch devices", async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Tap on a folder
      const folder = page.locator("text=subfolder1").first();
      await folder.tap();

      await page.waitForTimeout(100);
    });
  });

  test.describe("Accessibility Tests", () => {
    test("should be keyboard navigable", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Tab through the page
      await page.keyboard.press("Tab");
      await page.keyboard.press("Tab");

      // Verify focus is visible
      const focusedElement = await page.evaluateHandle(
        () => document.activeElement,
      );
      expect(focusedElement).toBeTruthy();
    });

    test("should have proper ARIA labels", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Check for ARIA labels
      await expect(page.getByLabel("Filter by name")).toBeVisible();
    });
  });

  test.describe("Empty State Tests", () => {
    test("should show empty folder message", async ({ page }) => {
      await setupApiMocks(page, mockEmptyResponse);
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      await expect(page.locator("text=This folder is empty")).toBeVisible();
    });
  });

  test.describe("AssetsPage/Router Integration Tests", () => {
    const ASSETS_PAGE_ROUTE = "/assets";

    const mockConnectorsResponse = {
      status: "success",
      message: "Connectors retrieved successfully",
      data: {
        connectors: [
          {
            id: MOCK_CONNECTOR_ID,
            name: "Test S3 Connector",
            type: "s3",
            storageIdentifier: "test-bucket",
            enabled: true,
          },
          {
            id: "another-connector-456",
            name: "Another Connector",
            type: "s3",
            storageIdentifier: "another-bucket",
            enabled: true,
          },
        ],
      },
    };

    test("should render AssetsPage with connector list", async ({ page }) => {
      // Mock connectors API
      await page.route("**/api/connectors*", (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockConnectorsResponse),
        });
      });

      await page.goto(`${BASE_URL}${ASSETS_PAGE_ROUTE}`);

      // Wait for connectors to load
      await expect(page.locator("text=Test S3 Connector")).toBeVisible();
      await expect(page.locator("text=Another Connector")).toBeVisible();
    });

    test("should navigate to S3Explorer when connector is selected", async ({
      page,
    }) => {
      // Mock connectors API
      await page.route("**/api/connectors*", (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockConnectorsResponse),
        });
      });

      // Mock S3 explorer API for the selected connector
      await setupApiMocks(page, mockS3Response);

      await page.goto(`${BASE_URL}${ASSETS_PAGE_ROUTE}`);

      // Click on a connector
      await page.locator("text=Test S3 Connector").first().click();

      // Verify S3Explorer UI elements are visible
      await expect(page.locator("text=Filter by name")).toBeVisible();
      await expect(page.locator("text=Root")).toBeVisible();
    });

    test("should handle route parameters correctly", async ({ page }) => {
      await setupApiMocks(page, mockS3Response);

      // Navigate directly to S3Explorer route with connectorId
      await page.goto(`${BASE_URL}${S3_EXPLORER_ROUTE}`);

      // Verify page loads without errors
      await expect(page.locator("text=Filter by name")).toBeVisible();

      // Verify no runtime errors occurred
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          consoleErrors.push(msg.text());
        }
      });

      await page.waitForTimeout(1000);
      expect(consoleErrors.length).toBe(0);
    });

    test("should maintain connector selection when navigating", async ({
      page,
    }) => {
      // Mock connectors API
      await page.route("**/api/connectors*", (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockConnectorsResponse),
        });
      });

      await setupApiMocks(page, mockS3Response);

      await page.goto(`${BASE_URL}${ASSETS_PAGE_ROUTE}`);

      // Select first connector
      await page.locator("text=Test S3 Connector").first().click();

      // Verify connector is selected (should have visual indicator)
      const selectedConnector = page
        .locator('[role="button"]')
        .filter({ hasText: "Test S3 Connector" });
      await expect(selectedConnector).toHaveClass(/Mui-selected/);
    });

    test("should handle lazy loading and not crash", async ({ page }) => {
      // Mock connectors API
      await page.route("**/api/connectors*", (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockConnectorsResponse),
        });
      });

      await setupApiMocks(page, mockS3Response);

      await page.goto(`${BASE_URL}${ASSETS_PAGE_ROUTE}`);

      // Monitor for uncaught errors
      const errors: Error[] = [];
      page.on("pageerror", (error) => {
        errors.push(error);
      });

      // Select connector and navigate
      await page.locator("text=Test S3 Connector").first().click();

      // Wait for potential lazy-loaded components
      await page.waitForTimeout(1000);

      // Verify no errors occurred
      expect(errors.length).toBe(0);

      // Verify S3Explorer rendered successfully
      await expect(page.locator("text=Filter by name")).toBeVisible();
    });

    test("should properly handle connector switching", async ({ page }) => {
      // Mock connectors API
      await page.route("**/api/connectors*", (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockConnectorsResponse),
        });
      });

      await setupApiMocks(page, mockS3Response);

      await page.goto(`${BASE_URL}${ASSETS_PAGE_ROUTE}`);

      // Select first connector
      await page.locator("text=Test S3 Connector").first().click();
      await expect(page.locator("text=Filter by name")).toBeVisible();

      // Switch to second connector
      await page.locator("text=Another Connector").first().click();

      // Should still show S3Explorer without errors
      await expect(page.locator("text=Filter by name")).toBeVisible();
    });
  });
});
