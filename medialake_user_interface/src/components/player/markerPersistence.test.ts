import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadMarkers, saveMarkers, type PersistedMarker } from "./markerPersistence";

const ASSET = "asset:uuid:abc";
const KEY = `markers:${ASSET}`;

const marker = (overrides: Partial<PersistedMarker> = {}): PersistedMarker => ({
  startTime: 10,
  endTime: 20,
  label: "Marker 1",
  color: "#abcdef",
  ...overrides,
});

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("saveMarkers / loadMarkers", () => {
  it("round-trips markers for an asset", () => {
    saveMarkers(ASSET, [marker(), marker({ startTime: 30, endTime: 40, label: "Marker 2" })]);
    const loaded = loadMarkers(ASSET);

    expect(loaded).toHaveLength(2);
    expect(loaded[0]).toMatchObject({ startTime: 10, endTime: 20, label: "Marker 1" });
  });

  it("keeps assets independent", () => {
    saveMarkers(ASSET, [marker()]);
    expect(loadMarkers("asset:uuid:other")).toEqual([]);
  });

  it("removes the entry entirely when the last marker is deleted", () => {
    saveMarkers(ASSET, [marker()]);
    saveMarkers(ASSET, []);

    // An empty array left behind would be indistinguishable from "never saved"
    // on read, but leaves a growing set of dead keys in storage.
    expect(localStorage.getItem(KEY)).toBeNull();
    expect(loadMarkers(ASSET)).toEqual([]);
  });

  it("ignores a blank asset id rather than writing a `markers:` key", () => {
    saveMarkers("", [marker()]);
    expect(localStorage.getItem("markers:")).toBeNull();
    expect(loadMarkers("")).toEqual([]);
  });
});

describe("loadMarkers resilience", () => {
  it("returns empty for absent, malformed, or non-array data", () => {
    expect(loadMarkers(ASSET)).toEqual([]);

    localStorage.setItem(KEY, "not json");
    expect(loadMarkers(ASSET)).toEqual([]);

    localStorage.setItem(KEY, JSON.stringify({ startTime: 1, endTime: 2 }));
    expect(loadMarkers(ASSET)).toEqual([]);
  });

  it("drops individual bad records but keeps the good ones", () => {
    // One hand-edited or truncated entry should not cost the user every marker.
    localStorage.setItem(
      KEY,
      JSON.stringify([
        marker(),
        { startTime: "ten", endTime: 20 },
        null,
        { startTime: 5 },
        marker({ startTime: 30, endTime: 40 }),
      ])
    );

    const loaded = loadMarkers(ASSET);
    expect(loaded).toHaveLength(2);
    expect(loaded.map((m) => m.startTime)).toEqual([10, 30]);
  });

  it("drops inverted and zero-length ranges", () => {
    localStorage.setItem(
      KEY,
      JSON.stringify([marker({ startTime: 20, endTime: 10 }), marker({ startTime: 5, endTime: 5 })])
    );
    expect(loadMarkers(ASSET)).toEqual([]);
  });

  it("discards the pre-1.1.1 revision-envelope format", () => {
    // The old MarkerSyncCoordinator stored envelopes, which carry no times at
    // all — there is nothing to migrate, so they are filtered out rather than
    // producing markers at 0.
    localStorage.setItem(
      KEY,
      JSON.stringify([
        { id: "m1", revision: 3, updatedAt: 1, source: "sidebar", sessionId: "s" },
        { id: "m2", revision: 1, updatedAt: 2, source: "track", sessionId: "s" },
      ])
    );
    expect(loadMarkers(ASSET)).toEqual([]);
  });

  it("survives storage being unavailable", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    expect(loadMarkers(ASSET)).toEqual([]);
  });
});

describe("saveMarkers resilience", () => {
  it("swallows a quota failure so marker editing does not break playback", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() => saveMarkers(ASSET, [marker()])).not.toThrow();
  });
});
