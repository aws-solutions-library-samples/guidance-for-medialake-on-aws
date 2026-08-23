/**
 * Saved upload destinations — domain hook.
 *
 * Phase 1 provides:
 *  - "remember my last upload location", which is what auto-populates the uploader
 *  - favorites with add + delete
 *
 * Explicitly deferred to a later phase (the stored shape already accommodates both):
 *  - a favorite marked as the default destination (`defaultId` is written as null and
 *    ignored on read; when it lands it takes precedence over last-used)
 *  - renaming and reordering favorites
 *
 * Both live in the generic per-user settings store under the `upload` namespace, as two
 * separate keys. Keeping them apart matters: last-used is written after every upload,
 * favorites are edited rarely, and a shared key would make every upload a
 * read-modify-write that contends with favorites edits.
 *
 * Design: assets/docs/favorite-upload-locations.md
 */
import { useCallback, useMemo } from "react";
import { useGetUserSettings, usePutUserSetting } from "@/api/hooks/useUserSettings";
import type { ConnectorSummary } from "@/api/hooks/useSearchConnectors";
import type { Collection } from "@/api/hooks/useCollections";
import {
  FAVORITE_LOCATIONS_SETTING_KEY,
  LAST_LOCATION_SETTING_KEY,
  MAX_FAVORITE_LOCATIONS,
  UPLOAD_LOCATION_SCHEMA_VERSION,
  UPLOAD_SETTINGS_NAMESPACE,
  buildUploadLocationLabel,
  isSameUploadLocation,
  newUploadLocationId,
  normalizeUploadPath,
  parseFavoriteLocationsSetting,
  parseLastLocationSetting,
  reconcileUploadLocationCollections,
  type FavoriteUploadLocation,
  type UploadLocation,
  type UploadLocationCollectionRef,
} from "../types/uploadLocation.types";

export interface ResolvedFavoriteUploadLocation extends FavoriteUploadLocation {
  /** The live connector, when it is still a usable upload target. */
  connector?: ConnectorSummary;
  /** True when this favorite can currently be selected. */
  available: boolean;
  /** Why it can't be selected — for the management UI, so entries don't vanish silently. */
  unavailableReason?: "connector-missing" | "path-not-allowed";
}

interface UseUploadLocationsArgs {
  /**
   * Connectors that are currently valid upload targets, already filtered by
   * FileUploader (active, s3, uploads enabled) and by the `connectors:upload` permission.
   */
  selectableConnectors: ConnectorSummary[];
  /** The My Assets connector id, when the caller provides one. */
  myAssetsConnectorId?: string;
  /**
   * The My Assets object prefix — the caller's own `personal/{sub}/`. Supplying it lets
   * saved My Assets sub-paths be validated against the caller's own folder, so an entry
   * pointing anywhere else (e.g. another user's prefix in stale data) is filtered out.
   */
  myAssetsObjectPrefix?: string;
  /** Live collections, used to drop saved collections that no longer resolve. */
  liveCollections?: Collection[];
}

/**
 * Resolve a saved path against a connector's allowed prefixes.
 *
 * An empty path is always fine — it means "connector default", and FileUploader's existing
 * effect fills in `allowedPrefixes[0]`. A non-empty path must still sit inside the
 * allow-list, or `POST /assets/upload` would reject it with a 403.
 */
