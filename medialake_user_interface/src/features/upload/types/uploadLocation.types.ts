/**
 * Saved upload destinations — types and pure helpers.
 *
 * An upload destination is fully identified by `(connectorId, path)`. The bucket is never
 * client-supplied: `POST /assets/upload` derives it from the connector's `storageIdentifier`
 * and re-validates the path against the connector's `objectPrefix` allow-list on every
 * upload. A saved location therefore carries no additional trust — a stale one simply
 * fails server-side validation.
 *
 * `connectorId` may be the My Assets (personal) connector. `path` may be empty, which
 * means "the connector's default / root prefix" and lets the existing prefix-defaulting
 * effect in FileUploader fill it in.
 *
 * Design: assets/docs/favorite-upload-locations.md
 */
import type { Collection } from "@/api/hooks/useCollections";
import { isAddable } from "@/api/hooks/useCollections";

/** Namespace and keys in the generic per-user settings store (`/users/settings`). */
export const UPLOAD_SETTINGS_NAMESPACE = "upload";
export const LAST_LOCATION_SETTING_KEY = "lastLocation";
export const FAVORITE_LOCATIONS_SETTING_KEY = "favoriteLocations";

/**
 * Stored shapes are versioned so the payload can evolve without guessing at read time.
 * Anything with an unrecognised version is ignored rather than misread.
 */
export const UPLOAD_LOCATION_SCHEMA_VERSION = 1;

/** Client-side cap. Also enforce server-side before this store grows unbounded. */
export const MAX_FAVORITE_LOCATIONS = 20;

/** Minimal collection reference, matching CollectionSelector's `CollectionRef`. */
export interface UploadLocationCollectionRef {
  id: string;
  name: string;
}

/** A destination: connector (possibly My Assets) + path, plus optional target collections. */
export interface UploadLocation {
  connectorId: string;
  /** Normalised: no leading slash, exactly one trailing slash, or "" for connector default. */
  path: string;
  collections?: UploadLocationCollectionRef[];
}

/** A saved, user-labelled destination. */
export interface FavoriteUploadLocation extends UploadLocation {
  id: string;
  label: string;
  /** Denormalised for display only — always re-resolved against the live connector list. */
  connectorName?: string;
  storageIdentifier?: string;
}

export interface FavoriteUploadLocationsSetting {
  version: number;
  /**
   * Reserved for the "default favorite" phase. Phase 1 auto-populates from the
   * last-used location instead, so this is written as null and ignored on read.
   */
  defaultId: string | null;
  locations: FavoriteUploadLocation[];
}

export interface LastUploadLocationSetting extends UploadLocation {
  version: number;
  updatedAt?: number;
}

/**
 * Canonical path form. Without this, `projects/a` and `projects/a/` would be treated as
 * two different destinations. Mirrors the trailing-slash normalisation FileUploader
 * already applies to `defaultObjectPrefix` and to `allowedPrefixes[0]`.
 */
export const normalizeUploadPath = (path?: string | null): string => {
  if (!path) return "";
  const collapsed = path
    .trim()
    .replace(/\/{2,}/g, "/")
    .replace(/^\/+/, "");
  if (!collapsed || collapsed === "/") return "";
  return collapsed.endsWith("/") ? collapsed : `${collapsed}/`;
};

/** Destination equality — the dedup key for saving. */
export const isSameUploadLocation = (
  a: Pick<UploadLocation, "connectorId" | "path"> | null | undefined,
  b: Pick<UploadLocation, "connectorId" | "path"> | null | undefined
): boolean => {
  if (!a || !b) return false;
  return (
    a.connectorId === b.connectorId && normalizeUploadPath(a.path) === normalizeUploadPath(b.path)
  );
};

/**
 * Human label for a destination, used when saving so nothing interrupts the upload with a
 * naming prompt. Renaming is a later phase.
 */
export const buildUploadLocationLabel = (connectorName: string, path?: string | null): string => {
  const normalized = normalizeUploadPath(path);
  return normalized ? `${connectorName} / ${normalized}` : connectorName;
};

