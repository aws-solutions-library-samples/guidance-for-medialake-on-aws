import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { SearchDefinition } from "./searchDefinition";

const mutate = vi.fn();
vi.mock("./api", () => ({
  useRecordSearch: () => ({ mutate }),
  useSavedSearches: () => ({ data: [], isLoading: false }),
  useSearchHistory: () => ({ data: [] }),
}));
vi.mock("react-router", () => ({ useNavigate: () => vi.fn() }));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import { RECORD_AFTER_MS, useRecordSearchOnSettle } from "./hooks";

const def = (q: string): SearchDefinition => ({ v: 1, q, semantic: false });

describe("useRecordSearchOnSettle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mutate.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it("records a search once its results have stayed on screen", () => {
    renderHook(() => useRecordSearchOnSettle(def("sunset"), { settled: true }));
    act(() => vi.advanceTimersByTime(RECORD_AFTER_MS - 1));
    expect(mutate).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(mutate).toHaveBeenCalledWith(def("sunset"));
  });

  it("skips the intermediate searches fired while typing", () => {
    const { rerender } = renderHook(({ q }) => useRecordSearchOnSettle(def(q), { settled: true }), {
      initialProps: { q: "sun" },
    });
    act(() => vi.advanceTimersByTime(500));
    rerender({ q: "suns" });
    act(() => vi.advanceTimersByTime(500));
    rerender({ q: "sunset" });
    act(() => vi.advanceTimersByTime(RECORD_AFTER_MS));
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate).toHaveBeenCalledWith(def("sunset"));
  });

  it("waits until results have loaded", () => {
    const { rerender } = renderHook(
      ({ settled }) => useRecordSearchOnSettle(def("x"), { settled }),
      { initialProps: { settled: false } }
    );
    act(() => vi.advanceTimersByTime(RECORD_AFTER_MS * 2));
    expect(mutate).not.toHaveBeenCalled();
    rerender({ settled: true });
    act(() => vi.advanceTimersByTime(RECORD_AFTER_MS));
    expect(mutate).toHaveBeenCalledTimes(1);
  });

  it("does not record the same search twice in a row, or blank searches", () => {
    const { rerender } = renderHook(
      ({ settled, q }) => useRecordSearchOnSettle(def(q), { settled }),
      { initialProps: { settled: true, q: "x" } }
    );
    act(() => vi.advanceTimersByTime(RECORD_AFTER_MS));
    // Paging or a refetch toggles `settled` without changing the search.
    rerender({ settled: false, q: "x" });
    rerender({ settled: true, q: "x" });
    act(() => vi.advanceTimersByTime(RECORD_AFTER_MS));
    rerender({ settled: true, q: "" });
    act(() => vi.advanceTimersByTime(RECORD_AFTER_MS));
    expect(mutate).toHaveBeenCalledTimes(1);
  });
});
