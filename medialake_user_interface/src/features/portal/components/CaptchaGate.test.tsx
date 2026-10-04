import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen, act, waitFor } from "@testing-library/react";
import CaptchaGate from "./CaptchaGate";
import { StorageHelper } from "@/common/helpers/storage-helper";
import { resetWafCaptchaSdkForTests } from "../api/wafCaptchaSdk";

// ---------------------------------------------------------------------------
// The SDK URL and API key come from aws-exports.json (Portal.captchaSdkUrl /
// Portal.captchaApiKey). VITE_WAF_CAPTCHA_API_KEY (set in vitest.config.ts)
// is the API-key fallback.
// ---------------------------------------------------------------------------

const TEST_API_KEY = "test-captcha-api-key";
const SDK_URL = "https://abc123.edge.captcha-sdk.awswaf.com/abc123/jsapi.js";
const LOAD_FAILED =
  "The CAPTCHA verification could not be loaded. Please check your network connection and try again.";
const CONFIG_MISSING = "CAPTCHA configuration is missing. Please contact the portal administrator.";

// ---------------------------------------------------------------------------
// Mock AwsWafCaptcha global
// ---------------------------------------------------------------------------

let capturedOnSuccess: (() => void) | undefined;
let capturedOnError: ((err: Error) => void) | undefined;

const mockRenderCaptcha = vi.fn(
  (_container: HTMLElement, options: { onSuccess: () => void; onError?: (err: Error) => void }) => {
    capturedOnSuccess = options.onSuccess;
    capturedOnError = options.onError;
  }
);

function installCaptchaGlobal() {
  (globalThis as Record<string, unknown>).AwsWafCaptcha = {
    renderCaptcha: mockRenderCaptcha,
  };
}

function removeCaptchaGlobal() {
  delete (globalThis as Record<string, unknown>).AwsWafCaptcha;
}

function sdkScripts(): HTMLScriptElement[] {
  return Array.from(document.querySelectorAll<HTMLScriptElement>('script[src*="awswaf.com"]'));
}

function setPortalConfig(portal: Record<string, string>) {
  StorageHelper.setAwsConfig({ region: "us-east-1", Portal: portal });
}

function renderGate(captchaEnabled = true, onComplete = vi.fn()) {
  render(
    <CaptchaGate captchaEnabled={captchaEnabled} onCaptchaComplete={onComplete}>
      <div data-testid="upload-ui">Upload Interface</div>
    </CaptchaGate>
  );
  return onComplete;
}

beforeEach(() => {
  capturedOnSuccess = undefined;
  capturedOnError = undefined;
  mockRenderCaptcha.mockClear();
  resetWafCaptchaSdkForTests();
  installCaptchaGlobal();
  // Default: the SDK URL is configured, the API key comes from the env fallback.
  setPortalConfig({ captchaSdkUrl: SDK_URL });
  // aws-exports.json re-fetch (only used when the cached config lacks a value)
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  );
});

