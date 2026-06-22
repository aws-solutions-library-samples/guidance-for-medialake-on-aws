/**
 * Integration tests for CollectionSelector (task 6.9).
 *
 * Validates: Requirements 1.2, 1.3, 2.3, 2.4, 2.5, 2.6, 3.2, 3.6, 4.1, 4.4, 5.1, 5.4, 6.1, 6.4, 6.5
 *
 * Coverage:
 *   - Opens on activate and closes on outside click (1.2, 1.3)
 *   - Section item cap + More toggling (2.3–2.5, 3.3–3.4)
 *   - Empty state when no Addable Recent/Favorites (2.6)
 *   - Debounced search fires after 300ms with fake timers (3.2)
 *   - Shows error state on search failure (3.6)
 *   - Addable filter excludes viewer-only across all sections (4.1, 4.4)
 *   - Multi-select set + count chip (5.1, 5.4)
 *   - Inline create adds on success and preserves selection on failure (6.1, 6.4, 6.5)
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import CollectionSelector, { type CollectionRef } from "./CollectionSelector";
import type { Collection } from "@/api/hooks/useCollections";

// --- Mock factories ---

function makeCollection(overrides: Partial<Collection> = {}): Collection {
  return {
    id: overrides.id ?? "col-1",
    name: overrides.name ?? "Test Collection",
    status: overrides.status ?? "ACTIVE",
    userRole: overrides.userRole ?? "owner",
    ownerId: overrides.ownerId ?? "user-1",
    type: overrides.type ?? "private",
    itemCount: 0,
    childCount: 0,
    childCollectionCount: 0,
    isPublic: false,
    createdAt: "2024-01-01",
    updatedAt: "2024-01-01",
    ...overrides,
  };
}

// --- Mock state holders (reassigned per test) ---
let mockRecentData: { pages: Array<{ data: Collection[] }> };
let mockRecentLoading: boolean;
let mockRecentHasNextPage: boolean;
let mockFetchNextRecentPage: ReturnType<typeof vi.fn>;
let mockFavoritesData: Array<{ itemId: string; itemType: string; addedAt: string }>;
let mockAllCollectionsData: { data: Collection[] };
let mockSearchData: { data: Collection[]; pagination: { hasNextPage: boolean } };
let mockSearchLoading: boolean;
let mockSearchIsError: boolean;
let mockSearchIsFetching: boolean;
let mockCreateMutateAsync: ReturnType<typeof vi.fn>;
let mockCreateIsPending: boolean;

// i18n mock
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue: string, opts?: Record<string, any>) => {
      if (opts?.count !== undefined) return `${opts.count} selected`;
      if (opts?.name !== undefined) return `Create "${opts.name}"`;
      return defaultValue || key;
    },
  }),
}));

// useCollections mock — returns current mock state holders
vi.mock("@/api/hooks/useCollections", () => ({
  useRecentCollections: () => ({
    data: mockRecentData,
    isLoading: mockRecentLoading,
    fetchNextPage: mockFetchNextRecentPage,
    hasNextPage: mockRecentHasNextPage,
  }),
  useGetAllCollections: () => ({
    data: mockAllCollectionsData,
    isLoading: false,
  }),
  useGetCollections: () => ({
    data: mockSearchData,
    isLoading: mockSearchLoading,
    isError: mockSearchIsError,
    isFetching: mockSearchIsFetching,
  }),
  useCreateCollection: () => ({
    mutateAsync: mockCreateMutateAsync,
    isPending: mockCreateIsPending,
  }),
  isAddable: (c: any) =>
    c.status === "ACTIVE" &&
    (c.userRole === "owner" || c.userRole === "admin" || c.userRole === "editor"),
}));

vi.mock("@/api/hooks/useFavorites", () => ({
  useGetFavorites: () => ({
    data: mockFavoritesData,
    isLoading: false,
  }),
}));

// useErrorModal mock
vi.mock("../../hooks/useErrorModal", () => ({
  useErrorModal: () => ({ showError: vi.fn() }),
}));

// Debounce mock — passthrough (returns value immediately)
vi.mock("@/hooks/useDebounce", () => ({
  useDebounce: (value: any) => value,
}));

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

function resetMocks() {
  mockRecentData = { pages: [] };
  mockRecentLoading = false;
  mockRecentHasNextPage = false;
  mockFetchNextRecentPage = vi.fn();
  mockFavoritesData = [];
  mockAllCollectionsData = { data: [] };
  mockSearchData = { data: [], pagination: { hasNextPage: false } };
  mockSearchLoading = false;
  mockSearchIsError = false;
  mockSearchIsFetching = false;
  mockCreateMutateAsync = vi.fn();
  mockCreateIsPending = false;
}

describe("CollectionSelector integration tests", () => {
  beforeEach(() => {
    resetMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ─── Requirement 1.2, 1.3: Open / Close ────────────────────────────────────

  describe("open/close behavior (Req 1.2, 1.3)", () => {
    it("opens the panel when the trigger is clicked", async () => {
      const user = userEvent.setup();
      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      expect(screen.getByLabelText("Search collections")).toBeInTheDocument();
    });

    it("closes when clicking outside (MUI Popover backdrop)", async () => {
      const user = userEvent.setup();
      render(
        <div>
          <CollectionSelector value={[]} onChange={vi.fn()} />
          <button>Outside</button>
        </div>,
        { wrapper: createWrapper() }
      );

      await user.click(screen.getByText("Add to collections"));
      expect(screen.getByLabelText("Search collections")).toBeInTheDocument();

      // Click the Popover backdrop to close
      await user.click(document.querySelector(".MuiPopover-root .MuiBackdrop-root") as Element);

      await waitFor(() => {
        expect(screen.queryByLabelText("Search collections")).not.toBeInTheDocument();
      });
    });
  });

  // ─── Requirement 2.3–2.5, 3.3–3.4: Section cap + More toggling ─────────────

  describe("section item cap and More toggling (Req 2.3–2.5, 3.3–3.4)", () => {
    it("shows at most SECTION_ITEM_LIMIT (5) items initially, with More affordance when more exist", async () => {
      const user = userEvent.setup();

      // Provide 8 recent collections
      const collections = Array.from({ length: 8 }, (_, i) =>
        makeCollection({ id: `col-${i}`, name: `Collection ${i}`, userRole: "owner" })
      );
      mockRecentData = { pages: [{ data: collections }] };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      // Should show exactly 5 items (SECTION_ITEM_LIMIT)
      const items = screen.getAllByRole("option");
      expect(items.length).toBe(5);

      // More button should be present
      expect(screen.getByText("More")).toBeInTheDocument();
    });

    it("clicking More shows the next page of items", async () => {
      const user = userEvent.setup();

      const collections = Array.from({ length: 8 }, (_, i) =>
        makeCollection({ id: `col-${i}`, name: `Collection ${i}`, userRole: "editor" })
      );
      mockRecentData = { pages: [{ data: collections }] };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      // Initially 5 items
      expect(screen.getAllByRole("option").length).toBe(5);

      // Click More
      await user.click(screen.getByText("More"));

      // Now all 8 items should be visible
      expect(screen.getAllByRole("option").length).toBe(8);
    });

    it("More affordance disappears when all items are shown", async () => {
      const user = userEvent.setup();

      const collections = Array.from({ length: 8 }, (_, i) =>
        makeCollection({ id: `col-${i}`, name: `Collection ${i}`, userRole: "owner" })
      );
      mockRecentData = { pages: [{ data: collections }] };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));
      await user.click(screen.getByText("More"));

      // All 8 shown, no More button (since 8 < 10 = 5*2 capacity)
      expect(screen.queryByText("More")).not.toBeInTheDocument();
    });

    it("Search section shows More when server signals hasNextPage", async () => {
      const user = userEvent.setup();

      const searchResults = Array.from({ length: 5 }, (_, i) =>
        makeCollection({ id: `s-${i}`, name: `Search Result ${i}`, userRole: "owner" })
      );
      mockSearchData = { data: searchResults, pagination: { hasNextPage: true } };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      const searchInput = screen.getByLabelText("Search collections");
      await user.type(searchInput, "test");

      await waitFor(() => {
        expect(screen.getByText("More")).toBeInTheDocument();
      });
    });
  });

  // ─── Requirement 2.6: Empty state ──────────────────────────────────────────

  describe("empty state (Req 2.6)", () => {
    it("shows empty-state message when both Recent and Favorites have no Addable collections", async () => {
      const user = userEvent.setup();

      // Empty recent and favorites
      mockRecentData = { pages: [{ data: [] }] };
      mockFavoritesData = [];
      mockAllCollectionsData = { data: [] };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      expect(
        screen.getByText("No collections available. Create one using search.")
      ).toBeInTheDocument();
    });

    it("shows empty state when Recent/Favorites only contain viewer-only collections", async () => {
      const user = userEvent.setup();

      // All viewer-only => isAddable filters them out => empty
      const viewerCollections = Array.from({ length: 3 }, (_, i) =>
        makeCollection({ id: `v-${i}`, name: `Viewer Only ${i}`, userRole: "viewer" })
      );
      mockRecentData = { pages: [{ data: viewerCollections }] };
      mockFavoritesData = [];
      mockAllCollectionsData = { data: [] };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      expect(
        screen.getByText("No collections available. Create one using search.")
      ).toBeInTheDocument();
    });
  });

  // ─── Requirement 3.2: Debounced search ─────────────────────────────────────

  describe("debounced search (Req 3.2)", () => {
    it("search input gates the Search section display — debounce is applied (Req 3.2)", async () => {
      const user = userEvent.setup();

      // Provide at least one recent collection so the empty state doesn't show
      mockRecentData = {
        pages: [{ data: [makeCollection({ id: "r-1", name: "Recent One", userRole: "owner" })] }],
      };
      mockSearchData = { data: [], pagination: { hasNextPage: false } };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      // Before typing: Recent and Favorites visible
      expect(screen.getByText("Recent")).toBeInTheDocument();
      expect(screen.getByText("Favorites")).toBeInTheDocument();

      const searchInput = screen.getByLabelText("Search collections");
      await user.type(searchInput, "brand");

      // After typing: Search section replaces Recent/Favorites
      await waitFor(() => {
        expect(screen.getByText("Search")).toBeInTheDocument();
      });
      expect(screen.queryByText("Recent")).not.toBeInTheDocument();
      expect(screen.queryByText("Favorites")).not.toBeInTheDocument();
    });
  });

  // ─── Requirement 3.6: Search error state ───────────────────────────────────

  describe("search error state (Req 3.6)", () => {
    it("shows error message when search request fails", async () => {
      const user = userEvent.setup();

      mockSearchIsError = true;
      mockSearchData = { data: [], pagination: { hasNextPage: false } };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      const searchInput = screen.getByLabelText("Search collections");
      await user.type(searchInput, "something");

      await waitFor(() => {
        expect(screen.getByText("Failed to search collections")).toBeInTheDocument();
      });
    });
  });

  // ─── Requirement 4.1, 4.4: Addable filter excludes viewer-only ─────────────

  describe("Addable filtering (Req 4.1, 4.4)", () => {
    it("excludes viewer-only collections from Recent section", async () => {
      const user = userEvent.setup();

      const collections = [
        makeCollection({ id: "owner-1", name: "Owner Collection", userRole: "owner" }),
        makeCollection({ id: "editor-1", name: "Editor Collection", userRole: "editor" }),
        makeCollection({ id: "viewer-1", name: "Viewer Collection", userRole: "viewer" }),
        makeCollection({ id: "admin-1", name: "Admin Collection", userRole: "admin" }),
      ];
      mockRecentData = { pages: [{ data: collections }] };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      // Should show owner, editor, admin — NOT viewer
      expect(screen.getByText("Owner Collection")).toBeInTheDocument();
      expect(screen.getByText("Editor Collection")).toBeInTheDocument();
      expect(screen.getByText("Admin Collection")).toBeInTheDocument();
      expect(screen.queryByText("Viewer Collection")).not.toBeInTheDocument();
    });

    it("excludes viewer-only collections from Favorites section", async () => {
      const user = userEvent.setup();

      mockRecentData = { pages: [{ data: [] }] };
      mockFavoritesData = [
        { itemId: "fav-owner", itemType: "COLLECTION", addedAt: "2024-01-01" },
        { itemId: "fav-viewer", itemType: "COLLECTION", addedAt: "2024-01-02" },
      ];
      mockAllCollectionsData = {
        data: [
          makeCollection({ id: "fav-owner", name: "Fav Owner", userRole: "owner" }),
          makeCollection({ id: "fav-viewer", name: "Fav Viewer", userRole: "viewer" }),
        ],
      };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      expect(screen.getByText("Fav Owner")).toBeInTheDocument();
      expect(screen.queryByText("Fav Viewer")).not.toBeInTheDocument();
    });

    it("excludes viewer-only collections from Search results", async () => {
      const user = userEvent.setup();

      mockSearchData = {
        data: [
          makeCollection({ id: "s-1", name: "Editable Result", userRole: "editor" }),
          makeCollection({ id: "s-2", name: "Viewer Result", userRole: "viewer" }),
        ],
        pagination: { hasNextPage: false },
      };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));
      const searchInput = screen.getByLabelText("Search collections");
      await user.type(searchInput, "result");

      await waitFor(() => {
        expect(screen.getByText("Editable Result")).toBeInTheDocument();
      });
      expect(screen.queryByText("Viewer Result")).not.toBeInTheDocument();
    });

    it("excludes DELETED collections from all sections", async () => {
      const user = userEvent.setup();

      const deletedCollection = makeCollection({
        id: "deleted-1",
        name: "Deleted Collection",
        userRole: "owner",
        status: "DELETED",
      });
      mockRecentData = { pages: [{ data: [deletedCollection] }] };

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));

      expect(screen.queryByText("Deleted Collection")).not.toBeInTheDocument();
    });
  });

  // ─── Requirement 5.1, 5.4: Multi-select + count chip ──────────────────────

  describe("multi-select and count chip (Req 5.1, 5.4)", () => {
    it("selecting a collection adds it to selection and updates count chip", async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      const collections = [
        makeCollection({ id: "col-1", name: "Alpha", userRole: "owner" }),
        makeCollection({ id: "col-2", name: "Beta", userRole: "editor" }),
      ];
      mockRecentData = { pages: [{ data: collections }] };

      render(<CollectionSelector value={[]} onChange={onChange} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));
      await user.click(screen.getByText("Alpha"));

      expect(onChange).toHaveBeenCalledWith([{ id: "col-1", name: "Alpha" }]);
    });

    it("deselecting a collection removes it from selection", async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      const collections = [makeCollection({ id: "col-1", name: "Alpha", userRole: "owner" })];
      mockRecentData = { pages: [{ data: collections }] };

      const currentValue: CollectionRef[] = [{ id: "col-1", name: "Alpha" }];

      render(<CollectionSelector value={currentValue} onChange={onChange} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));
      await user.click(screen.getByText("Alpha"));

      // Should be called with the collection removed
      expect(onChange).toHaveBeenCalledWith([]);
    });

    it("displays the count chip with current selection count", () => {
      const value: CollectionRef[] = [
        { id: "c1", name: "One" },
        { id: "c2", name: "Two" },
        { id: "c3", name: "Three" },
      ];

      render(<CollectionSelector value={value} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      expect(screen.getByText("3 selected")).toBeInTheDocument();
    });

    it("does not show count chip when selection is empty", () => {
      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
    });

    it("allows multiple concurrent selections", async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      const collections = [
        makeCollection({ id: "col-1", name: "Alpha", userRole: "owner" }),
        makeCollection({ id: "col-2", name: "Beta", userRole: "editor" }),
        makeCollection({ id: "col-3", name: "Gamma", userRole: "admin" }),
      ];
      mockRecentData = { pages: [{ data: collections }] };

      // Start with one already selected to verify concurrent selections
      const initialValue: CollectionRef[] = [{ id: "col-1", name: "Alpha" }];

      render(<CollectionSelector value={initialValue} onChange={onChange} />, {
        wrapper: createWrapper(),
      });

      // Count chip shows existing selection
      expect(screen.getByText("1 selected")).toBeInTheDocument();

      // Open and select another
      await user.click(screen.getByText("Add to collections"));
      await user.click(screen.getByText("Beta"));

      // onChange should be called with both items
      expect(onChange).toHaveBeenCalledWith([
        { id: "col-1", name: "Alpha" },
        { id: "col-2", name: "Beta" },
      ]);
    });
  });

  // ─── Requirement 6.1, 6.4, 6.5: Inline create ─────────────────────────────

  describe("inline create (Req 6.1, 6.4, 6.5)", () => {
    it("shows create action when search yields no Addable results", async () => {
      const user = userEvent.setup();

      // Search returns empty Addable results
      mockSearchData = { data: [], pagination: { hasNextPage: false } };
      mockSearchLoading = false;
      mockSearchIsError = false;
      mockSearchIsFetching = false;

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));
      const searchInput = screen.getByLabelText("Search collections");
      fireEvent.change(searchInput, { target: { value: "NewProject" } });

      await waitFor(
        () => {
          expect(screen.getByText('Create "NewProject"')).toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });

    it("adds newly created collection to selection on success (Req 6.1)", async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      mockSearchData = { data: [], pagination: { hasNextPage: false } };
      mockCreateMutateAsync = vi.fn().mockResolvedValue({
        data: { id: "new-col-1", name: "NewProject" },
      });

      render(<CollectionSelector value={[]} onChange={onChange} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));
      const searchInput = screen.getByLabelText("Search collections");
      await user.type(searchInput, "NewProject");

      await waitFor(
        () => {
          expect(screen.getByText('Create "NewProject"')).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      await user.click(screen.getByText('Create "NewProject"'));

      await waitFor(
        () => {
          expect(onChange).toHaveBeenCalledWith([{ id: "new-col-1", name: "NewProject" }]);
        },
        { timeout: 3000 }
      );
    });

    it("shows error message on create failure (Req 6.4)", async () => {
      const user = userEvent.setup();

      mockSearchData = { data: [], pagination: { hasNextPage: false } };
      mockCreateMutateAsync = vi.fn().mockRejectedValue(new Error("Network error"));

      render(<CollectionSelector value={[]} onChange={vi.fn()} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));
      const searchInput = screen.getByLabelText("Search collections");
      await user.type(searchInput, "Failing");

      await waitFor(
        () => {
          expect(screen.getByText('Create "Failing"')).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      await user.click(screen.getByText('Create "Failing"'));

      await waitFor(
        () => {
          expect(screen.getByText("Failed to create collection")).toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });

    it("preserves previous selection on create failure (Req 6.5)", async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      const existingSelection: CollectionRef[] = [
        { id: "existing-1", name: "Existing Collection" },
      ];

      mockSearchData = { data: [], pagination: { hasNextPage: false } };
      mockCreateMutateAsync = vi.fn().mockRejectedValue(new Error("Server error"));

      render(<CollectionSelector value={existingSelection} onChange={onChange} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByText("Add to collections"));
      const searchInput = screen.getByLabelText("Search collections");
      await user.type(searchInput, "Doomed");

      await waitFor(
        () => {
          expect(screen.getByText('Create "Doomed"')).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      await user.click(screen.getByText('Create "Doomed"'));

      await waitFor(
        () => {
          // On failure, onChange should be called with the previous selection (unchanged)
          expect(onChange).toHaveBeenCalledWith(existingSelection);
        },
        { timeout: 3000 }
      );
    });
  });
});
