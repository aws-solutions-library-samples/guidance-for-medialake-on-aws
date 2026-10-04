import { StorageHelper } from "@/common/helpers/storage-helper";

/**
 * AWS WAF CAPTCHA SDK configuration for upload portals.
 *
 * The deployment's own WAF CAPTCHA integration URL and API key come from
 * aws-exports.json (`Portal.captchaSdkUrl` / `Portal.captchaApiKey`, set by the
 * `waf_captcha_integration_url` / `waf_captcha_api_key` keys in config.json).
 * The SDK script is only injected when a CAPTCHA-enabled portal needs it.
 */
export interface WafCaptchaConfig {
  sdkUrl: string | null;
  apiKey: string | null;
}

/** Thrown when CAPTCHA is needed but no SDK URL is configured. */
export class WafCaptchaNotConfiguredError extends Error {
  constructor() {
    super("AWS WAF CAPTCHA SDK URL is not configured");
    this.name = "WafCaptchaNotConfiguredError";
  }
}

function readPortalConfig(awsConfig: unknown): WafCaptchaConfig {
  const portal = (awsConfig as { Portal?: Record<string, unknown> } | null)?.Portal;
  const sdkUrl = typeof portal?.captchaSdkUrl === "string" ? portal.captchaSdkUrl : "";
  const apiKey = typeof portal?.captchaApiKey === "string" ? portal.captchaApiKey : "";
  return { sdkUrl: sdkUrl || null, apiKey: apiKey || null };
}

/**
 * Resolve the CAPTCHA SDK URL and API key. Reads the cached aws-exports.json
 * first; if it has no CAPTCHA settings (e.g. it was cached before they were
 * configured) the file is re-fetched once. The API key falls back to the
 * build-time `VITE_WAF_CAPTCHA_API_KEY`.
 */
export async function resolveWafCaptchaConfig(): Promise<WafCaptchaConfig> {
  let { sdkUrl, apiKey } = readPortalConfig(StorageHelper.getAwsConfig());

  if (!sdkUrl || !apiKey) {
    try {
      const response = await fetch("/aws-exports.json", { cache: "no-store" });
      if (response.ok) {
        const fresh = readPortalConfig(await response.json());
        sdkUrl = sdkUrl || fresh.sdkUrl;
        apiKey = apiKey || fresh.apiKey;
      }
    } catch {
      // Keep whatever the cached config had; missing values fail closed.
    }
  }

  const envKey = import.meta.env.VITE_WAF_CAPTCHA_API_KEY as string | undefined;
  return { sdkUrl, apiKey: apiKey || envKey || null };
}

const SDK_SCRIPT_ID = "aws-waf-captcha-sdk";
let sdkLoad: Promise<void> | null = null;

/**
 * Inject the WAF CAPTCHA SDK script (jsapi.js, which also pulls in the
 * intelligent-threat integration used by `AwsWafIntegration.fetch`).
 * Resolves immediately if the SDK is already present, and rejects with
 * WafCaptchaNotConfiguredError when no URL is configured.
 */
export function loadWafCaptchaSdk(sdkUrl: string | null): Promise<void> {
  if (typeof AwsWafCaptcha !== "undefined") return Promise.resolve();
  if (!sdkUrl) return Promise.reject(new WafCaptchaNotConfiguredError());
  if (sdkLoad) return sdkLoad;

  sdkLoad = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.id = SDK_SCRIPT_ID;
    script.src = sdkUrl;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      // Allow a later retry to inject a fresh script.
      script.remove();
      sdkLoad = null;
      reject(new Error(`Failed to load AWS WAF CAPTCHA SDK from ${sdkUrl}`));
    };
    document.head.appendChild(script);
  });
  return sdkLoad;
}

/** Resolve the configured SDK URL and make sure the SDK is loaded. */
export async function ensureWafCaptchaSdk(): Promise<void> {
  if (typeof AwsWafIntegration !== "undefined") return;
  const { sdkUrl } = await resolveWafCaptchaConfig();
  await loadWafCaptchaSdk(sdkUrl);
}

/** Test-only: forget a pending/finished load so each test starts clean. */
export function resetWafCaptchaSdkForTests(): void {
  sdkLoad = null;
  document.getElementById(SDK_SCRIPT_ID)?.remove();
}
