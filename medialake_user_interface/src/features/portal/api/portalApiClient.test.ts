import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createPortalApiClient } from "./portalApiClient";
import { StorageHelper } from "@/common/helpers/storage-helper";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FAKE_ENDPOINT = "https://api.example.com/v1";
const SESSION_JWT = "test-session-jwt-token";

// ---------------------------------------------------------------------------
// Mock AwsWafIntegration global
// ---------------------------------------------------------------------------

const mockWafFetch = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>();

function installWafGlobal() {
  (globalThis as Record<string, unknown>).AwsWafIntegration = {
    fetch: mockWafFetch,
    getToken: vi.fn(),
  };
}

function removeWafGlobal() {
  delete (globalThis as Record<string, unknown>).AwsWafIntegration;
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockWafFetch.mockReset();
  installWafGlobal();

  // Provide a fake AWS config so getBaseURL() returns a known endpoint
  StorageHelper.setAwsConfig({
    API: {
      REST: {
        RestApi: {
          endpoint: FAKE_ENDPOINT,
        },
      },
    },
  });
});

afterEach(() => {
  removeWafGlobal();
  StorageHelper.clearAwsConfig();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("createPortalApiClient", () => {
  /**
   * Validates: Requirement 6.1
   * WHEN captchaEnabled is true, the Portal_API_Client SHALL use
   * AwsWafIntegration.fetch() to attach the WAF token cookie.
   */
  it("uses WAF fetch adapter when useCaptchaIntegration is true", async () => {
    // Arrange: mock AwsWafIntegration.fetch to return a valid Response
    mockWafFetch.mockResolvedValue(
      new Response(JSON.stringify({ presignedUrl: "https://s3.example.com/upload" }), {
        status: 200,
        statusText: "OK",
        headers: { "Content-Type": "application/json" },
      })
    );

    const client = createPortalApiClient(SESSION_JWT, true);

    // The adapter should be set to the wafFetchAdapter function
    expect(client.defaults.adapter).toBeDefined();
    expect(typeof client.defaults.adapter).toBe("function");

    // Act: make a request through the client
    const response = await client.post("/portal/test-slug/upload", {
      fileName: "test.mp4",
    });

    // Assert: AwsWafIntegration.fetch was called
    expect(mockWafFetch).toHaveBeenCalledTimes(1);

    // Verify the URL was constructed correctly
    const [calledUrl, calledInit] = mockWafFetch.mock.calls[0];
    expect(calledUrl).toContain("/portal/test-slug/upload");
    expect(calledInit?.method).toBe("POST");

    // Verify the response data was returned
    expect(response.data).toEqual({ presignedUrl: "https://s3.example.com/upload" });
  });

  /**
   * Validates: Requirement 6.2
   * WHEN captchaEnabled is false, the Portal_API_Client SHALL use
   * standard HTTP requests without WAF token integration.
   */
  it("uses standard Axios (no WAF adapter) when useCaptchaIntegration is false", () => {
    const client = createPortalApiClient(SESSION_JWT, false);

    // When useCaptchaIntegration is false, the adapter should be the Axios default
    // (an array of built-in adapter names like ['xhr', 'http', 'fetch']),
    // NOT a custom function (wafFetchAdapter).
    expect(typeof client.defaults.adapter).not.toBe("function");
  });

  /**
   * Validates: Requirement 6.2
   * WHEN useCaptchaIntegration is not provided, the Portal_API_Client SHALL
   * use standard HTTP requests without WAF token integration.
   */
  it("uses standard Axios when useCaptchaIntegration is omitted", () => {
    const client = createPortalApiClient(SESSION_JWT);

    // When useCaptchaIntegration is omitted, the adapter should be the Axios default,
    // NOT a custom function (wafFetchAdapter).
    expect(typeof client.defaults.adapter).not.toBe("function");
  });

  /**
   * Validates: Requirement 6.3
   * The Portal_API_Client SHALL include the X-Portal-Session header on all
   * requests regardless of CAPTCHA configuration.
   */
  it("includes X-Portal-Session header when useCaptchaIntegration is true", async () => {
    mockWafFetch.mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        statusText: "OK",
        headers: { "Content-Type": "application/json" },
      })
    );

    const client = createPortalApiClient(SESSION_JWT, true);
    await client.get("/portal/test-slug");

    // The WAF fetch should have been called with headers containing X-Portal-Session
    expect(mockWafFetch).toHaveBeenCalledTimes(1);
    const [, calledInit] = mockWafFetch.mock.calls[0];

    // Headers may be an AxiosHeaders object; convert to check
    const headers = calledInit?.headers;
    expect(headers).toBeDefined();

    // Check the header is present — AxiosHeaders are passed as HeadersInit
    // which could be a Headers object, plain object, or array of tuples
    if (headers instanceof Headers) {
      expect(headers.get("X-Portal-Session")).toBe(SESSION_JWT);
    } else if (typeof headers === "object" && headers !== null) {
      // Could be AxiosHeaders or plain object — check common access patterns
      const headerObj = headers as Record<string, unknown>;
      const sessionHeader = headerObj["X-Portal-Session"] ?? headerObj["x-portal-session"];
      expect(sessionHeader).toBe(SESSION_JWT);
    }
  });

  /**
   * Validates: Requirement 6.3
   * The Portal_API_Client SHALL include the X-Portal-Session header on all
   * requests regardless of CAPTCHA configuration (standard Axios mode).
   */
  it("includes X-Portal-Session header when useCaptchaIntegration is false", () => {
    const client = createPortalApiClient(SESSION_JWT, false);

    // Verify the interceptor is set up by checking that a request config
    // gets the header added. We can test this by inspecting the interceptors.
    // The interceptor adds the header at request time, so we verify the
    // interceptor count is correct (at least one request interceptor).
    expect(client.interceptors.request).toBeDefined();

    // We can also verify by running the interceptor manually through a config
    // Since we can't easily intercept without making a real request,
    // we verify the adapter is NOT set (standard mode) and the interceptor exists.
    // The actual header attachment is tested in the WAF mode test above,
    // and the interceptor is the same code path for both modes.

    // Create a mock config and run it through the interceptor handlers
    // Axios interceptors have a `handlers` array we can inspect
    const handlers = (client.interceptors.request as any).handlers;
    expect(handlers.length).toBeGreaterThan(0);

    // Find the fulfilled handler (the one that adds the header)
    const fulfilledHandler = handlers.find((h: any) => h?.fulfilled);
    expect(fulfilledHandler).toBeDefined();

    // Run the handler with a mock config to verify header is added
    const mockConfig = {
      headers: {
        set: vi.fn(),
      } as any,
    };

    const result = fulfilledHandler.fulfilled(mockConfig);
    expect(result.headers["X-Portal-Session"]).toBe(SESSION_JWT);
  });
});
