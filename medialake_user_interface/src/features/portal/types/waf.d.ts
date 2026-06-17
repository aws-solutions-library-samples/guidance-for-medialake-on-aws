/** Type declarations for AWS WAF JavaScript CAPTCHA and Integration APIs */

interface AwsWafCaptchaRenderOptions {
  /** WAF CAPTCHA API key (safe to embed client-side) */
  apiKey: string;
  /** Called with the WAF token string after a successful CAPTCHA solve */
  onSuccess: (wafToken: string) => void;
  /** Called when the CAPTCHA widget encounters an error */
  onError?: (error: Error) => void;
  /** Allow the widget to resize to fit its container */
  dynamicWidth?: boolean;
  /** Hide the default CAPTCHA title */
  skipTitle?: boolean;
}

interface AwsWafCaptchaApi {
  /** Render the interactive CAPTCHA widget into the given container element */
  renderCaptcha: (container: HTMLElement, options: AwsWafCaptchaRenderOptions) => void;
}

interface AwsWafIntegrationApi {
  /**
   * A drop-in replacement for `window.fetch` that automatically attaches
   * the `aws-waf-token` cookie to outbound requests.
   */
  fetch: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
  /** Retrieve the current WAF token value (if any) */
  getToken: () => Promise<string>;
}

declare const AwsWafCaptcha: AwsWafCaptchaApi;
declare const AwsWafIntegration: AwsWafIntegrationApi;
