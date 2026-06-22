/**
 * Unit tests for CollectionSelector scaffold (task 6.1).
 *
 * Validates: Requirements 1.2, 1.3
 *
 * Coverage:
 *   1. The trigger renders with "Add to collections" label.
 *   2. Clicking the trigger opens the popover with search, Recent, and Favorites sections.
 *   3. Clicking outside closes the popover (standard MUI Popover behavior).
 *   4. Typing search text replaces Recent/Favorites with the Search section.
 *   5. Clearing search text restores Recent/Favorites.
 *   6. The count chip renders when value has items.
 *   7. The trigger is inert when disabled.
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import CollectionSelector, { type CollectionRef } from "./CollectionSelector";

// Wrap component to provide minimal i18n context (passthrough)
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue: string, opts?: Record<string, any>) => {
      if (opts?.count !== undefined) return `${opts.count} selected`;
      return defaultValue || key;
    },
  }),
}));

// Mock the hooks used by CollectionSelector (wired in task 6.4)
vi.mock("@/api/hooks/useCollections", () => {
  const mockRecentCollection = {
    id: "recent-1",
    name: "Recent Collection",
    status: "ACTIVE",
    userRole: "owner",
    ownerId: "user-1",
    type: "private",
    itemCount: 0,
    childCount: 0,
    childCollectionCount: 0,
    isPublic: false,
    createdAt: "2024-01-01",
    updatedAt: "2024-01-01",
  };

  return {
    useRecentCollections: () => ({
      data: { pages: [{ data: [mockRecentCollection] }] },
      isLoading: false,
      fetchNextPage: vi.fn(),
      hasNextPage: false,
    }),
    useGetAllCollections: () => ({
      data: { data: [] },
      isLoading: false,
    }),
    useGetCollections: () => ({
      data: { data: [], pagination: { hasNextPage: false } },
      isLoading: false,
      isError: false,
      isFetching: false,
    }),
    useCreateCollection: () => ({
      mutateAsync: vi.fn(),
      isPending: false,
    }),
    isAddable: (c: any) =>
      c.status === "ACTIVE" &&
      (c.userRole === "owner" || c.userRole === "admin" || c.userRole === "editor"),
  };
});

vi.mock("@/api/hooks/useFavorites", () => ({
  useGetFavorites: () => ({
    data: [],
    isLoading: false,
  }),
}));

vi.mock("@/hooks/useDebounce", () => ({
  useDebounce: (value: any) => value,
}));

// Mock error modal to prevent unhandled errors in useGetCollections
vi.mock("../../hooks/useErrorModal", () => ({
  useErrorModal: () => ({ showError: vi.fn() }),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("CollectionSelector", () => {
  const defaultProps = {
    value: [] as CollectionRef[],
    onChange: vi.fn(),
  };

  it("renders the trigger with label text", () => {
    render(<CollectionSelector {...defaultProps} />, { wrapper: createWrapper() });
    expect(screen.getByText("Add to collections")).toBeInTheDocument();
  });

  it("opens the popover when the trigger is clicked (Req 1.2)", async () => {
    const user = userEvent.setup();
    render(<CollectionSelector {...defaultProps} />, { wrapper: createWrapper() });

    await user.click(screen.getByText("Add to collections"));

    // Popover should show search input and section headings
    expect(screen.getByLabelText("Search collections")).toBeInTheDocument();
    expect(screen.getByText("Recent")).toBeInTheDocument();
    expect(screen.getByText("Favorites")).toBeInTheDocument();
  });

  it("closes the popover on outside click (Req 1.3)", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <CollectionSelector {...defaultProps} />
        <button>Outside</button>
      </div>,
      { wrapper: createWrapper() }
    );

    // Open
    await user.click(screen.getByText("Add to collections"));
    expect(screen.getByLabelText("Search collections")).toBeInTheDocument();

    // Click outside — MUI Popover renders a backdrop
    await user.click(document.querySelector(".MuiPopover-root .MuiBackdrop-root") as Element);

    await waitFor(() => {
      expect(screen.queryByLabelText("Search collections")).not.toBeInTheDocument();
    });
  });

  it("shows Search section and hides Recent/Favorites when search text is present", async () => {
    const user = userEvent.setup();
    render(<CollectionSelector {...defaultProps} />, { wrapper: createWrapper() });

    await user.click(screen.getByText("Add to collections"));

    // Type into search
    const searchInput = screen.getByLabelText("Search collections");
    await user.type(searchInput, "brand");

    // Search section visible, Recent/Favorites hidden
    expect(screen.getByText("Search")).toBeInTheDocument();
    expect(screen.queryByText("Recent")).not.toBeInTheDocument();
    expect(screen.queryByText("Favorites")).not.toBeInTheDocument();
  });

  it("restores Recent/Favorites when search text is cleared", async () => {
    const user = userEvent.setup();
    render(<CollectionSelector {...defaultProps} />, { wrapper: createWrapper() });

    await user.click(screen.getByText("Add to collections"));
    const searchInput = screen.getByLabelText("Search collections");

    // Type and then clear
    await user.type(searchInput, "brand");
    await user.clear(searchInput);

    expect(screen.getByText("Recent")).toBeInTheDocument();
    expect(screen.getByText("Favorites")).toBeInTheDocument();
    expect(screen.queryByText("Search")).not.toBeInTheDocument();
  });

  it("displays count chip when value has items (Req 5.4 surface)", () => {
    const value: CollectionRef[] = [
      { id: "c1", name: "Collection A" },
      { id: "c2", name: "Collection B" },
    ];
    render(<CollectionSelector {...defaultProps} value={value} />, { wrapper: createWrapper() });

    expect(screen.getByText("2 selected")).toBeInTheDocument();
  });

  it("does not open when disabled", async () => {
    const user = userEvent.setup();
    render(<CollectionSelector {...defaultProps} disabled />, { wrapper: createWrapper() });

    await user.click(screen.getByText("Add to collections"));

    expect(screen.queryByLabelText("Search collections")).not.toBeInTheDocument();
  });
});
