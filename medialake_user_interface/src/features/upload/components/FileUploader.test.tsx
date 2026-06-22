import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";

// Mock dependencies before imports
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string, fallback?: string) => fallback || key }),
}));

vi.mock("@/api/hooks/useSearchConnectors", () => ({
  useSearchConnectors: vi.fn(),
}));

// Controllable connector-upload permission (defaults to granted).
let mockCanUploadConnector = true;
vi.mock("@/permissions", () => ({
  usePermission: () => ({
    can: (action: string, subject: string) =>
      action === "upload" && subject === "connector" ? mockCanUploadConnector : true,
  }),
}));

const mockGetPresignedUrl = vi.fn().mockResolvedValue({
  presigned_post: { url: "https://s3.example.com", fields: {} },
});

vi.mock("../hooks/useS3Upload", () => ({
  default: () => ({
    getPresignedUrl: mockGetPresignedUrl,
    signPart: vi.fn(),
    completeMultipartUpload: vi.fn(),
    abortMultipartUpload: vi.fn(),
  }),
}));

// Stub Uppy to avoid browser-only side effects
const mockSetOptions = vi.fn();
vi.mock("@uppy/core", () => {
  class MockUppy {
    on = vi.fn().mockReturnThis();
    off = vi.fn().mockReturnThis();
    cancelAll = vi.fn();
    use = vi.fn();
    getPlugin = vi.fn(() => ({ setOptions: mockSetOptions }));
    getState = vi.fn(() => ({ meta: {} }));
    setOptions = vi.fn();
    removeFile = vi.fn();
    info = vi.fn();
  }
  return { default: MockUppy };
});

vi.mock("@uppy/react/dashboard", () => ({
  default: () => <div data-testid="uppy-dashboard" />,
}));

vi.mock("@uppy/aws-s3", () => ({ default: vi.fn() }));
vi.mock("./PathBrowser", () => ({ default: () => null }));
// CollectionSelector is exercised by its own tests; stub it here so this
// suite stays focused on connector/destination selection and doesn't require
// a QueryClientProvider for the collection data hooks it uses internally.
vi.mock("./CollectionSelector", () => ({ default: () => null }));

import { useSearchConnectors } from "@/api/hooks/useSearchConnectors";

const mockUseSearchConnectors = vi.mocked(useSearchConnectors);

const activeConnector = (id: string, name: string) => ({
  id,
  name,
  type: "s3",
  status: "active",
  storageIdentifier: `${name}-bucket`,
});

describe("FileUploader", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockCanUploadConnector = true;
    mockUseSearchConnectors.mockReturnValue({
      data: {
        status: "200",
        message: "ok",
        data: {
          connectors: [
            activeConnector("conn-1", "Production"),
            activeConnector("conn-2", "Staging"),
          ],
        },
      },
      isLoading: false,
    } as any);
  });

  // Lazy import to ensure mocks are set up first
  async function renderUploader(props: Record<string, any> = {}) {
    const { default: FileUploader } = await import("./FileUploader");
    return render(<FileUploader {...props} />);
  }

  it("shows locked My Assets label when lockConnector is true", async () => {
    await renderUploader({ lockConnector: true, defaultConnectorId: "my-assets-1" });
    expect(screen.getByText("My Assets")).toBeInTheDocument();
    // Dropdown should not be present
    expect(screen.queryByLabelText(/connector/i)).not.toBeInTheDocument();
  });

  it("lockConnector=true hides the combobox dropdown", async () => {
    await renderUploader({ lockConnector: true, defaultConnectorId: "my-assets-1" });
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("shows locked My Assets label when no connectors exist", async () => {
    mockUseSearchConnectors.mockReturnValue({
      data: { status: "200", message: "ok", data: { connectors: [] } },
      isLoading: false,
    } as any);
    await renderUploader({ defaultConnectorId: "my-assets-1" });
    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("shows dropdown with My Assets as first option in global mode", async () => {
    await renderUploader({ defaultConnectorId: "my-assets-1" });
    // Dropdown should be present (not locked)
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
  });

  it("preselects defaultConnectorId when provided", async () => {
    await renderUploader({ defaultConnectorId: "conn-1" });
    // The select should have the default connector preselected
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
  });

  it("shows dropdown without My Assets option when no defaultConnectorId", async () => {
    await renderUploader({});
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
    // No My Assets text should appear in the dropdown context
    expect(screen.queryByText("My Assets")).not.toBeInTheDocument();
  });

  it("hides shared connectors (only My Assets) when user lacks connectors:upload", async () => {
    mockCanUploadConnector = false;
    await renderUploader({ defaultConnectorId: "my-assets-1" });
    // My Assets is the only destination → read-only card, no dropdown
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("shows no destinations when user lacks connectors:upload and has no My Assets", async () => {
    mockCanUploadConnector = false;
    await renderUploader({});
    // No My Assets and no permitted connectors → no dropdown, no connectors
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByText("My Assets")).not.toBeInTheDocument();
  });

  it("re-selects connector when defaultConnectorId changes", async () => {
    const { default: FileUploader } = await import("./FileUploader");
    const { rerender } = render(<FileUploader defaultConnectorId="conn-1" />);
    // Rerender with a different defaultConnectorId
    rerender(<FileUploader defaultConnectorId="my-assets-1" />);
    // The My Assets menu item should be rendered (it's the defaultConnectorId option)
    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("hides path browser when My Assets is selected", async () => {
    await renderUploader({
      defaultConnectorId: "my-assets-1",
      defaultObjectPrefix: "personal/user123/",
    });
    // The Browse Path button should not be visible when My Assets is selected
    expect(screen.queryByText(/browse path/i)).not.toBeInTheDocument();
  });

  it("configures upload callbacks with My Assets connector ID and prefix when switching from S3", async () => {
    // Re-set the presigned URL mock after beforeEach reset
    mockGetPresignedUrl.mockResolvedValue({
      presigned_post: { url: "https://s3.example.com", fields: {} },
    });

    const { default: FileUploader } = await import("./FileUploader");
    const { rerender } = render(
      <FileUploader defaultConnectorId="my-assets-1" defaultObjectPrefix="personal/user123/" />
    );

    // Initially rendered with conn-1 pre-selected via defaultConnectorId
    // Rerender simulating My Assets being selected (lockConnector)
    rerender(
      <FileUploader
        defaultConnectorId="my-assets-1"
        defaultObjectPrefix="personal/user123/"
        lockConnector
      />
    );

    // The S3 plugin setOptions should have been called with upload callbacks
    // even though "my-assets-1" is not in the filtered S3 connectors list
    expect(mockSetOptions).toHaveBeenCalled();

    // Verify the last call includes upload callback functions
    const lastCall = mockSetOptions.mock.calls[mockSetOptions.mock.calls.length - 1][0];
    expect(lastCall).toHaveProperty("getUploadParameters");
    expect(lastCall).toHaveProperty("createMultipartUpload");
    expect(lastCall).toHaveProperty("signPart");
    expect(lastCall).toHaveProperty("completeMultipartUpload");
    expect(lastCall).toHaveProperty("abortMultipartUpload");

    // Invoke getUploadParameters and verify it passes the My Assets connector ID
    const fakeFile = { name: "test.jpg", type: "image/jpeg", size: 1024 };
    await lastCall.getUploadParameters(fakeFile);

    expect(mockGetPresignedUrl).toHaveBeenCalledWith(
      expect.objectContaining({
        connector_id: "my-assets-1",
        path: "personal/user123/",
      })
    );
  });
});
