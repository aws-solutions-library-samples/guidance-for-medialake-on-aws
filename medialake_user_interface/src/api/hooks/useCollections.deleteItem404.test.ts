/**
 * DELETE /collections/{id}/items/{itemId} now returns 404 when the item is not in
 * the collection (it previously returned 200 {"removed": true}, which made a real
 * removal indistinguishable from a no-op).
 *
 * The caller's intent — the item should not be in the collection — is already
 * satisfied by a 404, and it is reachable benignly from a double-click or a stale
 * list, so the hook treats it as success. Every other failure must still surface.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { AxiosError, AxiosHeaders } from "axios";

const showError = vi.fn();
vi.mock("@/hooks/useErrorModal", () => ({
  useErrorModal: () => ({ showError }),
}));

const del = vi.fn();
vi.mock("@/api/apiClient", () => ({
  apiClient: {
    delete: (...args: unknown[]) => del(...args),
  },
}));

import { useDeleteItemFromCollection } from "./useCollections";

const makeAxiosError = (status: number) =>
  new AxiosError("request failed", "ERR_BAD_REQUEST", undefined, undefined, {
    status,
    statusText: String(status),
    data: {},
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  });

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe("useDeleteItemFromCollection — 404 handling", () => {
  beforeEach(() => {
    del.mockReset();
    showError.mockReset();
  });

  it("resolves without surfacing an error when the item is already absent (404)", async () => {
    del.mockRejectedValueOnce(makeAxiosError(404));

    const { result } = renderHook(() => useDeleteItemFromCollection(), { wrapper });
    result.current.mutate({ collectionId: "col_1", itemId: "ASSET#a1#FULL" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(showError).not.toHaveBeenCalled();
  });

  it("still surfaces other failures", async () => {
    del.mockRejectedValueOnce(makeAxiosError(500));

    const { result } = renderHook(() => useDeleteItemFromCollection(), { wrapper });
    result.current.mutate({ collectionId: "col_1", itemId: "ASSET#a1#FULL" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(showError).toHaveBeenCalledWith("Failed to remove item from collection");
  });

  it("encodes the item id so ASSET# keys survive the path", async () => {
    del.mockResolvedValueOnce({ data: {} });

    const { result } = renderHook(() => useDeleteItemFromCollection(), { wrapper });
    result.current.mutate({ collectionId: "col_1", itemId: "ASSET#a1#FULL" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(del).toHaveBeenCalledWith("/collections/col_1/items/ASSET%23a1%23FULL");
  });
});
