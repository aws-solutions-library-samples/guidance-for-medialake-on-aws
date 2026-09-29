import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";

vi.mock("@/common/helpers/token-helper", () => ({
  isTokenExpiringSoon: () => false,
}));

vi.mock("@/api/authService", () => ({
  authService: { refreshToken: vi.fn() },
}));

const API_ENDPOINT = "https://example.cloudfront.net/v1";

/** Adapter that records the config axios would send, instead of sending it. */
function recordingAdapter(seen: InternalAxiosRequestConfig[]): AxiosAdapter {
  return async (config) => {
    seen.push(config);
    return { data: { ok: true }, status: 200, statusText: "OK", headers: {}, config };
  };
}

describe("apiClient base URL", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("medialake-auth-token", "test-token");
    vi.resetModules();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("picks up the API endpoint once aws-exports is cached, even if it wasn't at load time", async () => {
    // First visit: the module loads before AwsConfigProvider caches the config.
    const { apiClient } = await import("./apiClient");
    localStorage.setItem(
      "medialake-aws-config",
      JSON.stringify({ API: { REST: { RestApi: { endpoint: API_ENDPOINT } } } })
    );

    const seen: InternalAxiosRequestConfig[] = [];
    await apiClient.get("/search/fields", { adapter: recordingAdapter(seen) });
    await apiClient.get("/users/search-history", { adapter: recordingAdapter(seen) });

    expect(seen.map((c) => c.baseURL)).toEqual([API_ENDPOINT, API_ENDPOINT]);
  });

  it("uses the cached endpoint when it is available at load time", async () => {
    localStorage.setItem(
      "medialake-aws-config",
      JSON.stringify({ API: { REST: { RestApi: { endpoint: API_ENDPOINT } } } })
    );
    const { apiClient } = await import("./apiClient");

    const seen: InternalAxiosRequestConfig[] = [];
    await apiClient.get("/search/fields", { adapter: recordingAdapter(seen) });

    expect(seen[0].baseURL).toBe(API_ENDPOINT);
  });

  it("leaves requests relative while no endpoint is known", async () => {
    const { apiClient } = await import("./apiClient");

    const seen: InternalAxiosRequestConfig[] = [];
    await apiClient.get("/search/fields", { adapter: recordingAdapter(seen) });

    expect(seen[0].baseURL).toBeFalsy();
  });
});
