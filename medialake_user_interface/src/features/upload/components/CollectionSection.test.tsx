/**
 * Unit tests for CollectionSection (task 6.2).
 *
 * Validates: Requirements 2.3, 2.4, 2.5, 3.3, 3.4, 3.5
 *
 * Coverage:
 *   1. Displays at most SECTION_ITEM_LIMIT items initially.
 *   2. Shows "More" button when more items exist than currently shown.
 *   3. Clicking "More" reveals the next page of items (client-side pagination).
 *   4. Does NOT show "More" when all items are visible and hasMore is false.
 *   5. Shows "More" when local items are exhausted but hasMore is true (server-side).
 *   6. Calls onMore for server-side pagination when local items are exhausted.
 *   7. Shows empty state when items is empty.
 *   8. Shows error state when error prop is set.
 *   9. Shows loading state when loading is true and items are empty.
 *  10. Renders checkboxes reflecting selectedIds.
 *  11. Calls onToggle when a collection item is clicked.
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import CollectionSection, { SECTION_ITEM_LIMIT } from "./CollectionSection";
import type { Collection } from "@/api/hooks/useCollections";

// Minimal i18n mock (passthrough)
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue: string) => defaultValue || _key,
  }),
}));

/** Helper: generate N fake Collection items */
function makeCollections(count: number): Collection[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `col-${i}`,
    name: `Collection ${i}`,
    description: "",
    type: "private" as const,
    ownerId: "user-1",
    ownerName: "Test User",
    itemCount: 0,
    childCount: 0,
    childCollectionCount: 0,
    isPublic: false,
    status: "ACTIVE",
    userRole: "owner",
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
  }));
}

