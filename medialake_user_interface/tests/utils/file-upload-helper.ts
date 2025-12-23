/**
 * File Upload Helper for Playwright Tests
 *
 * Provides reusable utilities for uploading files in E2E tests,
 * including test file creation, upload UI interaction, and cleanup.
 */

import { Page, Locator } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

export interface UploadOptions {
  /** Timeout for finding upload controls in ms (default: 5000) */
  timeout?: number;
  /** Wait time after upload in ms to allow processing (default: 3000) */
  waitAfterUpload?: number;
  /** Take screenshots during upload process (default: false) */
  captureScreenshots?: boolean;
  /** Screenshot directory path (default: "test-results") */
  screenshotDir?: string;
}

export interface UploadResult {
  /** Whether upload was successful */
  success: boolean;
  /** Upload method used */
  method: "file-input" | "file-chooser" | "not-found";
  /** Uploaded file paths */
  uploadedFiles: string[];
  /** Error message if upload failed */
  error?: string;
}

export interface TestFileOptions {
  /** Number of files to create (default: 3) */
  count?: number;
  /** Base file name prefix (default: "test-file") */
  prefix?: string;
  /** File extension (default: "txt") */
  extension?: string;
  /** Base file size in bytes (default: 100) */
  baseSize?: number;
  /** File content template function */
  contentGenerator?: (index: number) => string;
}

/**
 * Test ID for the upload button icon
 */
const UPLOAD_BUTTON_TEST_ID = "CloudUploadIcon";

/**
 * Upload progress indicator selectors
 */
const UPLOAD_PROGRESS_SELECTORS = [
  '[role="progressbar"]',
  '[data-testid*="upload"]',
  '[data-testid*="progress"]',
  ':has-text("Uploading")',
  ':has-text("Upload complete")',
  ':has-text("Upload successful")',
];

/**
 * Create test files for upload testing
 */
export function createTestFiles(testDir: string, options: TestFileOptions = {}): string[] {
  const {
    count = 3,
    prefix = "test-file",
    extension = "txt",
    baseSize = 100,
    contentGenerator,
  } = options;

  if (!fs.existsSync(testDir)) {
    fs.mkdirSync(testDir, { recursive: true });
  }

  const files: string[] = [];
  const timestamp = Date.now();

  for (let i = 1; i <= count; i++) {
    const fileName = `${prefix}-${i}-${timestamp}.${extension}`;
    const filePath = path.join(testDir, fileName);

    const content = contentGenerator
      ? contentGenerator(i)
      : `This is test file ${i} for upload testing.\nCreated at: ${new Date().toISOString()}\nFile size: ${
          i * baseSize
        } bytes\nTimestamp: ${timestamp}`;

    const paddedContent = content.padEnd(i * baseSize, " ");
    fs.writeFileSync(filePath, paddedContent);
    files.push(filePath);
  }

  console.log(`[FileUploadHelper] Created ${count} test files in ${testDir}`);
  return files;
}

/**
 * Cleanup test files after testing
 */
export function cleanupTestFiles(files: string[], removeDir: boolean = true): void {
  const directories = new Set<string>();

  files.forEach((file) => {
    if (fs.existsSync(file)) {
      const dir = path.dirname(file);
      directories.add(dir);
      fs.unlinkSync(file);
    }
  });

  console.log(`[FileUploadHelper] Cleaned up ${files.length} test files`);

  if (removeDir) {
    directories.forEach((dir) => {
      if (fs.existsSync(dir) && fs.readdirSync(dir).length === 0) {
        fs.rmdirSync(dir);
        console.log(`[FileUploadHelper] Removed empty directory: ${dir}`);
      }
    });
  }
}

/**
 * Find upload button and trigger file chooser
 */
async function findUploadButton(page: Page): Promise<Locator | null> {
  // Look for the upload button by test ID (CloudUploadIcon)
  const uploadButton = page.getByTestId(UPLOAD_BUTTON_TEST_ID);
  const buttonExists = (await uploadButton.count()) > 0;

  if (!buttonExists) {
    console.warn(
      `[FileUploadHelper] Upload button not found (data-testid="${UPLOAD_BUTTON_TEST_ID}")`
    );
    return null;
  }

  console.log(`[FileUploadHelper] Found upload button`);
  return uploadButton;
}

/**
 * Find file input element - either visible or hidden
 */
