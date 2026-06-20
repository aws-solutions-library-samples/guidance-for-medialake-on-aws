import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock logger
vi.mock("@/common/helpers/logger", () => ({
  logger: { warn: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

// Mock apiClient
const mockGet = vi.fn();
vi.mock("@/api/apiClient", () => ({
  apiClient: { get: (...args: any[]) => mockGet(...args) },
}));

import { useMyAssetsConnector } from "./useMyAssetsConnector";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useMyAssetsConnector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns connector data on success", async () => {
    const connectorData = {
      id: "ma-1",
      name: "My Assets",
      type: "my-assets",
      storageIdentifier: "personal-bucket",
      objectPrefix: "user/",
      status: "active",
      region: "us-east-1",
    };

    mockGet.mockResolvedValue({
      data: {
        status: "200",
        message: "ok",
        data: { connector: connectorData },
      },
    });

    const { result } = renderHook(() => useMyAssetsConnector(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.connector).toEqual(
      expect.objectContaining({ id: "ma-1", storageIdentifier: "personal-bucket" })
    );
    expect(mockGet).toHaveBeenCalledWith(
      "/connectors/my-assets",
      expect.objectContaining({ skipAccessDeniedRedirect: true })
    );
  });

  it("returns null connector gracefully on API failure", async () => {
    mockGet.mockRejectedValue({ response: { status: 403 }, message: "Forbidden" });

    const { result } = renderHook(() => useMyAssetsConnector(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.connector).toBeNull();
  });

  it("returns null connector on network error", async () => {
    mockGet.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useMyAssetsConnector(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.connector).toBeNull();
  });
});
