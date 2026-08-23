import { describe, it, expect } from "vitest";
import type { Collection } from "@/api/hooks/useCollections";
import {
  UPLOAD_LOCATION_SCHEMA_VERSION,
  buildUploadLocationLabel,
  isSameUploadLocation,
  normalizeUploadPath,
  parseFavoriteLocationsSetting,
  parseLastLocationSetting,
  reconcileUploadLocationCollections,
} from "./uploadLocation.types";

const collection = (id: string, overrides: Partial<Collection> = {}): Collection =>
  ({
    id,
    name: `Collection ${id}`,
    status: "ACTIVE",
    userRole: "owner",
    ...overrides,
  }) as Collection;

describe("normalizeUploadPath", () => {
  it("treats empty, missing and root paths as the connector default", () => {
    expect(normalizeUploadPath(undefined)).toBe("");
    expect(normalizeUploadPath(null)).toBe("");
    expect(normalizeUploadPath("")).toBe("");
    expect(normalizeUploadPath("   ")).toBe("");
    expect(normalizeUploadPath("/")).toBe("");
  });

  it("strips leading slashes, collapses doubles and adds exactly one trailing slash", () => {
    expect(normalizeUploadPath("projects/a")).toBe("projects/a/");
    expect(normalizeUploadPath("projects/a/")).toBe("projects/a/");
    expect(normalizeUploadPath("/projects/a")).toBe("projects/a/");
    expect(normalizeUploadPath("///projects//a//")).toBe("projects/a/");
  });

  it("is idempotent", () => {
    const once = normalizeUploadPath("/projects//a");
    expect(normalizeUploadPath(once)).toBe(once);
  });
});

describe("isSameUploadLocation", () => {
  it("ignores path formatting differences", () => {
    expect(
      isSameUploadLocation(
        { connectorId: "c1", path: "projects/a" },
        { connectorId: "c1", path: "/projects/a/" }
      )
    ).toBe(true);
  });

  it("distinguishes different paths on the same connector", () => {
    expect(
      isSameUploadLocation(
        { connectorId: "c1", path: "projects/a/" },
        { connectorId: "c1", path: "projects/b/" }
      )
    ).toBe(false);
  });

  it("distinguishes the same path on different connectors", () => {
    expect(
      isSameUploadLocation(
        { connectorId: "c1", path: "projects/a/" },
        { connectorId: "c2", path: "projects/a/" }
      )
    ).toBe(false);
  });

  it("treats an empty path and a root path as the same destination", () => {
    expect(
      isSameUploadLocation({ connectorId: "c1", path: "" }, { connectorId: "c1", path: "/" })
    ).toBe(true);
  });

  it("is false when either side is missing", () => {
    expect(isSameUploadLocation(null, { connectorId: "c1", path: "" })).toBe(false);
    expect(isSameUploadLocation({ connectorId: "c1", path: "" }, undefined)).toBe(false);
  });
});

describe("buildUploadLocationLabel", () => {
  it("uses the connector name alone when the path is the default root", () => {
    expect(buildUploadLocationLabel("prod-media", "")).toBe("prod-media");
    expect(buildUploadLocationLabel("My Assets", "/")).toBe("My Assets");
  });

  it("appends the normalised path when there is one", () => {
    expect(buildUploadLocationLabel("prod-media", "projects/a")).toBe("prod-media / projects/a/");
  });
});

describe("reconcileUploadLocationCollections", () => {
  it("returns nothing when no collections were saved", () => {
    expect(reconcileUploadLocationCollections(undefined, [collection("a")])).toEqual({
      collections: [],
      dropped: [],
    });
  });

  it("keeps everything while the live list is still loading", () => {
    const saved = [{ id: "a", name: "A" }];
    expect(reconcileUploadLocationCollections(saved, undefined)).toEqual({
      collections: saved,
      dropped: [],
    });
  });

  it("drops collections that no longer exist", () => {
    const result = reconcileUploadLocationCollections(
      [
        { id: "a", name: "A" },
        { id: "gone", name: "Deleted" },
      ],
      [collection("a")]
    );
    expect(result.collections).toEqual([{ id: "a", name: "Collection a" }]);
    expect(result.dropped).toEqual([{ id: "gone", name: "Deleted" }]);
  });

  it("drops collections the user can no longer add assets to", () => {
    const result = reconcileUploadLocationCollections(
      [{ id: "viewer-only", name: "Read only" }],
      [collection("viewer-only", { userRole: "viewer" })]
    );
    expect(result.collections).toEqual([]);
    expect(result.dropped).toEqual([{ id: "viewer-only", name: "Read only" }]);
  });

  it("drops archived collections", () => {
    const result = reconcileUploadLocationCollections(
      [{ id: "a", name: "A" }],
      [collection("a", { status: "ARCHIVED" } as Partial<Collection>)]
    );
    expect(result.collections).toEqual([]);
    expect(result.dropped).toHaveLength(1);
  });

  it("prefers the live name over the stored one, which goes stale on rename", () => {
    const result = reconcileUploadLocationCollections(
      [{ id: "a", name: "Old name" }],
      [collection("a", { name: "Renamed" })]
    );
    expect(result.collections).toEqual([{ id: "a", name: "Renamed" }]);
  });
});

