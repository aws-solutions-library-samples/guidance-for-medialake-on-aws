/**
 * `useSearch` retry behaviour: only failures that might succeed on a second
 * attempt are retried. A failure the search API reports in its response body
 * (for example semantic search not being configured) used to be sent four
 * times.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import React from "react";

import { server } from "../../../mocks/server";

vi.mock("@/hooks/useErrorModal", () => ({
  useErrorModal: () => ({ showError: vi.fn() }),
}));

import { useSearch, shouldRetrySearch, type SearchError } from "../useSearch";

const FAKE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.sig";

function renderSearch() {
  // No retry override here: the hook's own retry policy is what's under test.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retryDelay: 0 } } });
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  return renderHook(() => useSearch("bars", { isSemantic: true }), { wrapper });
}

function countSearchRequests(respond: () => Response) {
  const counter = { count: 0 };
  server.use(
    http.get("*/search", () => {
      counter.count++;
      return respond();
    })
  );
  return counter;
}

describe("useSearch retries", () => {
  beforeEach(() => {
    localStorage.setItem("medialake-auth-token", FAKE_JWT);
  });

  it("does not retry a failure reported in the response body", async () => {
    const requests = countSearchRequests(() =>
      HttpResponse.json({
        status: "500",
        message: "Search service temporarily unavailable",
        data: null,
      })
    );

    const { result } = renderSearch();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Search service temporarily unavailable");
    expect(requests.count).toBe(1);
  });

  it("does not retry an HTTP 4xx", async () => {
    const requests = countSearchRequests(() =>
      HttpResponse.json({ message: "Invalid query" }, { status: 400 })
    );

    const { result } = renderSearch();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(requests.count).toBe(1);
  });

  it("retries a gateway 5xx up to three times", async () => {
    const requests = countSearchRequests(() =>
      HttpResponse.json({ message: "Service Unavailable" }, { status: 503 })
    );

    const { result } = renderSearch();

    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 5000 });
    expect(requests.count).toBe(4);
  });

  it("recovers when a retried request succeeds", async () => {
    let calls = 0;
    server.use(
      http.get("*/search", () => {
        calls++;
        if (calls === 1) return HttpResponse.json({ message: "Bad Gateway" }, { status: 502 });
        return HttpResponse.json({
          status: "200",
          message: "ok",
          data: { results: [], searchMetadata: { totalResults: 0 } },
        });
      })
    );

    const { result } = renderSearch();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(2);
  });
});

describe("shouldRetrySearch", () => {
  const err = (props: Partial<SearchError> & { response?: { status: number } }) =>
    Object.assign(new Error("x"), props) as SearchError;

  it("stops after three retries", () => {
    expect(shouldRetrySearch(2, err({}))).toBe(true);
    expect(shouldRetrySearch(3, err({}))).toBe(false);
  });

  it("never retries non-retryable errors or 403s", () => {
    expect(shouldRetrySearch(0, err({ retryable: false }))).toBe(false);
    expect(shouldRetrySearch(0, err({ response: { status: 403 } }))).toBe(false);
  });
});
