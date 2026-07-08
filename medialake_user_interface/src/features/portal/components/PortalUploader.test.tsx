import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetSession = vi.fn();
const mockHeartbeat = vi.fn();
const mockSubmit = vi.fn();
const mockReleaseKey = vi.fn();
const mockGetPresignedUrl = vi.fn();
const mockBrowse = vi.fn();
const mockSignPart = vi.fn();
const mockCompleteMultipart = vi.fn();
const mockAbortMultipart = vi.fn();
const mockStartSession = vi.fn();

vi.mock("../hooks/usePortalApi", () => ({
  usePortalApi: () => ({
    getSession: mockGetSession,
    heartbeat: mockHeartbeat,
    submit: mockSubmit,
    releaseKey: mockReleaseKey,
    getPresignedUrl: mockGetPresignedUrl,
    browse: mockBrowse,
    signPart: mockSignPart,
    completeMultipart: mockCompleteMultipart,
    abortMultipart: mockAbortMultipart,
    authenticate: vi.fn(),
    getPortalConfig: vi.fn(),
    startSession: mockStartSession,
    createFolder: vi.fn(),
  }),
  PortalSessionExpiredError: class PortalSessionExpiredError extends Error {
    constructor() {
      super("Portal session expired");
      this.name = "PortalSessionExpiredError";
    }
  },
}));

vi.mock("@/common/helpers/storage-helper", () => ({
  StorageHelper: {
    getAwsConfig: () => ({
      API: { REST: { RestApi: { endpoint: "https://api.example.com" } } },
    }),
  },
}));

// Mock Uppy and Dashboard to avoid complex component rendering
const mockUppyOn = vi.fn();
const mockUppyOff = vi.fn();
const mockUppyGetFiles = vi.fn(() => []);
const mockUppyCancelAll = vi.fn();
const mockUppyUpload = vi.fn();
const mockUppyRemoveFile = vi.fn();
// Capture the AwsS3 plugin options the component registers via setOptions so
// tests can invoke getUploadParameters/createMultipartUpload directly.
let capturedS3Options: any = null;
const mockUppyGetPlugin = vi.fn((_name?: string) => ({
  setOptions: (opts: any) => {
    capturedS3Options = opts;
  },
}));
const mockUppyUse = vi.fn().mockReturnThis();

// Track event listeners registered with uppy.on()
let uppyEventListeners: Record<string, ((...args: any[]) => void)[]> = {};

vi.mock("@uppy/core", () => {
  return {
    default: class MockUppy {
      constructor() {
        uppyEventListeners = {};
      }
      on(event: string, handler: (...args: any[]) => void) {
        if (!uppyEventListeners[event]) uppyEventListeners[event] = [];
        uppyEventListeners[event].push(handler);
        mockUppyOn(event, handler);
        return this;
      }
      off(event: string, handler: (...args: any[]) => void) {
        if (uppyEventListeners[event]) {
          uppyEventListeners[event] = uppyEventListeners[event].filter((h) => h !== handler);
        }
        mockUppyOff(event, handler);
        return this;
      }
      getFiles() {
        return mockUppyGetFiles();
      }
      cancelAll() {
        mockUppyCancelAll();
      }
      upload() {
        mockUppyUpload();
      }
      removeFile(id: string) {
        mockUppyRemoveFile(id);
      }
      getPlugin(name: string) {
        return mockUppyGetPlugin(name);
      }
      use(...args: any[]) {
        mockUppyUse(...args);
        return this;
      }
    },
  };
});

vi.mock("@uppy/aws-s3", () => ({ default: class {} }));
vi.mock("@uppy/react/dashboard", () => ({
  default: () => <div data-testid="uppy-dashboard" />,
}));
vi.mock("@uppy/core/css/style.min.css", () => ({}));
vi.mock("@uppy/dashboard/css/style.min.css", () => ({}));
vi.mock("./UploadQueueTable", () => ({
  default: () => <div data-testid="upload-queue-table" />,
}));
vi.mock("./ConflictResolutionDialog", () => ({
  default: () => null,
}));

// Import the component after mocks
import PortalUploader from "./PortalUploader";

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

const defaultProps = {
  portalSlug: "test-portal",
  sessionJwt: "test-jwt",
  destination: {
    destinationId: "dest-1",
    friendlyName: "Test Destination",
    connectorId: "connector-1",
    rootPath: "/root",
    allowBrowsing: true,
    allowFolderCreation: true,
    order: 0,
  },
  currentPath: "/root/subdir",
  metadataFields: {},
  onSessionExpired: vi.fn(),
};

const SESSION_STORAGE_KEY = "upload-session:test-portal:dest-1";

