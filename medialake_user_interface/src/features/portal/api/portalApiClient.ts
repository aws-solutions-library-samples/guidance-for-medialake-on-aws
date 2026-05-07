import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { StorageHelper } from "@/common/helpers/storage-helper";

function getBaseURL(): string {
  return StorageHelper.getAwsConfig()?.API?.REST?.RestApi?.endpoint || "";
}

/** Unwrap Lambda proxy integration response format: { statusCode, body } → body */
function unwrapLambdaProxy(response: any) {
  if (
    response.data &&
    typeof response.data === "object" &&
    "body" in response.data &&
    "statusCode" in response.data
  ) {
    const body = response.data.body;
    if (typeof body === "object") {
      response.data = body;
    } else if (typeof body === "string") {
      try {
        response.data = JSON.parse(body);
      } catch {
        // leave as-is
      }
    }
  }
  return response;
}

/**
 * Custom Axios adapter that uses AwsWafIntegration.fetch() to attach
 * the aws-waf-token cookie to outbound requests.
 */
async function wafFetchAdapter(config: InternalAxiosRequestConfig): Promise<AxiosResponse> {
  const url = new URL(config.url!, config.baseURL);
  const fetchOptions: RequestInit = {
    method: config.method?.toUpperCase() || "GET",
    headers: config.headers as unknown as HeadersInit,
    body: config.data ? JSON.stringify(config.data) : undefined,
  };

  const response = await AwsWafIntegration.fetch(url.toString(), fetchOptions);

  // Parse the response body defensively: some endpoints (WAF challenge
  // responses, 204 No Content, HTML error pages) do not return JSON, and
  // `response.json()` would throw an unhelpful SyntaxError. We inspect
  // the Content-Type header first and fall back to reading the body as
  // text so consumers see a meaningful error that includes the status.
  const contentType = response.headers.get("content-type") || "";
  const looksLikeJson = contentType.toLowerCase().includes("application/json");

  let data: unknown;
  if (!looksLikeJson) {
    // Either empty, HTML, or some other content type — return the raw
    // text so callers can inspect it. An empty 204 ends up as "".
    const text = await response.text();
    if (!response.ok) {
      throw new Error(
        `Request to ${url.toString()} failed with ${response.status} ${response.statusText}: ${text}`,
      );
    }
    data = text;
  } else {
    try {
      data = await response.json();
    } catch (parseError) {
      // Clone would be cleaner but `response.json()` has already consumed
      // the body; surface the status details so the caller can react.
      throw new Error(
        `Request to ${url.toString()} returned invalid JSON (${response.status} ${response.statusText}): ${
          (parseError as Error).message
        }`,
      );
    }
  }

  return {
    data,
    status: response.status,
    statusText: response.statusText,
    headers: Object.fromEntries(response.headers.entries()),
    config,
  } as AxiosResponse;
}

/** Authenticated portal client — attaches X-Portal-Session header, optionally uses WAF integration */
export function createPortalApiClient(
  sessionJwt: string,
  useCaptchaIntegration?: boolean
): AxiosInstance {
  const instance = axios.create({
    baseURL: getBaseURL(),
    timeout: 120000,
  });

  if (useCaptchaIntegration) {
    instance.defaults.adapter = wafFetchAdapter;
  }

  instance.interceptors.request.use((config) => {
    config.headers["X-Portal-Session"] = sessionJwt;
    return config;
  });

  instance.interceptors.response.use(unwrapLambdaProxy);

  return instance;
}

/** Unauthenticated portal client — for initial auth call */
export function createUnauthPortalApiClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: getBaseURL(),
    timeout: 30000,
  });

  instance.interceptors.response.use(unwrapLambdaProxy);

  return instance;
}
