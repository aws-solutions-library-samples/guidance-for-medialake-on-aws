import { test, expect } from "../fixtures/perf-auth.fixtures";
import * as path from "path";
import * as crypto from "crypto";
import * as fs from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Pipeline Import & Deploy E2E Tests
 *
 * Each test imports a pipeline JSON from the pipeline_library, saves it,
 * and polls until the deployment status reaches DEPLOYED (Active).
 *
 * API keys: Pipelines that need API keys (TwelveLabs API, Coactive) read
 * from environment variables. Set them locally in medialake_user_interface/.env
 * or in GitLab CI/CD Variables (masked + protected).
 *
 * Run with:
 *   AWS_PROFILE=ml-uat4 npx playwright test --config=playwright.pipelines.config.ts
 *
 * Run a single pipeline:
 *   AWS_PROFILE=ml-uat4 npx playwright test --config=playwright.pipelines.config.ts --grep "Marengo 3.0 Audio"
 */

// Load .env file if present (for local API keys)
const envPath = path.resolve(__dirname, "../../.env");
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, "utf-8");
  for (const line of envContent.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx > 0) {
      const key = trimmed.slice(0, eqIdx).trim();
      const value = trimmed.slice(eqIdx + 1).trim();
      if (!process.env[key]) process.env[key] = value;
    }
  }
}

const PIPELINE_ROOT = path.resolve(__dirname, "../../../pipeline_library");

interface PipelineConfig {
  /** Relative path from pipeline_library root */
  file: string;
  /** Environment variable name for API key, if required */
  apiKeyEnv?: string;
}

const PIPELINES: PipelineConfig[] = [
  // Bedrock OpenSearch — Marengo 3.0 (no API key)
  {
    file: "Semantic Search/TwelveLabs/Bedrock/OpenSearch/TwelveLabs Bedrock Marengo 3.0 Audio Embedding to OpenSearch.json",
  },
  {
    file: "Semantic Search/TwelveLabs/Bedrock/OpenSearch/TwelveLabs Bedrock Marengo 3.0 Image Embedding to OpenSearch.json",
  },
  {
    file: "Semantic Search/TwelveLabs/Bedrock/OpenSearch/TwelveLabs Bedrock Marengo 3.0 Video Embedding to OpenSearch.json",
  },
  // Bedrock OpenSearch — Marengo 2.7 (no API key)
  {
    file: "Semantic Search/TwelveLabs/Bedrock/OpenSearch/TwelveLabs Bedrock Marengo 2.7 Audio Embedding to OpenSearch.json",
  },
  {
    file: "Semantic Search/TwelveLabs/Bedrock/OpenSearch/TwelveLabs Bedrock Marengo 2.7 Image Embedding to OpenSearch.json",
  },
  {
    file: "Semantic Search/TwelveLabs/Bedrock/OpenSearch/TwelveLabs Bedrock Marengo 2.7 Video Embedding to OpenSearch.json",
  },
  // Bedrock S3 Vectors — Marengo 2.7 (no API key)
  {
    file: "Semantic Search/TwelveLabs/Bedrock/S3 Vectors/TwelveLabs Bedrock Marengo 2.7 Audio Embedding to S3 Vectors.json",
  },
  {
    file: "Semantic Search/TwelveLabs/Bedrock/S3 Vectors/TwelveLabs Bedrock Marengo 2.7 Image Embedding to S3 Vectors.json",
  },
  {
    file: "Semantic Search/TwelveLabs/Bedrock/S3 Vectors/TwelveLabs Bedrock Marengo 2.7 Video Embedding to S3 Vectors.json",
  },
  // API OpenSearch (requires TWELVELABS_API_KEY)
  {
    file: "Semantic Search/TwelveLabs/API/OpenSearch/TwelveLabs API Marengo 2.7 Audio Embedding to OpenSearch Vectors.json",
    apiKeyEnv: "TWELVELABS_API_KEY",
  },
  {
    file: "Semantic Search/TwelveLabs/API/OpenSearch/TwelveLabs API Marengo 2.7 Image Embedding to OpenSearch Vectors.json",
    apiKeyEnv: "TWELVELABS_API_KEY",
  },
  {
    file: "Semantic Search/TwelveLabs/API/OpenSearch/TwelveLabs API Marengo 2.7 Video Embedding to OpenSearch Vectors.json",
    apiKeyEnv: "TWELVELABS_API_KEY",
  },
  // API S3 Vectors (requires TWELVELABS_API_KEY)
  {
    file: "Semantic Search/TwelveLabs/API/S3 Vectors/TwelveLabs API Audio Embedding to S3 Vectors.json",
    apiKeyEnv: "TWELVELABS_API_KEY",
  },
  {
    file: "Semantic Search/TwelveLabs/API/S3 Vectors/TwelveLabs API Image Embedding to S3 Vectors.json",
    apiKeyEnv: "TWELVELABS_API_KEY",
  },
  {
    file: "Semantic Search/TwelveLabs/API/S3 Vectors/TwelveLabs API Video Embedding to S3 Vectors.json",
    apiKeyEnv: "TWELVELABS_API_KEY",
  },
  // Coactive (requires COACTIVE_API_KEY)
  {
    file: "Semantic Search/Coactive/Coactive API Image Ingestion Pipeline.json",
    apiKeyEnv: "COACTIVE_API_KEY",
  },
  {
    file: "Semantic Search/Coactive/Coactive API Video Ingestion Pipeline.json",
    apiKeyEnv: "COACTIVE_API_KEY",
  },
  // Default Pipelines (no API key)
  { file: "Default Pipelines/Default Audio Pipeline.json" },
  { file: "Default Pipelines/Default Image Pipeline.json" },
  { file: "Default Pipelines/Default Video Pipeline.json" },
  // Enrichment (no API key)
  { file: "Enrichment/External Metadata Enrichment.json" },
  { file: "Enrichment/TwelveLabs Pegasus Bedrock Video Enrichment.json" },
  { file: "Enrichment/TwelveLabs Pegasus Bedrock Video Enrichment with Splitter.json" },
  // Transcription (no API key)
  { file: "Transcription/Audio Transcription.json" },
  { file: "Transcription/Video Transcription.json" },
];