function emitUppyEvent(event: string, ...args: any[]) {
  const handlers = uppyEventListeners[event] || [];
  handlers.forEach((handler) => handler(...args));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PortalUploader — session integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    uppyEventListeners = {};
    capturedS3Options = null;
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // -------------------------------------------------------------------------
  // Single-flight session creation (concurrency regression)
  //
  // Regression for the multi-file fragmentation bug: AwsS3 fires up to `limit`
  // concurrent getUploadParameters/createMultipartUpload calls. Previously each
  // read sessionIdRef.current === null before any response returned and POSTed
  // /upload with no sessionId, so the server minted a separate session per file.
  // ensureSession() must collapse the whole first wave onto ONE session.
  // -------------------------------------------------------------------------
  describe("Single-flight session creation (concurrency regression)", () => {
    it("creates exactly one session and reuses it across concurrent uploads", async () => {
      // Defer the session creation so two uploads race while it is in flight.
      let resolveStart!: (v: any) => void;
      const startPromise = new Promise<any>((res) => {
        resolveStart = res;
      });
      mockStartSession.mockReturnValueOnce(startPromise);

      mockGetPresignedUrl.mockResolvedValue({
        sessionId: "session-AAA",
        presignedPost: { url: "https://s3.example.com", fields: {} },
      });

      render(<PortalUploader {...defaultProps} />);

      // Wait for the S3 plugin callbacks to be registered.
      await waitFor(() => expect(capturedS3Options).not.toBeNull());
      const getUploadParameters = capturedS3Options.getUploadParameters;

      // Fire two concurrent uploads BEFORE the session create resolves — this
      // is the exact race that previously fragmented the batch.
      const p1 = getUploadParameters({ name: "a.txt", type: "text/plain", size: 10 });
      const p2 = getUploadParameters({ name: "b.txt", type: "text/plain", size: 20 });

      // Resolve the single in-flight session creation.
      resolveStart({
        sessionId: "session-AAA",
        status: "OPEN",
        expectedCount: 0,
        completedCount: 0,
      });

      await act(async () => {
        await Promise.all([p1, p2]);
      });

      // startSession invoked exactly once despite two concurrent uploads.
      expect(mockStartSession).toHaveBeenCalledTimes(1);

      // Both presigned-URL requests carried the SAME sessionId and a batchToken.
      expect(mockGetPresignedUrl).toHaveBeenCalledTimes(2);
      const bodies = mockGetPresignedUrl.mock.calls.map((c) => c[0]);
      expect(bodies[0].sessionId).toBe("session-AAA");
      expect(bodies[1].sessionId).toBe("session-AAA");
      expect(bodies[0].sessionId).toBe(bodies[1].sessionId);
      expect(bodies[0].batchToken).toBeTruthy();
      expect(bodies[1].batchToken).toBe(bodies[0].batchToken);
    });

    it("reuses a resumed session and never calls startSession", async () => {
      // A stored OPEN session is resumed on mount; ensureSession must honor it.
      sessionStorage.setItem(SESSION_STORAGE_KEY, "resumed-session");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "resumed-session",
        status: "OPEN",
        expectedCount: 0,
        completedCount: 0,
      });
      mockGetPresignedUrl.mockResolvedValue({
        sessionId: "resumed-session",
        presignedPost: { url: "https://s3.example.com", fields: {} },
      });

      render(<PortalUploader {...defaultProps} />);

      await waitFor(() => expect(mockGetSession).toHaveBeenCalledWith("resumed-session"));
      await waitFor(() => expect(capturedS3Options).not.toBeNull());
      // Let the resume promise settle so sessionIdRef.current is assigned.
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      await act(async () => {
        await capturedS3Options.getUploadParameters({
          name: "a.txt",
          type: "text/plain",
          size: 10,
        });
      });

      expect(mockStartSession).not.toHaveBeenCalled();
      const body = mockGetPresignedUrl.mock.calls[0][0];
      expect(body.sessionId).toBe("resumed-session");
      expect(body.batchToken).toBeTruthy();
    });
  });

  // -------------------------------------------------------------------------
  // Resume reuse: stored sessionId + OPEN status => reuse
  // -------------------------------------------------------------------------
  describe("Resume reuse vs discard (Requirements 2.2, 2.3)", () => {
    it("reuses the stored sessionId when getSession returns OPEN", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "existing-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "existing-session-id",
        status: "OPEN",
        expectedCount: 3,
        completedCount: 1,
      });

      render(<PortalUploader {...defaultProps} />);

      await waitFor(() => {
        expect(mockGetSession).toHaveBeenCalledWith("existing-session-id");
      });

      // The stored id should still be in sessionStorage (not removed)
      expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe("existing-session-id");
    });

    it("discards the stored sessionId when getSession returns non-OPEN status", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "completed-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "completed-session-id",
        status: "COMPLETE",
        expectedCount: 5,
        completedCount: 5,
      });

      render(<PortalUploader {...defaultProps} />);

      await waitFor(() => {
        expect(mockGetSession).toHaveBeenCalledWith("completed-session-id");
      });

      // The stored id should be removed from sessionStorage
      await waitFor(() => {
        expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
      });
    });

    it("discards the stored sessionId when getSession throws (e.g. 404)", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "missing-session-id");
      mockGetSession.mockRejectedValueOnce(new Error("Not Found"));

      render(<PortalUploader {...defaultProps} />);

      await waitFor(() => {
        expect(mockGetSession).toHaveBeenCalledWith("missing-session-id");
      });

      // The stored id should be removed from sessionStorage
      await waitFor(() => {
        expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
      });
    });

    it("does nothing when there is no stored sessionId", async () => {
      render(<PortalUploader {...defaultProps} />);

      // Should not call getSession at all
      expect(mockGetSession).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // Heartbeat scheduling moved to the page level (UploadPortalPage) so it runs
  // for the whole life of the authenticated survey (any page, upload in flight
  // or not), not just during upload. The uploader no longer schedules
  // heartbeats, so the former uploader-heartbeat tests were removed; the
  // page-level heartbeat is covered in the UploadPortalPage tests.
  // -------------------------------------------------------------------------

  // -------------------------------------------------------------------------
  // Submit is now an explicit survey-level action — the uploader no longer
  // finalizes on Uppy complete or on beforeunload. It releases failed keys and
  // reports uploading state / counts up to the survey.
  // -------------------------------------------------------------------------
  describe("Release on error and upload-state reporting", () => {
    it("does NOT call submit on the Uppy complete event", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "no-finalize-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "no-finalize-session-id",
        status: "OPEN",
        expectedCount: 1,
        completedCount: 0,
      });

      render(<PortalUploader {...defaultProps} />);
      await waitFor(() => {
        expect(mockGetSession).toHaveBeenCalledWith("no-finalize-session-id");
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      act(() => {
        emitUppyEvent("complete", { successful: [], failed: [] });
      });

      // The uploader must not trigger the pipeline — submit is survey-level.
      expect(mockSubmit).not.toHaveBeenCalled();
    });

    it("reports uploading state via onUploadingChange on upload/complete", async () => {
      const onUploadingChange = vi.fn();
      render(<PortalUploader {...defaultProps} onUploadingChange={onUploadingChange} />);

      act(() => {
        emitUppyEvent("upload");
      });
      expect(onUploadingChange).toHaveBeenCalledWith(true);

      act(() => {
        emitUppyEvent("complete", { successful: [], failed: [] });
      });
      expect(onUploadingChange).toHaveBeenCalledWith(false);
    });

    it("releases a failed upload's key via portalApi.releaseKey", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "release-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "release-session-id",
        status: "OPEN",
        expectedCount: 0,
        completedCount: 0,
      });
      mockGetPresignedUrl.mockResolvedValue({
        sessionId: "release-session-id",
        presignedPost: { url: "https://s3.example.com", fields: { key: "k" } },
      });
      mockReleaseKey.mockResolvedValue(undefined);

      render(<PortalUploader {...defaultProps} />);
      await waitFor(() => {
        expect(mockGetSession).toHaveBeenCalledWith("release-session-id");
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      // Register a file through the captured AwsS3 getUploadParameters so the
      // per-file locator (filename, path) is recorded.
      const file = { id: "file-1", name: "broken.mp4", type: "video/mp4", size: 100 };
      await act(async () => {
        await capturedS3Options.getUploadParameters(file);
      });

      // The upload then fails → the key is released against the session.
      act(() => {
        emitUppyEvent("upload-error", file);
      });

      await waitFor(() => {
        expect(mockReleaseKey).toHaveBeenCalledWith("release-session-id", {
          destinationId: "dest-1",
          filename: "broken.mp4",
          // currentPath "/root/subdir" with rootPath "/root" → "/subdir"
          path: "/subdir",
        });
      });
    });

    it("does nothing on beforeunload (no finalize beacon)", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "beacon-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "beacon-session-id",
        status: "OPEN",
        expectedCount: 1,
        completedCount: 0,
      });

      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response());

      render(<PortalUploader {...defaultProps} />);
      await waitFor(() => {
        expect(mockGetSession).toHaveBeenCalledWith("beacon-session-id");
      });

      act(() => {
        window.dispatchEvent(new Event("beforeunload"));
      });

      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });
});
