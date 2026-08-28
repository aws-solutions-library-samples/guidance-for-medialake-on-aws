import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  useRecentBinActions,
  __resetRecentBinActionsCache,
  type RecentBinAction,
} from "./useRecentBinActions";

const STORAGE_KEY = "medialake.binRecentActions.v1";

const seed = (entries: unknown) => localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));

const stored = (): RecentBinAction[] => JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");

beforeEach(() => {
  localStorage.clear();
  __resetRecentBinActionsCache();
});

describe("useRecentBinActions", () => {
  it("starts empty when nothing is stored", () => {
    const { result } = renderHook(() => useRecentBinActions());
    expect(result.current.recents).toEqual([]);
  });

  it("reads stored entries most-recently-used first", () => {
    seed([
      { kind: "collection", id: "c1", name: "Older", usedAt: 1 },
      { kind: "workflow", id: "w1", name: "Newer", usedAt: 9 },
    ]);

    const { result } = renderHook(() => useRecentBinActions());

    expect(result.current.recents.map((r) => r.name)).toEqual(["Newer", "Older"]);
  });

  it("records a use, moving the entry to the front and persisting it", () => {
    seed([{ kind: "collection", id: "c1", name: "First", usedAt: 1 }]);
    const { result } = renderHook(() => useRecentBinActions());

    act(() => result.current.recordUse("collection", "c2", "Second"));

    expect(result.current.recents[0]).toMatchObject({ id: "c2", name: "Second" });
    expect(stored().map((e) => e.id)).toEqual(["c2", "c1"]);
  });

  it("deduplicates by kind+id and refreshes the cached name", () => {
    seed([{ kind: "collection", id: "c1", name: "Old Name", usedAt: 1 }]);
    const { result } = renderHook(() => useRecentBinActions());

    act(() => result.current.recordUse("collection", "c1", "Renamed"));

    const collections = result.current.recents.filter((r) => r.kind === "collection");
    expect(collections).toHaveLength(1);
    expect(collections[0].name).toBe("Renamed");
  });

  it("treats the same id under different kinds as separate entries", () => {
    const { result } = renderHook(() => useRecentBinActions());

    act(() => result.current.recordUse("collection", "shared-id", "A Collection"));
    act(() => result.current.recordUse("workflow", "shared-id", "A Workflow"));

    expect(result.current.recents).toHaveLength(2);
  });

  it("caps stored entries per kind, dropping the least recently used", () => {
    const { result } = renderHook(() => useRecentBinActions());

    for (let i = 0; i < 12; i++) {
      act(() => result.current.recordUse("collection", `c${i}`, `Collection ${i}`));
    }

    const collections = result.current.recents.filter((r) => r.kind === "collection");
    expect(collections).toHaveLength(8);
    // The most recent survives, the first does not.
    expect(collections.some((c) => c.id === "c11")).toBe(true);
    expect(collections.some((c) => c.id === "c0")).toBe(false);
  });

  it("caps each kind independently", () => {
    const { result } = renderHook(() => useRecentBinActions());

    for (let i = 0; i < 10; i++) {
      act(() => result.current.recordUse("collection", `c${i}`, `Collection ${i}`));
      act(() => result.current.recordUse("workflow", `w${i}`, `Workflow ${i}`));
    }

    expect(result.current.recents.filter((r) => r.kind === "collection")).toHaveLength(8);
    expect(result.current.recents.filter((r) => r.kind === "workflow")).toHaveLength(8);
  });

  it("forgets an entry", () => {
    seed([
      { kind: "collection", id: "c1", name: "Keep", usedAt: 2 },
      { kind: "collection", id: "c2", name: "Drop", usedAt: 1 },
    ]);
    const { result } = renderHook(() => useRecentBinActions());

    act(() => result.current.forget("collection", "c2"));

    expect(result.current.recents.map((r) => r.id)).toEqual(["c1"]);
    expect(stored().map((e) => e.id)).toEqual(["c1"]);
  });

  it("ignores a forget for an entry that is not there", () => {
    seed([{ kind: "collection", id: "c1", name: "Keep", usedAt: 2 }]);
    const { result } = renderHook(() => useRecentBinActions());

    act(() => result.current.forget("workflow", "c1"));

    expect(result.current.recents).toHaveLength(1);
  });

  it("rejects a corrupted blob instead of throwing", () => {
    localStorage.setItem(STORAGE_KEY, "{not json");
    const { result } = renderHook(() => useRecentBinActions());
    expect(result.current.recents).toEqual([]);
  });

  it("rejects entries that do not match the schema", () => {
    seed([{ kind: "banana", id: "x", name: "Nope", usedAt: 1 }]);
    const { result } = renderHook(() => useRecentBinActions());
    expect(result.current.recents).toEqual([]);
  });

  it("skips a record with a blank id or name rather than storing an unusable chip", () => {
    const { result } = renderHook(() => useRecentBinActions());

    act(() => result.current.recordUse("collection", "   ", "No id"));
    act(() => result.current.recordUse("collection", "c1", "   "));

    expect(result.current.recents).toEqual([]);
  });

  it("keeps separate hook instances in sync", () => {
    const first = renderHook(() => useRecentBinActions());
    const second = renderHook(() => useRecentBinActions());

    act(() => first.result.current.recordUse("collection", "c1", "Shared"));

    expect(second.result.current.recents.map((r) => r.id)).toEqual(["c1"]);
  });
});
