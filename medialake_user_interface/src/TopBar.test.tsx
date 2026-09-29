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
  useFeatureFlag: (flag: string) => flag === "my-assets-enabled",
}));

vi.mock("./stores/searchStore", () => ({
  useSearchFilters: () => ({}),
  useSearchQuery: () => "",
  useSemanticSearch: () => false,
  useDomainActions: () => ({ setQuery: vi.fn(), setIsSemantic: vi.fn() }),
  useUIActions: () => ({ openFilterModal: vi.fn() }),
  useActiveFilterCount: () => 0,
  appendFiltersToUrlParams: vi.fn(),
  useSearchStore: { getState: () => ({ semanticMode: "clip", searchModes: ["visual"] }) },
}));

// Saved / recent searches dropdown data
const mockSuggestions = vi.fn();
const mockRunSearch = vi.fn();
vi.mock("./features/search-history/hooks", () => ({
  useSearchSuggestions: (...args: unknown[]) => mockSuggestions(...args),
  useRunSearch: () => mockRunSearch,
}));
vi.mock("./features/search-history/api", () => ({
  useRemoveHistoryEntry: () => ({ mutate: vi.fn() }),
  useClearSearchHistory: () => ({ mutate: vi.fn() }),
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

const EMPTY_SUGGESTIONS = {
  items: [],
  savedItems: [],
  historyItems: [],
  totalSaved: 0,
  hasAny: false,
};

const savedItem = {
  kind: "saved",
  id: "saved-s1",
  definition: { v: 1, q: "sunset", semantic: false },
  saved: {
    id: "s1",
    name: "Sunsets",
    definition: { v: 1, q: "sunset", semantic: false },
    fingerprint: "f1",
    createdAt: "2026-09-01T00:00:00Z",
    updatedAt: "2026-09-01T00:00:00Z",
  },
};
const historyItem = {
  kind: "history",
  id: "history-f2",
  definition: { v: 1, q: "beach", semantic: false },
  entry: {
    fingerprint: "f2",
    definition: { v: 1, q: "beach", semantic: false },
    searchedAt: "2026-09-02T00:00:00Z",
  },
};
const WITH_SUGGESTIONS = {
  items: [savedItem, historyItem],
  savedItems: [savedItem],
  historyItems: [historyItem],
  totalSaved: 1,
  hasAny: true,
};

describe("TopBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSuggestions.mockReturnValue(EMPTY_SUGGESTIONS);
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

  describe("saved and recent searches dropdown", () => {
    it("renders nothing when the user has no saved or recent searches", async () => {
      const user = userEvent.setup();
      render(<TopBar />);
      await user.click(screen.getByRole("combobox"));
      expect(screen.queryByRole("listbox")).toBeNull();
      expect(screen.getByRole("combobox")).toHaveAttribute("aria-expanded", "false");
    });

    it("lists saved searches before recent searches on focus", async () => {
      mockSuggestions.mockReturnValue(WITH_SUGGESTIONS);
      const user = userEvent.setup();
      render(<TopBar />);
      await user.click(screen.getByRole("combobox"));

      const options = screen.getAllByRole("option");
      expect(options.map((o) => o.textContent)).toEqual([
        expect.stringContaining("Sunsets"),
        expect.stringContaining("beach"),
      ]);
      expect(screen.getByRole("combobox")).toHaveAttribute("aria-expanded", "true");
    });

    it("runs a search chosen with the keyboard", async () => {
      mockSuggestions.mockReturnValue(WITH_SUGGESTIONS);
      const user = userEvent.setup();
      render(<TopBar />);
      const input = screen.getByRole("combobox");
      await user.click(input);
      await user.keyboard("{ArrowDown}{ArrowDown}");
      expect(input).toHaveAttribute("aria-activedescendant", "search-suggestion-history-f2");
      await user.keyboard("{Enter}");
      expect(mockRunSearch).toHaveBeenCalledWith(historyItem.definition);
      expect(screen.queryByRole("listbox")).toBeNull();
    });

    it("runs a search chosen with the mouse", async () => {
      mockSuggestions.mockReturnValue(WITH_SUGGESTIONS);
      const user = userEvent.setup();
      render(<TopBar />);
      await user.click(screen.getByRole("combobox"));
      await user.click(screen.getByRole("option", { name: /Sunsets/ }));
      expect(mockRunSearch).toHaveBeenCalledWith(savedItem.definition);
    });

    it("closes on Escape", async () => {
      mockSuggestions.mockReturnValue(WITH_SUGGESTIONS);
      const user = userEvent.setup();
      render(<TopBar />);
      await user.click(screen.getByRole("combobox"));
      expect(screen.getByRole("listbox")).toBeInTheDocument();
      await user.keyboard("{Escape}");
      expect(screen.queryByRole("listbox")).toBeNull();
    });
  });
});
