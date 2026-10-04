import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { StorageHelper } from "@/common/helpers/storage-helper";
import {
  WafCaptchaNotConfiguredError,
  loadWafCaptchaSdk,
  resetWafCaptchaSdkForTests,
  resolveWafCaptchaConfig,
} from "./wafCaptchaSdk";

const SDK_URL = "https://abc123.edge.captcha-sdk.awswaf.com/abc123/jsapi.js";
const ENV_KEY = "test-captcha-api-key"; // vitest.config.ts VITE_WAF_CAPTCHA_API_KEY

function sdkScripts(): HTMLScriptElement[] {
  return Array.from(document.querySelectorAll<HTMLScriptElement>('script[src*="awswaf.com"]'));
}

function mockAwsExportsFetch(body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  );
}

beforeEach(() => {
  resetWafCaptchaSdkForTests();
  StorageHelper.clearAwsConfig();
  delete (globalThis as Record<string, unknown>).AwsWafCaptcha;
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  resetWafCaptchaSdkForTests();
  delete (globalThis as Record<string, unknown>).AwsWafCaptcha;
});

describe("resolveWafCaptchaConfig", () => {
  it("reads the SDK URL and API key from the cached aws-exports Portal section", async () => {
    const fetchSpy = mockAwsExportsFetch({});
    StorageHelper.setAwsConfig({ Portal: { captchaSdkUrl: SDK_URL, captchaApiKey: "cfg-key" } });

    expect(await resolveWafCaptchaConfig()).toEqual({ sdkUrl: SDK_URL, apiKey: "cfg-key" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("re-fetches aws-exports.json when the cached copy predates the CAPTCHA settings", async () => {
    StorageHelper.setAwsConfig({ region: "us-east-1" });
    const fetchSpy = mockAwsExportsFetch({
      Portal: { captchaSdkUrl: SDK_URL, captchaApiKey: "fresh-key" },
    });

    expect(await resolveWafCaptchaConfig()).toEqual({ sdkUrl: SDK_URL, apiKey: "fresh-key" });
    expect(fetchSpy).toHaveBeenCalledWith("/aws-exports.json", { cache: "no-store" });
  });

  it("falls back to VITE_WAF_CAPTCHA_API_KEY when no API key is configured", async () => {
    mockAwsExportsFetch({});
    StorageHelper.setAwsConfig({ Portal: { captchaSdkUrl: SDK_URL } });

    expect(await resolveWafCaptchaConfig()).toEqual({ sdkUrl: SDK_URL, apiKey: ENV_KEY });
  });

  it("returns nulls when nothing is configured and the re-fetch fails", async () => {
    vi.stubEnv("VITE_WAF_CAPTCHA_API_KEY", "");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));

    expect(await resolveWafCaptchaConfig()).toEqual({ sdkUrl: null, apiKey: null });
  });
});

describe("loadWafCaptchaSdk", () => {
  it("rejects with WafCaptchaNotConfiguredError when no SDK URL is configured", async () => {
    await expect(loadWafCaptchaSdk(null)).rejects.toBeInstanceOf(WafCaptchaNotConfiguredError);
    expect(sdkScripts()).toHaveLength(0);
  });

  it("does not inject a script when the SDK is already present", async () => {
    (globalThis as Record<string, unknown>).AwsWafCaptcha = { renderCaptcha: vi.fn() };

    await expect(loadWafCaptchaSdk(SDK_URL)).resolves.toBeUndefined();
    expect(sdkScripts()).toHaveLength(0);
  });

  it("injects the configured script once and resolves when it loads", async () => {
    const first = loadWafCaptchaSdk(SDK_URL);
    const second = loadWafCaptchaSdk(SDK_URL);

    const scripts = sdkScripts();
    expect(scripts).toHaveLength(1);
    expect(scripts[0].src).toBe(SDK_URL);
    expect(scripts[0].parentElement).toBe(document.head);

    scripts[0].dispatchEvent(new Event("load"));
    await expect(first).resolves.toBeUndefined();
    await expect(second).resolves.toBeUndefined();
  });

  it("rejects on a load error and lets a retry inject a fresh script", async () => {
    const attempt = loadWafCaptchaSdk(SDK_URL);
    sdkScripts()[0].dispatchEvent(new Event("error"));
    await expect(attempt).rejects.toThrow(/Failed to load AWS WAF CAPTCHA SDK/);
    expect(sdkScripts()).toHaveLength(0);

    const retry = loadWafCaptchaSdk(SDK_URL);
    expect(sdkScripts()).toHaveLength(1);
    sdkScripts()[0].dispatchEvent(new Event("load"));
    await expect(retry).resolves.toBeUndefined();
  });
});
