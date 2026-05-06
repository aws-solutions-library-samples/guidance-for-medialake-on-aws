import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCollectionViewPreferences, DEFAULT_PREFS } from "./useCollectionViewPreferences";

const STORAGE_KEY = "medialake.collectionViewPrefs.v1";

describe("useCollectionViewPreferences", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("starts from DEFAULT_PREFS when there is nothing in storage", () => {
    const { result } = renderHook(() => useCollectionViewPreferences());
    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
  });

  it("setPreset rewrites the toggle profile and labels the preset", () => {
    const { result } = renderHook(() => useCollectionViewPreferences());

    act(() => result.current.setPreset("compact"));

    expect(result.current.prefs.preset).toBe("compact");
    expect(result.current.prefs.showDescription).toBe(false);
    expect(result.current.prefs.showTags).toBe(true);
    expect(result.current.prefs.maxMetadataKeys).toBe(0);
  });

  it("toggleCoreField flips one field and re-labels preset as 'custom'", () => {
    const { result } = renderHook(() => useCollectionViewPreferences());

    // Starting preset is rich; toggling description off puts us in custom territory.
    act(() => result.current.toggleCoreField("description"));

    expect(result.current.prefs.showDescription).toBe(false);
    expect(result.current.prefs.preset).toBe("custom");
  });

  it("toggleCoreField re-labels back to a known preset when toggles match it", () => {
    const { result } = renderHook(() => useCollectionViewPreferences());

    // Go to compact (description off, meta/tags/visibility on, max=0, parentBC on)
    act(() => result.current.setPreset("compact"));
    // Flipping description back on moves us to rich territory but max stays 0,
    // so we remain custom. Validates inferPreset doesn't false-positive.
    act(() => result.current.toggleCoreField("description"));
    expect(result.current.prefs.preset).toBe("custom");
  });

  it("toggleMetadataKey adds and removes keys from visibleMetadataKeys", () => {
    const { result } = renderHook(() => useCollectionViewPreferences());

    act(() => result.current.toggleMetadataKey("priority"));
    expect(result.current.prefs.visibleMetadataKeys).toEqual(["priority"]);

    act(() => result.current.toggleMetadataKey("client"));
    expect(result.current.prefs.visibleMetadataKeys).toEqual(["priority", "client"]);

    act(() => result.current.toggleMetadataKey("priority"));
    expect(result.current.prefs.visibleMetadataKeys).toEqual(["client"]);
  });

  it("seeds visibleMetadataKeys alphabetically when storage is empty", () => {
    const { result, rerender } = renderHook(
      ({ keys }: { keys: string[] }) =>
        useCollectionViewPreferences({ availableMetadataKeys: keys }),
      { initialProps: { keys: [] as string[] } }
    );

    expect(result.current.prefs.visibleMetadataKeys).toEqual([]);

    rerender({ keys: ["episode", "client", "priority", "version"] });

    expect(result.current.prefs.visibleMetadataKeys).toEqual(["client", "episode", "priority"]);
    expect(result.current.prefs.metadataKeysInitialized).toBe(true);
  });

  it("re-seeds users whose saved prefs predate the init flag", () => {
    // Simulate an early-rollout user whose saved prefs have no
    // metadataKeysInitialized flag and an empty visibleMetadataKeys list.
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        ...DEFAULT_PREFS,
        visibleMetadataKeys: [],
        // metadataKeysInitialized intentionally omitted
      })
    );

    const { result } = renderHook(() =>
      useCollectionViewPreferences({
        availableMetadataKeys: ["client", "episode", "priority"],
      })
    );

    expect(result.current.prefs.visibleMetadataKeys).toEqual(["client", "episode", "priority"]);
    expect(result.current.prefs.metadataKeysInitialized).toBe(true);
  });

  it("does not re-seed after the user has emptied the list explicitly", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        ...DEFAULT_PREFS,
        visibleMetadataKeys: [],
        metadataKeysInitialized: true,
      })
    );

    const { result } = renderHook(() =>
      useCollectionViewPreferences({
        availableMetadataKeys: ["client", "episode", "priority"],
      })
    );

    expect(result.current.prefs.visibleMetadataKeys).toEqual([]);
  });

  it("prunes stale keys when the available list changes", () => {
    // Pre-seed storage with keys that no longer exist.
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        ...DEFAULT_PREFS,
        visibleMetadataKeys: ["legacy-key", "priority"],
      })
    );

    const { result } = renderHook(() =>
      useCollectionViewPreferences({
        availableMetadataKeys: ["priority", "client"],
      })
    );

    // "legacy-key" is pruned, "priority" survives.
    expect(result.current.prefs.visibleMetadataKeys).toEqual(["priority"]);
  });

  it("persists changes to localStorage", async () => {
    const { result } = renderHook(() => useCollectionViewPreferences());

    act(() => result.current.setPreset("full"));

    // Debounce is 150ms; wait past it and check storage.
    await new Promise((r) => setTimeout(r, 200));

    const raw = localStorage.getItem(STORAGE_KEY);
    expect(raw).toBeTruthy();
    const saved = JSON.parse(raw!);
    expect(saved.preset).toBe("full");
    expect(saved.maxMetadataKeys).toBe(20);
  });

  it("rejects corrupted storage and falls back to DEFAULT_PREFS", () => {
    localStorage.setItem(STORAGE_KEY, "{not valid json");
    const { result } = renderHook(() => useCollectionViewPreferences());
    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
  });

  it("rejects storage that doesn't match the schema", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ preset: "bogus", cardSize: 999 }));
    const { result } = renderHook(() => useCollectionViewPreferences());
    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
  });

  it("reset returns to DEFAULT_PREFS", () => {
    const { result } = renderHook(() => useCollectionViewPreferences());

    act(() => result.current.setPreset("full"));
    act(() => result.current.setCardSize("large"));
    act(() => result.current.toggleMetadataKey("priority"));
    act(() => result.current.reset());

    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
  });
});
