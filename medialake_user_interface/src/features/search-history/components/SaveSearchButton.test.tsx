import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithUser } from "@/test/render";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string, opts?: Record<string, unknown>) =>
      (fallback ?? _key).replace(/\{\{(\w+)\}\}/g, (_m, k) => String(opts?.[k] ?? "")),
  }),
}));

const createMutate = vi.fn();
const renameMutate = vi.fn();
const deleteMutate = vi.fn();
vi.mock("../api", () => ({
  useCreateSavedSearch: () => ({ mutate: createMutate, isPending: false }),
  useRenameSavedSearch: () => ({ mutate: renameMutate, isPending: false }),
  useDeleteSavedSearch: () => ({ mutate: deleteMutate, isPending: false }),
}));
const matching = vi.fn();
vi.mock("../hooks", () => ({ useMatchingSavedSearch: (...a: unknown[]) => matching(...a) }));

import { SaveSearchButton } from "./SaveSearchButton";

const definition = {
  v: 1,
  q: "sunset",
  semantic: false,
  filters: { type: "Video" },
};

describe("SaveSearchButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    matching.mockReturnValue({ match: undefined, isReady: true });
  });

  it("is hidden for a browse-everything search with no filters", () => {
    const { container } = renderWithUser(
      <SaveSearchButton definition={{ v: 1, q: "", semantic: false }} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("saves the current search under a suggested, editable name", async () => {
    const { user } = renderWithUser(<SaveSearchButton definition={definition} />);
    await user.click(screen.getByRole("button", { name: "Save search" }));

    const dialog = screen.getByRole("dialog", { name: "Save this search" });
    const name = within(dialog).getByLabelText("Name");
    expect(name).toHaveValue("sunset · Video");

    await user.clear(name);
    await user.type(name, "Sunset videos");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    expect(createMutate).toHaveBeenCalledWith(
      { name: "Sunset videos", definition },
      expect.anything()
    );
  });

  it("will not save an empty name", async () => {
    const { user } = renderWithUser(<SaveSearchButton definition={definition} />);
    await user.click(screen.getByRole("button", { name: "Save search" }));
    const dialog = screen.getByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Name"));
    expect(within(dialog).getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("shows Saved with rename and remove once the search is saved", async () => {
    matching.mockReturnValue({
      match: { id: "s1", name: "Sunsets", definition, fingerprint: "f" },
      isReady: true,
    });
    const { user } = renderWithUser(<SaveSearchButton definition={definition} />);

    await user.click(screen.getByRole("button", { name: "Saved as “Sunsets”" }));
    await user.click(screen.getByRole("menuitem", { name: "Remove from saved searches" }));
    expect(deleteMutate).toHaveBeenCalledWith("s1");

    await user.click(screen.getByRole("button", { name: "Saved as “Sunsets”" }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    const dialog = screen.getByRole("dialog", { name: "Rename saved search" });
    const name = within(dialog).getByLabelText("Name");
    expect(name).toHaveValue("Sunsets");
    await user.clear(name);
    await user.type(name, "Golden hour{Enter}");
    expect(renameMutate).toHaveBeenCalledWith({ id: "s1", name: "Golden hour" }, expect.anything());
  });
});
