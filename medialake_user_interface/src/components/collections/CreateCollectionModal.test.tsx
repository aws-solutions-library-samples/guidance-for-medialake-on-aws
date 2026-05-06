import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

// ---- Mocks ----

const mockCreateMutateAsync = vi.fn();
const mockSetThumbnailMutateAsync = vi.fn();
const mockSetIconMutateAsync = vi.fn();

vi.mock("../../api/hooks/useCollections", () => ({
  useCreateCollection: () => ({
    mutateAsync: mockCreateMutateAsync,
    isPending: false,
    isError: false,
    reset: vi.fn(),
  }),
  useGetAllCollections: () => ({ data: { data: [] } }),
  useSetCollectionThumbnail: () => ({
    mutateAsync: mockSetThumbnailMutateAsync,
    isPending: false,
  }),
  useSetCollectionIcon: () => ({
    mutateAsync: mockSetIconMutateAsync,
    isPending: false,
  }),
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

import { CreateCollectionModal } from "./CreateCollectionModal";

describe("CreateCollectionModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateMutateAsync.mockResolvedValue({ data: { id: "new-col-1" } });
  });

  it("renders the KeyValueEditor with Add Row button", () => {
    render(<CreateCollectionModal open={true} onClose={() => {}} />);
    expect(screen.getByText("Custom Metadata")).toBeInTheDocument();
    expect(screen.getByText("Add Row")).toBeInTheDocument();
  });

  it("includes metadata in the create request payload", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<CreateCollectionModal open={true} onClose={onClose} />);

    // Fill in required name field
    const nameInput = screen.getByLabelText(/Name/i);
    await user.type(nameInput, "Test Collection");

    // Add a metadata row
    await user.click(screen.getByText("Add Row"));

    // Fill in key and value
    const keyInput = screen.getByPlaceholderText("Key");
    const valueInput = screen.getByPlaceholderText("Value");
    await user.type(keyInput, "project");
    await user.type(valueInput, "alpha");

    // Submit — use getAllByText since "Create Collection" appears in header and button
    const buttons = screen.getAllByText("Create Collection");
    const submitButton = buttons.find((el) => el.closest("button"));
    await user.click(submitButton!);

    await waitFor(() => {
      expect(mockCreateMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Test Collection",
          metadata: { project: "alpha" },
        })
      );
    });
  });

  it("omits metadata field when no valid entries exist", async () => {
    const user = userEvent.setup();

    render(<CreateCollectionModal open={true} onClose={() => {}} />);

    // Fill in required name
    const nameInput = screen.getByLabelText(/Name/i);
    await user.type(nameInput, "No Metadata Collection");

    // Submit without adding metadata — use getAllByText since text appears in header too
    const buttons = screen.getAllByText("Create Collection");
    const submitButton = buttons.find((el) => el.closest("button"));
    await user.click(submitButton!);

    await waitFor(() => {
      expect(mockCreateMutateAsync).toHaveBeenCalledTimes(1);
      const payload = mockCreateMutateAsync.mock.calls[0][0];
      expect(payload.metadata).toBeUndefined();
    });
  });
});
