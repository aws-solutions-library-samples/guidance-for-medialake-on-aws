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
  cancelAll: ReturnType<typeof vi.fn>;
  removeFile: ReturnType<typeof vi.fn>;
  info: ReturnType<typeof vi.fn>;
  _eventHandlers: Map<string, UppyEventHandler[]>;
  _emit: (event: string, ...args: any[]) => void;
};

let mockPluginSetOptions: ReturnType<typeof vi.fn>;
let capturedPluginOptions: any;

function createMockUppy() {
  const eventHandlers = new Map<string, UppyEventHandler[]>();
  mockPluginSetOptions = vi.fn((opts: any) => {
    capturedPluginOptions = opts;
  });

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
    use: vi.fn(),
    setOptions: vi.fn(),
    getState: vi.fn(() => ({ meta: {} })),
    getPlugin: vi.fn(() => ({
      setOptions: mockPluginSetOptions,
    })),
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

// --- Mock @uppy/aws-s3 ---
vi.mock("@uppy/aws-s3", () => ({
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

// --- Mock getPresignedUrl ---
const mockGetPresignedUrl = vi.fn();
const mockSignPart = vi.fn();
const mockCompleteMultipartUpload = vi.fn();
const mockAbortMultipartUpload = vi.fn();

vi.mock("../hooks/useS3Upload", () => ({
  default: () => ({
    getPresignedUrl: mockGetPresignedUrl,
    signPart: mockSignPart,
    completeMultipartUpload: mockCompleteMultipartUpload,
    abortMultipartUpload: mockAbortMultipartUpload,
    isLoading: false,
    error: null,
  }),
}));

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
    mockGetPresignedUrl.mockReset();
    mockGetPresignedUrl.mockResolvedValue({
      bucket: "test-bucket",
      key: "uploads/test.jpg",
      presigned_post: {
        url: "https://s3.amazonaws.com/test-bucket",
        fields: { key: "uploads/test.jpg" },
      },
      expires_in: 3600,
      multipart: false,
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
    it("passes collection_ids in single-part presigned-URL request via getUploadParameters", async () => {
      const user = userEvent.setup();
      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Select collections
      await user.click(screen.getByTestId("collection-selector-trigger"));

      // Wait for plugin options to be configured
      await waitFor(() => {
        expect(capturedPluginOptions).not.toBeNull();
        expect(capturedPluginOptions.getUploadParameters).toBeDefined();
      });

      // Simulate a single-part upload by calling getUploadParameters
      const mockFile = { name: "photo.jpg", type: "image/jpeg", size: 1024 };
      await capturedPluginOptions.getUploadParameters(mockFile);

      // Assert getPresignedUrl was called with collection_ids
      expect(mockGetPresignedUrl).toHaveBeenCalledWith(
        expect.objectContaining({
          connector_id: "connector-1",
          filename: "photo.jpg",
          content_type: "image/jpeg",
          file_size: 1024,
          collection_ids: ["col-1", "col-2"],
        })
      );
    });

    it("passes collection_ids in multipart presigned-URL request via createMultipartUpload", async () => {
      const user = userEvent.setup();

      // Mock getPresignedUrl to return multipart response for large files
      mockGetPresignedUrl.mockResolvedValue({
        bucket: "test-bucket",
        key: "uploads/large-video.mp4",
        upload_id: "upload-123",
        multipart: true,
        part_size: 5 * 1024 * 1024,
        total_parts: 20,
        expires_in: 3600,
      });

      render(<FileUploader />, { wrapper: createWrapper() });

      await selectConnector(user);

      // Select collections
      await user.click(screen.getByTestId("collection-selector-trigger"));

      // Wait for plugin options to be configured
      await waitFor(() => {
        expect(capturedPluginOptions).not.toBeNull();
        expect(capturedPluginOptions.createMultipartUpload).toBeDefined();
      });

      // Simulate a multipart upload by calling createMultipartUpload
      const mockFile = {
        id: "file-1",
        name: "large-video.mp4",
        type: "video/mp4",
        size: 200 * 1024 * 1024,
      };
      await capturedPluginOptions.createMultipartUpload(mockFile);

      // Assert getPresignedUrl was called with collection_ids
      expect(mockGetPresignedUrl).toHaveBeenCalledWith(
        expect.objectContaining({
          connector_id: "connector-1",
          filename: "large-video.mp4",
          content_type: "video/mp4",
          file_size: 200 * 1024 * 1024,
          collection_ids: ["col-1", "col-2"],
        })
      );
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

      // Wait for plugin options to be configured
      await waitFor(() => {
        expect(capturedPluginOptions).not.toBeNull();
        expect(capturedPluginOptions.getUploadParameters).toBeDefined();
      });

      // Simulate a single-part upload
      const mockFile = { name: "photo.jpg", type: "image/jpeg", size: 1024 };
      await capturedPluginOptions.getUploadParameters(mockFile);

      // Assert getPresignedUrl was called with empty collection_ids
      expect(mockGetPresignedUrl).toHaveBeenCalledWith(
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