const MAX_DEPLOY_WAIT = 600000; // 10 minutes
const POLL_INTERVAL = 5000;

function pipelineDisplayName(relativePath: string): string {
  return path.basename(relativePath, ".json");
}

test.describe("Pipeline Import & Deploy", () => {
  for (const pipeline of PIPELINES) {
    const displayName = pipelineDisplayName(pipeline.file);
    const fullPath = path.join(PIPELINE_ROOT, pipeline.file);

    test(`${displayName}`, async ({ authenticatedPage }) => {
      // Skip if API key is required but not set
      if (pipeline.apiKeyEnv && !process.env[pipeline.apiKeyEnv]) {
        console.log(`[pipeline] Skipping "${displayName}" — ${pipeline.apiKeyEnv} not set`);
        test.skip(true, `${pipeline.apiKeyEnv} not set. Add it to .env or CI variables.`);
        return;
      }

      const page = authenticatedPage;
      const uid = crypto.randomBytes(4).toString("hex");

      // 1. Navigate to Settings > Pipelines
      console.log(`[pipeline] Navigating to Pipelines...`);
      await page.getByRole("button", { name: "Settings" }).click();
      await page.getByRole("button", { name: "Pipelines" }).click();
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      // Wait for table to load
      await page
        .locator("table tbody tr")
        .first()
        .waitFor({ state: "visible", timeout: 15000 })
        .catch(() => {});

      // 2. Open import menu
      console.log(`[pipeline] Opening import menu...`);
      const dropdownArrow = page.getByRole("button", { name: "select pipeline action" });
      await dropdownArrow.waitFor({ state: "visible", timeout: 10000 });
      await dropdownArrow.click();

      const importMenuItem = page.getByRole("menuitem", { name: /Import/i });
      await importMenuItem.waitFor({ state: "visible", timeout: 5000 });

      // 3. Upload the file
      const fileChooserPromise = page.waitForEvent("filechooser");
      await importMenuItem.click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles(fullPath);
      console.log(`[pipeline] Uploaded: ${displayName}`);

      // 4. Wait for editor
      await page.waitForURL("**/settings/pipelines/new", { timeout: 15000 });
      await page
        .locator("text=Importing Pipeline...")
        .waitFor({ state: "hidden", timeout: 30000 })
        .catch(() => {});

      // 5. Append UID to the default pipeline name
      const nameInput = page.getByPlaceholder(/pipeline name/i);
      await expect(nameInput).toBeVisible({ timeout: 10000 });
      const currentValue = await nameInput.inputValue();
      const actualName = `${currentValue} ${uid}`;
      await nameInput.fill(actualName);
      console.log(`[pipeline] Name: ${actualName}`);

      // 6. Wait for nodes
      await page.locator(".react-flow__node").first().waitFor({ state: "visible", timeout: 15000 });
      const nodeCount = await page.locator(".react-flow__node").count();
      console.log(`[pipeline] ${nodeCount} node(s) rendered`);
      expect(nodeCount).toBeGreaterThan(0);

      // 7. Save
      //    In production builds MUI strips data-testid from icons, so we
      //    cannot rely on [data-testid="SaveIcon"]. Use a locator that
      //    works in both compact mode (IconButton inside "Save" tooltip)
      //    and full mode (Button with "Save" text).
      console.log(`[pipeline] Saving...`);
      const saveButton = page
        .locator(
          // Full mode: <Button> with "Save" text
          // Compact mode: <IconButton> inside a tooltip span labelled "Save"
          'button:has-text("Save"), [aria-label*="Save" i] button, [data-testid="SaveIcon"]'
        )
        .first();
      await saveButton.waitFor({ state: "visible", timeout: 10000 });
      await saveButton.click();

      // 8. Wait for save — either success message or redirect to pipelines list
      console.log(`[pipeline] Waiting for save confirmation...`);
      await Promise.race([
        expect(page.locator("text=/Pipeline created|success|started/i").first()).toBeVisible({
          timeout: 30000,
        }),
        page.waitForURL("**/pipelines", { timeout: 30000 }),
      ]).catch(() => {
        console.log("[pipeline] No explicit success message, continuing...");
      });

      // 9. Poll the pipelines list until the pipeline appears AND deploys
      //    The backend is eventually consistent — newly created pipelines may take
      //    minutes to appear in the list API. We combine list verification and
      //    deployment polling into a single loop.
      console.log(`[pipeline] Waiting for "${actualName}" to appear and deploy...`);
      const pipelineRow = page.locator("table tbody tr", { hasText: uid });
      const deployStart = Date.now();
      let deployed = false;
      let appearedInList = false;

      while (Date.now() - deployStart < MAX_DEPLOY_WAIT) {
        await page.goto("/pipelines", { waitUntil: "domcontentloaded" });
        await page
          .locator("table tbody tr")
          .first()
          .waitFor({ state: "visible", timeout: 10000 })
          .catch(() => {});
        await page.waitForTimeout(2000);

        // Check if our pipeline row exists at all
        const rowVisible = await pipelineRow
          .first()
          .isVisible()
          .catch(() => false);
        if (!rowVisible) {
          const elapsed = Math.round((Date.now() - deployStart) / 1000);
          console.log(`[pipeline] Not in list yet (${elapsed}s)`);
          await page.waitForTimeout(POLL_INTERVAL);
          continue;
        }

        if (!appearedInList) {
          appearedInList = true;
          const elapsed = Math.round((Date.now() - deployStart) / 1000);
          console.log(`[pipeline] Appeared in list at ${elapsed}s`);
        }

        // Check if deployed (toggle switch visible in the row)
        const hasToggle = await pipelineRow
          .locator('input[type="checkbox"], [role="switch"]')
          .first()
          .isVisible()
          .catch(() => false);

        if (hasToggle) {
          deployed = true;
          break;
        }

        // Check for FAILED status
        const rowText = await pipelineRow.textContent().catch(() => "");
        if (rowText?.includes("FAILED")) {
          console.error(`[pipeline] Deployment FAILED`);
          break;
        }

        const elapsed = Math.round((Date.now() - deployStart) / 1000);
        const status =
          rowText?.match(/CREATING|PENDING|DEPLOYING|UPDATING|PROCESSING[^\n]*/)?.[0] || "unknown";
        console.log(`[pipeline] Status: ${status} (${elapsed}s)`);

        await page.waitForTimeout(POLL_INTERVAL);
      }

      const deployTime = Math.round((Date.now() - deployStart) / 1000);
      if (deployed) {
        console.log(`[pipeline] Deployed in ${deployTime}s`);
      } else if (!appearedInList) {
        console.error(`[pipeline] Never appeared in list within ${MAX_DEPLOY_WAIT / 1000}s`);
      } else {
        console.error(`[pipeline] Did not deploy within ${MAX_DEPLOY_WAIT / 1000}s`);
      }
      expect(deployed).toBe(true);

      console.log(`[pipeline] ✓ ${displayName} — imported, saved, deployed`);
    });
  }
});
