import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ConnectorSummary } from "@/api/hooks/useSearchConnectors";
import type { Collection } from "@/api/hooks/useCollections";

let mockSettings: Record<string, unknown> = {};
let mockIsLoading = false;
const mockPutSetting = vi.fn();

vi.mock("@/api/hooks/useUserSettings", () => ({
  useGetUserSettings: () => ({ data: mockSettings, isLoading: mockIsLoading }),
  usePutUserSetting: () => ({ mutate: mockPutSetting }),
}));

import { useUploadLocations } from "./useUploadLocations";
import {
  FAVORITE_LOCATIONS_SETTING_KEY,
  LAST_LOCATION_SETTING_KEY,
  MAX_FAVORITE_LOCATIONS,
  UPLOAD_LOCATION_SCHEMA_VERSION,
} from "../types/uploadLocation.types";

const connector = (id: string, overrides: Partial<ConnectorSummary> = {}): ConnectorSummary => ({
  id,
  name: id,
  type: "s3",
  status: "active",
  storageIdentifier: `${id}-bucket`,
  ...overrides,
});

const favoritesSetting = (locations: unknown[]) => ({
  [FAVORITE_LOCATIONS_SETTING_KEY]: {
    version: UPLOAD_LOCATION_SCHEMA_VERSION,
    defaultId: null,
    locations,
  },
});

const renderUploadLocations = (
  args: {
    selectableConnectors?: ConnectorSummary[];
    myAssetsConnectorId?: string;
    myAssetsObjectPrefix?: string;
    liveCollections?: Collection[];
  } = {}
) =>
  renderHook(() =>
    useUploadLocations({
      selectableConnectors: args.selectableConnectors ?? [connector("c1")],
      myAssetsConnectorId: args.myAssetsConnectorId,
      myAssetsObjectPrefix: args.myAssetsObjectPrefix,
      liveCollections: args.liveCollections,
    })
  );

beforeEach(() => {
  mockSettings = {};
  mockIsLoading = false;
  mockPutSetting.mockReset();
});

