import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { render, screen, act, waitFor } from "@testing-library/react";
import CaptchaGate from "./CaptchaGate";

// ---------------------------------------------------------------------------
// The VITE_WAF_CAPTCHA_API_KEY env variable is set in vitest.config.ts
// so the module-level const in CaptchaGate.tsx captures it at load time.
// ---------------------------------------------------------------------------

const TEST_API_KEY = "test-captcha-api-key";

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

beforeEach(() => {
  capturedOnSuccess = undefined;
  capturedOnError = undefined;
  mockRenderCaptcha.mockClear();
  installCaptchaGlobal();
});

afterEach(() => {
  removeCaptchaGlobal();
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
    const onComplete = vi.fn();

    render(
      <CaptchaGate captchaEnabled={false} onCaptchaComplete={onComplete}>
        <div data-testid="upload-ui">Upload Interface</div>
      </CaptchaGate>
    );

    // Children should be visible
    expect(screen.getByTestId("upload-ui")).toBeInTheDocument();
    expect(screen.getByText("Upload Interface")).toBeInTheDocument();

    // CAPTCHA widget should NOT be rendered
    expect(screen.queryByText("Please complete the verification below")).not.toBeInTheDocument();

    // renderCaptcha should not have been called
    expect(mockRenderCaptcha).not.toHaveBeenCalled();
  });

  /**
   * Validates: Requirement 5.2
   * WHEN captchaEnabled is true, the CAPTCHA container is rendered (not children).
   */
  it("renders CAPTCHA container when captchaEnabled is true", async () => {
    const onComplete = vi.fn();

    render(
      <CaptchaGate captchaEnabled={true} onCaptchaComplete={onComplete}>
        <div data-testid="upload-ui">Upload Interface</div>
      </CaptchaGate>
    );

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

  /**
   * Validates: Requirement 5.3
   * WHEN a visitor successfully solves the CAPTCHA, onCaptchaComplete is called
   * and children are rendered.
   */
  it("calls onCaptchaComplete and renders children after successful solve", async () => {
    const onComplete = vi.fn();

    render(
      <CaptchaGate captchaEnabled={true} onCaptchaComplete={onComplete}>
        <div data-testid="upload-ui">Upload Interface</div>
      </CaptchaGate>
    );

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

  /**
   * Validates: Requirement 7.1
   * IF the AWS WAF CAPTCHA script fails to load, a user-friendly error message
   * is shown with a retry option.
   */
  it("shows error message when CAPTCHA script fails to load", async () => {
    // Remove the AwsWafCaptcha global to simulate script not loaded
    removeCaptchaGlobal();

    const onComplete = vi.fn();

    render(
      <CaptchaGate captchaEnabled={true} onCaptchaComplete={onComplete}>
        <div data-testid="upload-ui">Upload Interface</div>
      </CaptchaGate>
    );

    // Error message should be displayed
    await waitFor(() => {
      expect(
        screen.getByText(
          "The CAPTCHA verification could not be loaded. Please check your network connection and try again."
        )
      ).toBeInTheDocument();
    });

    // Children should NOT be visible
    expect(screen.queryByTestId("upload-ui")).not.toBeInTheDocument();

    // Retry button should be present
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();

    // renderCaptcha should NOT have been called (global is missing)
    expect(mockRenderCaptcha).not.toHaveBeenCalled();
  });
});