/**
 * Drop collections that no longer exist, or that the user can no longer add assets to.
 *
 * `POST /assets/upload` does NOT verify collection existence (it only caps the count at
 * MAX_COLLECTIONS_PER_UPLOAD and stamps the ids into S3 metadata), so a saved location
 * could otherwise carry ids that silently never resolve. Reconciling here means the user
 * is told, and the upload request only carries collections that are currently usable.
 *
 * `isAddable` is reused so a collection the user has lost edit rights on is treated the
 * same as a deleted one — it is equally unusable as an upload target.
 */
export const reconcileUploadLocationCollections = (
  saved: UploadLocationCollectionRef[] | undefined,
  liveCollections: Collection[] | undefined
): { collections: UploadLocationCollectionRef[]; dropped: UploadLocationCollectionRef[] } => {
  if (!saved?.length) return { collections: [], dropped: [] };

  // Undefined means "not loaded yet" — keep everything rather than wrongly dropping.
  if (!liveCollections) return { collections: saved, dropped: [] };

  const liveById = new Map(liveCollections.map((c) => [c.id, c]));
  const collections: UploadLocationCollectionRef[] = [];
  const dropped: UploadLocationCollectionRef[] = [];

  for (const ref of saved) {
    const live = liveById.get(ref.id);
    if (live && isAddable(live)) {
      // Prefer the live name — the stored one goes stale on rename.
      collections.push({ id: live.id, name: live.name });
    } else {
      dropped.push(ref);
    }
  }

  return { collections, dropped };
};

/**
 * Accept the schema version as either a JSON number or a numeric string.
 *
 * `GET /users/settings` serialises the stored payload with `json.dumps(..., default=str)`,
 * which renders DynamoDB's `Decimal('1')` as the string `"1"`, while `PUT` echoes back the
 * in-memory `int` as `1`. A strict `!==` against the numeric constant therefore discarded
 * every payload on read, so saved locations vanished on reload. The backend now emits
 * native numbers, but this stays tolerant so already-stored rows keep working and the two
 * deploys need not be ordered.
 *
 * Deliberately narrow: `Number()` alone would coerce `true`, `null`, `[]` and `""` to 0/1.
 */
const isSupportedSchemaVersion = (version: unknown): boolean => {
  if (typeof version === "number") return version === UPLOAD_LOCATION_SCHEMA_VERSION;
  if (typeof version === "string" && version.trim() !== "") {
    return Number(version) === UPLOAD_LOCATION_SCHEMA_VERSION;
  }
  return false;
};

/** Parse a stored favorites payload defensively. Unknown/malformed shapes read as empty. */
export const parseFavoriteLocationsSetting = (raw: unknown): FavoriteUploadLocation[] => {
  if (!raw || typeof raw !== "object") return [];
  const candidate = raw as Partial<FavoriteUploadLocationsSetting>;
  if (!isSupportedSchemaVersion(candidate.version)) return [];
  if (!Array.isArray(candidate.locations)) return [];

  return candidate.locations.filter(
    (entry): entry is FavoriteUploadLocation =>
      !!entry &&
      typeof entry === "object" &&
      typeof entry.id === "string" &&
      entry.id.length > 0 &&
      typeof entry.connectorId === "string" &&
      entry.connectorId.length > 0 &&
      // `PUT /users/settings` accepts arbitrary JSON, so a non-string path is storable and
      // would throw inside normalizeUploadPath's `.trim()`.
      (entry.path === undefined || typeof entry.path === "string") &&
      (entry.label === undefined || typeof entry.label === "string")
  );
};

/** Parse a stored last-location payload defensively. */
export const parseLastLocationSetting = (raw: unknown): UploadLocation | null => {
  if (!raw || typeof raw !== "object") return null;
  const candidate = raw as Partial<LastUploadLocationSetting>;
  if (!isSupportedSchemaVersion(candidate.version)) return null;
  if (typeof candidate.connectorId !== "string" || !candidate.connectorId) return null;
  if (candidate.path !== undefined && typeof candidate.path !== "string") return null;

  return {
    connectorId: candidate.connectorId,
    path: normalizeUploadPath(candidate.path),
    collections: Array.isArray(candidate.collections) ? candidate.collections : [],
  };
};

/** Stable id for a saved location. `crypto.randomUUID` is the convention in this codebase. */
export const newUploadLocationId = (): string => crypto.randomUUID();
