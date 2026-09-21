/**
 * Integration tests for FileUploader upload carry-through (task 7.3).
 *
 * Validates: Requirements 1.1, 1.4, 7.1, 7.2, 7.3, 7.4, 7.5
 *
 * Coverage:
 *   - collection_ids flow into Uppy meta when collections are selected (7.1)
 *   - collection_ids is passed in the presigned-URL request for single-part uploads (7.2, 7.3)
 *   - collection_ids is passed in the presigned-URL request for multipart uploads (7.2, 7.3)
 *   - CollectionSelector is disabled during upload (7.4)
 *   - Completion notice appears when upload completes with ≥1 collection selected (7.5)
 *   - Empty selection uploads normally without collection_ids in the request (1.4)
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Types for mocks ---
type UppyEventHandler = (...args: any[]) => void;

// --- Capture Uppy instance interactions ---
let mockUppyInstance: {
  on: ReturnType<typeof vi.fn>;
  off: ReturnType<typeof vi.fn>;
  use: ReturnType<typeof vi.fn>;
  setOptions: ReturnType<typeof vi.fn>;
  getState: ReturnType<typeof vi.fn>;
  getPlugin: ReturnType<typeof vi.fn>;
  getFile: ReturnType<typeof vi.fn>;
  getFiles: ReturnType<typeof vi.fn>;
  setFileMeta: ReturnType<typeof vi.fn>;
  cancelAll: ReturnType<typeof vi.fn>;
  removeFile: ReturnType<typeof vi.fn>;
  info: ReturnType<typeof vi.fn>;
  _eventHandlers: Map<string, UppyEventHandler[]>;
  _emit: (event: string, ...args: any[]) => void;
};

// Options the component hands to the AwsS3 plugin via uppy.use(AwsS3, opts); the tests
// drive its `signRequest` the way the plugin would.
let capturedPluginOptions: any;
// Files "in" the mock Uppy, keyed by id, so signRequest can resolve the create request.
const mockFiles = new Map<string, any>();

function createMockUppy() {
  const eventHandlers = new Map<string, UppyEventHandler[]>();

  mockUppyInstance = {
    on: vi.fn((event: string, handler: UppyEventHandler) => {
      const handlers = eventHandlers.get(event) || [];
      handlers.push(handler);
      eventHandlers.set(event, handlers);
    }),
    off: vi.fn((event: string, handler: UppyEventHandler) => {
      const handlers = eventHandlers.get(event) || [];
      eventHandlers.set(
        event,
        handlers.filter((h) => h !== handler)
      );
    }),
    use: vi.fn((_plugin: unknown, opts: any) => {
      if (opts?.signRequest) capturedPluginOptions = opts;
    }),
    setOptions: vi.fn(),
    getState: vi.fn(() => ({ meta: {} })),
    getPlugin: vi.fn(),
    getFile: vi.fn((id: string) => mockFiles.get(id)),
    getFiles: vi.fn(() => [...mockFiles.values()]),
    setFileMeta: vi.fn((id: string, meta: Record<string, unknown>) => {
      const file = mockFiles.get(id);
      if (file) file.meta = { ...(file.meta ?? {}), ...meta };
    }),
    cancelAll: vi.fn(),
    removeFile: vi.fn(),
    info: vi.fn(),
    _eventHandlers: eventHandlers,
    _emit: (event: string, ...args: any[]) => {
      const handlers = eventHandlers.get(event) || [];
      handlers.forEach((h) => h(...args));
    },
  };

  return mockUppyInstance;
}

// --- Mock @uppy/core ---
vi.mock("@uppy/core", () => {
  return {
    default: class Uppy {
      constructor() {
        return createMockUppy();
      }
    },
  };
});

// --- Mock @uppy/react/dashboard ---
vi.mock("@uppy/react/dashboard", () => ({
  default: ({ uppy, disabled }: { uppy: any; disabled: boolean }) => (
    <div data-testid="uppy-dashboard" data-disabled={disabled}>
      Uppy Dashboard
    </div>
  ),
}));

// --- Mock @uppy/aws-s3 and @uppy/golden-retriever ---
vi.mock("@uppy/aws-s3", () => ({
  default: vi.fn(),
}));
vi.mock("@uppy/golden-retriever", () => ({
  default: vi.fn(),
}));

// --- Mock CSS imports ---
vi.mock("@uppy/core/css/style.min.css", () => ({}));
vi.mock("@uppy/dashboard/css/style.min.css", () => ({}));

// --- Mock react-i18next ---
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue?: string) => defaultValue || key,
  }),
}));

// --- Mock the presign API hook ---
const mockCreateUpload = vi.fn();
const mockSignMultipart = vi.fn();

vi.mock("../hooks/useS3Upload", () => ({
  default: () => ({
    createUpload: mockCreateUpload,
    signMultipart: mockSignMultipart,
    isLoading: false,
    error: null,
  }),
}));

/** Register a file with the mock Uppy and sign its create request as the plugin would. */
async function signCreateFor(
  file: { id: string; name: string; type: string; size: number },
  method: "PUT" | "POST" = "PUT"
) {
  mockFiles.set(file.id, { ...file, meta: {} });
  return capturedPluginOptions.signRequest({ method, key: file.id });
}

