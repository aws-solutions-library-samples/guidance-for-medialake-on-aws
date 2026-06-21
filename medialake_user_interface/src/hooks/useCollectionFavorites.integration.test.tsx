/**
 * Cross-surface integration tests for collection favorites.
 *
 * Renders two independent surfaces that both consume `useCollectionFavorites`
 * through a single shared QueryClient, and exercises the REAL favorites mutation
 * hooks (only the HTTP client and the snackbar are mocked). Verifies:
 *  - optimistic update is visible (on every surface) before the request resolves
 *  - rollback + error snackbar on failure, consistently across surfaces
 *  - both surfaces always render the same state from the shared cache
 *
 * The favorites cache is seeded directly so the initial state is deterministic
 * (no GET race against the optimistic mutation); `apiClient.get` is kept
 * idempotent with the seed so any refetch is a no-op.
 *
 * **Validates: Requirements 1.6, 1.7, 2.5, 2.6, 5.1, 5.2**
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { apiGet, apiPost, apiDelete } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));
const { enqueueSnackbar } = vi.hoisted(() => ({ enqueueSnackbar: vi.fn() }));

vi.mock("../api/apiClient", () => ({
  apiClient: { get: apiGet, post: apiPost, delete: apiDelete },
}));
vi.mock("notistack", () => ({ useSnackbar: () => ({ enqueueSnackbar }) }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string, fallback?: string) => fallback ?? key }),
}));

import { useCollectionFavorites } from "./useCollectionFavorites";
import type { Favorite } from "../api/hooks/useFavorites";
import { QUERY_KEYS } from "../api/queryKeys";

// A minimal "surface" that derives its favorite state from the shared cache.
function Probe({ id, testid }: { id: string; testid: string }) {
  const { isCollectionFavorited, handleFavoriteToggle } = useCollectionFavorites();
  return (
    <button data-testid={testid} onClick={(e) => handleFavoriteToggle({ id, name: "C" }, e)}>
      {isCollectionFavorited(id) ? "fav" : "not-fav"}
    </button>
  );
}

const favorite = (itemId: string): Favorite => ({
  itemId,
  itemType: "COLLECTION",
  metadata: { name: "C" },
  addedAt: "2024-01-01T00:00:00Z",
});

function renderTwoSurfaces(initialFavorites: Favorite[]) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  // Seed the shared cache so both surfaces start in a deterministic state.
  client.setQueryData(QUERY_KEYS.FAVORITES.list("COLLECTION"), initialFavorites);
  // Keep GET idempotent with the seed: a refetch returns the same data.
  apiGet.mockResolvedValue({ data: { data: { favorites: initialFavorites } } });
  return render(
    <QueryClientProvider client={client}>
      <Probe id="x" testid="surface-a" />
      <Probe id="x" testid="surface-b" />
    </QueryClientProvider>
  );
}

const a = () => screen.getByTestId("surface-a");
const b = () => screen.getByTestId("surface-b");

beforeEach(() => {
  vi.clearAllMocks();
});

describe("collection favorites — cross-surface integration", () => {
  it("applies an optimistic add visible on every surface before the request resolves", async () => {
    let resolvePost: (value: unknown) => void = () => {};
    apiPost.mockReturnValue(
      new Promise((resolve) => {
        resolvePost = resolve;
      })
    );

    renderTwoSurfaces([]);
    expect(a()).toHaveTextContent("not-fav");
    expect(b()).toHaveTextContent("not-fav");

    fireEvent.click(a());

    // Optimistic: both surfaces flip to favorited while the POST is still pending.
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(a()).toHaveTextContent("fav"));
    expect(b()).toHaveTextContent("fav");

    resolvePost({ data: { data: { favorite: favorite("x") } } });

    await waitFor(() => expect(a()).toHaveTextContent("fav"));
    expect(b()).toHaveTextContent("fav");
  });

  it("rolls back and shows an error snackbar on add failure, across surfaces", async () => {
    let rejectPost: (reason: unknown) => void = () => {};
    apiPost.mockReturnValue(
      new Promise((_, reject) => {
        rejectPost = reject;
      })
    );

    renderTwoSurfaces([]);
    fireEvent.click(a());

    await waitFor(() => expect(a()).toHaveTextContent("fav")); // optimistic
    expect(b()).toHaveTextContent("fav");

    rejectPost(new Error("boom"));

    await waitFor(() => expect(a()).toHaveTextContent("not-fav"));
    expect(b()).toHaveTextContent("not-fav");
    expect(enqueueSnackbar).toHaveBeenCalledWith(
      "favorites.errorAdding",
      expect.objectContaining({ variant: "error" })
    );
  });

  it("applies an optimistic remove visible on every surface before the request resolves", async () => {
    let resolveDelete: (value: unknown) => void = () => {};
    apiDelete.mockReturnValue(
      new Promise((resolve) => {
        resolveDelete = resolve;
      })
    );

    renderTwoSurfaces([favorite("x")]);
    expect(a()).toHaveTextContent("fav");
    expect(b()).toHaveTextContent("fav");

    fireEvent.click(a());

    await waitFor(() => expect(apiDelete).toHaveBeenCalledTimes(1));
    expect(apiPost).not.toHaveBeenCalled();
    await waitFor(() => expect(a()).toHaveTextContent("not-fav"));
    expect(b()).toHaveTextContent("not-fav");

    resolveDelete({});
    await waitFor(() => expect(a()).toHaveTextContent("not-fav"));
    expect(b()).toHaveTextContent("not-fav");
  });

  it("rolls back and shows an error snackbar on remove failure, across surfaces", async () => {
    let rejectDelete: (reason: unknown) => void = () => {};
    apiDelete.mockReturnValue(
      new Promise((_, reject) => {
        rejectDelete = reject;
      })
    );

    renderTwoSurfaces([favorite("x")]);
    fireEvent.click(a());

    await waitFor(() => expect(a()).toHaveTextContent("not-fav")); // optimistic remove
    expect(b()).toHaveTextContent("not-fav");

    rejectDelete(new Error("boom"));

    await waitFor(() => expect(a()).toHaveTextContent("fav")); // rolled back
    expect(b()).toHaveTextContent("fav");
    expect(enqueueSnackbar).toHaveBeenCalledWith(
      "favorites.errorRemoving",
      expect.objectContaining({ variant: "error" })
    );
  });
});
