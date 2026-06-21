import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetSession = vi.fn();
const mockHeartbeat = vi.fn();
const mockFinalize = vi.fn();
const mockGetPresignedUrl = vi.fn();
const mockBrowse = vi.fn();
const mockSignPart = vi.fn();
const mockCompleteMultipart = vi.fn();
const mockAbortMultipart = vi.fn();

vi.mock("../hooks/usePortalApi", () => ({
  usePortalApi: () => ({
    getSession: mockGetSession,
    heartbeat: mockHeartbeat,
    finalize: mockFinalize,
    getPresignedUrl: mockGetPresignedUrl,
    browse: mockBrowse,
    signPart: mockSignPart,
    completeMultipart: mockCompleteMultipart,
    abortMultipart: mockAbortMultipart,
    authenticate: vi.fn(),
    getPortalConfig: vi.fn(),
    startSession: vi.fn(),
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
const mockUppyGetPlugin = vi.fn((_name?: string) => ({ setOptions: vi.fn() }));
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
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
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
  // Heartbeat interval scheduling and cleanup (Requirement 3.1)
  // -------------------------------------------------------------------------
  describe("Heartbeat interval scheduling/cleanup (Requirement 3.1)", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("posts a heartbeat every ~30s while uploading with a sessionId", async () => {
      // Set up a stored session that will be reused
      sessionStorage.setItem(SESSION_STORAGE_KEY, "hb-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "hb-session-id",
        status: "OPEN",
        expectedCount: 0,
        completedCount: 0,
      });
      mockHeartbeat.mockResolvedValue(undefined);

      const { rerender } = render(<PortalUploader {...defaultProps} />);

      // Wait for the session resume to resolve
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // Simulate the upload starting by triggering the 'upload' event
      act(() => {
        emitUppyEvent("upload");
      });

      // Rerender to let state updates propagate (isUploading = true)
      rerender(<PortalUploader {...defaultProps} />);

      // Advance 30 seconds — first heartbeat
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000);
      });

      expect(mockHeartbeat).toHaveBeenCalledWith("hb-session-id");

      // Advance another 30 seconds — second heartbeat
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000);
      });

      expect(mockHeartbeat).toHaveBeenCalledTimes(2);
    });

    it("stops heartbeat when uploading completes", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "hb-cleanup-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "hb-cleanup-session-id",
        status: "OPEN",
        expectedCount: 0,
        completedCount: 0,
      });
      mockHeartbeat.mockResolvedValue(undefined);
      mockFinalize.mockResolvedValue({
        status: "COMPLETE",
        expectedCount: 1,
        completedCount: 1,
      });

      const { rerender } = render(<PortalUploader {...defaultProps} />);

      // Wait for session resume
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // Simulate upload start
      act(() => {
        emitUppyEvent("upload");
      });
      rerender(<PortalUploader {...defaultProps} />);

      // First heartbeat fires
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000);
      });
      expect(mockHeartbeat).toHaveBeenCalledTimes(1);

      // Simulate upload complete — triggers isUploading = false
      act(() => {
        emitUppyEvent("complete", { successful: [], failed: [] });
      });
      rerender(<PortalUploader {...defaultProps} />);

      // Clear heartbeat call count
      mockHeartbeat.mockClear();

      // Advance 30 more seconds — no heartbeat should fire
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000);
      });

      expect(mockHeartbeat).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // Finalize on complete and beforeunload (Requirement 3.1)
  // -------------------------------------------------------------------------
  describe("Finalize on complete and beforeunload", () => {
    it("calls portalApi.finalize when Uppy emits the complete event", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "finalize-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "finalize-session-id",
        status: "OPEN",
        expectedCount: 2,
        completedCount: 0,
      });
      mockFinalize.mockResolvedValue({
        status: "COMPLETE",
        expectedCount: 2,
        completedCount: 2,
      });

      render(<PortalUploader {...defaultProps} />);

      // Wait for session resume to resolve so sessionIdRef is set
      await waitFor(() => {
        expect(mockGetSession).toHaveBeenCalledWith("finalize-session-id");
      });
      // Allow the promise chain to settle so sessionIdRef.current is assigned
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      // Simulate Uppy complete event
      act(() => {
        emitUppyEvent("complete", { successful: [], failed: [] });
      });

      await waitFor(() => {
        expect(mockFinalize).toHaveBeenCalledWith("finalize-session-id", expect.any(Number));
      });
    });

    it("fires a fetch with keepalive:true on beforeunload when a sessionId exists", async () => {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "beacon-session-id");
      mockGetSession.mockResolvedValueOnce({
        sessionId: "beacon-session-id",
        status: "OPEN",
        expectedCount: 1,
        completedCount: 0,
      });

      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response());

      render(<PortalUploader {...defaultProps} />);

      // Wait for session resume
      await waitFor(() => {
        expect(mockGetSession).toHaveBeenCalledWith("beacon-session-id");
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      // Fire beforeunload event
      act(() => {
        window.dispatchEvent(new Event("beforeunload"));
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/portal/test-portal/upload-session/beacon-session-id/finalize"),
        expect.objectContaining({
          method: "POST",
          keepalive: true,
          headers: expect.objectContaining({
            "Content-Type": "application/json",
            "X-Portal-Session": "test-jwt",
          }),
          body: expect.any(String),
        })
      );

      fetchSpy.mockRestore();
    });

    it("does not fire fetch on beforeunload when no sessionId exists", async () => {
      // No stored session, so sessionIdRef stays null
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response());

      render(<PortalUploader {...defaultProps} />);

      // Fire beforeunload event
      act(() => {
        window.dispatchEvent(new Event("beforeunload"));
      });

      expect(fetchSpy).not.toHaveBeenCalled();

      fetchSpy.mockRestore();
    });
  });
});