describe("favorites availability", () => {
  it("exposes a favorite whose connector is still a valid target", () => {
    mockSettings = favoritesSetting([
      { id: "f1", label: "c1 / a/", connectorId: "c1", path: "a/" },
    ]);

    const { result } = renderUploadLocations();

    expect(result.current.availableFavorites).toHaveLength(1);
    expect(result.current.favorites[0].available).toBe(true);
  });

  it("marks a favorite unavailable when its connector is gone, with a reason for the UI", () => {
    mockSettings = favoritesSetting([
      { id: "f1", label: "gone", connectorId: "deleted-connector", path: "a/" },
    ]);

    const { result } = renderUploadLocations();

    expect(result.current.availableFavorites).toHaveLength(0);
    // Kept in the full list so management UI can explain rather than silently drop it.
    expect(result.current.favorites).toHaveLength(1);
    expect(result.current.favorites[0].unavailableReason).toBe("connector-missing");
  });

  it("marks a favorite unavailable when its path is outside the connector's allowed prefixes", () => {
    mockSettings = favoritesSetting([
      { id: "f1", label: "outside", connectorId: "c1", path: "somewhere/else/" },
    ]);

    const { result } = renderUploadLocations({
      selectableConnectors: [connector("c1", { objectPrefix: ["projects/"] })],
    });

    expect(result.current.availableFavorites).toHaveLength(0);
    expect(result.current.favorites[0].unavailableReason).toBe("path-not-allowed");
  });

  it("accepts a path inside an allowed prefix", () => {
    mockSettings = favoritesSetting([
      { id: "f1", label: "inside", connectorId: "c1", path: "projects/a/" },
    ]);

    const { result } = renderUploadLocations({
      selectableConnectors: [connector("c1", { objectPrefix: "projects/" })],
    });

    expect(result.current.availableFavorites).toHaveLength(1);
  });

  it("accepts an empty path, which means the connector default root", () => {
    mockSettings = favoritesSetting([{ id: "f1", label: "root", connectorId: "c1", path: "" }]);

    const { result } = renderUploadLocations({
      selectableConnectors: [connector("c1", { objectPrefix: ["projects/"] })],
    });

    expect(result.current.availableFavorites).toHaveLength(1);
  });

  it("treats My Assets as a valid target even though it is not in the selectable list", () => {
    mockSettings = favoritesSetting([
      { id: "f1", label: "My Assets", connectorId: "my-assets", path: "personal/sub/" },
    ]);

    const { result } = renderUploadLocations({
      selectableConnectors: [],
      myAssetsConnectorId: "my-assets",
      myAssetsObjectPrefix: "personal/sub/",
    });

    expect(result.current.availableFavorites).toHaveLength(1);
  });

  // The UI does not offer browsing inside My Assets, so in practice only the root is saved
  // (stored as an empty path). These two cases guard the validation of stored data anyway:
  // a path that arrives from anywhere must still be confined to the caller's own folder.
  it("accepts a stored My Assets sub-path inside the caller's own personal folder", () => {
    mockSettings = favoritesSetting([
      {
        id: "f1",
        label: "My Assets / projects",
        connectorId: "my-assets",
        path: "personal/sub/projects/",
      },
    ]);

    const { result } = renderUploadLocations({
      selectableConnectors: [],
      myAssetsConnectorId: "my-assets",
      myAssetsObjectPrefix: "personal/sub/",
    });

    expect(result.current.availableFavorites).toHaveLength(1);
  });

  it("rejects a stored My Assets path pointing at somebody else's personal folder", () => {
    mockSettings = favoritesSetting([
      {
        id: "f1",
        label: "someone else",
        connectorId: "my-assets",
        path: "personal/other-user/projects/",
      },
    ]);

    const { result } = renderUploadLocations({
      selectableConnectors: [],
      myAssetsConnectorId: "my-assets",
      myAssetsObjectPrefix: "personal/sub/",
    });

    expect(result.current.availableFavorites).toHaveLength(0);
    expect(result.current.favorites[0].unavailableReason).toBe("path-not-allowed");
  });
});

