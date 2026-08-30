import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}));

// The modal lists collections it can file into; the manifest under test is
// independent of that list, so the queries are stubbed to a stable empty result.
vi.mock("../../api/hooks/useCollections", () => ({
  useGetAllCollections: () => ({ data: { data: [] }, isLoading: false, refetch: vi.fn() }),
  useCreateCollection: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { AddToCollectionModal } from "./AddToCollectionModal";

const baseProps = {
  open: true,
  onClose: vi.fn(),
  assetId: "asset-1",
  assetName: "2 selected",
  assetType: "Video",
  onAddToCollection: vi.fn(),
};

describe("AddToCollectionModal clip manifest", () => {
  it("lists each clip's time range so several clips of one asset are distinguishable", () => {
    render(
      <AddToCollectionModal
        {...baseProps}
        items={[
          { id: "a#clip#1", name: "interview.mp4", timeRange: "01:05 – 02:10" },
          { id: "a#clip#2", name: "interview.mp4", timeRange: "04:00 – 04:30" },
        ]}
      />
    );

    expect(screen.getByText("01:05 – 02:10")).toBeInTheDocument();
    expect(screen.getByText("04:00 – 04:30")).toBeInTheDocument();
    expect(screen.getAllByText("interview.mp4")).toHaveLength(2);
  });

  it("exposes the manifest as a labelled list for assistive technology", () => {
    render(
      <AddToCollectionModal
        {...baseProps}
        items={[{ id: "a#clip#1", name: "interview.mp4", timeRange: "01:05 – 02:10" }]}
      />
    );

    expect(screen.getByRole("list", { name: "Items being added" })).toBeInTheDocument();
  });

  it("omits the manifest for whole assets, which have no range worth listing", () => {
    render(
      <AddToCollectionModal
        {...baseProps}
        items={[
          { id: "asset-1", name: "photo.jpg" },
          { id: "asset-2", name: "clip.mp4", timeRange: null },
        ]}
      />
    );

    expect(screen.queryByRole("list", { name: "Items being added" })).not.toBeInTheDocument();
    // The header still identifies the selection.
    expect(screen.getByText("2 selected")).toBeInTheDocument();
  });

  it("shows only the clips when a selection mixes clips and whole assets", () => {
    render(
      <AddToCollectionModal
        {...baseProps}
        items={[
          { id: "asset-1", name: "photo.jpg" },
          { id: "a#clip#1", name: "interview.mp4", timeRange: "01:05 – 02:10" },
        ]}
      />
    );

    expect(screen.getByText("01:05 – 02:10")).toBeInTheDocument();
    expect(screen.queryByText("photo.jpg")).not.toBeInTheDocument();
  });

  it("falls back to the asset name when no items are supplied", () => {
    // The single-asset callers that predate the manifest must be unaffected.
    render(<AddToCollectionModal {...baseProps} assetName="holiday.mp4" />);

    expect(screen.getByText("holiday.mp4")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Items being added" })).not.toBeInTheDocument();
  });
});
