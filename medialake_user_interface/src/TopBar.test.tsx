import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Capture S3UploaderModal props
const mockS3UploaderModal = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string, fallback?: string) => fallback || key }),
}));

vi.mock("react-router", () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: "/", search: "" }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock("./contexts/ChatContext", () => ({
  useChat: () => ({ toggleChat: vi.fn(), isOpen: false }),
}));

vi.mock("./hooks/useTheme", () => ({
  useTheme: () => ({ theme: "light" }),
}));

vi.mock("./contexts/DirectionContext", () => ({
  useDirection: () => ({ direction: "ltr" }),
}));

vi.mock("./contexts/FeatureFlagsContext", () => ({
  useFeatureFlag: () => false,
}));

vi.mock("./stores/searchStore", () => ({
  useSearchFilters: () => ({}),
  useSearchQuery: () => "",
  useSemanticSearch: () => false,
  useDomainActions: () => ({ setQuery: vi.fn(), setIsSemantic: vi.fn() }),
  useUIActions: () => ({ openFilterModal: vi.fn() }),
}));

vi.mock("./components/search/FilterModal", () => ({
  default: () => null,
}));

vi.mock("./components/NotificationCenter", () => ({
  NotificationCenter: () => null,
}));

vi.mock("./components/TopBar/SemanticModeToggle", () => ({
  default: () => null,
}));

vi.mock("./components/TopBar/SearchModeSelector", () => ({
  default: () => null,
}));

vi.mock("./features/settings/system/hooks/useSystemSettings", () => ({
  useSemanticSearchStatus: () => ({
    isSemanticSearchEnabled: false,
    isConfigured: false,
    providerData: null,
  }),
}));

const mockUseMyAssetsConnector = vi.fn();
vi.mock("./api/hooks/useMyAssetsConnector", () => ({
  useMyAssetsConnector: (...args: any[]) => mockUseMyAssetsConnector(...args),
}));

// Grant upload permission so the upload entry point renders in tests.
vi.mock("./permissions", () => ({
  usePermission: () => ({ can: () => true }),
}));

vi.mock("./features/upload", () => ({
  S3UploaderModal: (props: any) => {
    mockS3UploaderModal(props);
    return props.open ? <div data-testid="upload-modal" /> : null;
  },
}));

import TopBar from "./TopBar";

describe("TopBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMyAssetsConnector.mockReturnValue({
      connector: {
        id: "my-assets-1",
        objectPrefix: "personal/user123/",
      },
      isLoading: false,
      error: null,
    });
  });

  it("opens upload modal with My Assets preselected", async () => {
    const user = userEvent.setup();
    render(<TopBar />);

    // Click the upload icon button
    const uploadButton = screen.getByRole("button", { name: "" });
    // Find the button that contains CloudUploadIcon — it's an IconButton
    const buttons = screen.getAllByRole("button");
    const uploadBtn = buttons.find((btn) =>
      btn.querySelector("svg[data-testid='CloudUploadIcon']")
    );
    expect(uploadBtn).toBeDefined();
    await user.click(uploadBtn!);

    expect(mockS3UploaderModal).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultConnectorId: "my-assets-1",
        defaultObjectPrefix: "personal/user123/",
      })
    );
  });

  it("modal does not receive lockConnector", () => {
    render(<TopBar />);

    // S3UploaderModal is rendered (closed) on mount
    expect(mockS3UploaderModal).toHaveBeenCalledWith(
      expect.not.objectContaining({ lockConnector: true })
    );
  });

  it("passes undefined defaultConnectorId when myAssetsConnector is null", () => {
    mockUseMyAssetsConnector.mockReturnValue({
      connector: null,
      isLoading: false,
      error: null,
    });

    render(<TopBar />);

    expect(mockS3UploaderModal).toHaveBeenCalledWith(
      expect.objectContaining({ defaultConnectorId: undefined })
    );
  });
});
