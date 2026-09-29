import { describe, it, expect, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithUser } from "@/test/render";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string, opts?: Record<string, unknown>) =>
      (fallback ?? key).replace(/\{\{(\w+)\}\}/g, (_m, k) => String(opts?.[k] ?? "")),
  }),
}));
import { SearchSuggestionsPanel } from "./SearchSuggestionsPanel";
import type { SuggestionItem } from "../hooks";

const saved: SuggestionItem = {
  kind: "saved",
  id: "saved-s1",
  definition: { v: 1, q: "sunset", semantic: false, filters: { type: "Video" } },
  saved: {
    id: "s1",
    name: "Sunset videos",
    definition: { v: 1, q: "sunset", semantic: false, filters: { type: "Video" } },
    fingerprint: "fp1",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
  },
};

const recent: SuggestionItem = {
  kind: "history",
  id: "history-fp2",
  definition: { v: 1, q: "beach", semantic: false, filters: { type: "Image" } },
  entry: {
    fingerprint: "fp2",
    definition: { v: 1, q: "beach", semantic: false, filters: { type: "Image" } },
    searchedAt: new Date().toISOString(),
  },
};

function renderPanel() {
  const anchor = document.createElement("div");
  document.body.appendChild(anchor);
  return renderWithUser(
    <SearchSuggestionsPanel
      open
      anchorEl={anchor}
      savedItems={[saved]}
      historyItems={[recent]}
      totalSaved={1}
      activeId={null}
      onSelect={vi.fn()}
      onRemoveHistory={vi.fn()}
      onClearHistory={vi.fn()}
      onManage={vi.fn()}
      onClose={vi.fn()}
      onHover={vi.fn()}
    />
  );
}

const textContainer = (option: HTMLElement) => within(option).getByTestId("suggestion-text");

describe("SearchSuggestionsPanel", () => {
  it("shows a saved search on one line: name, then query and filters", () => {
    renderPanel();

    const option = screen.getByRole("option", { name: /Sunset videos/ });
    const text = textContainer(option);
    // Name and details are side by side in a flex row, not stacked.
    expect(getComputedStyle(text).display).toBe("flex");
    expect(text.children).toHaveLength(2);
    expect(text.children[0]).toHaveTextContent("Sunset videos");
    expect(text.children[1]).toHaveTextContent("sunset · Video");
  });

  it("keeps the full saved-search details available when they are cut off", () => {
    renderPanel();

    const option = screen.getByRole("option", { name: /Sunset videos/ });
    expect(option).toHaveAttribute("title", "Sunset videos — sunset · Video");
    // Screen readers still get the name and the details.
    expect(option).toHaveAccessibleName(/Sunset videos.*sunset · Video/);
  });

  it("leaves recent searches as they were", () => {
    renderPanel();

    const option = screen.getByRole("option", { name: /beach/ });
    expect(getComputedStyle(textContainer(option)).display).not.toBe("flex");
    expect(option).not.toHaveAttribute("title");
    expect(
      within(option).getByRole("button", { name: "Remove beach from history" })
    ).toBeInTheDocument();
  });
});
