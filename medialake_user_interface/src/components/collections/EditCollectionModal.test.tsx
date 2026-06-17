import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { Collection } from "../../api/hooks/useCollections";

// ---- Mocks ----

const mockUpdateMutateAsync = vi.fn();

vi.mock("../../api/hooks/useCollections", () => ({
  useUpdateCollection: () => ({
    mutateAsync: mockUpdateMutateAsync,
    isPending: false,
    isError: false,
  }),
  useGetAllCollections: () => ({ data: { data: [] } }),
  useSetCollectionThumbnail: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetCollectionIcon: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteCollectionThumbnail: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("../../api/hooks/useCollectionCollectionTypes", () => ({
  useCollectionCollectionTypes: () => ({ data: { data: [] } }),
}));

vi.mock("./ThumbnailSelector", () => ({
  ThumbnailSelector: () => <div data-testid="thumbnail-selector" />,
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback: string) => fallback,
  }),
}));

import { EditCollectionModal } from "./EditCollectionModal";

const makeCollection = (overrides: Partial<Collection> = {}): Collection => ({
  id: "col-1",
  name: "Test Collection",
  type: "private",
  ownerId: "user-1",
  itemCount: 0,
  childCount: 0,
  childCollectionCount: 0,
  isPublic: false,
  status: "active",
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  ...overrides,
});

describe("EditCollectionModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("pre-populates metadata rows from collection.customMetadata", () => {
    const collection = makeCollection({
      customMetadata: { project: "alpha", region: "us-west-2" },
    });

    render(<EditCollectionModal open={true} onClose={() => {}} collection={collection} />);

    // Verify the KeyValueEditor rendered with pre-populated rows
    const keyInputs = screen.getAllByPlaceholderText("Key");
    const valueInputs = screen.getAllByPlaceholderText("Value");

    expect(keyInputs).toHaveLength(2);
    expect(valueInputs).toHaveLength(2);

    // Check values are populated (order may vary based on Object.entries)
    const keyValues = keyInputs.map((input) => (input as HTMLInputElement).value);
    const valueValues = valueInputs.map((input) => (input as HTMLInputElement).value);

    expect(keyValues).toContain("project");
    expect(keyValues).toContain("region");
    expect(valueValues).toContain("alpha");
    expect(valueValues).toContain("us-west-2");
  });

  it("renders empty metadata editor when collection has no customMetadata", () => {
    const collection = makeCollection({ customMetadata: undefined });

    render(<EditCollectionModal open={true} onClose={() => {}} collection={collection} />);

    // Should show the label but no key/value rows
    expect(screen.getByText("Custom Metadata")).toBeInTheDocument();
    expect(screen.queryAllByPlaceholderText("Key")).toHaveLength(0);
    expect(screen.getByText("Add Row")).toBeInTheDocument();
  });

  it("renders empty metadata editor when customMetadata is empty object", () => {
    const collection = makeCollection({ customMetadata: {} });

    render(<EditCollectionModal open={true} onClose={() => {}} collection={collection} />);

    expect(screen.queryAllByPlaceholderText("Key")).toHaveLength(0);
    expect(screen.getByText("Add Row")).toBeInTheDocument();
  });
});
