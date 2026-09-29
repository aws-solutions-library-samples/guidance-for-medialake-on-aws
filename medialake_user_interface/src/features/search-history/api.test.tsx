import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/queryKeys";
import type { SavedSearch } from "./api";

const apiClient = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));
vi.mock("@/api/apiClient", () => ({ apiClient }));
const enqueueSnackbar = vi.fn();
vi.mock("notistack", () => ({ useSnackbar: () => ({ enqueueSnackbar }) }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_key: string, fallback?: string) => fallback ?? _key }),
}));

import {
  useCreateSavedSearch,
  useDeleteSavedSearch,
  useRecordSearch,
  useSavedSearches,
  useSearchHistory,
} from "./api";

const saved = (id: string, name = id): SavedSearch => ({
  id,
  name,
  definition: { v: 1, q: name, semantic: false },
  fingerprint: `fp-${id}`,
  createdAt: "2026-09-01T00:00:00Z",
  updatedAt: "2026-09-01T00:00:00Z",
});

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

describe("search history / saved searches hooks", () => {
  beforeEach(() => vi.clearAllMocks());

  it("reads lists without redirecting on 403", async () => {
    apiClient.get.mockResolvedValue({ data: { data: { items: [saved("a")] } } });
    const { wrapper } = setup();
    const { result } = renderHook(() => useSavedSearches(), { wrapper });
    await waitFor(() => expect(result.current.data).toHaveLength(1));
    expect(apiClient.get).toHaveBeenCalledWith(
      "/users/saved-searches",
      expect.objectContaining({ skipAccessDeniedRedirect: true })
    );
  });

  it("recording a search replaces the cached history with the server's list", async () => {
    const items = [
      { fingerprint: "f", definition: { v: 1, q: "x", semantic: false }, searchedAt: "t" },
    ];
    apiClient.get.mockResolvedValue({ data: { data: { items: [] } } });
    apiClient.post.mockResolvedValue({ data: { data: { items } } });
    const { wrapper, client } = setup();
    const history = renderHook(() => useSearchHistory(), { wrapper });
    await waitFor(() => expect(history.result.current.isSuccess).toBe(true));

    const record = renderHook(() => useRecordSearch(), { wrapper });
    await act(() => record.result.current.mutateAsync({ v: 1, q: "x", semantic: false }));
    expect(client.getQueryData(QUERY_KEYS.SEARCH_HISTORY.all)).toEqual(items);
    // History is a convenience: failures are never shown to the user.
    expect(enqueueSnackbar).not.toHaveBeenCalled();
  });

  it("saving an already-saved search does not add a duplicate", async () => {
    const { wrapper, client } = setup();
    client.setQueryData(QUERY_KEYS.SAVED_SEARCHES.all, [saved("a")]);
    apiClient.post.mockResolvedValue({ data: { data: { ...saved("a"), existing: true } } });
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper });
    await act(() =>
      result.current.mutateAsync({ name: "again", definition: saved("a").definition })
    );
    expect(client.getQueryData(QUERY_KEYS.SAVED_SEARCHES.all)).toEqual([saved("a")]);
    expect(enqueueSnackbar).toHaveBeenCalledWith(
      expect.stringContaining("already saved"),
      expect.objectContaining({ variant: "info" })
    );
  });

  it("a new saved search goes to the top", async () => {
    const { wrapper, client } = setup();
    client.setQueryData(QUERY_KEYS.SAVED_SEARCHES.all, [saved("a")]);
    apiClient.post.mockResolvedValue({ data: { data: { ...saved("b"), existing: false } } });
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper });
    await act(() => result.current.mutateAsync({ name: "b", definition: saved("b").definition }));
    const list = client.getQueryData<SavedSearch[]>(QUERY_KEYS.SAVED_SEARCHES.all)!;
    expect(list.map((s) => s.id)).toEqual(["b", "a"]);
  });

  it("shows the API's message when saving fails (e.g. the 50-search cap)", async () => {
    const { wrapper } = setup();
    apiClient.post.mockRejectedValue({
      response: { status: 409, data: { message: "You can save at most 50 searches." } },
    });
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper });
    await act(async () => {
      await result.current
        .mutateAsync({ name: "x", definition: saved("x").definition })
        .catch(() => undefined);
    });
    expect(enqueueSnackbar).toHaveBeenCalledWith(
      "You can save at most 50 searches.",
      expect.objectContaining({ variant: "error" })
    );
  });

  it("deleting removes optimistically and rolls back on failure", async () => {
    const { wrapper, client } = setup();
    client.setQueryData(QUERY_KEYS.SAVED_SEARCHES.all, [saved("a"), saved("b")]);
    let reject!: (e: unknown) => void;
    apiClient.delete.mockReturnValue(new Promise((_r, rej) => (reject = rej)));
    const { result } = renderHook(() => useDeleteSavedSearch(), { wrapper });

    act(() => result.current.mutate("a"));
    await waitFor(() =>
      expect(
        client.getQueryData<SavedSearch[]>(QUERY_KEYS.SAVED_SEARCHES.all)!.map((s) => s.id)
      ).toEqual(["b"])
    );
    await act(async () => reject(new Error("boom")));
    await waitFor(() =>
      expect(
        client.getQueryData<SavedSearch[]>(QUERY_KEYS.SAVED_SEARCHES.all)!.map((s) => s.id)
      ).toEqual(["a", "b"])
    );
    expect(enqueueSnackbar).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ variant: "error" })
    );
  });
});