async function findFileInput(page: Page): Promise<Locator | null> {
  // Look for any file input on the page
  const fileInput = page.locator('input[type="file"]').first();
  const inputExists = (await fileInput.count()) > 0;

  if (inputExists) {
    console.log("[FileUploadHelper] Found file input element");

    // Make the file input visible if it's hidden (common for styled file inputs)
    await fileInput.evaluate((el: HTMLInputElement) => {
      el.style.display = "block";
      el.style.visibility = "visible";
      el.style.opacity = "1";
      el.style.position = "relative";
    });

    return fileInput;
  }

  console.warn("[FileUploadHelper] File input not found");
  return null;
}

/**
 * Check for upload progress indicators
 */
async function checkUploadProgress(page: Page): Promise<number> {
  let foundCount = 0;

  for (const selector of UPLOAD_PROGRESS_SELECTORS) {
    const indicator = page.locator(selector);
    const count = await indicator.count();

    if (count > 0) {
      foundCount += count;
      console.log(`[FileUploadHelper] Found upload indicator: ${selector} (${count} elements)`);
    }
  }

  return foundCount;
}

/**
 * Upload files through the UI
 */
export async function uploadFiles(
  page: Page,
  filePaths: string[],
  options: UploadOptions = {}
): Promise<UploadResult> {
  const {
    timeout = 5000,
    waitAfterUpload = 3000,
    captureScreenshots = false,
    screenshotDir = "test-results",
  } = options;

  console.log(`[FileUploadHelper] Attempting to upload ${filePaths.length} files`);

  if (captureScreenshots && !fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  if (captureScreenshots) {
    await page.screenshot({
      path: path.join(screenshotDir, "before-upload.png"),
      fullPage: true,
    });
  }

  // First, check if upload button exists
  const uploadButton = await findUploadButton(page);

  if (!uploadButton) {
    console.warn(
      `[FileUploadHelper] ⚠️  Upload button not found (expected data-testid="${UPLOAD_BUTTON_TEST_ID}")`
    );

    if (captureScreenshots) {
      await page.screenshot({
        path: path.join(screenshotDir, "upload-button-not-found.png"),
        fullPage: true,
      });
    }

    return {
      success: false,
      method: "not-found",
      uploadedFiles: [],
      error: `Upload button not found. Expected element with data-testid="${UPLOAD_BUTTON_TEST_ID}".`,
    };
  }

  // Try to upload files using file chooser (for when button opens a file dialog)
  try {
    console.log("[FileUploadHelper] Setting up file chooser listener");

    // Set up file chooser promise before clicking
    const fileChooserPromise = page.waitForEvent("filechooser", {
      timeout: 5000,
    });

    // Click the upload button to trigger file chooser
    await uploadButton.click();
    console.log("[FileUploadHelper] Clicked upload button");

    // Wait for and handle file chooser
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(filePaths);
    console.log("[FileUploadHelper] Files set via file chooser");

    await page.waitForTimeout(waitAfterUpload);
    await checkUploadProgress(page);

    if (captureScreenshots) {
      await page.screenshot({
        path: path.join(screenshotDir, "after-upload.png"),
        fullPage: true,
      });
    }

    return {
      success: true,
      method: "file-chooser",
      uploadedFiles: filePaths,
    };
  } catch (error: any) {
    console.log("[FileUploadHelper] File chooser method failed, trying direct file input");

    // Fallback: Try to find and use file input directly
    const fileInput = await findFileInput(page);

    if (!fileInput) {
      if (captureScreenshots) {
        await page.screenshot({
          path: path.join(screenshotDir, "upload-error.png"),
          fullPage: true,
        });
      }

      return {
        success: false,
        method: "not-found",
        uploadedFiles: [],
        error: `Upload failed: ${error.message}. No file input found as fallback.`,
      };
    }

    try {
      await fileInput.setInputFiles(filePaths);
      console.log("[FileUploadHelper] Files set on file input (fallback method)");

      await page.waitForTimeout(waitAfterUpload);
      await checkUploadProgress(page);

      if (captureScreenshots) {
        await page.screenshot({
          path: path.join(screenshotDir, "after-upload.png"),
          fullPage: true,
        });
      }

      return {
        success: true,
        method: "file-input",
        uploadedFiles: filePaths,
      };
    } catch (fallbackError: any) {
      console.error("[FileUploadHelper] File input upload failed:", fallbackError.message);

      if (captureScreenshots) {
        await page.screenshot({
          path: path.join(screenshotDir, "upload-error.png"),
          fullPage: true,
        });
      }

      return {
        success: false,
        method: "file-input",
        uploadedFiles: [],
        error: fallbackError.message,
      };
    }
  }
}

/**
 * Create test files and upload them in one operation
 */
export async function createAndUploadFiles(
  page: Page,
  testDir: string,
  fileOptions: TestFileOptions = {},
  uploadOptions: UploadOptions = {}
): Promise<UploadResult & { testFiles: string[] }> {
  const testFiles = createTestFiles(testDir, fileOptions);
  const result = await uploadFiles(page, testFiles, uploadOptions);

  return {
    ...result,
    testFiles,
  };
}

/**
 * Upload files with automatic cleanup
 */
export async function uploadFilesWithCleanup(
  page: Page,
  testDir: string,
  fileOptions: TestFileOptions = {},
  uploadOptions: UploadOptions = {}
): Promise<UploadResult> {
  const testFiles = createTestFiles(testDir, fileOptions);

  try {
    const result = await uploadFiles(page, testFiles, uploadOptions);
    return result;
  } finally {
    cleanupTestFiles(testFiles);
  }
}

/**
 * Wait for upload to complete by checking progress indicators
 */
export async function waitForUploadComplete(
  page: Page,
  maxWaitMs: number = 30000
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < maxWaitMs) {
    const progressCount = await checkUploadProgress(page);

    if (progressCount > 0) {
      console.log("[FileUploadHelper] Upload in progress...");
      await page.waitForTimeout(1000);
      continue;
    }

    await page.waitForTimeout(500);
    const recheckCount = await checkUploadProgress(page);

    if (recheckCount === 0) {
      console.log("[FileUploadHelper] Upload appears complete");
      return true;
    }
  }

  console.warn("[FileUploadHelper] Upload timeout reached");
  return false;
}