describe("saving and removing", () => {
  it("saves the current destination with an auto-derived label and the selected collections", () => {
    const { result } = renderUploadLocations();

    act(() => {
      result.current.toggleSaved(
        {
          connectorId: "c1",
          path: "projects/a",
          collections: [{ id: "col-1", name: "Client A" }],
        },
        "prod-media",
        "prod-bucket"
      );
    });

    expect(mockPutSetting).toHaveBeenCalledTimes(1);
    const payload = mockPutSetting.mock.calls[0][0];
    expect(payload.key).toBe(FAVORITE_LOCATIONS_SETTING_KEY);
    expect(payload.value.version).toBe(UPLOAD_LOCATION_SCHEMA_VERSION);
    // Reserved for the default-favorite phase, deliberately unset for now.
    expect(payload.value.defaultId).toBeNull();
    expect(payload.value.locations).toHaveLength(1);
    expect(payload.value.locations[0]).toMatchObject({
      label: "prod-media / projects/a/",
      connectorId: "c1",
      path: "projects/a/",
      collections: [{ id: "col-1", name: "Client A" }],
      connectorName: "prod-media",
      storageIdentifier: "prod-bucket",
    });
    expect(payload.value.locations[0].id).toBeTruthy();
  });

  it("omits collections entirely when none are selected", () => {
    const { result } = renderUploadLocations();

    act(() => {
      result.current.toggleSaved({ connectorId: "c1", path: "", collections: [] }, "prod-media");
    });

    expect(mockPutSetting.mock.calls[0][0].value.locations[0].collections).toBeUndefined();
  });

  it("removes the entry when toggling an already-saved destination", () => {
    mockSettings = favoritesSetting([
      { id: "f1", label: "keep", connectorId: "c1", path: "keep/" },
      { id: "f2", label: "drop", connectorId: "c1", path: "drop/" },
    ]);

    const { result } = renderUploadLocations();

    act(() => {
      result.current.toggleSaved({ connectorId: "c1", path: "drop/" }, "c1");
    });

    const saved = mockPutSetting.mock.calls[0][0].value.locations;
    expect(saved.map((entry: { id: string }) => entry.id)).toEqual(["f1"]);
  });

  it("recognises an already-saved destination regardless of path formatting", () => {
    mockSettings = favoritesSetting([
      { id: "f1", label: "saved", connectorId: "c1", path: "projects/a/" },
    ]);

    const { result } = renderUploadLocations();

    expect(result.current.isSaved({ connectorId: "c1", path: "/projects/a" })).toBe(true);
    expect(result.current.isSaved({ connectorId: "c1", path: "projects/b" })).toBe(false);
  });

  it("removes a favorite by id", () => {
    mockSettings = favoritesSetting([
      { id: "f1", label: "a", connectorId: "c1", path: "a/" },
      { id: "f2", label: "b", connectorId: "c1", path: "b/" },
    ]);

    const { result } = renderUploadLocations();

    act(() => {
      result.current.removeFavorite("f1");
    });

    expect(
      mockPutSetting.mock.calls[0][0].value.locations.map((e: { id: string }) => e.id)
    ).toEqual(["f2"]);
  });

  it("refuses to save beyond the cap but still allows removing", () => {
    mockSettings = favoritesSetting(
      Array.from({ length: MAX_FAVORITE_LOCATIONS }, (_, index) => ({
        id: `f${index}`,
        label: `l${index}`,
        connectorId: "c1",
        path: `p${index}/`,
      }))
    );

    const { result } = renderUploadLocations();
    expect(result.current.isAtCapacity).toBe(true);

    act(() => {
      result.current.toggleSaved({ connectorId: "c1", path: "one-too-many/" }, "c1");
    });
    expect(mockPutSetting).not.toHaveBeenCalled();

    act(() => {
      result.current.toggleSaved({ connectorId: "c1", path: "p0/" }, "c1");
    });
    expect(mockPutSetting.mock.calls[0][0].value.locations).toHaveLength(
      MAX_FAVORITE_LOCATIONS - 1
    );
  });

  it("ignores a save with no connector", () => {
    const { result } = renderUploadLocations();

    act(() => {
      result.current.toggleSaved({ connectorId: "", path: "a/" }, "c1");
    });

    expect(mockPutSetting).not.toHaveBeenCalled();
  });
});