const isPathAllowed = (path: string, connector: ConnectorSummary): boolean => {
  const normalizedPath = normalizeUploadPath(path);
  if (!normalizedPath) return true;

  const raw = connector.objectPrefix ?? connector.configuration?.objectPrefix;
  const prefixes = (Array.isArray(raw) ? raw : raw ? [raw] : [])
    .map((prefix) => normalizeUploadPath(prefix))
    .filter(Boolean);

  // No declared prefixes means the whole bucket is fair game.
  if (prefixes.length === 0) return true;

  return prefixes.some((prefix) => normalizedPath.startsWith(prefix));
};
export const useUploadLocations = ({
  selectableConnectors,
  myAssetsConnectorId,
  myAssetsObjectPrefix,
  liveCollections,
}: UseUploadLocationsArgs) => {
  const { data: settings, isLoading } = useGetUserSettings(UPLOAD_SETTINGS_NAMESPACE);
  const { mutate: putSetting } = usePutUserSetting();

  const storedFavorites = useMemo(
    () => parseFavoriteLocationsSetting(settings?.[FAVORITE_LOCATIONS_SETTING_KEY]),
    [settings]
  );

  const storedLastLocation = useMemo(
    () => parseLastLocationSetting(settings?.[LAST_LOCATION_SETTING_KEY]),
    [settings]
  );

  /**
   * Every connector that can host a destination, including My Assets. My Assets is not in
   * `selectableConnectors` (FileUploader filters it out to render it separately) but is a
   * legitimate favorite target.
   */
  const connectorsById = useMemo(() => {
    const map = new Map<string, ConnectorSummary>();
    for (const connector of selectableConnectors) map.set(connector.id, connector);
    return map;
  }, [selectableConnectors]);

  const resolveConnector = useCallback(
    (connectorId: string): ConnectorSummary | undefined => {
      const connector = connectorsById.get(connectorId);
      if (connector) return connector;
      // My Assets is a valid target even though it isn't in the selectable list. Its
      // objectPrefix is the caller's own personal folder, so its paths get validated
      // against it like any other connector.
      if (myAssetsConnectorId && connectorId === myAssetsConnectorId) {
        return {
          id: connectorId,
          name: "My Assets",
          type: "s3",
          storageIdentifier: "",
          status: "active",
          objectPrefix: myAssetsObjectPrefix,
        };
      }
      return undefined;
    },
    [connectorsById, myAssetsConnectorId, myAssetsObjectPrefix]
  );

  /**
   * Whether a stored location's path is usable for the given connector.
   *
   * My Assets fails closed: its allow-list is the caller's own `personal/{sub}/`, supplied
   * by the caller as `myAssetsObjectPrefix`, and that is `undefined` until
   * `useMyAssetsConnector` resolves. Falling through to `isPathAllowed` in that window would
   * find no prefixes and accept *any* path — including one pointing at another user's
   * folder. Neither the upload handler nor the explorer would honour it, but the entry would
   * still be offered and then fail. While the prefix is unknown, only an empty path (the
   * personal root) is accepted.
   */
  const isStoredPathUsable = useCallback(
    (path: string, connector: ConnectorSummary, isMyAssets: boolean): boolean => {
      if (isMyAssets && !normalizeUploadPath(myAssetsObjectPrefix)) {
        return !normalizeUploadPath(path);
      }
      return isPathAllowed(path, connector);
    },
    [myAssetsObjectPrefix]
  );

  const favorites = useMemo<ResolvedFavoriteUploadLocation[]>(
    () =>
      storedFavorites.map((favorite) => {
        const connector = resolveConnector(favorite.connectorId);
        const isMyAssets = !!myAssetsConnectorId && favorite.connectorId === myAssetsConnectorId;

        if (!connector) {
          return { ...favorite, available: false, unavailableReason: "connector-missing" };
        }
        if (!isStoredPathUsable(favorite.path, connector, isMyAssets)) {
          return {
            ...favorite,
            connector,
            available: false,
            unavailableReason: "path-not-allowed",
          };
        }
        return { ...favorite, connector, available: true };
      }),
    [storedFavorites, resolveConnector, myAssetsConnectorId, isStoredPathUsable]
  );

  const availableFavorites = useMemo(() => favorites.filter((f) => f.available), [favorites]);

  const writeFavorites = useCallback(
    (locations: FavoriteUploadLocation[]) => {
      putSetting({
        namespace: UPLOAD_SETTINGS_NAMESPACE,
        key: FAVORITE_LOCATIONS_SETTING_KEY,
        value: {
          version: UPLOAD_LOCATION_SCHEMA_VERSION,
          // Reserved for the default-favorite phase.
          defaultId: null,
          locations,
        },
      });
    },
    [putSetting]
  );

  const isSaved = useCallback(
    (location: Pick<UploadLocation, "connectorId" | "path"> | null | undefined) =>
      storedFavorites.some((favorite) => isSameUploadLocation(favorite, location)),
    [storedFavorites]
  );

  const findSaved = useCallback(
    (location: Pick<UploadLocation, "connectorId" | "path"> | null | undefined) =>
      storedFavorites.find((favorite) => isSameUploadLocation(favorite, location)),
    [storedFavorites]
  );

  const isAtCapacity = storedFavorites.length >= MAX_FAVORITE_LOCATIONS;

  /**
   * Save the current destination, or remove it if already saved. Collections are captured
   * as-selected, so a favorite can carry "this prefix plus these collections".
   */
  const toggleSaved = useCallback(
    (location: UploadLocation, connectorName: string, storageIdentifier?: string) => {
      if (!location.connectorId) return;

      const existing = findSaved(location);
      if (existing) {
        writeFavorites(storedFavorites.filter((favorite) => favorite.id !== existing.id));
        return;
      }

      if (isAtCapacity) return;

      const path = normalizeUploadPath(location.path);
      const entry: FavoriteUploadLocation = {
        id: newUploadLocationId(),
        label: buildUploadLocationLabel(connectorName, path),
        connectorId: location.connectorId,
        path,
        collections: location.collections?.length ? location.collections : undefined,
        connectorName,
        storageIdentifier,
      };

      writeFavorites([...storedFavorites, entry]);
    },
    [findSaved, isAtCapacity, storedFavorites, writeFavorites]
  );

  const removeFavorite = useCallback(
    (id: string) => writeFavorites(storedFavorites.filter((favorite) => favorite.id !== id)),
    [storedFavorites, writeFavorites]
  );

  /** Record where an upload actually went, so the next uploader open can restore it. */
  const rememberLastLocation = useCallback(
    (location: UploadLocation) => {
      if (!location.connectorId) return;
      putSetting({
        namespace: UPLOAD_SETTINGS_NAMESPACE,
        key: LAST_LOCATION_SETTING_KEY,
        value: {
          version: UPLOAD_LOCATION_SCHEMA_VERSION,
          connectorId: location.connectorId,
          path: normalizeUploadPath(location.path),
          collections: location.collections ?? [],
          updatedAt: Date.now(),
        },
      });
    },
    [putSetting]
  );

  /**
   * The last-used destination, but only if it is still usable right now — the connector
   * must still exist and be permitted, and the path must still be inside its allow-list.
   */
  const restorableLastLocation = useMemo<UploadLocation | null>(() => {
    if (!storedLastLocation) return null;

    const connector = resolveConnector(storedLastLocation.connectorId);
    if (!connector) return null;

    const isMyAssets =
      !!myAssetsConnectorId && storedLastLocation.connectorId === myAssetsConnectorId;
    if (!isStoredPathUsable(storedLastLocation.path, connector, isMyAssets)) return null;

    return storedLastLocation;
  }, [storedLastLocation, resolveConnector, myAssetsConnectorId, isStoredPathUsable]);

  /**
   * Drop saved collections that no longer exist or are no longer addable.
   *
   * Called when a saved destination is applied and again before an upload starts, because
   * `POST /assets/upload` does not verify collection existence.
   */
  const reconcileCollections = useCallback(
    (
      collections: UploadLocationCollectionRef[] | undefined
    ): { collections: UploadLocationCollectionRef[]; dropped: UploadLocationCollectionRef[] } =>
      reconcileUploadLocationCollections(collections, liveCollections),
    [liveCollections]
  );

  return {
    isLoading,
    favorites,
    availableFavorites,
    isSaved,
    isAtCapacity,
    maxFavorites: MAX_FAVORITE_LOCATIONS,
    toggleSaved,
    removeFavorite,
    rememberLastLocation,
    restorableLastLocation,
    reconcileCollections,
  };
};
