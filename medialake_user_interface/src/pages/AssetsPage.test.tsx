import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock dependencies before importing the component
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}));

vi.mock("react-router", () => ({
  useNavigate: () => vi.fn(),
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

const mockUseSearchConnectors = vi.fn();
vi.mock("@/api/hooks/useSearchConnectors", () => ({
  useSearchConnectors: (...args: any[]) => mockUseSearchConnectors(...args),
}));

const mockUseMyAssetsConnector = vi.fn();
vi.mock("@/api/hooks/useMyAssetsConnector", () => ({
  useMyAssetsConnector: (...args: any[]) => mockUseMyAssetsConnector(...args),
}));

// Grant upload permission so the upload entry point renders in tests.
vi.mock("@/permissions", () => ({
  usePermission: () => ({ can: () => true }),
}));

vi.mock("@/contexts/FeatureFlagsContext", () => ({
  useFeatureFlag: (flag: string) => flag === "my-assets-enabled",
}));

vi.mock("@/features/upload", () => ({
  S3UploaderModal: (props: any) => (props.open ? <div data-testid="upload-modal" /> : null),
}));

vi.mock("@/components/common/layout", () => ({
  PageHeader: ({ title }: any) => <div data-testid="page-header">{title}</div>,
  PageContent: ({ children }: any) => <div>{children}</div>,
}));

const mockAssetExplorer = vi.fn();
vi.mock("@/features/assets/AssetExplorer", () => ({
  default: (props: any) => {
    mockAssetExplorer(props);
    return (
      <div data-testid="asset-explorer">
        {props.emptyStateContent && <div data-testid="empty-state">{props.emptyStateContent}</div>}
      </div>
    );
  },
}));

import AssetsPage from "./AssetsPage";

describe("AssetsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSearchConnectors.mockReturnValue({
      data: {
        status: "200",
        message: "ok",
        data: {
          connectors: [
            {
              id: "c1",
              name: "Prod",
              type: "s3",
              storageIdentifier: "prod-bucket",
              status: "active",
            },
          ],
        },
      },
      isLoading: false,
    });
    mockUseMyAssetsConnector.mockReturnValue({
      connector: {
        id: "my-assets-1",
        name: "My Assets",
        type: "my-assets",
        storageIdentifier: "personal-bucket",
        objectPrefix: "user123/",
        status: "active",
        region: "us-east-1",
      },
      isLoading: false,
      error: null,
    });
  });

  it("renders My Assets sidebar item", () => {
    render(<AssetsPage />);
    expect(screen.getAllByText("assetsPage.myAssets").length).toBeGreaterThanOrEqual(1);
  });

  it("renders connector items in sidebar", () => {
    render(<AssetsPage />);
    expect(screen.getAllByText("Prod").length).toBeGreaterThanOrEqual(1);
  });

  it("shows AssetExplorer with empty state when My Assets is selected", async () => {
    const user = userEvent.setup();
    render(<AssetsPage />);

    // Find the My Assets sidebar button via the Personal chip
    const personalChip = screen.getByText("Personal");
    const sidebarButton = personalChip.closest("[role='button']");
    expect(sidebarButton).not.toBeNull();
    await user.click(sidebarButton!);

    expect(screen.getByTestId("asset-explorer")).toBeInTheDocument();
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });

  it("empty state shows correct copy", async () => {
    const user = userEvent.setup();
    render(<AssetsPage />);

    const personalChip = screen.getByText("Personal");
    await user.click(personalChip.closest("[role='button']")!);

    expect(screen.getByText("Upload your first file to My Assets")).toBeInTheDocument();
  });

  it("AssetExplorer receives objectPrefix from connector", async () => {
    const user = userEvent.setup();
    render(<AssetsPage />);

    const personalChip = screen.getByText("Personal");
    await user.click(personalChip.closest("[role='button']")!);

    expect(mockAssetExplorer).toHaveBeenCalledWith(
      expect.objectContaining({ objectPrefix: "user123/" })
    );
  });

  it("shows loading state while myAssetsConnector is loading", async () => {
    mockUseMyAssetsConnector.mockReturnValue({
      connector: null,
      isLoading: true,
      error: null,
    });

    const user = userEvent.setup();
    render(<AssetsPage />);

    // My Assets sidebar item should still render (loading indicator in sidebar)
    // Click it to see the loading state in the main panel
    const myAssetsItems = screen.getAllByText("assetsPage.myAssets");
    const sidebarButton = myAssetsItems[0].closest("[role='button']");
    if (sidebarButton) {
      await user.click(sidebarButton);
    }

    // CircularProgress should be rendered in the main panel
    expect(screen.getAllByRole("progressbar").length).toBeGreaterThanOrEqual(1);
  });

  it("opens upload modal from My Assets header", async () => {
    const user = userEvent.setup();
    render(<AssetsPage />);

    // Select My Assets
    const personalChip = screen.getByText("Personal");
    await user.click(personalChip.closest("[role='button']")!);

    // Click the header Upload button
    const uploadButtons = screen
      .getAllByRole("button")
      .filter((btn) => btn.textContent === "Upload");
    expect(uploadButtons.length).toBeGreaterThanOrEqual(1);
    await user.click(uploadButtons[0]);

    expect(screen.getByTestId("upload-modal")).toBeInTheDocument();
  });
});