describe("CollectionSection", () => {
  const defaultProps = {
    title: "Recent",
    items: [] as Collection[],
    selectedIds: new Set<string>(),
    onToggle: vi.fn(),
  };

  it("displays at most SECTION_ITEM_LIMIT items initially (Req 2.3, 3.3)", () => {
    const items = makeCollections(8);
    render(<CollectionSection {...defaultProps} items={items} />);

    // Only the first 5 should be visible
    for (let i = 0; i < SECTION_ITEM_LIMIT; i++) {
      expect(screen.getByText(`Collection ${i}`)).toBeInTheDocument();
    }
    // Items beyond the limit should NOT be shown
    expect(screen.queryByText(`Collection ${SECTION_ITEM_LIMIT}`)).not.toBeInTheDocument();
  });

  it("shows More button when more items exist than shown (Req 2.4, 3.4)", () => {
    const items = makeCollections(SECTION_ITEM_LIMIT + 1);
    render(<CollectionSection {...defaultProps} items={items} />);

    expect(screen.getByRole("button", { name: /more/i })).toBeInTheDocument();
  });

  it("does NOT show More when all items fit within the limit", () => {
    const items = makeCollections(SECTION_ITEM_LIMIT);
    render(<CollectionSection {...defaultProps} items={items} />);

    expect(screen.queryByRole("button", { name: /more/i })).not.toBeInTheDocument();
  });

  it("clicking More reveals the next page of items (Req 2.5, client-side)", async () => {
    const user = userEvent.setup();
    const items = makeCollections(SECTION_ITEM_LIMIT + 3); // 8 total
    render(<CollectionSection {...defaultProps} items={items} />);

    // Initially 5 visible
    expect(screen.queryByText(`Collection ${SECTION_ITEM_LIMIT}`)).not.toBeInTheDocument();

    // Click More
    await user.click(screen.getByRole("button", { name: /more/i }));

    // Now all 8 should be visible
    for (let i = 0; i < items.length; i++) {
      expect(screen.getByText(`Collection ${i}`)).toBeInTheDocument();
    }
  });

  it("hides More after all local items are shown and hasMore is false", async () => {
    const user = userEvent.setup();
    const items = makeCollections(SECTION_ITEM_LIMIT + 2); // 7 total
    render(<CollectionSection {...defaultProps} items={items} hasMore={false} />);

    // Click More to show remaining 2
    await user.click(screen.getByRole("button", { name: /more/i }));

    // All shown, no hasMore → button gone
    expect(screen.queryByRole("button", { name: /more/i })).not.toBeInTheDocument();
  });

  it("shows More when local items exhausted but hasMore is true (Req 3.4, server-side)", async () => {
    const user = userEvent.setup();
    // Exactly SECTION_ITEM_LIMIT items, but server has more
    const items = makeCollections(SECTION_ITEM_LIMIT);
    render(<CollectionSection {...defaultProps} items={items} hasMore={true} />);

    // Even though all local items are visible, hasMore shows the button
    expect(screen.getByRole("button", { name: /more/i })).toBeInTheDocument();
  });

  it("calls onMore for server-side pagination when local items are exhausted (Req 3.5)", async () => {
    const user = userEvent.setup();
    const onMore = vi.fn();
    const items = makeCollections(SECTION_ITEM_LIMIT);
    render(<CollectionSection {...defaultProps} items={items} hasMore={true} onMore={onMore} />);

    await user.click(screen.getByRole("button", { name: /more/i }));

    expect(onMore).toHaveBeenCalledTimes(1);
  });

  it("shows empty state when items is empty and not loading", () => {
    render(<CollectionSection {...defaultProps} items={[]} emptyMessage="No recent collections" />);

    expect(screen.getByText("No recent collections")).toBeInTheDocument();
  });

  it("shows error state when error prop is set", () => {
    render(<CollectionSection {...defaultProps} items={[]} error="Failed to load collections" />);

    expect(screen.getByText("Failed to load collections")).toBeInTheDocument();
  });

  it("shows loading state when loading is true and items are empty", () => {
    render(<CollectionSection {...defaultProps} items={[]} loading={true} />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders checkboxes reflecting selectedIds", () => {
    const items = makeCollections(3);
    const selectedIds = new Set(["col-0", "col-2"]);
    render(<CollectionSection {...defaultProps} items={items} selectedIds={selectedIds} />);

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes[0]).toBeChecked(); // col-0 selected
    expect(checkboxes[1]).not.toBeChecked(); // col-1 not selected
    expect(checkboxes[2]).toBeChecked(); // col-2 selected
  });

  it("calls onToggle when a collection item is clicked", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    const items = makeCollections(2);
    render(<CollectionSection {...defaultProps} items={items} onToggle={onToggle} />);

    await user.click(screen.getByText("Collection 1"));

    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onToggle).toHaveBeenCalledWith(items[1]);
  });

  it("renders the section title", () => {
    render(<CollectionSection {...defaultProps} title="Favorites" items={[]} />);
    expect(screen.getByText("Favorites")).toBeInTheDocument();
  });

  it("paginates correctly across multiple More clicks (Req 2.5)", async () => {
    const user = userEvent.setup();
    // 12 items = needs 3 pages of 5 (5 + 5 + 2)
    const items = makeCollections(12);
    render(<CollectionSection {...defaultProps} items={items} />);

    // Page 1: 0-4 visible
    expect(screen.getByText("Collection 4")).toBeInTheDocument();
    expect(screen.queryByText("Collection 5")).not.toBeInTheDocument();

    // Click More → page 2: 0-9 visible
    await user.click(screen.getByRole("button", { name: /more/i }));
    expect(screen.getByText("Collection 9")).toBeInTheDocument();
    expect(screen.queryByText("Collection 10")).not.toBeInTheDocument();

    // Click More → page 3: all visible
    await user.click(screen.getByRole("button", { name: /more/i }));
    expect(screen.getByText("Collection 11")).toBeInTheDocument();
    // No more button
    expect(screen.queryByRole("button", { name: /more/i })).not.toBeInTheDocument();
  });
});