// --- Mock useSearchConnectors ---
// Two connectors so the merged FileUploader renders the connector dropdown.
// (With a single destination and no My Assets, main's logic auto-selects it
// and hides the dropdown, which these tests don't exercise.)
const mockConnectors = [
  {
    id: "connector-1",
    name: "Test Bucket",
    type: "s3",
    storageIdentifier: "test-bucket",
    status: "active",
  },
  {
    id: "connector-2",
    name: "Second Bucket",
    type: "s3",
    storageIdentifier: "second-bucket",
    status: "active",
  },
];

vi.mock("@/api/hooks/useSearchConnectors", () => ({
  useSearchConnectors: () => ({
    data: {
      status: "success",
      message: "ok",
      data: { connectors: mockConnectors },
    },
    isLoading: false,
  }),
}));

// --- Mock usePermission ---
// The merged FileUploader gates shared-connector destinations on the
// `upload:connector` permission (My Assets feature). Grant it so the connector
// dropdown renders for these carry-through tests.
vi.mock("@/permissions", () => ({
  usePermission: () => ({
    can: () => true,
  }),
}));

// --- Mock CollectionSelector ---
let collectionSelectorOnChange:
  | ((collections: Array<{ id: string; name: string }>) => void)
  | null = null;
let collectionSelectorDisabled = false;

vi.mock("./CollectionSelector", () => ({
  default: ({
    value,
    onChange,
    disabled,
  }: {
    value: Array<{ id: string; name: string }>;
    onChange: (collections: Array<{ id: string; name: string }>) => void;
    disabled: boolean;
  }) => {
    collectionSelectorOnChange = onChange;
    collectionSelectorDisabled = disabled;
    return (
      <div data-testid="collection-selector" data-disabled={disabled}>
        <span data-testid="collection-selector-value">{JSON.stringify(value)}</span>
        <button
          data-testid="collection-selector-trigger"
          onClick={() =>
            onChange([
              { id: "col-1", name: "Alpha" },
              { id: "col-2", name: "Beta" },
            ])
          }
        >
          Select Collections
        </button>
        <button data-testid="collection-selector-clear" onClick={() => onChange([])}>
          Clear
        </button>
      </div>
    );
  },
  CollectionRef: {},
}));

// --- Mock PathBrowser ---
vi.mock("./PathBrowser", () => ({
  default: () => <div data-testid="path-browser" />,
}));

// --- Helpers ---

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
        staleTime: Infinity,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

// Import the component under test AFTER mocks are set up
import FileUploader from "./FileUploader";