afterEach(() => {
  removeCaptchaGlobal();
  resetWafCaptchaSdkForTests();
  StorageHelper.clearAwsConfig();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CaptchaGate", () => {
  /**
   * Validates: Requirement 5.1
   * WHEN captchaEnabled is false, children render immediately.
   */
  it("renders children immediately when captchaEnabled is false", () => {
    removeCaptchaGlobal();
    renderGate(false);

    // Children should be visible
    expect(screen.getByTestId("upload-ui")).toBeInTheDocument();
    expect(screen.getByText("Upload Interface")).toBeInTheDocument();

    // CAPTCHA widget should NOT be rendered
    expect(screen.queryByText("Please complete the verification below")).not.toBeInTheDocument();

    // renderCaptcha should not have been called, and the SDK is never loaded
    expect(mockRenderCaptcha).not.toHaveBeenCalled();
    expect(sdkScripts()).toHaveLength(0);
  });

  /**
   * Validates: Requirement 5.2
   * WHEN captchaEnabled is true, the CAPTCHA container is rendered (not children).
   */
  it("renders CAPTCHA container when captchaEnabled is true", async () => {
    renderGate();

    // CAPTCHA prompt should be visible
    expect(screen.getByText("Please complete the verification below")).toBeInTheDocument();

    // Children should NOT be visible yet
    expect(screen.queryByTestId("upload-ui")).not.toBeInTheDocument();

    // renderCaptcha should have been called
    await waitFor(() => {
      expect(mockRenderCaptcha).toHaveBeenCalledTimes(1);
    });

    expect(mockRenderCaptcha).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        apiKey: TEST_API_KEY,
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
        dynamicWidth: true,
        skipTitle: true,
      })
    );
  });

  it("uses the API key from aws-exports.json over the build-time fallback", async () => {
    setPortalConfig({ captchaSdkUrl: SDK_URL, captchaApiKey: "deployment-key" });
    renderGate();

    await waitFor(() => expect(mockRenderCaptcha).toHaveBeenCalledTimes(1));
    expect(mockRenderCaptcha.mock.calls[0][1]).toMatchObject({ apiKey: "deployment-key" });
  });

  /**
   * Validates: Requirement 5.3
   * WHEN a visitor successfully solves the CAPTCHA, onCaptchaComplete is called
   * and children are rendered.
   */
  it("calls onCaptchaComplete and renders children after successful solve", async () => {
    const onComplete = renderGate();

    // Wait for the CAPTCHA to render and capture callbacks
    await waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    // Before solve: children hidden, CAPTCHA shown
    expect(screen.queryByTestId("upload-ui")).not.toBeInTheDocument();
    expect(screen.getByText("Please complete the verification below")).toBeInTheDocument();

    // Simulate successful CAPTCHA solve
    act(() => {
      capturedOnSuccess!();
    });

    // After solve: children visible, CAPTCHA prompt gone
    expect(screen.getByTestId("upload-ui")).toBeInTheDocument();
    expect(screen.getByText("Upload Interface")).toBeInTheDocument();
    expect(screen.queryByText("Please complete the verification below")).not.toBeInTheDocument();

    // onCaptchaComplete should have been called
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("lazy-loads the configured SDK script and renders once it has loaded", async () => {
    removeCaptchaGlobal();
    renderGate();

    await waitFor(() => expect(sdkScripts()).toHaveLength(1));
    expect(sdkScripts()[0].src).toBe(SDK_URL);
    expect(mockRenderCaptcha).not.toHaveBeenCalled();

    // The SDK defines its global, then fires load.
    installCaptchaGlobal();
    act(() => {
      sdkScripts()[0].dispatchEvent(new Event("load"));
    });

    await waitFor(() => expect(mockRenderCaptcha).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("upload-ui")).not.toBeInTheDocument();
  });

  /**
   * Validates: Requirement 7.1
   * IF the AWS WAF CAPTCHA script fails to load, a user-friendly error message
   * is shown with a retry option.
   */
  it("shows error message when CAPTCHA script fails to load", async () => {
    removeCaptchaGlobal();
    renderGate();

    await waitFor(() => expect(sdkScripts()).toHaveLength(1));
    act(() => {
      sdkScripts()[0].dispatchEvent(new Event("error"));
    });

    // Error message should be displayed
    await waitFor(() => {
      expect(screen.getByText(LOAD_FAILED)).toBeInTheDocument();
    });

    // Children should NOT be visible
    expect(screen.queryByTestId("upload-ui")).not.toBeInTheDocument();

    // Retry button should be present
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();

    // renderCaptcha should NOT have been called (global is missing)
    expect(mockRenderCaptcha).not.toHaveBeenCalled();

    // Retry injects the script again
    act(() => {
      screen.getByRole("button", { name: /retry/i }).click();
    });
    await waitFor(() => expect(sdkScripts()).toHaveLength(1));
  });

  it("fails closed when no SDK URL is configured", async () => {
    removeCaptchaGlobal();
    StorageHelper.clearAwsConfig();
    renderGate();

    await waitFor(() => expect(screen.getByText(CONFIG_MISSING)).toBeInTheDocument());
    expect(screen.queryByTestId("upload-ui")).not.toBeInTheDocument();
    expect(sdkScripts()).toHaveLength(0);
    expect(mockRenderCaptcha).not.toHaveBeenCalled();
  });

  it("fails closed when no API key is configured", async () => {
    vi.stubEnv("VITE_WAF_CAPTCHA_API_KEY", "");
    renderGate();

    await waitFor(() => expect(screen.getByText(CONFIG_MISSING)).toBeInTheDocument());
    expect(screen.queryByTestId("upload-ui")).not.toBeInTheDocument();
    expect(mockRenderCaptcha).not.toHaveBeenCalled();
  });
});

describe("index.html", () => {
  it("does not hard-code a third-party WAF CAPTCHA SDK", () => {
    const html = readFileSync(path.resolve(__dirname, "../../../../index.html"), "utf-8");
    expect(html).not.toMatch(/awswaf\.com/);
  });
});