describe("parseFavoriteLocationsSetting", () => {
  it("reads a well-formed payload", () => {
    const locations = parseFavoriteLocationsSetting({
      version: UPLOAD_LOCATION_SCHEMA_VERSION,
      defaultId: null,
      locations: [{ id: "1", label: "L", connectorId: "c1", path: "a/" }],
    });
    expect(locations).toHaveLength(1);
    expect(locations[0].connectorId).toBe("c1");
  });

  it("ignores payloads from an unknown schema version rather than misreading them", () => {
    expect(
      parseFavoriteLocationsSetting({
        version: 999,
        locations: [{ id: "1", label: "L", connectorId: "c1", path: "a/" }],
      })
    ).toEqual([]);
  });

  // Regression: GET /users/settings serialises DynamoDB's Decimal('1') as the string
  // "1" (json.dumps default=str), while PUT echoes the in-memory int as 1. A strict
  // !== against the numeric constant discarded every payload on read, so saved
  // locations disappeared on reload while the PUT response looked correct.
  it("accepts a stringified schema version, as the settings GET path returns", () => {
    const locations = parseFavoriteLocationsSetting({
      version: String(UPLOAD_LOCATION_SCHEMA_VERSION),
      defaultId: null,
      locations: [{ id: "1", label: "L", connectorId: "c1", path: "a/" }],
    });
    expect(locations).toHaveLength(1);
    expect(locations[0].connectorId).toBe("c1");
  });

  it("does not let version coercion accept non-numeric or boolean versions", () => {
    const locations = [{ id: "1", label: "L", connectorId: "c1", path: "a/" }];
    // Number(true) === 1 and Number("") === 0 would slip through a bare Number() cast.
    expect(parseFavoriteLocationsSetting({ version: true, locations })).toEqual([]);
    expect(parseFavoriteLocationsSetting({ version: "", locations })).toEqual([]);
    expect(parseFavoriteLocationsSetting({ version: null, locations })).toEqual([]);
    expect(parseFavoriteLocationsSetting({ version: "abc", locations })).toEqual([]);
    expect(parseFavoriteLocationsSetting({ version: "999", locations })).toEqual([]);
  });

  it("is defensive about malformed input", () => {
    expect(parseFavoriteLocationsSetting(undefined)).toEqual([]);
    expect(parseFavoriteLocationsSetting("nonsense")).toEqual([]);
    expect(parseFavoriteLocationsSetting({ version: 1 })).toEqual([]);
    expect(parseFavoriteLocationsSetting({ version: 1, locations: "no" })).toEqual([]);
  });

  it("drops entries whose path or label is not a string", () => {
    // PUT /users/settings accepts arbitrary JSON, so these shapes are storable — and a
    // non-string path would throw inside normalizeUploadPath's .trim().
    const locations = parseFavoriteLocationsSetting({
      version: UPLOAD_LOCATION_SCHEMA_VERSION,
      defaultId: null,
      locations: [
        { id: "bad-path", label: "L", connectorId: "c1", path: 123 },
        { id: "bad-label", label: 7, connectorId: "c1", path: "a/" },
        { id: "ok", label: "L", connectorId: "c1", path: "a/" },
        { id: "ok-no-path", label: "L", connectorId: "c1" },
      ],
    });

    expect(locations.map((entry) => entry.id)).toEqual(["ok", "ok-no-path"]);
    // The surviving entries must be safe to normalise.
    expect(() => locations.forEach((entry) => normalizeUploadPath(entry.path))).not.toThrow();
  });

  it("drops entries missing an id or a connector", () => {
    expect(
      parseFavoriteLocationsSetting({
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        defaultId: null,
        locations: [
          { id: "", label: "L", connectorId: "c1", path: "" },
          { id: "2", label: "L", connectorId: "", path: "" },
          { id: "3", label: "L", connectorId: "c3", path: "" },
        ],
      }).map((entry) => entry.id)
    ).toEqual(["3"]);
  });
});

describe("parseLastLocationSetting", () => {
  it("reads and normalises a well-formed payload", () => {
    expect(
      parseLastLocationSetting({
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        connectorId: "c1",
        path: "/projects//a",
        collections: [{ id: "x", name: "X" }],
      })
    ).toEqual({
      connectorId: "c1",
      path: "projects/a/",
      collections: [{ id: "x", name: "X" }],
    });
  });

  it("accepts a location with no path, meaning the connector default", () => {
    expect(
      parseLastLocationSetting({ version: UPLOAD_LOCATION_SCHEMA_VERSION, connectorId: "c1" })
    ).toEqual({ connectorId: "c1", path: "", collections: [] });
  });

  it("rejects malformed or unversioned payloads", () => {
    expect(parseLastLocationSetting(null)).toBeNull();
    expect(parseLastLocationSetting({ connectorId: "c1" })).toBeNull();
    expect(parseLastLocationSetting({ version: 2, connectorId: "c1" })).toBeNull();
    expect(parseLastLocationSetting({ version: 1, connectorId: "" })).toBeNull();
    expect(parseLastLocationSetting({ version: true, connectorId: "c1" })).toBeNull();
    expect(parseLastLocationSetting({ version: "", connectorId: "c1" })).toBeNull();
  });

  // Regression: see the matching case in parseFavoriteLocationsSetting. This is why the
  // uploader reopened on the default destination instead of the last-used one.
  it("accepts a stringified schema version, as the settings GET path returns", () => {
    expect(
      parseLastLocationSetting({
        version: String(UPLOAD_LOCATION_SCHEMA_VERSION),
        connectorId: "c1",
        path: "a/",
        updatedAt: "1786593960338",
      })
    ).toEqual({ connectorId: "c1", path: "a/", collections: [] });
  });

  it("rejects a non-string path rather than throwing when it is normalised", () => {
    expect(
      parseLastLocationSetting({
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        connectorId: "c1",
        path: 123,
      })
    ).toBeNull();
  });
});