/**
 * Upload files through the modal UI (with connector selection)
 * This handles the full modal workflow:
 * 1. Click upload button to open modal
 * 2. Select connector from dropdown
 * 3. Add files
 * 4. Click "Upload X files" button
 */
export async function uploadFilesViaModal(
  page: Page,
  filePaths: string[],
  connectorName?: string,
  options: UploadOptions = {}
): Promise<UploadResult> {
  const {
    timeout = 5000,
    waitAfterUpload = 3000,
    captureScreenshots = false,
    screenshotDir = "test-results",
  } = options;

  console.log(`[FileUploadHelper] Uploading ${filePaths.length} files via modal`);

  if (captureScreenshots && !fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  try {
    // Step 1: Find and click upload button to open modal
    const uploadButton = await findUploadButton(page);
    if (!uploadButton) {
      return {
        success: false,
        method: "not-found",
        uploadedFiles: [],
        error: "Upload button not found",
      };
    }

    await uploadButton.click();
    console.log("[FileUploadHelper] Clicked upload button, modal should open");
    await page.waitForTimeout(1000);

    if (captureScreenshots) {
      await page.screenshot({
        path: path.join(screenshotDir, "upload-modal-opened.png"),
        fullPage: true,
      });
    }

    // Step 2: Select connector from dropdown
    console.log("[FileUploadHelper] Selecting connector from dropdown");

    // Find the combobox (the actual dropdown element)
    const connectorCombobox = page.getByRole("combobox", {
      name: "S3 Connector",
    });
    await connectorCombobox.waitFor({ state: "visible", timeout: 5000 });
    await connectorCombobox.click();
    await page.waitForTimeout(1500);

    if (connectorName) {
      console.log(`[FileUploadHelper] Looking for connector: ${connectorName}`);
      // Select the specific connector by name
      const targetOption = page.getByRole("option", {
        name: new RegExp(connectorName, "i"),
      });
      await targetOption.click();
      console.log(`[FileUploadHelper] Selected connector: ${connectorName}`);
    } else {
      // Select the first ENABLED connector (skip the disabled placeholder)
      console.log("[FileUploadHelper] Selecting first available enabled connector");

      // Get all options and filter for enabled ones
      const allOptions = page.getByRole("option");
      const optionCount = await allOptions.count();

      let selectedConnector = false;
      for (let i = 0; i < optionCount; i++) {
        const option = allOptions.nth(i);
        const isDisabled = await option.getAttribute("aria-disabled");

        if (isDisabled !== "true") {
          // This is an enabled option, click it
          const optionText = await option.textContent();
          console.log(`[FileUploadHelper] Clicking enabled connector: ${optionText}`);
          await option.click();
          selectedConnector = true;
          break;
        }
      }

      if (!selectedConnector) {
        throw new Error("No enabled connectors found in dropdown");
      }
    }

    await page.waitForTimeout(1500);

    if (captureScreenshots) {
      await page.screenshot({
        path: path.join(screenshotDir, "connector-selected.png"),
        fullPage: true,
      });
    }
    // Step 3: Add files directly to Uppy's file input (more reliable than file chooser)
    console.log("[FileUploadHelper] Adding files directly to Uppy input");

    // Wait a bit for the connector selection to fully process
    await page.waitForTimeout(1500);

    // Find the Uppy file input (the one WITHOUT webkitdirectory attribute)
    const uppyFileInput = page.locator('.uppy-Dashboard-input[type="file"][multiple]').first();
    await uppyFileInput.waitFor({ state: "attached", timeout: 5000 });

    console.log(`[FileUploadHelper] Setting ${filePaths.length} files on Uppy input`);
    console.log(`[FileUploadHelper] Files to upload:`);
    filePaths.forEach((fp, idx) => {
      console.log(`  ${idx + 1}. ${path.basename(fp)}`);
    });

    // Set the files directly on the input element
    await uppyFileInput.setInputFiles(filePaths);
    console.log(`[FileUploadHelper] Files set on Uppy input element`);

    // Wait longer for Uppy to process and validate files
    console.log(
      "[FileUploadHelper] Waiting for Uppy to process files (file type validation, etc.)"
    );
    await page.waitForTimeout(4000);

    // Check if any files were actually added to Uppy's dashboard
    const fileItems = page.locator(".uppy-Dashboard-Item");
    const fileItemCount = await fileItems.count();
    console.log(`[FileUploadHelper] Files visible in Uppy dashboard: ${fileItemCount}`);

    if (fileItemCount === 0) {
      console.warn("[FileUploadHelper] ⚠️  No files visible in Uppy dashboard!");
      console.warn(
        "[FileUploadHelper] This usually means files were rejected due to invalid MIME types"
      );
      console.warn(
        "[FileUploadHelper] Uppy only accepts: audio/*, video/*, image/*, HLS, MPEG-DASH"
      );

      // Take a screenshot showing the empty state
      if (captureScreenshots) {
        await page.screenshot({
          path: path.join(screenshotDir, "no-files-in-uppy.png"),
          fullPage: true,
        });
      }

      throw new Error(
        `Files were rejected by Uppy. Ensure files are valid media types (audio/video/image/HLS/MPEG-DASH). ` +
          `Files attempted: ${filePaths.map((f) => path.basename(f)).join(", ")}`
      );
    }

    console.log(`[FileUploadHelper] ✓ Successfully added ${fileItemCount} file(s) to Uppy`);
    await page.waitForTimeout(2000);

    if (captureScreenshots) {
      await page.screenshot({
        path: path.join(screenshotDir, "files-added.png"),
        fullPage: true,
      });
    }

    // Step 4: Find and scroll to the upload button
    console.log("[FileUploadHelper] Looking for upload button");

    // Find the upload button using the specific Uppy class
    const uploadSubmitButton = page.locator(".uppy-StatusBar-actionBtn--upload").first();

    // Wait for the button to be visible (with a reasonable timeout)
    await uploadSubmitButton.waitFor({ state: "visible", timeout: 15000 });
    console.log("[FileUploadHelper] Upload button found and visible");

    // Ensure it's in view - use a simpler approach
    try {
      await uploadSubmitButton.scrollIntoViewIfNeeded({ timeout: 5000 });
      console.log("[FileUploadHelper] Button scrolled into view");
    } catch (scrollError) {
      console.log("[FileUploadHelper] Button already in view or scroll not needed");
    }

    await page.waitForTimeout(500);

    // Click the button - use force to bypass actionability checks if needed
    console.log("[FileUploadHelper] Clicking upload button to submit");
    try {
      await uploadSubmitButton.click({ timeout: 10000 });
    } catch (clickError) {
      console.log("[FileUploadHelper] Normal click failed, trying force click");
      await uploadSubmitButton.click({ force: true, timeout: 5000 });
    }
    console.log("[FileUploadHelper] Upload submitted, waiting for completion");

    // Wait for upload to complete - monitor the "Uploading" text
    const maxUploadWaitTime = 180000; // 3 minutes max
    const startTime = Date.now();
    let uploadComplete = false;
    let lastProgress = "";

    console.log(`[FileUploadHelper] Monitoring upload progress (max ${maxUploadWaitTime / 1000}s)`);

    while (Date.now() - startTime < maxUploadWaitTime && !uploadComplete) {
      // Check if "Uploading" text is still present
      const uploadingIndicator = page.locator("text=/Uploading/i").first();
      const uploadingCount = await uploadingIndicator.count();

      if (uploadingCount === 0) {
        console.log("[FileUploadHelper] ✓ Upload complete - 'Uploading' indicator disappeared");
        uploadComplete = true;
        break;
      }

      // Log progress if it changed
      try {
        const progressText = await uploadingIndicator.textContent();
        if (progressText && progressText !== lastProgress) {
          console.log(`[FileUploadHelper] Progress: ${progressText.trim()}`);
          lastProgress = progressText;
        }
      } catch (e) {
        // Ignore text extraction errors
      }

      // Wait before checking again
      await page.waitForTimeout(2000);
    }

    if (!uploadComplete) {
      console.warn(
        `[FileUploadHelper] ⚠️  Upload still showing 'Uploading' after ${
          maxUploadWaitTime / 1000
        }s - may still be processing`
      );
    }

    // Extra wait to ensure backend processing and modal update
    console.log("[FileUploadHelper] Waiting for backend processing to complete");
    await page.waitForTimeout(Math.max(waitAfterUpload, 5000));

    if (captureScreenshots) {
      await page.screenshot({
        path: path.join(screenshotDir, "after-upload-submit.png"),
        fullPage: true,
      });
    }

    return {
      success: true,
      method: "file-input",
      uploadedFiles: filePaths,
    };
  } catch (error: any) {
    console.error("[FileUploadHelper] Modal upload failed:", error.message);

    if (captureScreenshots) {
      try {
        // Check if page is still open before taking screenshot
        if (!page.isClosed()) {
          await page.screenshot({
            path: path.join(screenshotDir, "upload-modal-error.png"),
            fullPage: true,
          });
        }
      } catch (screenshotError) {
        console.warn("[FileUploadHelper] Could not capture error screenshot");
      }
    }

    return {
      success: false,
      method: "not-found",
      uploadedFiles: [],
      error: error.message,
    };
  }
}

/**
 * Create test files and upload them via modal in one operation
 */
export async function createAndUploadFilesViaModal(
  page: Page,
  testDir: string,
  fileOptions: TestFileOptions = {},
  connectorName?: string,
  uploadOptions: UploadOptions = {}
): Promise<UploadResult & { testFiles: string[] }> {
  const testFiles = createTestFiles(testDir, fileOptions);
  const result = await uploadFilesViaModal(page, testFiles, connectorName, uploadOptions);

  return {
    ...result,
    testFiles,
  };
}

/**
 * Upload all files from an existing directory via modal
 *
 * @param page - Playwright page object
 * @param sourceDir - Path to directory containing files to upload
 * @param connectorName - Optional connector name (auto-selects first if not provided)
 * @param uploadOptions - Upload options
 * @returns Upload result with list of uploaded files
 */
export async function uploadFilesFromDirectory(
  page: Page,
  sourceDir: string,
  connectorName?: string,
  uploadOptions: UploadOptions = {}
): Promise<UploadResult> {
  console.log(`[FileUploadHelper] Scanning directory: ${sourceDir}`);

  if (!fs.existsSync(sourceDir)) {
    return {
      success: false,
      method: "not-found",
      uploadedFiles: [],
      error: `Directory not found: ${sourceDir}`,
    };
  }

  // Read all files from the directory (not subdirectories)
  const entries = fs.readdirSync(sourceDir, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile())
    .map((entry) => path.join(sourceDir, entry.name));

  if (files.length === 0) {
    return {
      success: false,
      method: "not-found",
      uploadedFiles: [],
      error: `No files found in directory: ${sourceDir}`,
    };
  }

  console.log(`[FileUploadHelper] Found ${files.length} files to upload`);
  files.forEach((file) => {
    console.log(`  - ${path.basename(file)}`);
  });

  // Upload the files using the modal
  return await uploadFilesViaModal(page, files, connectorName, uploadOptions);
}