describe("remembering the last location", () => {
  it("writes the last location under its own settings key, separate from favorites", () => {
    const { result } = renderUploadLocations();

    act(() => {
      result.current.rememberLastLocation({
        connectorId: "c1",
        path: "/projects//a",
        collections: [{ id: "col-1", name: "Client A" }],
      });
    });

    const payload = mockPutSetting.mock.calls[0][0];
    expect(payload.key).toBe(LAST_LOCATION_SETTING_KEY);
    expect(payload.value).toMatchObject({
      version: UPLOAD_LOCATION_SCHEMA_VERSION,
      connectorId: "c1",
      path: "projects/a/",
      collections: [{ id: "col-1", name: "Client A" }],
    });
  });

  it("restores a last location that is still usable", () => {
    mockSettings = {
      [LAST_LOCATION_SETTING_KEY]: {
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        connectorId: "c1",
        path: "projects/a/",
      },
    };

    const { result } = renderUploadLocations({
      selectableConnectors: [connector("c1", { objectPrefix: ["projects/"] })],
    });

    expect(result.current.restorableLastLocation).toMatchObject({
      connectorId: "c1",
      path: "projects/a/",
    });
  });

  it("does not restore a last location whose connector is gone", () => {
    mockSettings = {
      [LAST_LOCATION_SETTING_KEY]: {
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        connectorId: "deleted-connector",
        path: "a/",
      },
    };

    const { result } = renderUploadLocations();

    expect(result.current.restorableLastLocation).toBeNull();
  });

  it("does not restore a last location whose path is no longer allowed", () => {
    mockSettings = {
      [LAST_LOCATION_SETTING_KEY]: {
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        connectorId: "c1",
        path: "somewhere/else/",
      },
    };

    const { result } = renderUploadLocations({
      selectableConnectors: [connector("c1", { objectPrefix: ["projects/"] })],
    });

    expect(result.current.restorableLastLocation).toBeNull();
  });

  it("restores a stored My Assets sub-path when it is inside the personal folder", () => {
    mockSettings = {
      [LAST_LOCATION_SETTING_KEY]: {
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        connectorId: "my-assets",
        path: "personal/sub/projects/",
      },
    };

    const { result } = renderUploadLocations({
      selectableConnectors: [],
      myAssetsConnectorId: "my-assets",
      myAssetsObjectPrefix: "personal/sub/",
    });

    expect(result.current.restorableLastLocation).toMatchObject({
      connectorId: "my-assets",
      path: "personal/sub/projects/",
    });
  });

  it("does not restore a My Assets path outside the caller's own personal folder", () => {
    mockSettings = {
      [LAST_LOCATION_SETTING_KEY]: {
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        connectorId: "my-assets",
        path: "personal/other-user/",
      },
    };

    const { result } = renderUploadLocations({
      selectableConnectors: [],
      myAssetsConnectorId: "my-assets",
      myAssetsObjectPrefix: "personal/sub/",
    });

    expect(result.current.restorableLastLocation).toBeNull();
  });

  it("ignores a remember call with no connector", () => {
    const { result } = renderUploadLocations();

    act(() => {
      result.current.rememberLastLocation({ connectorId: "", path: "a/" });
    });

    expect(mockPutSetting).not.toHaveBeenCalled();
  });
});

describe("collection reconciliation passthrough", () => {
  it("fails closed for My Assets while the personal prefix is still unknown", () => {
    // TopBar passes defaultObjectPrefix as undefined until useMyAssetsConnector resolves.
    // In that window there is nothing to validate against, so only the root is accepted —
    // otherwise a stored path aimed at another user's folder would be offered and then fail.
    mockSettings = favoritesSetting([
      { id: "f1", label: "root", connectorId: "my-assets", path: "" },
      { id: "f2", label: "other", connectorId: "my-assets", path: "personal/other-user/" },
    ]);

    const { result } = renderUploadLocations({
      selectableConnectors: [],
      myAssetsConnectorId: "my-assets",
      myAssetsObjectPrefix: undefined,
    });

    expect(result.current.availableFavorites.map((f) => f.id)).toEqual(["f1"]);
    expect(result.current.favorites[1].unavailableReason).toBe("path-not-allowed");
  });

  it("does not restore a My Assets sub-path while the personal prefix is still unknown", () => {
    mockSettings = {
      [LAST_LOCATION_SETTING_KEY]: {
        version: UPLOAD_LOCATION_SCHEMA_VERSION,
        connectorId: "my-assets",
        path: "personal/other-user/",
      },
    };

    const { result } = renderUploadLocations({
      selectableConnectors: [],
      myAssetsConnectorId: "my-assets",
      myAssetsObjectPrefix: undefined,
    });

    expect(result.current.restorableLastLocation).toBeNull();
  });

  it("drops saved collections that no longer resolve", () => {
    const { result } = renderUploadLocations({
      liveCollections: [
        { id: "col-1", name: "Live", status: "ACTIVE", userRole: "owner" } as Collection,
      ],
    });

    const reconciled = result.current.reconcileCollections([
      { id: "col-1", name: "Live" },
      { id: "col-gone", name: "Deleted" },
    ]);

    expect(reconciled.collections).toEqual([{ id: "col-1", name: "Live" }]);
    expect(reconciled.dropped).toEqual([{ id: "col-gone", name: "Deleted" }]);
  });
});
