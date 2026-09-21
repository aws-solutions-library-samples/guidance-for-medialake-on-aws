import { useMemo, useCallback } from "react";
import { createPortalApiClient, createUnauthPortalApiClient } from "../api/portalApiClient";
import type {
  PortalAuthCredentials,
  PortalAuthResponse,
  PortalConfig,
} from "../types/portal.types";

export interface UploadSessionResponse {
  sessionId: string;
  status: "OPEN" | "COMPLETE" | "COMPLETE_WITH_ERRORS";
  expectedCount: number;
  completedCount: number;
  /**
   * The batch's user-entered portal form fields ({ slug: value }). Empty until
   * the user submits; populated once the session is terminal so the UI can
   * review what was captured for a completed batch.
   */
  userMetadata?: Record<string, string>;
  /** Present only once the session has reached a terminal status. */
  outcome?: "COMPLETE" | "COMPLETE_WITH_ERRORS";
}

export interface SubmitResponse {
  status: "OPEN" | "COMPLETE" | "COMPLETE_WITH_ERRORS";
  expectedCount: number;
  completedCount: number;
  outcome?: "COMPLETE" | "COMPLETE_WITH_ERRORS";
}

/** Back-compat alias. */
export type FinalizeResponse = SubmitResponse;

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

  /**
   * Sign the request that creates the object — a PUT for a single-part upload or a
   * CreateMultipartUpload POST — and register the key against the session. The browser
   * performs the S3 request itself (Uppy 6 @uppy/aws-s3 signRequest). `key` is the
   * server's choice and must be used for the rest of the upload.
   */
  const createUpload = useCallback(
    async (fileData: {
      filename: string;
      contentType: string;
      fileSize: number;
      path: string;
      destinationId: string;
      method: "PUT" | "POST";
      metadata?: Record<string, string>;
      sessionId?: string;
      batchToken?: string;
    }) => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.post(`/portal/${slug}/upload`, fileData);
        return data as {
          sessionId?: string;
          multipart: boolean;
          bucket: string;
          key: string;
          url: string;
          method: "PUT" | "POST";
          expiresIn: number;
        };
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  /** Sign one request of an in-flight multipart upload (part, list, complete, abort). */
  const signMultipart = useCallback(
    async (request: {
      uploadId: string;
      key: string;
      destinationId: string;
      operation: "part" | "list" | "complete" | "abort";
      partNumber?: number;
    }) => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.post(`/portal/${slug}/upload/multipart/sign`, request);
        return data as {
          presignedUrl: string;
          operation: string;
          method: "PUT" | "GET" | "POST" | "DELETE";
          expiresIn: number;
          partNumber?: number;
        };
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

  const startSession = useCallback(
    async (resumeSessionId?: string): Promise<UploadSessionResponse> => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const body = resumeSessionId ? { resumeSessionId } : {};
        const { data } = await authClient.post(`/portal/${slug}/upload-session`, body);
        return data as UploadSessionResponse;
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const getSession = useCallback(
    async (sessionId: string): Promise<UploadSessionResponse> => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.get(`/portal/${slug}/upload-session/${sessionId}`);
        return data as UploadSessionResponse;
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const heartbeat = useCallback(
    async (sessionId: string): Promise<void> => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        await authClient.post(`/portal/${slug}/upload-session/${sessionId}/heartbeat`, {});
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const submit = useCallback(
    async (
      sessionId: string,
      payload: {
        metadata?: Record<string, string>;
        uploadedKeys?: string[];
        fileCount?: number;
      } = {}
    ): Promise<SubmitResponse> => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        const { data } = await authClient.post(
          `/portal/${slug}/upload-session/${sessionId}/submit`,
          payload
        );
        return data as SubmitResponse;
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  const releaseKey = useCallback(
    async (
      sessionId: string,
      fileLocator: { destinationId: string; filename: string; path?: string }
    ): Promise<void> => {
      if (!authClient) throw new PortalNotAuthenticatedError();
      try {
        await authClient.post(
          `/portal/${slug}/upload-session/${sessionId}/release-key`,
          fileLocator
        );
      } catch (e) {
        return handleApiError(e);
      }
    },
    [authClient, slug]
  );

  return {
    authenticate,
    getPortalConfig,
    createUpload,
    signMultipart,
    browse,
    createFolder,
    startSession,
    getSession,
    heartbeat,
    submit,
    releaseKey,
  };
}