describe("FileUploader integration tests — upload carry-through (Task 7.3)", () => {
  beforeEach(() => {
    capturedPluginOptions = null;
    collectionSelectorOnChange = null;
    collectionSelectorDisabled = false;
    mockFiles.clear();
    mockCreateUpload.mockReset();
    mockSignMultipart.mockReset();
    mockCreateUpload.mockResolvedValue({
      bucket: "test-bucket",
      key: "uploads/test.jpg",
      url: "https://s3.amazonaws.com/test-bucket/uploads/test.jpg?X-Amz-Signature=abc",
      method: "PUT",
      multipart: false,
      expires_in: 3600,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // Helper: select a connector to activate the S3 plugin configuration
  async function selectConnector(user: ReturnType<typeof userEvent.setup>) {
    // The connector select renders with an MUI Select; open it and pick the item
    const connectorSelect = screen.getByLabelText("upload.connectorLabel");
    await user.click(connectorSelect);
    const option = await screen.findByText("Test Bucket (test-bucket)");
    await user.click(option);
  }

  // ─── Requirement 7.1: collection_ids flow into Uppy meta ─────────────────

  describe("collection_ids in Uppy meta (Req 7.1)", () => {
    it("sets collection_ids in Uppy meta when collections are selected", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      // Select connector to trigger plugin configuration
      await selectConnector(user);

      // Select collections via the mock CollectionSelector
      await user.click(screen.getByTestId("collection-selector-trigger"));

      // The Uppy meta should be set with collection_ids
      await waitFor(() => {
        const setOptionsCalls = mockUppyInstance.setOptions.mock.calls;
        const lastCall = setOptionsCalls[setOptionsCalls.length - 1];
        expect(lastCall[0].meta.collection_ids).toEqual(["col-1", "col-2"]);
      });
    });

    it("updates Uppy meta with empty collection_ids when selection is cleared", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Select collections
      await user.click(screen.getByTestId("collection-selector-trigger"));

      // Clear collections
      await user.click(screen.getByTestId("collection-selector-clear"));

      await waitFor(() => {
        const setOptionsCalls = mockUppyInstance.setOptions.mock.calls;
        const lastCall = setOptionsCalls[setOptionsCalls.length - 1];
        expect(lastCall[0].meta.collection_ids).toEqual([]);
      });
    });
  });

  // ─── Requirement 7.2, 7.3: collection_ids in presigned-URL requests ──────

  describe("collection_ids in presigned-URL requests (Req 7.2, 7.3)", () => {
    it("passes collection_ids on the single-part create request (PUT)", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Select collections
      await user.click(screen.getByTestId("collection-selector-trigger"));

      // Wait for the AwsS3 plugin to be installed with a signRequest
      await waitFor(() => {
        expect(capturedPluginOptions).not.toBeNull();
        expect(capturedPluginOptions.signRequest).toBeDefined();
      });

      // Simulate the single-part create request (PUT) the plugin would sign
      const mockFile = { id: "file-1", name: "photo.jpg", type: "image/jpeg", size: 1024 };
      const signed = await signCreateFor(mockFile, "PUT");

      // Assert createUpload was called with collection_ids and the PUT method
      expect(mockCreateUpload).toHaveBeenCalledWith(
        expect.objectContaining({
          connector_id: "connector-1",
          filename: "photo.jpg",
          content_type: "image/jpeg",
          file_size: 1024,
          collection_ids: ["col-1", "col-2"],
          method: "PUT",
        })
      );
      // The server's key and URL are handed back to the plugin, and the key is stamped on
      // the file so later multipart requests can be routed.
      expect(signed).toEqual({
        url: "https://s3.amazonaws.com/test-bucket/uploads/test.jpg?X-Amz-Signature=abc",
        key: "uploads/test.jpg",
      });
      expect(mockUppyInstance.setFileMeta).toHaveBeenCalledWith(
        "file-1",
        expect.objectContaining({ s3Key: "uploads/test.jpg", s3ConnectorId: "connector-1" })
      );
    });

    it("passes collection_ids on the CreateMultipartUpload request and routes later requests", async () => {
      const user = userEvent.setup();

      // The create request for a large file is a CreateMultipartUpload (POST)
      mockCreateUpload.mockResolvedValue({
        bucket: "test-bucket",
        key: "uploads/large-video.mp4",
        url: "https://s3.amazonaws.com/test-bucket/uploads/large-video.mp4?uploads",
        method: "POST",
        multipart: true,
        expires_in: 3600,
      });
      mockSignMultipart.mockResolvedValue({
        operation: "part",
        method: "PUT",
        presigned_url: "https://s3.amazonaws.com/part",
        expires_in: 3600,
        part_number: 1,
      });

      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Select collections
      await user.click(screen.getByTestId("collection-selector-trigger"));

      // Wait for the AwsS3 plugin to be installed with a signRequest
      await waitFor(() => {
        expect(capturedPluginOptions).not.toBeNull();
        expect(capturedPluginOptions.signRequest).toBeDefined();
      });

      // Simulate the CreateMultipartUpload request (POST, no uploadId)
      const mockFile = {
        id: "file-1",
        name: "large-video.mp4",
        type: "video/mp4",
        size: 200 * 1024 * 1024,
      };
      expect(capturedPluginOptions.shouldUseMultipart(mockFile)).toBe(true);
      const created = await signCreateFor(mockFile, "POST");

      // Assert createUpload was called with collection_ids and the POST method
      expect(mockCreateUpload).toHaveBeenCalledWith(
        expect.objectContaining({
          connector_id: "connector-1",
          filename: "large-video.mp4",
          content_type: "video/mp4",
          file_size: 200 * 1024 * 1024,
          collection_ids: ["col-1", "col-2"],
          method: "POST",
        })
      );
      expect(created.key).toBe("uploads/large-video.mp4");

      // Every later request carries the server key and an uploadId and is routed to the
      // connector stamped on the file: a part, the ListParts used to resume, the completion
      // and the abort.
      await capturedPluginOptions.signRequest({
        method: "PUT",
        key: "uploads/large-video.mp4",
        uploadId: "upload-123",
        partNumber: 1,
      });
      expect(mockSignMultipart).toHaveBeenLastCalledWith({
        connector_id: "connector-1",
        upload_id: "upload-123",
        key: "uploads/large-video.mp4",
        operation: "part",
        part_number: 1,
      });
      for (const [method, operation] of [
        ["GET", "list"],
        ["POST", "complete"],
        ["DELETE", "abort"],
      ] as const) {
        await capturedPluginOptions.signRequest({
          method,
          key: "uploads/large-video.mp4",
          uploadId: "upload-123",
        });
        expect(mockSignMultipart).toHaveBeenLastCalledWith({
          connector_id: "connector-1",
          upload_id: "upload-123",
          key: "uploads/large-video.mp4",
          operation,
        });
      }
    });
  });

  // ─── Requirement 7.4: CollectionSelector disabled during upload ───────────

  describe("CollectionSelector disabled during upload (Req 7.4)", () => {
    it("disables the CollectionSelector when upload is in progress", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Initially not disabled
      expect(screen.getByTestId("collection-selector")).toHaveAttribute("data-disabled", "false");

      // Emit the 'upload' event to signal upload start
      act(() => {
        mockUppyInstance._emit("upload");
      });

      // Should now be disabled
      await waitFor(() => {
        expect(screen.getByTestId("collection-selector")).toHaveAttribute("data-disabled", "true");
      });
    });

    it("re-enables the CollectionSelector when upload completes", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Start upload
      act(() => {
        mockUppyInstance._emit("upload");
      });

      await waitFor(() => {
        expect(screen.getByTestId("collection-selector")).toHaveAttribute("data-disabled", "true");
      });

      // Complete upload
      act(() => {
        mockUppyInstance._emit("complete", { successful: [] });
      });

      await waitFor(() => {
        expect(screen.getByTestId("collection-selector")).toHaveAttribute("data-disabled", "false");
      });
    });

    it("re-enables the CollectionSelector when upload is cancelled", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Start upload
      act(() => {
        mockUppyInstance._emit("upload");
      });

      await waitFor(() => {
        expect(screen.getByTestId("collection-selector")).toHaveAttribute("data-disabled", "true");
      });

      // Cancel upload
      act(() => {
        mockUppyInstance._emit("cancel-all");
      });

      await waitFor(() => {
        expect(screen.getByTestId("collection-selector")).toHaveAttribute("data-disabled", "false");
      });
    });
  });

  // ─── Requirement 7.5: Completion notice with ≥1 collection ────────────────

  describe("completion notice (Req 7.5)", () => {
    it("shows info notice when upload completes with ≥1 collection selected", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Select collections
      await user.click(screen.getByTestId("collection-selector-trigger"));

      // Start and complete upload with successful files
      act(() => {
        mockUppyInstance._emit("upload");
      });

      act(() => {
        mockUppyInstance._emit("complete", {
          successful: [{ name: "file1.jpg" }],
        });
      });

      // The info method should have been called with the association notice
      await waitFor(() => {
        expect(mockUppyInstance.info).toHaveBeenCalledWith(
          "Files will be added to the selected collections after processing completes.",
          "info",
          5000
        );
      });
    });

    it("does NOT show info notice when upload completes with no collections selected", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Do NOT select collections (empty selection by default)

      // Start and complete upload with successful files
      act(() => {
        mockUppyInstance._emit("upload");
      });

      act(() => {
        mockUppyInstance._emit("complete", {
          successful: [{ name: "file1.jpg" }],
        });
      });

      // info should NOT be called with the association notice
      expect(mockUppyInstance.info).not.toHaveBeenCalled();
    });

    it("does NOT show info notice when upload completes with zero successful files", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Select collections
      await user.click(screen.getByTestId("collection-selector-trigger"));

      // Start and complete upload with NO successful files
      act(() => {
        mockUppyInstance._emit("upload");
      });

      act(() => {
        mockUppyInstance._emit("complete", { successful: [] });
      });

      // info should NOT be called
      expect(mockUppyInstance.info).not.toHaveBeenCalled();
    });
  });

  // ─── Requirement 1.4: Empty selection uploads normally ────────────────────

  describe("empty selection uploads normally (Req 1.4)", () => {
    it("uploads without collection_ids when no collections are selected", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Do NOT select any collections — the default state is empty

      // Wait for the AwsS3 plugin to be installed with a signRequest
      await waitFor(() => {
        expect(capturedPluginOptions).not.toBeNull();
        expect(capturedPluginOptions.signRequest).toBeDefined();
      });

      // Simulate a single-part upload
      await signCreateFor({ id: "file-1", name: "photo.jpg", type: "image/jpeg", size: 1024 });

      // Assert createUpload was called with empty collection_ids
      expect(mockCreateUpload).toHaveBeenCalledWith(
        expect.objectContaining({
          connector_id: "connector-1",
          filename: "photo.jpg",
          collection_ids: [],
        })
      );
    });

    it("Uppy meta has empty collection_ids when no collections are selected", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // With no collections selected, meta should have empty collection_ids
      await waitFor(() => {
        const setOptionsCalls = mockUppyInstance.setOptions.mock.calls;
        const lastCall = setOptionsCalls[setOptionsCalls.length - 1];
        expect(lastCall[0].meta.collection_ids).toEqual([]);
      });
    });
  });
});
