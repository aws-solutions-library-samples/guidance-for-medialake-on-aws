import { useMemo, useCallback } from "react";
import { createPortalApiClient, createUnauthPortalApiClient } from "../api/portalApiClient";
import type {
  PortalAuthCredentials,
  PortalAuthResponse,
  PortalConfig,
} from "../types/portal.types";

export class PortalSessionExpiredError extends Error {
  constructor() {
    super("Portal session expired");
    this.name = "PortalSessionExpiredError";
  }
}

export class WafTokenExpiredError extends Error {
  constructor() {
    super("WAF CAPTCHA token expired");
    this.name = "WafTokenExpiredError";
  }
}

/**
 * Thrown when an authenticated API call is made before a session JWT is
 * available. Surfaces as a typed error so callers can distinguish it from
 * a network failure and trigger the appropriate reauth flow.
 */
export class PortalNotAuthenticatedError extends Error {
  constructor() {
    super("Portal authClient not initialized: user not authenticated");
    this.name = "PortalNotAuthenticatedError";
  }
}

function handleApiError(error: any): never {
  if (error?.response?.status === 401) {
    throw new PortalSessionExpiredError();
  }
  if (error?.response?.status === 405 || error?.status === 405) {
    throw new WafTokenExpiredError();
  }
  throw error;
}

export function usePortalApi(
  slug: string,
  sessionJwt: string | null,
  useCaptchaIntegration?: boolean
) {
  const unauthClient = useMemo(() => createUnauthPortalApiClient(), []);
  const authClient = useMemo(
    () => (sessionJwt ? createPortalApiClient(sessionJwt, useCaptchaIntegration) : null),
    [sessionJwt, useCaptchaIntegration]
  );

  const authenticate = useCallback(
    async (
      credentials: PortalAuthCredentials,
      headers?: Record<string, string>
    ): Promise<PortalAuthResponse> => {
      const { data } = await unauthClient.post(
        `/portal/${slug}/auth`,
        credentials,
        headers ? { headers } : undefined
      );
      return data as PortalAuthResponse;
    },
    [unauthClient, slug]
  );

  const getPortalConfig = useCallback(async (): Promise<PortalConfig> => {
    if (!authClient) throw new PortalNotAuthenticatedError();
    try {
      const { data } = await authClient.get(`/portal/${slug}`);
      return data;
    } catch (e) {
      return handleApiError(e);
    }
  }, [authClient, slug]);

  const getPresignedUrl = useCallback(
    async (fileData: {
      filename: string;
      contentType: string;
      fileSize: number;
      path: string;
      destinationId: string;
      metadata?: Record<string, string>;
    }) => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.post(`/portal/${slug}/upload`, fileData);
        return data;
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const signPart = useCallback(
    async (partData: {
      uploadId: string;
      key: string;
      partNumber: number;
      destinationId: string;
    }) => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.post(`/portal/${slug}/upload/multipart/sign`, partData);
        return data;
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const completeMultipart = useCallback(
    async (payload: {
      uploadId: string;
      key: string;
      parts: Array<{ PartNumber: number; ETag: string }>;
      destinationId: string;
    }) => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.post(
          `/portal/${slug}/upload/multipart/complete`,
          payload
        );
        return data;
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const abortMultipart = useCallback(
    async (payload: { uploadId: string; key: string; destinationId: string }) => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        await authClient.post(`/portal/${slug}/upload/multipart/abort`, payload);
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const browse = useCallback(
    async (prefix: string, destinationId: string) => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.get(`/portal/${slug}/browse`, {
          params: { prefix, destinationId },
        });
        return data;
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const createFolder = useCallback(
    async (path: string, destinationId: string) => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.post(`/portal/${slug}/folder`, {
          path,
          destinationId,
        });
        return data;
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  return {
    authenticate,
    getPortalConfig,
    getPresignedUrl,
    signPart,
    completeMultipart,
    abortMultipart,
    browse,
    createFolder,
  };
}
